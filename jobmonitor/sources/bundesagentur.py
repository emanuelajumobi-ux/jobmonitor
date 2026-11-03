"""Bundesagentur für Arbeit – inoffizielle öffentliche Jobsuche-Schnittstelle.

Stand 31.10.2026: /pc/v4 und /pc/v5 liefern 403, /pc/v6 funktioniert mit X-API-Key: jobboerse-jobsuche.
Es gibt keinen funktionierenden Homeoffice-Filterparameter mehr; Treffer tragen aber das Feld
`homeofficemoeglich`. Für Remote suchen wir daher bundesweit und behalten nur diese Treffer.
robots.txt des API-Hosts liefert 403 (es ist keine Website); die Abfrage ist bewusst sparsam.
"""
from __future__ import annotations

import base64
import logging
import re

import requests

from ..http import Fetcher
from ..models import Job, SourceResult

log = logging.getLogger(__name__)
NAME = "Bundesagentur für Arbeit"
DETAIL_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
MARKDOWN = re.compile(r"[*#_`]+")
SHORT_TEXT = 800   # kürzere API-Texte sind bei Partneranzeigen nur ein Anreißer


def parse_results(data: dict, remote_only: bool = False) -> list[Job]:
    jobs = []
    for item in data.get("ergebnisliste") or []:
        remote = bool(item.get("homeofficemoeglich"))
        if remote_only and not remote:
            continue
        refnr = item.get("referenznummer") or item.get("refnr") or ""
        orte = [(loc.get("adresse") or {}).get("ort", "") for loc in item.get("stellenlokationen") or []]
        jobs.append(Job(
            title=item.get("stellenangebotsTitel") or item.get("titel") or "",
            company=item.get("firma") or item.get("arbeitgeber") or "",
            url=item.get("externeURL") or DETAIL_URL.format(refnr=refnr),
            source=NAME,
            location=", ".join(o for o in orte if o),
            remote=remote,
            description=" ".join(item.get("alleBerufe") or []) + " " + (item.get("hauptberuf") or ""),
            kind=item.get("stellenangebotsart") or "",
            posted=item.get("datumErsteVeroeffentlichung") or "",
            external_id=refnr,
            distance_km=None if remote_only else item.get("entfernung"),
        ))
    return jobs


class BundesagenturSource:
    name = NAME

    def __init__(self, cfg: dict, fetcher: Fetcher, profil_name: str = ""):
        """cfg: sources.bundesagentur plus suchbegriffe (und optional angebotsart) des Suchprofils."""
        self.cfg = cfg
        self.fetcher = fetcher
        self.version: str | None = None
        self.name = f"{NAME} ({profil_name})" if profil_name else NAME

    def _search(self, params: dict) -> dict:
        headers = {"X-API-Key": self.cfg["api_key"], "Accept": "application/json"}
        versions = [self.version] if self.version else self.cfg["api_versions"]
        last_error = None
        for version in versions:
            url = f"{self.cfg['base_url']}/{version}/jobs"
            try:
                resp = self.fetcher.get(url, check_robots=False, headers=headers, params=params)
                if self.version is None:
                    self.version = version
                    log.info("BA-API: verwende %s", version)
                return resp.json()
            except requests.HTTPError as exc:
                last_error = exc
                log.warning("BA-API %s: %s", version, exc)
        raise RuntimeError(f"Keine BA-API-Version erreichbar ({', '.join(versions)}): {last_error}")

    def description(self, refnr: str) -> str:
        """Volltext einer Anzeige (jobdetails, Stand 31.10.2026 nur unter v4 erreichbar)."""
        b64 = base64.b64encode(refnr.encode("utf-8")).decode("ascii")
        url = f"{self.cfg['base_url']}/{self.cfg['detail_api_version']}/jobdetails/{b64}"
        headers = {"X-API-Key": self.cfg["api_key"], "Accept": "application/json"}
        data = self.fetcher.get(url, check_robots=False, headers=headers).json()
        return MARKDOWN.sub("", data.get("stellenangebotsBeschreibung") or "").strip()

    def add_details(self, jobs: list[Job]) -> int:
        """Beschreibung neuer, bereits gefilterter BA-Treffer nachladen (für das Fit-Rating). Fehler sind still."""
        done = 0
        for job in [j for j in jobs if j.source.startswith(NAME) and j.external_id][: self.cfg["max_details"]]:
            try:
                text = self.description(job.external_id)
            except Exception as exc:   # Fit bleibt dann "–", der Lauf geht weiter
                log.info("BA-Detail %s nicht geladen: %s", job.external_id, exc)
                text = ""
            if len(text) < SHORT_TEXT and "arbeitsagentur.de" not in job.url:   # Partnerbörse: nur Anreißer
                text = f"{text}\n{self._partner_page(job.url)}".strip()
            if text:
                job.description = f"{job.description}\n{text}"
                done += 1
        return done

    def _partner_page(self, url: str) -> str:
        """Anzeige liegt bei einer Partnerbörse (externeURL): Seite einmal lesen, mit robots.txt und ohne
        LinkedIn/StepStone/Indeed & Co. (gleiche Regeln wie bei selbst angegebenen Stellen)."""
        from ..eigene_stelle import from_url
        try:
            return from_url(url, self.fetcher).description
        except Exception as exc:
            log.info("Partnerseite %s nicht gelesen: %s", url, exc)
            return ""

    def fetch(self) -> SourceResult:
        result = SourceResult(self.name)
        base = {"size": self.cfg["page_size"], "page": 1, "veroeffentlichtseit": self.cfg["veroeffentlicht_seit_tage"]}
        if self.cfg.get("angebotsart"):   # 1 = Arbeit, 34 = Praktikum/Trainee/Werkstudent; ohne = alle
            base["angebotsart"] = self.cfg["angebotsart"]
        for term in self.cfg["suchbegriffe"]:
            try:
                data = self._search({**base, "was": term, "wo": self.cfg["wo"], "umkreis": self.cfg["umkreis_km"]})
                result.jobs += parse_results(data)
                if self.cfg.get("bundesweit_remote"):
                    data = self._search({**base, "was": term})
                    result.jobs += parse_results(data, remote_only=True)
            except Exception as exc:  # eine Suche darf die anderen nicht stoppen
                result.errors.append(f"Suche '{term}': {exc}")
                if self.version is None:
                    break  # keine API-Version erreichbar → restliche Suchen sinnlos
        if self.version and self.version != self.cfg["api_versions"][0]:
            result.notes.append(f"BA-API läuft nur noch über {self.version}")
        return result
