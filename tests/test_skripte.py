"""Alle Skripte in den Seiten müssen gültiges JavaScript sein (ein kaputtes Skript legt die ganze Seite lahm).

Auf der Suchprofil-Seite stand einmal ein echter Zeilenumbruch mitten in einem JS-Text – Zähler, Abruf-Schätzung und
die Vorlagen der Karrierestufe waren dadurch tot, ohne dass ein Python-Test es merkte.
"""
import html
import re
import shutil
import subprocess

import pytest

from jobmonitor import erststart
from jobmonitor.gui import App

SEITEN = ["index", "master", "bewerbungen", "firmen", "einstellungen", "profil", "unterlagen", "luecken", "hilfe",
          "einrichten", "eigene", "rueckblick", "bericht", "suchprofil", "uebung"]


def _pruefen(js: str, tmp_path, name: str) -> str:
    datei = tmp_path / f"{name}.js"
    datei.write_text(js, encoding="utf-8")
    proc = subprocess.run(["node", "--check", str(datei)], capture_output=True, text=True)
    return "" if proc.returncode == 0 else " ".join(proc.stderr.splitlines()[1:5])


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht installiert")
@pytest.mark.parametrize("seite", SEITEN)
def test_skripte_sind_gueltig(seite, tmp_path):
    root = tmp_path / "daten"
    erststart.vorbereiten(root)
    app = App(root, compile_pdf=False)
    if seite == "hilfe":
        from jobmonitor import gui_hilfe as gh
        text = app.page("Anleitung", gh.render(), "hilfe", gh.CSS).decode("utf-8")
    elif seite == "uebung":
        text = app.uebung_seite("").decode("utf-8")
    else:
        text = getattr(app, seite)().decode("utf-8")
    fehler = []
    for i, m in enumerate(re.finditer(r"<script(?![^>]*application/(?:ld\+)?json)[^>]*>(.*?)</script>", text, re.S)):
        if m.group(1).strip() and (f := _pruefen(m.group(1), tmp_path, f"s{i}")):
            fehler.append(f"Skript {i}: {f}")
    for i, m in enumerate(re.finditer(r'\son\w+="([^"]*)"', text)):
        if f := _pruefen("(function(){" + html.unescape(m.group(1)) + "\n})", tmp_path, f"h{i}"):
            fehler.append(f"Handler {m.group(1)[:80]}: {f}")
    assert not fehler, fehler
