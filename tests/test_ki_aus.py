"""Ohne eingerichtete KI sind KI-Knöpfe ausgegraut (Klick erklärt, wo man sie einrichtet); Schlüssel speichern und
Update laden bleiben bedienbar. Dazu: Sprungziele und zwischengespeicherte config.yaml."""
import time

from jobmonitor import config, ki
from jobmonitor import gui_layout as layout
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


def test_ki_aus_graut_nur_ki_knoepfe_aus():
    html = ('<button class="small" data-ki="KI liest …">Lesen</button>'
            '<button data-ki-immer data-ki="Schlüssel …">Sicher speichern</button>'
            '<button class="ghost">Speichern</button>')
    neu = layout.ki_aus(html)
    assert '<button class="small" data-ki-aus aria-disabled="true" title="Braucht KI' in neu
    assert 'data-ki="KI liest' not in neu                      # kein Overlay „KI arbeitet“
    assert '<button data-ki-immer data-ki="Schlüssel …">' in neu
    assert '<button class="ghost">Speichern</button>' in neu


def test_seite_ohne_und_mit_ki(root, monkeypatch):  # noqa: F811
    app = App(root, compile_pdf=False)
    monkeypatch.setattr(ki, "schluessel", lambda *a, **k: None)
    ohne = app.page("Test", '<form><button data-ki="KI liest …">Lesen</button></form>').decode()
    assert "data-ki-aus" in ohne and "button[data-ki-aus]" in ohne
    monkeypatch.setattr(ki, "schluessel", lambda *a, **k: "sk-test")
    mit = app.page("Test", '<form><button data-ki="KI liest …">Lesen</button></form>').decode()
    assert '<button data-ki="KI liest …">' in mit


def test_sprungziel_skript_und_stil():
    assert "function sprung(" in layout.JS and ".sprungziel" in layout.CSS


def test_config_zwischengespeichert_und_frisch(tmp_path):
    pfad = tmp_path / "config.yaml"
    pfad.write_text("a: 1\n", encoding="utf-8")
    eins = config.load_config(pfad)
    eins["a"] = 99                                              # Kopie: wirkt nicht zurück
    assert config.load_config(pfad)["a"] == 1
    time.sleep(0.01)
    pfad.write_text("a: 22\n", encoding="utf-8")
    assert config.load_config(pfad)["a"] == 22
