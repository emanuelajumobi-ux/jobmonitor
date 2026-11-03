"""Firmen, die Initiativbewerbungen annehmen (companies.yaml → initiativ.moeglich: ja) – eine Liste für Bericht und
Firmen-Seite, damit beide dasselbe zeigen.

Nicht dabei: inaktive Firmen, Firmen ohne Link zur Initiativ-Seite und Firmen ohne Standort in Reichweite (außer
Remote). Firmen, die gerade passende Stellen haben, bleiben drin, aber markiert und hinten: Dort bewirbst du dich
besser direkt auf die Stelle.
"""
from __future__ import annotations

from .location import travel_minutes
from .models import normalize
from .report import InitiativTip


def kandidaten(companies_doc, src, matched_companies: set[str], cfg: dict) -> list[tuple[InitiativTip, bool]]:
    """[(Vorschlag, hat gerade passende Stellen)] – neu entdeckte und wichtige Kategorien zuerst.
    `src`: CompaniesSource des Laufs (für „neu entdeckt“) oder None."""
    prio = cfg["initiativ"]["prioritaet_kategorien"]
    candidates = []
    for entry in companies_doc.get("firmen") or []:
        info = entry.get("initiativ") or {}
        if entry.get("aktiv") is False or info.get("moeglich") != "ja" or not info.get("url"):
            continue
        hat_stellen = any(normalize(entry["name"]) in c for c in matched_companies)
        outcome = src.outcomes.get(entry["name"]) if src else None
        neu = bool(outcome and outcome.initiativ_neu)
        standorte = list(entry.get("standorte") or [])
        remote = "Remote" in standorte
        minuten = [travel_minutes(s, None, cfg["ort"].get("fahrzeiten")) for s in standorte]
        nah = [m for m in minuten if m is not None and m <= cfg["ort"]["max_fahrzeit_min"]]
        if standorte and not nah and not remote:
            continue  # kein Standort in Reichweite und kein Remote
        kat = entry.get("kategorie", "")
        warum = f"{entry.get('branche') or kat.capitalize()}"
        if entry.get("fokus"):
            warum += f" mit Bezug zu {', '.join(entry['fokus'][:3])}"
        orte = [s for s in standorte if s != "Remote"]
        warum += f"; Standort {', '.join(orte)}" if orte else ""
        warum += " und Remote-Option." if remote else "."
        if entry.get("notizen"):
            warum += f" ({entry['notizen']})"
        rank = (hat_stellen, not neu, prio.index(kat) if kat in prio else len(prio), not remote, entry["name"].lower())
        candidates.append((rank, InitiativTip(entry["name"], info["url"], warum, neu), hat_stellen))
    candidates.sort(key=lambda c: c[0])
    return [(tip, hat) for _, tip, hat in candidates]
