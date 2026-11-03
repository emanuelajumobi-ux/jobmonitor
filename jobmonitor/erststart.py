"""Erster Start ohne eigene Dateien (installierte App oder frischer Ordner): Datenordner mit Standard-Dateien anlegen.

Kopiert nur, was fehlt – vorhandene Dateien werden nie überschrieben. Quelle sind jobmonitor/vorlagen/ (neutrale
config.yaml und leere Firmenliste) und die Vorlagen in cv/ des Programmordners. Danach führt der
Einrichtungs-Assistent (gui_assistent.py) durch Profil, Wohnort, Suchprofil und Lebenslauf.
"""
from __future__ import annotations

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


def eingerichtet(root: Path) -> bool:
    """Gilt als eingerichtet, sobald Master-CV oder persönliche Angaben da sind oder der Assistent abgeschlossen ist."""
    return any((root / p).exists() for p in ("cv/cv_master.yaml", "cv_master.yaml", "cv/profile.yaml",
                                            ".gui_eingerichtet.json"))
