"""Stufe 1 „für alle Richtungen“: Ausschlüsse nach Stufe und Fachgebiet, Karrierestufen-Vorlagen, Wohnort mit
eigener Fahrzeit-Tabelle (KI), abschaltbares Traumprofil, leere Firmenliste. Die Claude-API wird nie aufgerufen."""
import json
from datetime import date

import pytest

from jobmonitor import gui_suchprofile as gsp
from jobmonitor import gui_layout as layout
from jobmonitor import ki, llm, scoring, suchprofil, wohnort
from jobmonitor.config import load_config
from jobmonitor.gui import App
from jobmonitor.gui_sync import SyncResult
from jobmonitor.http import Fetcher
from jobmonitor.location import location_points
from jobmonitor.models import Job
from jobmonitor.sources.companies import CompaniesSource
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

BWL = {"name": "BWL", "stufe": "werkstudent", "rollen": {"werkstudent": 30},
       "fach": {"controlling": 14, "marketing": 12, "finanzen": 10, "bwl": 8},
       "suchbegriffe": {"bundesagentur": ["Werkstudent Controlling"]}}


def job(title, desc="", ort="Köln"):
    return Job(title=title, company="Firma", location=ort, url="https://x.de/1", source="Test", description=desc)


def test_ausschluesse_nach_stufe_und_fach():
    f = load_config()["filter"]
    assert "marketing" in scoring.ausschluesse(f) and "senior" in scoring.ausschluesse(f)
    assert "marketing" not in scoring.ausschluesse(f, eigen=True) and "senior" in scoring.ausschluesse(f, eigen=True)
    assert "senior" not in scoring.ausschluesse(f, eigen=True, stufe="berufserfahren")


def test_bwl_und_berufserfahren_finden_ihre_stellen():
    cfg = load_config()
    cfg["profile"]["bwl"] = BWL
    bwl = suchprofil.get(cfg, "bwl")
    assert bwl.stufe == "werkstudent"
    stelle = job("Werkstudent Controlling und Marketing (m/w/d)", "Finanzen, Reporting")
    assert scoring.evaluate(job(stelle.title, stelle.description), cfg, bwl.rollen, fach=bwl.fach) is not None
    # dein IT-Profil schließt Marketing weiter aus
    ws = suchprofil.get(cfg, "werkstudent")
    assert scoring.evaluate(job("Werkstudent Marketing Cloud", "Azure"), cfg, ws.rollen) is None
    # berufserfahren: „Senior Controller“ zählt, bei Werkstudent nicht
    rollen = suchprofil.STUFEN["berufserfahren"]["rollen"]
    senior = job("Senior Controlling Specialist (m/w/d)", "Finanzen, Controlling")
    assert scoring.evaluate(job(senior.title, senior.description), cfg, rollen, fach=bwl.fach,
                            stufe="berufserfahren") is not None
    assert scoring.evaluate(job(senior.title, senior.description), cfg, rollen, fach=bwl.fach) is None


def test_stufen_vorlagen_im_formular(root):  # noqa: F811
    html = App(root, compile_pdf=False).suchprofil().decode()
    assert 'name="stufe"' in html and "Ausbildung / duales Studium" in html and "data-vorlagen=" in html
    cfg = load_config(root / "config.yaml")
    form = {"name": "Pflege", "enabled": "", "art": "ausbildung", "stufe": "ausbildung",
            "rollen": "\n".join(f"{k}: {v}" for k, v in suchprofil.STUFEN["ausbildung"]["rollen"].items()),
            "such_bundesagentur": "Ausbildung Pflegefachkraft", "such_stellenwerk": "", "fachgebiet": "eigen",
            "fach": "pflege: 14\npflegefachkraft: 14\ngesundheit: 8", "fit_begriffe": ""}
    gsp.speichern(root, *gsp.aus_formular(form, cfg))
    p = suchprofil.get(load_config(root / "config.yaml"), "pflege")
    assert p.stufe == "ausbildung" and p.angebotsart == 4 and p.rollen["azubi"] == 28


def test_fahrzeiten_fuer_andere_stadt():
    ort = {"max_fahrzeit_min": 60, "punkte_koeln": 15, "punkte_umkreis": 10, "punkte_grenze": 5, "punkte_remote": 12,
           "zentrum": "München", "fahrzeiten": {"münchen": 0, "freising": 25, "augsburg": 50, "ingolstadt": 70}}
    assert location_points("München", False, ort) == (15, "München")
    assert location_points("Freising", False, ort)[0] == 10 and location_points("Augsburg", False, ort)[0] == 5
    assert location_points("Ingolstadt", False, ort) is None and location_points("Köln", False, ort) is None
    assert location_points("Köln", False, {k: v for k, v in ort.items() if k not in ("zentrum", "fahrzeiten")}) \
        == (15, "Köln")                                                   # ohne Tabelle: Köln wie bisher


def test_wohnort_mit_ki(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    prompts = []

    def ask(model, prompt, **kw):
        prompts.append(prompt)
        kw["usage"].append((100, 50))
        return json.dumps({"orte": {"München": 0, "Freising": 25, "Augsburg": 45, "Rosenheim": 40, "Dachau": 20,
                                    "Mond": 900, "": 5}})
    monkeypatch.setattr(llm, "_ask", ask)
    monkeypatch.setattr("jobmonitor.gui.sync", lambda r: SyncResult(True, "Hochgeladen."))
    app = App(root, compile_pdf=False)
    assert "Fahrzeiten mit KI erstellen" in app.einstellungen().decode()
    html = app.einstellungen_post({"aktion": "wohnort", "stadt": "München"}).decode()
    assert "Wohnort ist jetzt München mit 5 Orten" in html and "Dachau 20 min" in html
    cfg = load_config(root / "config.yaml")
    assert cfg["ort"]["zentrum"] == "München" and cfg["ort"]["fahrzeiten"]["augsburg"] == 45
    assert "mond" not in cfg["ort"]["fahrzeiten"] and cfg["sources"]["bundesagentur"]["wo"] == "München"
    assert prompts[0].count("München") >= 2 and "Max Muster" not in prompts[0]
    assert "Bitte einen Ortsnamen" in app.einstellungen_post({"aktion": "wohnort", "stadt": "x; rm -rf /"}).decode()
    # zweimal speichern ersetzt die Tabelle statt sie zu verdoppeln
    text = wohnort.config_text((root / "config.yaml").read_text(encoding="utf-8"), "Köln", {"köln": 0, "bonn": 30})
    assert text.count("  fahrzeiten:") == 1 and text.count("  zentrum:") == 1


def test_traumprofil_abschaltbar(root):  # noqa: F811
    assert "Cloud Security" in layout.nav("stellen", {}, "t")
    assert "/?traum=1" not in layout.nav("stellen", {}, "t", traum_name=None)
    path = root / "config.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("traumprofil:\n  enabled: true",
                                                            "traumprofil:\n  enabled: false"), encoding="utf-8")
    html = App(root, compile_pdf=False).index().decode()
    assert "/?traum=1" not in html


def test_leere_firmenliste():
    f = Fetcher("job-monitor-test/0.1", min_delay=0, sleep=lambda s: None)
    result = CompaniesSource({"firmen": []}, {"max_detail_pages": 3}, f, date(2026, 11, 3)).fetch()
    assert result.jobs == [] and not result.errors


@pytest.mark.parametrize("stadt", ["", "a" * 41, "Köln<script>"])
def test_ungueltiger_ort(stadt):
    with pytest.raises(wohnort.WohnortError):
        wohnort.config_text("ort:\n  max_fahrzeit_min: 60\n", stadt, {})
