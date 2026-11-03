"""Bewerbungsfristen aus dem Anzeigentext lesen („bis spätestens 21.10.2026“, „Bewerbungsfrist: 15. November“).

Es zählen nur Datumsangaben in der Nähe eines Frist-Stichworts, damit Eintrittstermine („Start: 01.04.2027“)
nicht als Frist gelten. Ohne Jahresangabe wird das nächste passende Datum angenommen.
"""
from __future__ import annotations

import re
from datetime import date

MONATE = {m: i for i, m in enumerate(["januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
                                      "september", "oktober", "november", "dezember"], 1)}
MONATE.update({"maerz": 3, "jan": 1, "feb": 2, "mär": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
               "sept": 9, "okt": 10, "nov": 11, "dez": 12})
KEYWORD = re.compile(r"bewerbungsfrist|bewerbungsschluss|einsendeschluss|deadline|application deadline|"
                     r"bewirb dich bis|bewerben sie sich bis|bewerbung(?:en)? bis|bis (?:spätestens|zum)|"
                     r"bis einschließlich|apply by|apply until|applications? close", re.I)
NUMERIC = re.compile(r"(\d{1,2})\.\s?(\d{1,2})\.(\s?\d{4}|\s?\d{2}(?!\d))?")
WRITTEN = re.compile(r"(\d{1,2})\.?\s+(" + "|".join(sorted(MONATE, key=len, reverse=True)) + r")\.?(\s+\d{4})?",
                     re.I)
WINDOW = 60   # Zeichen nach dem Stichwort, in denen das Datum stehen muss
# „… bis 21.10.2026“ ohne „spätestens“ zählt nur, wenn kurz davor von der Bewerbung die Rede ist
# (sonst wäre „befristet bis 31.08.2027“ eine Frist).
PLAIN_BIS = re.compile(r"\bbis(?=\s+\d{1,2}\.\s?\d{1,2}\.)", re.I)
BEWERB = re.compile(r"bewerb|unterlagen|lebenslauf|zusende|schick", re.I)


def _make(day: int, month: int, year: str | None, today: date) -> date | None:
    try:
        if year:
            y = int(year.strip())
            return date(y + 2000 if y < 100 else y, month, day)
        candidate = date(today.year, month, day)
        # Ohne Jahr: liegt das Datum deutlich zurück, ist das nächste Jahr gemeint
        return candidate if (today - candidate).days <= 60 else date(today.year + 1, month, day)
    except ValueError:
        return None


def find(text: str, today: date) -> date | None:
    """Früheste plausible Frist im Text oder None."""
    found = []
    text = text or ""
    anchors = [kw.end() for kw in KEYWORD.finditer(text)]
    anchors += [m.end() for m in PLAIN_BIS.finditer(text) if BEWERB.search(text[max(0, m.start() - 150): m.start()])]
    for end in anchors:
        window = text[end: end + WINDOW]
        for m in NUMERIC.finditer(window):
            d = _make(int(m.group(1)), int(m.group(2)), m.group(3), today)
            if d:
                found.append(d)
        for m in WRITTEN.finditer(window):
            d = _make(int(m.group(1)), MONATE[m.group(2).lower()], m.group(3), today)
            if d:
                found.append(d)
    plausible = [d for d in found if -365 <= (d - today).days <= 365]
    return min(plausible) if plausible else None


def label(frist: str | None, today: date) -> str:
    """„Frist 21.10.2026 (in 5 Tagen)“, „Frist abgelaufen (21.10.2026)“ oder ""."""
    if not frist:
        return ""
    d = date.fromisoformat(frist)
    days = (d - today).days
    if days < 0:
        return f"Frist abgelaufen ({d:%d.%m.%Y})"
    when = "heute" if days == 0 else "morgen" if days == 1 else f"in {days} Tagen"
    return f"Frist {d:%d.%m.%Y} ({when})"
