"""Neu-Nutzer-Check: Eine frische Installation darf keine Spuren der Einrichtung des Entwicklers zeigen – weder
persönliche Angaben noch sein Fachgebiet, Wohnort oder Arbeitgeber. Läuft auf allen Seiten der Oberfläche."""
import html
import re
from pathlib import Path

import pytest

from jobmonitor import erststart
from jobmonitor import gui_hilfe as gh
from jobmonitor.gui import App

# Fachgebiet, Wohnort und Firmen der eigenen Einrichtung (nicht persönlich, aber für Fremde verwirrend)
FREMD = ["cloud security", "cloud-security", "köln", "koeln", "niederrhein", "adesso", "werkstudent cloud"]   # dazu persönliche Begriffe
ERLAUBT = re.compile(r"paypal\.me/\S+|https://github\.com/emanuelajumobi-ux\S*|/Users/\S+", re.I)   # Spendenlink, Repo


def _persoenlich() -> list[str]:
    """Persönliche Begriffe aus dem Export-Werkzeug (nur im privaten Repo vorhanden)."""
    pfad = Path(__file__).resolve().parent.parent / "tools" / "oeffentlich.py"
    if not pfad.exists():
        return []
    m = re.search(r"^PERSOENLICH = (\[.*?\])", pfad.read_text(encoding="utf-8"), re.M)
    return eval(m.group(1)) if m else []   # noqa: S307 – eigene Datei, nur eine Liste aus Zeichenketten


@pytest.fixture
def app(tmp_path):
    erststart.vorbereiten(tmp_path)
    return App(tmp_path, compile_pdf=False)


def test_frische_installation_ohne_fremde_spuren(app):
    seiten = {"Stellen": app.index, "Einstellungen": app.einstellungen, "Firmen": app.firmen,
              "Bewerbungen": app.bewerbungen, "Eigene Stelle": app.eigene, "Profil": app.profil,
              "Unterlagen": app.unterlagen, "Einrichten": app.einrichten, "Lücken": app.luecken,
              "Rückblick": app.rueckblick, "KI-Anleitung": app.ki_anleitung, "Suchprofil": app.suchprofil,
              "Bericht": app.bericht, "Anleitung": lambda: app.page("Anleitung", gh.render(), "hilfe", gh.CSS)}
    begriffe = FREMD + [w.lower() for w in _persoenlich()]
    funde = []
    for name, seite in seiten.items():
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", seite().decode(), flags=re.S)
        text = ERLAUBT.sub("", html.unescape(text)).lower()
        funde += [f"{name}: „{w}“ … {text[max(0, i - 50):i + 40]!r}"
                  for w in begriffe for i in [text.find(w)] if i >= 0]
    assert not funde, "Spuren der eigenen Einrichtung auf einer frischen Installation:\n" + "\n".join(funde)
