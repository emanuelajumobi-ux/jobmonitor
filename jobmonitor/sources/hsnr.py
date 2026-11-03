"""Stellenbörse der Hochschule Niederrhein (öffentlich, ohne Login).

Liste: div.container.job mit Spalten FB / Stellentyp / Firma / Stellenbezeichnung (Link auf PDF) /
Standort / Eingestellt am. Pagination über den Link "nächste" (enthält cHash, daher aus dem HTML übernehmen).
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pypdf import PdfReader

from ..http import Fetcher
from ..location import is_remote
from ..models import Job, SourceResult
from ..scoring import matches
from ..state import State

log = logging.getLogger(__name__)
NAME = "Hochschule Niederrhein"
SOURCE_ID = "hsnr"
# Grobes IT-Vorsieb für den Titel, bevor das PDF geladen wird
IT_HINTS = ["informatik", "it", "software", "netzwerk", "system", "cyber", "security", "sicherheit", "cloud",
            "devops", "admin", "digital", "infrastruktur", "azure", "daten", "entwickl", "programm", "ki"]


@dataclass
class Row:
    fachbereich: str
    stellentyp: str
    firma: str
    titel: str
    url: str
    standort: str
    datum: str


def parse_list(html: str, base_url: str) -> tuple[list[Row], str | None]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for div in soup.select("div.container.job"):
        cols = div.find_all("div", recursive=False)
        link = div.find("a", href=True)
        if len(cols) < 6 or link is None:
            continue
        rows.append(Row(
            fachbereich=cols[0].get_text(" ", strip=True),
            stellentyp=cols[1].get_text(" ", strip=True),
            firma=cols[2].get_text(" ", strip=True),
            titel=link.get_text(" ", strip=True),
            url=urljoin(base_url, link["href"]),
            standort=cols[4].get_text(" ", strip=True),
            datum=cols[5].get_text(" ", strip=True),
        ))
    nxt = soup.find("a", string=re.compile(r"^\s*nächste\s*$", re.IGNORECASE))
    return rows, (urljoin(base_url, nxt["href"]) if nxt and nxt.get("href") else None)


def pdf_text(data: bytes, max_pages: int = 4) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:max_pages])


class HsnrSource:
    name = NAME

    def __init__(self, cfg: dict, fach_keywords, fetcher: Fetcher, state: State, today: date):
        self.cfg = cfg
        self.fach_keywords = list(fach_keywords)
        self.fetcher = fetcher
        self.state = state
        self.today = today.isoformat()

    def _interesting(self, row: Row) -> bool:
        if row.stellentyp not in self.cfg["stellentypen"]:
            return False
        return bool(matches(row.titel, self.fach_keywords) or matches(row.titel, IT_HINTS))

    def fetch(self) -> SourceResult:
        result = SourceResult(self.name)
        url: str | None = self.cfg["url"]
        incremental = self.state.has_crawled_any(SOURCE_ID)
        pages = 0
        while url and pages < self.cfg["max_pages"]:
            pages += 1
            try:
                html = self.fetcher.get(url).text
            except Exception as exc:
                result.errors.append(f"Seite {pages}: {exc}")
                break
            rows, url = parse_list(html, self.cfg["url"])
            if not rows:
                result.errors.append(f"Seite {pages}: keine Einträge erkannt (Seitenstruktur geändert?)")
                break
            new_rows = [r for r in rows if not self.state.is_crawled(SOURCE_ID, r.url)]
            for row in new_rows:
                self.state.mark_crawled(SOURCE_ID, row.url, self.today)
                if self._interesting(row):
                    result.jobs.append(self._to_job(row, result))
            if incremental and len(new_rows) < len(rows):
                break  # bekannte Einträge erreicht
        result.notes.append(f"{pages} Seite(n) gelesen")
        return result

    def _to_job(self, row: Row, result: SourceResult) -> Job:
        text = ""
        if row.url.lower().endswith(".pdf"):
            try:
                text = pdf_text(self.fetcher.get(row.url).content)
            except Exception as exc:
                result.errors.append(f"PDF '{row.titel}': {exc}")
        return Job(
            title=row.titel, company=row.firma, url=row.url, source=NAME, location=row.standort,
            remote=is_remote(row.standort, text), description=text, kind=row.stellentyp,
            posted=row.datum, external_id=row.url,
        )
