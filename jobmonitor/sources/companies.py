"""Karriereseiten aus companies.yaml: ATS automatisch erkennen und öffentliche Feeds nutzen."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date

import requests

from ..http import Fetcher, RobotsDisallowed
from ..location import is_remote
from ..initiativ import find_initiativ_link, update_entry
from ..models import Job, SourceResult
from .ats import boards, jsonld, oeffentlich, personio, sitemap, workday

log = logging.getLogger(__name__)
NAME = "Firmen-Karriereseiten"

# (ats-Name, Regex mit ID-Gruppe). Reihenfolge = Priorität.
ATS_PATTERNS = [
    ("personio", re.compile(r"([a-z0-9-]+)\.jobs\.personio\.(?:de|com)", re.I)),
    ("greenhouse", re.compile(r"boards(?:-api)?\.greenhouse\.io/(?:v1/boards/|embed/job_board\?for=)?([a-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([a-z0-9_-]+)", re.I)),
    ("workday", re.compile(r"([a-z0-9-]+\.wd\d+\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?[A-Za-z0-9_-]+)")),
    ("teamtailor", re.compile(r"([a-z0-9-]+)\.teamtailor\.com", re.I)),
    ("recruitee", re.compile(r"([a-z0-9-]+)\.recruitee\.com", re.I)),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9]+)|"
                                   r"smartrecruiters\.com/([A-Za-z0-9]+)/[0-9a-f-]{20,}")),
]
# Systeme ohne bekannten öffentlichen Feed; Stellen meist per JavaScript geladen → JSON-LD, Links, Sitemap, sonst manuell
JS_ATS = ["rexx", "softgarden", "successfactors", "smartrecruiters", "phenom", "dvinci", "d.vinci", "onlyfy",
          "prescreen", "umantis", "milch-zucker", "concludis", "jobbase"]
# Inoffizielle bzw. per robots.txt eingeschränkte Schnittstellen: nur nach Freigabe in config.yaml (ats_freigabe)
NEEDS_APPROVAL = {"workday", "smartrecruiters"}


def detect_ats(html: str, url: str) -> tuple[str, str | None]:
    hay = url + " " + html
    for name, pattern in ATS_PATTERNS:
        m = pattern.search(hay)
        if m:
            return name, next(g for g in m.groups() if g)
    low = hay.lower()
    for name in JS_ATS:
        if name in low:
            return name.replace(".", ""), None
    return "jsonld", None


@dataclass
class CompanyOutcome:
    name: str
    jobs: list[Job] = field(default_factory=list)
    initiativ_neu: bool = False
    status: str = "ok"            # ok | fehler | blockiert | manuell | veraltet (siehe quellen_verlauf.py)
    detail_links: int = 0
    detail_fehler: int = 0


class CompaniesSource:
    name = NAME

    def __init__(self, companies_doc, cfg: dict, fetcher: Fetcher, today: date, approvals: dict | None = None,
                 role: re.Pattern = jsonld.ROLE_SLUG, ats_terms: list[str] | None = None, state=None):
        """role: Rollen-Muster für Links/Sitemaps aller aktiven Suchprofile; ats_terms: Suchbegriffe für Workday,
        SuccessFactors und Phenom; state: merkt sich gelesene Sitemap-Anzeigen (nur neue werden abgerufen)."""
        self.doc = companies_doc
        self.cfg = cfg
        self.approvals = approvals or {}
        self.role = role
        self.ats_terms = ats_terms or workday.SEARCH_TERMS
        self.fetcher = fetcher
        self.today = today.isoformat()
        self.outcomes: dict[str, CompanyOutcome] = {}
        self.state = state

    def fetch(self) -> SourceResult:
        result = SourceResult(self.name)
        for entry in self.doc.get("firmen") or []:
            if entry.get("aktiv") is False or not entry.get("karriereseite_url"):
                continue
            outcome = CompanyOutcome(entry["name"])
            self.outcomes[entry["name"]] = outcome
            try:
                outcome.jobs = self._company(entry, outcome, result)
                result.jobs += outcome.jobs
            except RobotsDisallowed as exc:
                outcome.status = "blockiert"
                result.manual_check.append(f"{entry['name']}: robots.txt verbietet das Auslesen ({exc})")
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code in (401, 403):
                    outcome.status = "blockiert"
                    result.manual_check.append(f"{entry['name']}: Seite blockiert automatische Abrufe "
                                               f"(HTTP {exc.response.status_code}) – {entry['karriereseite_url']}")
                else:
                    outcome.status = "fehler"
                    result.teilfehler.append(f"{entry['name']}: {exc}")
                    result.manual_check.append(f"{entry['name']}: Fehler beim Abruf, bitte manuell prüfen")
            except Exception as exc:
                outcome.status = "fehler"
                log.exception("Firma %s", entry["name"])
                result.teilfehler.append(f"{entry['name']}: {exc}")
                result.manual_check.append(f"{entry['name']}: Fehler beim Abruf, bitte manuell prüfen")
        return result

    def _company(self, entry, outcome: CompanyOutcome, result: SourceResult) -> list[Job]:
        name, url = entry["name"], entry["karriereseite_url"]
        html = self.fetcher.get(url).text

        outcome.initiativ_neu = update_entry(entry, find_initiativ_link(html, url), self.today)

        ats, ats_id = entry.get("ats"), entry.get("ats_id")
        if not ats:
            ats, ats_id = detect_ats(html, url)
            entry["ats"], entry["ats_id"] = ats, ats_id
            log.info("%s: ATS erkannt: %s %s", name, ats, ats_id or "")

        if entry.get("abruf") == "nur_initiativ":
            return []   # Stellen kommen über die Bundesagentur; hier nur Initiativ-Check
        get = self.fetcher.get
        if ats == "personio" and ats_id:
            return personio.parse(get(personio.feed_url(ats_id)).text, ats_id, name, NAME)
        if ats == "greenhouse" and ats_id:
            return boards.parse_greenhouse(get(boards.greenhouse_url(ats_id)).json(), name, NAME)
        if ats == "lever" and ats_id:
            return boards.parse_lever(get(boards.lever_url(ats_id)).json(), name, NAME)
        if ats == "recruitee" and ats_id:
            return boards.parse_recruitee(get(boards.recruitee_url(ats_id)).json(), name, NAME)
        if ats == "teamtailor" and ats_id:
            return boards.parse_rss(get(boards.teamtailor_url(ats_id)).text, name, NAME)
        if ats == "dvinci" and ats_id:
            return oeffentlich.parse_dvinci(get(oeffentlich.dvinci_url(ats_id)).json(), name, NAME)
        if ats == "phenom" and ats_id:
            return self._suche(lambda term: oeffentlich.parse_phenom(get(oeffentlich.phenom_url(ats_id, term)).text,
                                                                     ats_id, name, NAME))
        if ats == "successfactors" and ats_id:
            treffer = self._suche(lambda term: oeffentlich.parse_successfactors(
                get(oeffentlich.successfactors_url(ats_id, term)).text, ats_id))
            links = [u for title, u, _ in treffer if self.role.search(title)]
            orte = {u: ort for _, u, ort in treffer}
            jobs = self._details(entry, links, result)
            for job in jobs:
                job.location = job.location or orte.get(job.url, "")
            return jobs
        if ats == "eingebettet":
            return oeffentlich.parse_eingebettet(html, url, name, NAME)
        if ats == "sitemap" and ats_id:
            return self._sitemap_anzeigen(entry, ats_id, result)
        if ats == "workday" and ats_id and not self.approvals.get("workday"):
            # Ohne Freigabe: offizielle Workday-Sitemap (in robots.txt angekündigt) + JSON-LD der Detailseiten
            host, _, site = workday.split_id(ats_id)
            return self._generic(entry, "", ats, result, sitemap_urls=[f"https://{host}/{site}/siteMap.xml"])
        if ats in NEEDS_APPROVAL and ats_id:
            if not self.approvals.get(ats):
                # Ohne Freigabe nur die allgemeinen Wege (JSON-LD, Links, Sitemap)
                return self._generic(entry, html, ats, result)
            if ats == "workday":
                jobs = []
                for term in self.ats_terms:
                    data = self.fetcher.post_json(workday.search_url(ats_id), workday.payload(term)).json()
                    jobs += workday.parse(data, ats_id, name, NAME)
                return jobs
            # SmartRecruiters: robots.txt der API erlaubt nur LinkedInBot → bewusst ohne robots-Prüfung, nur nach Freigabe
            return boards.parse_smartrecruiters(get(boards.smartrecruiters_url(ats_id), check_robots=False).json(),
                                                name, NAME)
        return self._generic(entry, html, ats, result)

    def _suche(self, eine_suche) -> list:
        """Eine Suche je Suchbegriff der aktiven Profile (höchstens 6), Ergebnisse ohne Doppelte."""
        out, seen = [], set()
        for term in list(dict.fromkeys(self.ats_terms))[:6]:
            for item in eine_suche(term):
                key = item.url if isinstance(item, Job) else item[1]
                if key not in seen:
                    seen.add(key)
                    out.append(item)
        return out

    def _details(self, entry, links: list[str], _result: SourceResult | None = None) -> list[Job]:
        """Detailseiten lesen (JSON-LD, sonst Seitentext), höchstens max_detail_pages."""
        name = entry["name"]
        outcome = self.outcomes.get(name) or CompanyOutcome(name)
        jobs = []
        for link in links[: self.cfg["max_detail_pages"]]:
            outcome.detail_links += 1
            try:
                detail = self.fetcher.get(link).text
            except (RobotsDisallowed, requests.HTTPError) as exc:
                log.info("%s: Detailseite übersprungen (%s)", name, exc)
                outcome.detail_fehler += 1
                continue
            found = jsonld.parse_postings(detail, link, name, NAME)
            if not found:
                text = jsonld._text(detail)[:5000]
                found = [Job(title=jsonld.page_title(detail), company=name, url=link, source=NAME,
                             location=", ".join(jsonld.microdata_locations(detail)), description=text,
                             remote=is_remote(text))]
            for job in found:
                job.url = link
            jobs += found
        return jobs

    def _sitemap_anzeigen(self, entry, sitemap_url: str, result: SourceResult) -> list[Job]:
        """Stellen-Sitemap (z. B. WDR): Detailseiten nur für neue Adressen lesen (höchstens max_detail_pages je Lauf);
        Titel bekannter Anzeigen kommen aus dem Zwischenspeicher, damit die Rohtreffer stimmen und nichts doppelt
        abgefragt wird."""
        name = entry["name"]
        links = oeffentlich.sitemap_links(self.fetcher.get(sitemap_url).text, sitemap_url)
        key = f"sitemap_titel:{name}"
        cache = json.loads(self.state.get_meta(key) or "{}") if self.state is not None else {}
        cache = {u: t for u, t in cache.items() if u in links}            # Anzeigen, die es nicht mehr gibt, fallen weg
        neu = [u for u in links if u not in cache]
        jobs = self._details(entry, neu, result)
        for job in jobs:
            cache[job.url] = job.title
        jobs += [Job(title=t, company=name, url=u, source=NAME) for u, t in cache.items()
                 if u not in {j.url for j in jobs}]
        if self.state is not None:
            self.state.set_meta(key, json.dumps(cache, ensure_ascii=False))
        if len(neu) > self.cfg["max_detail_pages"]:
            result.notes.append(f"{name}: {len(neu)} neue Anzeigen, die übrigen folgen in den nächsten Läufen")
        return jobs

    def _generic(self, entry, html: str, ats: str, result: SourceResult,
                 sitemap_urls: list[str] | None = None) -> list[Job]:
        """JSON-LD auf der Seite → Detailseiten mit Rollen-Stichwort → Sitemap → sonst manuell prüfen."""
        name, url = entry["name"], entry["karriereseite_url"]
        jobs = jsonld.parse_postings(html, url, name, NAME)
        role_links, all_links = jsonld.job_links(html, url, self.role)
        if not jobs and not role_links:
            try:
                role_links, rss_jobs = sitemap.collect(self.fetcher, url, name, NAME, sitemap_urls, self.role)
                jobs += rss_jobs
                if role_links or rss_jobs:
                    result.notes.append(f"{name}: über Sitemap gelesen")
            except RobotsDisallowed:
                pass
        role_links.sort(key=lambda u: not jsonld.TECH_SLUG.search(u.rsplit("/", 2)[-2] + u.rsplit("/", 1)[-1]))
        outcome = self.outcomes.get(name) or CompanyOutcome(name)
        jobs += self._details(entry, role_links, result)
        for job in jobs:
            if not job.location and entry.get("standorte"):
                job.location = ", ".join(s for s in entry["standorte"] if s != "Remote")
                job.flags.append("Ort aus Firmenliste angenommen – in der Anzeige prüfen")
        if not jobs and outcome.detail_links and outcome.detail_fehler == outcome.detail_links:
            outcome.status = "veraltet"   # Links gefunden, aber keine einzige Detailseite erreichbar
        if not jobs and not role_links and len(all_links) < 3:
            outcome.status = "manuell"
            reason = (f"Stellenliste wird per JavaScript geladen ({ats})" if ats != "jsonld"
                      else "keine maschinenlesbaren Stellen gefunden")
            result.manual_check.append(f"{name}: {reason} – {url}")
        return jobs
