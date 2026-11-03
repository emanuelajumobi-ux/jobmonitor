"""Lernvorschläge zur Lücken-Auswertung: Zu Begriffen, die dir in gefundenen Stellen am meisten Fit kosten,
passende Zertifikate oder kleine Projekte aus lernpfade.yaml – und auf Knopfdruck als „geplant“ in
cv/cv_master.yaml übernehmen (im_cv: false, zählt nicht für den Fit, bis du es erledigt hast).
"""
from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from . import gui_master as gm
from .cv_data import _entries
from .models import normalize

DATEI = "lernpfade.yaml"
SECTION = {"zertifikat": "zertifikate", "projekt": "projekte"}


class LernpfadError(Exception):
    pass


def load(root: Path) -> dict[str, list[dict]]:
    path = root / DATEI
    if not path.is_file():
        return {}
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
    return {str(term): [v for v in items or [] if isinstance(v, dict) and v.get("name")]
            for term, items in data.items()}


def vorhanden(cv: dict, vorschlag: dict) -> str | None:
    """Status des passenden Eintrags im Master-CV (geplant, in_arbeit, erreicht …) oder None."""
    name = normalize(vorschlag["name"])
    for section in SECTION.values():
        for entry in _entries(cv.get(section)):
            other = normalize(str(entry.get("name") or ""))
            if other and (name in other or other in name):
                return str(entry.get("status") or "vorhanden")
    return None


def vorschlaege(rows: list[dict], pfade: dict, cv: dict, limit: int = 6) -> list[dict]:
    """Für die wichtigsten Lücken (Zeilen aus gui_luecken.analyse mit Fit-Gewinn) die Vorschläge samt Stand."""
    out = []
    for r in rows:
        if not r["gewinn"] or r["term"] not in pfade:
            continue
        items = [{**v, "index": i, "stand": vorhanden(cv, v)} for i, v in enumerate(pfade[r["term"]])]
        out.append({"term": r["term"], "gewinn": max(r["gewinn"].values()), "items": items})
        if len(out) >= limit:
            break
    return out


def uebernehmen(root: Path, term: str, index: int) -> dict:
    """Vorschlag als geplanten Eintrag in cv_master.yaml schreiben (alter Stand → .bak). Gibt ihn zurück."""
    items = load(root).get(term) or []
    if not 0 <= index < len(items):
        raise LernpfadError("Vorschlag nicht gefunden (lernpfade.yaml geändert?). Seite neu laden.")
    v = items[index]
    if v.get("art") not in SECTION:
        raise LernpfadError(f"Unbekannte Art „{v.get('art')}“ in lernpfade.yaml.")
    data = gm.load(root)
    if vorhanden(data, v):
        raise LernpfadError(f"„{v['name']}“ steht schon in deinem Master-CV.")
    if v["art"] == "zertifikat":
        entry = {"name": v["name"], "zusatz": v.get("zusatz", ""), "datum": "", "status": "geplant", "im_cv": False}
    else:
        entry = {"name": v["name"], "zeitraum": "", "status": "geplant", "beschreibung": v.get("zusatz", ""),
                 "technologien": list(v.get("technologien") or [term]), "im_cv": False}
    data.setdefault(SECTION[v["art"]], [])
    data[SECTION[v["art"]]] = list(data[SECTION[v["art"]]] or []) + [entry]
    gm.save(root, data)
    return entry
