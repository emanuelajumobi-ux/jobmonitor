"""applications.csv: Bewerbungs-Tracking und Nachfass-Erinnerungen."""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

FIELDS = ["firma", "typ", "status", "datum", "link", "notizen", "termin"]   # termin: Gespräch, ISO-Datum+Zeit
STATUSES = ["neu", "Entwurf", "beworben", "nachgefasst", "Antwort", "Absage", "Zusage", "verworfen"]


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def save(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def add_if_missing(rows: list[dict], firma: str, typ: str, link: str, today: date, notizen: str = "") -> bool:
    if any(r.get("link") == link or (typ == "Initiativ" and r.get("firma") == firma and r.get("typ") == typ)
           for r in rows):
        return False
    rows.append({"firma": firma, "typ": typ, "status": "neu", "datum": today.isoformat(), "link": link,
                 "notizen": notizen})
    return True


def follow_ups(rows: list[dict], today: date, days: int, beantwortet: set[str] = frozenset()) -> list[dict]:
    """Bewerbungen mit Status 'beworben', deren Datum mindestens `days` Tage zurückliegt. `beantwortet`: Links, zu
    denen schon eine Antwort im Postfach erkannt wurde (antworten.py) – dort wäre eine Nachfrage unpassend."""
    due = []
    for r in rows:
        if r.get("status", "").strip().lower() != "beworben" or r.get("link") in beantwortet:
            continue
        try:
            sent = date.fromisoformat(r.get("datum", "").strip())
        except ValueError:
            continue
        if today - sent >= timedelta(days=days):
            due.append({**r, "tage": (today - sent).days})
    return due
