"""Designs für Lebenslauf und Anschreiben: Auswahl je Profil und Bewerbung, Vorlagen, Hinweis für Bewerbungsportale."""
import json

import pytest

from jobmonitor import bewerbung as bw
from jobmonitor import cv_build, designs, pdf_html
from jobmonitor.config import CODE, load_config
from jobmonitor.gui import App
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)


def test_auswahl(tmp_path):
    cfg = load_config()
    cfg["profile"]["pflege"] = {"name": "Pflege", "stufe": "ausbildung", "rollen": {"azubi": 30}}
    cfg["profile"]["design_x"] = {"name": "X", "stufe": "ausbildung", "design": "kreativ", "rollen": {"a": 1}}
    assert designs.fuer_profil(cfg, "pflege") == "kompakt"                    # nach Karrierestufe
    assert designs.fuer_profil(cfg, "design_x") == "kreativ"                  # ausdrücklich gewählt
    assert designs.fuer_profil(cfg, "werkstudent") == "klassisch"
    assert designs.fuer_bewerbung(cfg, tmp_path, {"profil": "pflege"}) == "kompakt"
    designs.waehlen(tmp_path, "modern")
    assert designs.fuer_bewerbung(cfg, tmp_path, {"profil": "pflege"}) == "modern"   # je Bewerbung gewinnt
    with pytest.raises(ValueError):
        designs.waehlen(tmp_path, "gibtsnicht")
    assert designs.akzent({"cv": {"akzentfarbe": "#aa3300"}}) == "#aa3300"
    assert designs.akzent({"cv": {"akzentfarbe": "red; }"}}) == "#1F4E79"


def test_portal_hinweis():
    assert "Bewerbungssystem" in designs.ats_warnung("modern", "https://career5.successfactors.eu/x")
    assert designs.ats_warnung("kompakt", "https://career5.successfactors.eu/x") == ""
    assert designs.ats_warnung("kreativ", "https://www.kleine-agentur.de/jobs") == ""


@pytest.mark.parametrize("key", [k for k in designs.DESIGNS if k != "klassisch"])
def test_vorlagen_rendern(root, key):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    html = cv_build.build(root, cfg, compile_pdf=False, design=key).read_text(encoding="utf-8")
    assert "Max Muster" in html and "@page" in html and "Azure" in html
    vorlage = CODE / designs.DESIGNS[key]["anschreiben"]
    brief = pdf_html.environment(vorlage.parent).get_template(vorlage.name).render(
        profile=bw.load_profile(root), firma="Beispiel AG", empfaenger=["Personal"], ort_datum="Köln, 03.11.2026",
        betreff="Bewerbung als Werkstudent", anrede="Guten Tag,", absaetze=["Absatz <eins>"], anlagen=["Lebenslauf"],
        akzent="#123456")
    assert "Beispiel AG" in brief and "Absatz &lt;eins&gt;" in brief and "#123456" in brief


def test_in_der_app(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    app = App(root, compile_pdf=False)
    html = app.bewerbung(folder.name).decode()
    assert "<h2>Design</h2>" in html and 'value="klassisch" selected' in html
    html = app.bewerbung_post(folder.name, {"aktion": "design", "design": "kompakt"}).decode()
    assert "Design „Kompakt“ gewählt" in html and json.loads((folder / "design.json").read_text())["design"] == "kompakt"
    assert "Unbekanntes Design" in app.bewerbung_post(folder.name, {"aktion": "design", "design": "x"}).decode()
    assert "Designs für Lebenslauf und Anschreiben" in app.master().decode()
    assert "Max Muster" in app.design_vorschau("modern").decode() and app.design_vorschau("x") is None


def test_vorschau_mit_seitenrand():
    html = designs.mit_seitenrand('<html><head><style>@page { size: A4; margin: 15mm 18mm; }</style></head></html>')
    assert "@media screen" in html and "padding:15mm 18mm;" in html
    assert designs.mit_seitenrand("<html><head></head></html>") == "<html><head></head></html>"
