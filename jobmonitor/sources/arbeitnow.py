"""Arbeitnow – freie Job-Board-API (https://www.arbeitnow.com/blog/job-board-api), ohne Schlüssel.

Arbeitnow sammelt Stellen aus Bewerbungssystemen (Greenhouse, SmartRecruiters, Join.com, Teamtailor, Recruitee,
Comeet), vor allem in Deutschland. Die API hat keine Suche: Sie liefert alle Stellen, neueste zuerst, 300 je Seite.
Wir lesen Seite für Seite, bis die Stellen älter als `tage` sind (höchstens `max_seiten`); Ort, Rolle und Fach filtert
danach die Pipeline wie bei jeder Quelle.

Bedingungen (Stand 03.11.2026): persönliche, nicht kommerzielle Nutzung; Rücklink auf arbeitnow.com erbeten (steht im
Bericht an der Quelle); die Erlaubnis kann jederzeit widerrufen werden. robots.txt erlaubt /api.
"""
from __future__ import annotations

import logging
import time

from bs4 import BeautifulSoup

from ..http import Fetcher
from ..models import Job, SourceResult

log = logging.getLogger(__name__)
NAME = "Arbeitnow"
URL = "https://www.arbeitnow.com/api/job-board-api"
LINK = "https://www.arbeitnow.com"


def text(html: str) -> str:
    return BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)


def parse(data: dict) -> list[Job]:
    jobs = []
    for item in data.get("data") or []:
        if not item.get("title") or not item.get("url"):
            continue
        art = ", ".join(item.get("job_types") or [])
        jobs.append(Job(
            title=item["title"],
            company=item.get("company_name") or "",
            url=item["url"],
            source=NAME,
            location=item.get("location") or "",
            remote=bool(item.get("remote")),
            description=" ".join([text(item.get("description") or ""), " ".join(item.get("tags") or [])]),
            kind=art,
            posted=time.strftime("%Y-%m-%d", time.gmtime(item["created_at"])) if item.get("created_at") else "",
            external_id=item.get("slug") or "",
        ))
    return jobs


class ArbeitnowSource:
    name = NAME

    def __init__(self, cfg: dict, fetcher: Fetcher, jetzt: float | None = None):
        """cfg: sources.arbeitnow (tage, max_seiten)."""
        self.cfg = cfg
        self.fetcher = fetcher
        self.jetzt = jetzt

    def fetch(self) -> SourceResult:
        result = SourceResult(self.name)
        grenze = (self.jetzt or time.time()) - int(self.cfg.get("tage", 14)) * 86400
        for seite in range(1, int(self.cfg.get("max_seiten", 10)) + 1):
            try:
                data = self.fetcher.get(URL, params={"page": seite}, headers={"Accept": "application/json"}).json()
            except Exception as exc:
                result.errors.append(f"Seite {seite}: {exc}")
                break
            items = data.get("data") or []
            result.jobs += parse({"data": [i for i in items if (i.get("created_at") or 0) >= grenze]})
            if not items or min(i.get("created_at") or 0 for i in items) < grenze or not (data.get("links") or {}).get("next"):
                break
        else:
            result.notes.append(f"nach {self.cfg.get('max_seiten', 10)} Seiten abgebrochen (max_seiten)")
        return result
