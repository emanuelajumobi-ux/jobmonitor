"""Karte „Heute bewerben“ auf der Startseite: die drei Stellen, für die sich eine Bewerbung jetzt am meisten lohnt.

Grundlage ist der Fit. Dazu kommen Zuschläge für eine nahe Bewerbungsfrist, eine ganz frische Anzeige und einen Treffer
im Traumprofil. Nicht dabei: Stellen, auf die du dich schon beworben hast (oder die du verworfen hast), die nicht mehr
online sind oder deren Frist abgelaufen ist, und Stellen unter `min_fit`.
"""
from __future__ import annotations

from datetime import date
from html import escape

ERLEDIGT = ("beworben", "nachgefasst", "Antwort", "Absage", "Zusage", "verworfen")
DEFAULTS = {"anzahl": 3, "min_fit": 50}


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def _datum(text) -> date | None:
    try:
        return date.fromisoformat(str(text or "")[:10])
    except ValueError:
        return None


def auswahl(jobs: list[dict], status_of: dict[str, str], offline: dict[str, str], heute: date,
            cfg: dict | None = None) -> list[tuple[int, dict, list[str]]]:
    """[(Priorität, Stelle, Gründe)] – höchstens `anzahl`, beste zuerst."""
    c = {**DEFAULTS, **(cfg or {})}
    out = []
    for d in jobs:
        if d.get("fit") is None or d["fit"] < c["min_fit"] or status_of.get(d["url"]) in ERLEDIGT \
                or d["url"] in offline:
            continue
        punkte, gruende = d["fit"], [f"Fit {d['fit']} %"]
        frist = _datum(d.get("frist"))
        if frist is not None:
            tage = (frist - heute).days
            if tage < 0:
                continue
            if tage <= 7:
                punkte, gruende = punkte + 15, gruende + [f"Frist in {tage} Tag{'en' if tage != 1 else ''}"
                                                          if tage else "Frist heute"]
            elif tage <= 14:
                punkte, gruende = punkte + 8, gruende + [f"Frist am {frist:%d.%m.}"]
        neu = _datum(d.get("first_seen"))
        if neu is not None and (heute - neu).days <= 3:
            punkte, gruende = punkte + 10, gruende + ["frisch – früh bewerben lohnt sich"]
        if d.get("traum"):
            punkte, gruende = punkte + 10, gruende + ["Traumprofil"]
        if status_of.get(d["url"]) == "Entwurf":
            punkte, gruende = punkte + 5, gruende + ["Entwurf liegt schon bereit"]
        out.append((punkte, d, gruende))
    out.sort(key=lambda x: (-x[0], x[1].get("title", "")))
    return out[: c["anzahl"]]


def render(eintraege: list[tuple[int, dict, list[str]]]) -> str:
    if not eintraege:
        return ""
    zeilen = "".join(
        f'<li><div><a href="{esc(d["url"])}" target="_blank" rel="noopener"><b>{esc(d["title"])}</b></a>'
        f'<p class="muted">{esc(d["company"])} · {esc(" · ".join(gruende))}</p></div>'
        f'<a class="btn small" href="/bewerbung?job={esc(d["id"])}">Bewerbung</a></li>'
        for _, d, gruende in eintraege)
    return (f'<div class="card heute"><div class="head"><h2>Heute bewerben</h2><span class="muted">Fit, Frist und '
            f'Frische zusammen</span></div><ul>{zeilen}</ul></div>')


CSS = """
.heute ul { list-style:none; margin:4px 0 0; padding:0; display:grid; gap:2px; }
.heute li { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:10px 0;
  border-top:1px solid var(--line); }
.heute li:first-child { border-top:0; } .heute li p { margin:2px 0 0; font-size:13px; }
.heute li a b { color:var(--text); }
"""
