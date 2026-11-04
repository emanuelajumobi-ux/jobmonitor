"""Erster Start ohne eigene Dateien (installierte App oder frischer Ordner): Datenordner mit Standard-Dateien anlegen.

Kopiert nur, was fehlt – vorhandene Dateien werden nie überschrieben. Quelle sind jobmonitor/vorlagen/ (neutrale
config.yaml und leere Firmenliste) und die Vorlagen in cv/ des Programmordners. Danach führt der
Einrichtungs-Assistent (gui_assistent.py) durch Profil, Wohnort, Suchprofil und Lebenslauf.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import CODE

VORLAGEN = CODE / "jobmonitor" / "vorlagen"
DATEIEN = {"config.yaml": VORLAGEN / "config.default.yaml", "companies.yaml": VORLAGEN / "companies.default.yaml"}
CV_DATEIEN = ["template.tex.j2", "anschreiben.tex.j2", "template.html.j2", "anschreiben.html.j2",
              "anschreiben_vorlage.txt", "nachfassen_vorlage.txt", "profile.example.yaml"]


def vorbereiten(root: Path) -> list[str]:
    """Fehlende Dateien anlegen; gibt die angelegten relativen Pfade zurück."""
    neu = []
    root.mkdir(parents=True, exist_ok=True)
    for name, quelle in DATEIEN.items():
        if not (root / name).exists() and quelle.is_file():
            shutil.copy(quelle, root / name)
            neu.append(name)
    if "config.yaml" in neu:          # erster Start: Oberfläche in der Sprache des Systems (Deutsch oder Englisch)
        from . import i18n
        try:
            if i18n.systemsprache() == "en":
                i18n.setzen(root, "en")
        except Exception:   # Sprache ist nur Komfort – der erste Start darf daran nicht scheitern
            pass
    (root / "cv").mkdir(exist_ok=True)
    for name in CV_DATEIEN:
        ziel, quelle = root / "cv" / name, CODE / "cv" / name
        if (VORLAGEN / name).is_file():           # neutrale Fassung für neue Nutzer (ohne „Ich studiere …“)
            quelle = VORLAGEN / name
        if not ziel.exists() and quelle.is_file() and quelle.resolve() != ziel.resolve():
            shutil.copy(quelle, ziel)
            neu.append(f"cv/{name}")
    (root / "state").mkdir(exist_ok=True)
    return neu


ASSISTENT = ".gui_eingerichtet.json"


def _assistent(root: Path) -> dict:
    try:
        data = json.loads((root / ASSISTENT).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def eingerichtet(root: Path) -> bool:
    """Fertig, sobald der Assistent abgeschlossen ist. Wurde er begonnen, aber nicht beendet (z. B. weil man zwischendurch
    die KI-Anleitung geöffnet hat), führt die App wieder dorthin. Ältere Stände ohne Merker gelten wie bisher als
    eingerichtet, sobald Master-CV oder persönliche Angaben da sind."""
    data = _assistent(root)
    if data.get("fertig"):
        return True
    if data.get("begonnen"):
        return False
    return any((root / p).exists() for p in ("cv/cv_master.yaml", "cv_master.yaml", "cv/profile.yaml", ASSISTENT))


def unfertig(root: Path) -> bool:
    """Assistent begonnen, aber noch nicht abgeschlossen."""
    data = _assistent(root)
    return bool(data.get("begonnen")) and not data.get("fertig")


def beginnen(root: Path) -> None:
    """Beim ersten Öffnen des Assistenten merken, dass die Einrichtung läuft (nur bei neuen Nutzern)."""
    if eingerichtet(root) or _assistent(root).get("begonnen"):
        return
    from datetime import date
    data = {**_assistent(root), "begonnen": date.today().isoformat()}
    (root / ASSISTENT).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
