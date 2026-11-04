"""Selbst angegebene Stelle für `make cv`: Anzeigentext aus einer Datei oder einmaliger Abruf eines Links.

Läuft nur lokal. LinkedIn, StepStone, Indeed & Co. werden nicht abgerufen (dort Text in eine Datei kopieren),
robots.txt und Login-Seiten werden respektiert.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from . import fit, fristen, tracking
from .cv_data import covered_terms, load_cv_master
from .http import Fetcher, RobotsDisallowed
from .models import Job
from .report import fit_line
from .sources.ats.jsonld import page_title, parse_postings
from .sources.hsnr import pdf_text

BLOCKED_HOSTS = ("linkedin.", "stepstone.", "indeed.", "xing.", "glassdoor.", "monster.")
DATEI_TIPP = "Kopiere den Anzeigentext in eine Datei und nutze make cv STELLE=<datei>."


class StelleError(Exception):
    pass


def from_file(path: Path, firma: str | None = None, link: str | None = None) -> Job:
    """Erste nicht-leere Zeile = Titel, alles = Beschreibung. Firma aus FIRMA, sonst aus dem Dateinamen."""
    if not path.is_file():
        raise StelleError(f"Datei {path} nicht gefunden.")
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        raise StelleError(f"Datei {path} ist leer.")
    title = next(line.strip() for line in text.splitlines() if line.strip())[:150]
    company = firma or path.stem.replace("_", " ").replace("-", " ").strip()
    return Job(title=title, company=company, url=link or f"eigene:{path.name}", source="eigene Stelle",
               description=text)


def _blocked(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return any(b in host for b in BLOCKED_HOSTS)


def _main_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return main.get_text("\n", strip=True)


def _site_name(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content"):
        return og["content"].strip()
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    return host.split(".")[-2] if host.count(".") else host


def _hiring_org(html: str) -> str:
    m = re.search(r'"hiringOrganization"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', html)
    return m.group(1) if m else ""


def from_url(url: str, fetcher: Fetcher, firma: str | None = None) -> Job:
    """Lädt die Anzeige einmal. JSON-LD (JobPosting) zuerst, sonst Seitentext; PDFs werden als Text gelesen."""
    if not url.startswith(("http://", "https://")):
        raise StelleError("URL muss mit http:// oder https:// beginnen.")
    if _blocked(url):
        raise StelleError(f"{urlsplit(url).netloc} wird nicht automatisch abgerufen. {DATEI_TIPP}")
    try:
        resp = fetcher.get(url)
    except RobotsDisallowed:
        raise StelleError(f"robots.txt der Seite verbietet den Abruf. {DATEI_TIPP}") from None
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        hint = "Seite verlangt Login oder blockiert Abrufe. " if code in (401, 403) else ""
        raise StelleError(f"Abruf fehlgeschlagen (HTTP {code}). {hint}{DATEI_TIPP}") from None
    except requests.RequestException as exc:
        raise StelleError(f"Abruf fehlgeschlagen ({type(exc).__name__}). {DATEI_TIPP}") from None

    if "pdf" in resp.headers.get("Content-Type", "").lower() or url.lower().endswith(".pdf"):
        text = pdf_text(resp.content)
        title = next((line.strip() for line in text.splitlines() if line.strip()), "Stellenanzeige")
        return Job(title=title[:150], company=firma or _site_name("", url), url=url, source="eigene Stelle",
                   description=text)

    html = resp.text
    postings = parse_postings(html, url, firma or _hiring_org(html) or _site_name(html, url), "eigene Stelle")
    if postings and len(postings[0].description) > 200:
        job = postings[0]
        job.url = url
        return job
    text = _main_text(html)
    if len(text) < 200:
        raise StelleError(f"Auf der Seite steht kaum Text (vermutlich per JavaScript geladen). {DATEI_TIPP}")
    return Job(title=page_title(html).strip()[:150] or "Stellenanzeige",
               company=firma or _hiring_org(html) or _site_name(html, url), url=url, source="eigene Stelle",
               description=text)


def fetcher_from(cfg: dict) -> Fetcher:
    h = cfg["http"]
    return Fetcher(h["user_agent"], h["min_delay_seconds"], h["timeout_seconds"], h["retries"])


def prepare(job: Job, root: Path, cfg: dict, today: date | None = None, ki_ask=None) -> dict:
    """Fit berechnen und in applications.csv eintragen. Ergebnis für make cv bzw. die Oberfläche.
    `ki_ask`: wie llm._ask (z. B. ki.frage_funktion) – dann liest die KI die Anforderungen wie bei gefundenen
    Stellen zusätzlich zur Stichwortsuche (Pflicht oder Wunsch, Sprachen, Eckdaten)."""
    cv, _ = load_cv_master(root)
    if cv is None:
        raise StelleError("cv_master.yaml fehlt.")
    fit.rate(job, covered_terms(cv, cfg["fit"]["begriffe"]), cfg["fit"])
    gelesen: set = set()
    if ki_ask is not None:
        fit.mit_ki([job], cv, {**cfg["fit"], "ki": {**(cfg["fit"].get("ki") or {}), "enabled": True}},
                   ask=ki_ask, gelesen=gelesen)
    today = today or date.today()
    frist = fristen.find(f"{job.title}\n{job.description}", today)
    job.frist = frist.isoformat() if frist else None
    apps_path = root / "applications.csv"
    apps = tracking.load(apps_path)
    fit_text = f"Fit {job.fit} %" if job.fit is not None else "Fit –"
    eingetragen = tracking.add_if_missing(apps, job.company, "Stelle", job.url, today,
                                          f"{job.title} ({fit_text}, selbst eingetragen)")
    if eingetragen:
        tracking.save(apps_path, apps)
    return {"id": today.isoformat(), "company": job.company, "title": job.title, "url": job.url,
            "anforderungen": job.fit_anforderungen, "fit": job.fit, "fit_line": fit_line(job), "frist": job.frist,
            "eingetragen": eingetragen, "ki": bool(gelesen), "eckdaten": job.eckdaten}
