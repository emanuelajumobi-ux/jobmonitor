"""Stellenwerk-Portale (z. B. Köln für Uni Köln/TH Köln, Düsseldorf für die HSD), öffentlich ohne Login.

robots.txt von stellenwerk.de antwortet mit HTTP 403 (S3 "AccessDenied") statt mit Regeln. Auf deine
ausdrückliche Freigabe hin wird die Seite trotzdem gelesen – sparsam: wenige Suchanfragen pro Lauf,
Detailseiten nur einmal (danach aus dem State bekannt), Rate-Limit wie überall.
Suche: /{portal}?_q=Begriff (serverseitig gerendert, 10 Treffer); Detailseiten enthalten JSON-LD JobPosting.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urlsplit

from ..http import Fetcher
from ..models import Job, SourceResult
from ..state import State
from .ats import jsonld

log = logging.getLogger(__name__)
NAME = "Stellenwerk"
DETAIL_RE = r"/{portal}/[a-z0-9-]+-\d{{6}}-\d+"


def search_links(html: str, portal: str) -> list[str]:
    out = []
    for path in re.findall(DETAIL_RE.format(portal=re.escape(portal)), html):
        url = f"https://www.stellenwerk.de{path}"
        if url not in out:
            out.append(url)
    return out


def interesting(url: str) -> bool:
    slug = url.rsplit("/", 1)[-1]
    return bool(jsonld.ROLE_SLUG.search(slug) or jsonld.TECH_SLUG.search(slug))


class StellenwerkSource:
    name = NAME

    def __init__(self, portals: list[dict], cfg: dict, fetcher: Fetcher, state: State, today: date,
                 profil_name: str = ""):
        self.portals = portals          # Einträge aus companies.yaml (quelle: stellenwerk, aktiv: true)
        self.cfg = cfg                  # sources.stellenwerk plus suchbegriffe des Suchprofils
        self.name = f"{NAME} ({profil_name})" if profil_name else NAME
        self.fetcher = fetcher
        self.state = state
        self.today = today.isoformat()

    def fetch(self) -> SourceResult:
        result = SourceResult(self.name)
        details = 0
        for entry in self.portals:
            portal = urlsplit(entry["karriereseite_url"]).path.strip("/").split("/")[0]
            links: list[str] = []
            for term in self.cfg["suchbegriffe"]:
                try:
                    html = self.fetcher.get(f"https://www.stellenwerk.de/{portal}", check_robots=False,
                                            params={"_q": term}).text
                except Exception as exc:
                    result.errors.append(f"{entry['name']}, Suche '{term}': {exc}")
                    continue
                links += [u for u in search_links(html, portal) if u not in links]
            source_id = f"stellenwerk-{portal}"
            new = [u for u in links if interesting(u) and not self.state.is_crawled(source_id, u)]
            for url in new[: self.cfg["max_detail_pages"]]:
                try:
                    detail = self.fetcher.get(url, check_robots=False).text
                except Exception as exc:
                    result.errors.append(f"{entry['name']}: {url}: {exc}")
                    continue
                self.state.mark_crawled(source_id, url, self.today)
                details += 1
                for job in jsonld.parse_postings(detail, url, "", entry["name"]):
                    job.url = url
                    job.company = job.company or _hiring_org(detail) or "(Stellenwerk)"
                    result.jobs.append(job)
            result.notes.append(f"{portal}: {len(links)} Suchtreffer, {len(new)} neu")
        result.notes.append(f"{details} Detailseite(n) gelesen")
        return result


def _hiring_org(html: str) -> str:
    m = re.search(r'"hiringOrganization"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', html)
    return m.group(1) if m else ""
