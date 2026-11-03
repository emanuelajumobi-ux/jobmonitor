"""Adzuna – offizielle Job-Suchmaschinen-API (https://developer.adzuna.com), Deutschland (`de`).

Braucht einen eigenen, kostenlosen Zugang: ADZUNA_APP_ID und ADZUNA_APP_KEY als Umgebungsvariablen (lokal .env, in
der Pipeline GitHub Secrets) – nie im Code oder in config.yaml. Ohne beide läuft die Quelle nicht.

Gesucht wird wie bei der Bundesagentur: je Suchprofil die ersten `max_begriffe` BA-Suchbegriffe, Köln + Umkreis, nur
Anzeigen der letzten `tage` Tage. Adzuna liefert nur einen Auszug der Beschreibung; der Link führt über adzuna.de zur
Originalanzeige und wird nie abgerufen (das kann eine Jobbörse wie StepStone sein).

Bedingungen (Stand 03.11.2026): „Personal job search“ ist ausdrücklich erlaubt; nicht weitergeben, nicht kommerziell.
robots.txt des API-Hosts sperrt pauschal alles – der Zugang ist über die API-Bedingungen und den eigenen Schlüssel
geregelt (wie bei der Bundesagentur), daher ohne robots-Prüfung, aber sparsam.
"""
from __future__ import annotations

import logging
import os
import re

from ..http import Fetcher
from ..location import is_remote
from ..models import Job, SourceResult

log = logging.getLogger(__name__)
NAME = "Adzuna"
URL = "https://api.adzuna.com/v1/api/jobs/de/search/{seite}"
LINK = "https://www.adzuna.de"
TAG = re.compile(r"<[^>]+>")


def zugang() -> tuple[str, str] | None:
    app_id, key = os.environ.get("ADZUNA_APP_ID", "").strip(), os.environ.get("ADZUNA_APP_KEY", "").strip()
    return (app_id, key) if app_id and key else None


def _rein(text: str) -> str:
    return TAG.sub("", text or "").replace("\n", " ").strip()


def parse(data: dict) -> list[Job]:
    jobs = []
    for item in data.get("results") or []:
        titel, url = _rein(item.get("title")), item.get("redirect_url") or ""
        if not titel or not url:
            continue
        beschreibung = _rein(item.get("description"))
        ort = (item.get("location") or {}).get("display_name") or ""
        jobs.append(Job(
            title=titel,
            company=(item.get("company") or {}).get("display_name") or "",
            url=url,
            source=NAME,
            location=ort,
            remote=is_remote(titel, beschreibung),
            description=beschreibung,
            kind=item.get("contract_time") or "",
            posted=(item.get("created") or "")[:10],
            external_id=str(item.get("id") or ""),
        ))
    return jobs


class AdzunaSource:
    name = NAME

    def __init__(self, cfg: dict, fetcher: Fetcher, suchbegriffe: list[str], profil_name: str = ""):
        """cfg: sources.adzuna (wo, umkreis_km, tage, max_begriffe, je_seite); suchbegriffe: BA-Begriffe des Profils."""
        self.cfg = cfg
        self.fetcher = fetcher
        self.suchbegriffe = suchbegriffe[:int(cfg.get("max_begriffe", 8))]
        self.name = f"{NAME} ({profil_name})" if profil_name else NAME

    def fetch(self) -> SourceResult:
        result = SourceResult(self.name)
        z = zugang()
        if z is None:
            result.notes.append("kein Zugang (ADZUNA_APP_ID/ADZUNA_APP_KEY nicht gesetzt) – übersprungen")
            return result
        for begriff in self.suchbegriffe:
            params = {"app_id": z[0], "app_key": z[1], "what": begriff, "where": self.cfg.get("wo", "Köln"),
                      "distance": self.cfg.get("umkreis_km", 50), "max_days_old": self.cfg.get("tage", 7),
                      "results_per_page": self.cfg.get("je_seite", 50), "sort_by": "date"}
            try:
                resp = self.fetcher.get(URL.format(seite=1), check_robots=False, params=params,
                                        headers={"Accept": "application/json"})
                result.jobs += parse(resp.json())
            except Exception as exc:
                # Fehlertext ohne Schlüssel: die URL mit app_key landet nie im Bericht
                meldung = str(exc).replace(z[1], "***").replace(z[0], "***")
                result.errors.append(f"Suche '{begriff}': {meldung}")
                if "401" in meldung or "403" in meldung:
                    break   # Zugang falsch → restliche Suchen sinnlos
        return result
