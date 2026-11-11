"""HTTP-Zugriff mit ehrlichem User-Agent, robots.txt-Prüfung und Rate-Limit pro Host."""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import unquote, urlsplit

import requests

log = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    pass


class Robots:
    """robots.txt nach RFC 9309 (wie Google): Gruppen je User-Agent, Platzhalter `*` und `$`, längste passende Regel
    gewinnt, bei Gleichstand Allow. Pythons urllib.robotparser kennt keine Platzhalter und hätte z. B.
    „Disallow: /*/about/careers/*/job-search“ übersehen."""

    def __init__(self, lines: list[str] | None = None):
        self.allow_all = False
        self.disallow_all = False
        self._gruppen: list[tuple[list[str], list[tuple[bool, str]]]] = []
        self._sitemaps: list[str] = []
        if lines is not None:
            self.parse(lines)

    def parse(self, lines: list[str]) -> None:
        agents: list[str] = []
        regeln: list[tuple[bool, str]] = []
        in_regeln = False
        for roh in lines:
            zeile = roh.split("#", 1)[0].strip()
            if ":" not in zeile:
                continue
            feld, wert = (t.strip() for t in zeile.split(":", 1))
            feld = feld.lower()
            if feld == "user-agent":
                if in_regeln:                      # neue Gruppe beginnt
                    self._gruppen.append((agents, regeln))
                    agents, regeln, in_regeln = [], [], False
                agents.append(wert.lower())
            elif feld in ("allow", "disallow"):
                in_regeln = True
                if agents and wert:                # leeres Disallow = alles erlaubt
                    regeln.append((feld == "allow", wert))
            elif feld == "sitemap" and wert:
                self._sitemaps.append(wert)
        if agents:
            self._gruppen.append((agents, regeln))

    def site_maps(self) -> list[str]:
        return list(self._sitemaps)

    def _regeln(self, user_agent: str) -> list[tuple[bool, str]]:
        token = user_agent.split("/", 1)[0].strip().lower()
        eigene = [r for agents, r in self._gruppen if any(a != "*" and a in token for a in agents)]
        if eigene:
            return [regel for r in eigene for regel in r]
        return [regel for agents, r in self._gruppen if "*" in agents for regel in r]

    @staticmethod
    def _muster(pfad: str) -> re.Pattern:
        ende = pfad.endswith("$")
        teile = (re.escape(unquote(t)) for t in (pfad[:-1] if ende else pfad).split("*"))
        return re.compile(".*".join(teile) + ("$" if ende else ""))

    def can_fetch(self, user_agent: str, url: str) -> bool:
        if self.disallow_all:
            return False
        if self.allow_all:
            return True
        teile = urlsplit(url)
        pfad = unquote(teile.path or "/") + (f"?{unquote(teile.query)}" if teile.query else "")
        if pfad == "/robots.txt":
            return True
        bester: tuple[int, bool] | None = None
        for erlaubt, muster in self._regeln(user_agent):
            if self._muster(muster).match(pfad):
                laenge = len(muster)
                if bester is None or laenge > bester[0] or (laenge == bester[0] and erlaubt):
                    bester = (laenge, erlaubt)
        return True if bester is None else bester[1]


class Fetcher:
    def __init__(self, user_agent: str, min_delay: float = 2.0, timeout: float = 25, retries: int = 2,
                 session: requests.Session | None = None, sleep=None):
        self.user_agent = user_agent
        self.min_delay = min_delay
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.session.headers["Accept-Language"] = "de-DE,de;q=0.9,en;q=0.5"
        self._sleep = sleep or (lambda seconds: time.sleep(seconds))
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, Robots] = {}
        # Hosts, die in diesem Lauf nicht zu erreichen waren (Zeitüberschreitung, keine Verbindung): nicht noch
        # mehrmals je 25 Sekunden warten – eine tote Karriereseite kostete sonst anderthalb Minuten je Suche
        self._tot: set[str] = set()

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self.min_delay - (time.monotonic() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(base)
        if parser is None:
            parser = Robots()
            try:
                self._throttle(parts.netloc)
                resp = self.session.get(base + "/robots.txt", timeout=self.timeout)
                if resp.status_code in (401, 403):
                    parser.disallow_all = True
                elif resp.status_code >= 400 or "text/html" in resp.headers.get("Content-Type", ""):
                    # Kein robots.txt (oft eine 404-HTML-Seite) = keine Einschränkung
                    parser.allow_all = True
                else:
                    parser.parse(resp.text.splitlines())
            except requests.RequestException as exc:
                if isinstance(exc, requests.Timeout):     # Server antwortet gar nicht (nicht bloß: keine robots.txt)
                    self._tot.add(parts.netloc)
                    log.warning("%s ist nicht erreichbar (%s) – in diesem Lauf übersprungen", base,
                                exc.__class__.__name__)
                else:
                    log.warning("robots.txt für %s nicht lesbar (%s), behandle als erlaubt", base, exc)
                parser.allow_all = True
            self._robots[base] = parser
        return parser.can_fetch(self.user_agent, url)

    def sitemaps(self, url: str) -> list[str]:
        """Sitemap-Einträge aus robots.txt des Hosts (nach allowed())."""
        parts = urlsplit(url)
        self.allowed(url)
        parser = self._robots.get(f"{parts.scheme}://{parts.netloc}")
        return list((parser.site_maps() if parser else None) or [])

    def get(self, url: str, **kwargs) -> requests.Response:
        return self._request("GET", url, **kwargs)

    def post_json(self, url: str, payload: dict, **kwargs) -> requests.Response:
        return self._request("POST", url, json=payload, **kwargs)

    def _request(self, method: str, url: str, *, check_robots: bool = True, headers: dict | None = None,
                 params: dict | None = None, json: dict | None = None) -> requests.Response:
        if check_robots and not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt verbietet {url}")
        host = urlsplit(url).netloc
        if host in self._tot:
            raise requests.ConnectionError(f"{host} war in diesem Lauf schon nicht erreichbar")
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            self._throttle(host)
            try:
                resp = self.session.request(method, url, headers=headers, params=params, json=json,
                                            timeout=self.timeout)
                if resp.status_code in (429, 502, 503, 504) and attempt < self.retries:
                    self._sleep(self.min_delay * (attempt + 2))
                    continue
                resp.raise_for_status()
                if "charset" not in resp.headers.get("Content-Type", "").lower():
                    # requests nimmt sonst ISO-8859-1 an → "KÃ¶ln" statt "Köln"
                    resp.encoding = "utf-8"
                return resp
            except requests.HTTPError:
                raise
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    self._sleep(self.min_delay * (attempt + 2))
        if isinstance(last_exc, requests.Timeout):
            self._tot.add(host)
        raise last_exc  # type: ignore[misc]
