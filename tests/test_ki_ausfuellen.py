"""KI-Zuschnitt des Lebenslaufs, „Mit KI ausfüllen“ (Suchprofil, Nachfrage, Profiltext), Nachholen fehlender
KI-Bewertungen in der Pipeline und die Ladeanzeige. Die Claude-API wird nie aufgerufen (llm._ask gefälscht)."""
import json
from collections import Counter
from datetime import date, timedelta

import pytest

from jobmonitor import bewerbung as bw
from jobmonitor import cv_build, ki, llm, nachbewertung, runner, tracking
from jobmonitor.config import load_config
from jobmonitor.cv_data import load_cv_master
from jobmonitor.gui import App
from jobmonitor.gui_layout import JS
from jobmonitor.state import State
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)

ZUSCHNITT = {"profil": "Cyber-Security-Student mit Praxis in Entra ID und PowerShell sowie Azure-Projekten. "
                       "Ziel: Werkstudent in der Cloud-Administration.",
             "aufgaben": {"0": [1, 0]}, "projekte": [1, 9, 0, 1]}


class Ask:
    def __init__(self, *antworten):
        self.antworten, self.prompts = list(antworten), []

    def __call__(self, model, prompt, **kw):
        self.prompts.append(prompt)
        kw["usage"].append((100, 50))
        return self.antworten.pop(0) if self.antworten else None


@pytest.fixture
def mit_ki(monkeypatch):
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")


def test_zuschnitt_nur_auswahl_und_reihenfolge(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    cv, _ = load_cv_master(root)
    neu, hinweise = cv_build.ki_anwenden(cv, cv, ZUSCHNITT, cfg["fit"]["begriffe"], 2)
    assert neu["profil"] == ZUSCHNITT["profil"] and "bitte gegenlesen" in hinweise[0]
    assert neu["stationen"][0]["aufgaben"] == ["Automatisierung mit PowerShell", "Benutzer- und Rechteverwaltung "
                                                                                  "in Entra ID"]
    assert [p["name"] for p in neu["projekte"]] == ["Azure Landing Zone mit Terraform", "Homelab mit Proxmox"]
    # erfundene Kenntnis im Profiltext: verworfen, alter Text bleibt
    erfunden = {**ZUSCHNITT, "profil": "Student mit langjähriger Erfahrung in Kubernetes und AWS-Architekturen."}
    neu, hinweise = cv_build.ki_anwenden(cv, cv, erfunden, cfg["fit"]["begriffe"], 2)
    assert neu["profil"] == cv["profil"] and "verworfen" in hinweise[0]
    # zu wenige Aufgaben übrig: Reihenfolge bleibt
    neu, _ = cv_build.ki_anwenden(cv, cv, {"aufgaben": {"0": [1]}}, cfg["fit"]["begriffe"], 2)
    assert neu["stationen"][0]["aufgaben"] == cv["stationen"][0]["aufgaben"]


def test_lebenslauf_mit_ki_bauen(root, mit_ki, monkeypatch):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    ask = Ask(json.dumps(ZUSCHNITT))
    monkeypatch.setattr(llm, "_ask", ask)
    monkeypatch.setattr(ki, "anzeige", lambda r, link, f, cache=None: "Wir suchen Unterstützung in Entra ID.")
    app = App(root, compile_pdf=False)
    zuschnitt, info = app.ki_lebenslauf(cfg, STELLE)
    assert zuschnitt == ZUSCHNITT and info == ""
    assert app.ki_lebenslauf(cfg, STELLE)[0] == ZUSCHNITT and len(ask.prompts) == 1        # aus dem Speicher
    prompt = ask.prompts[0]
    assert "Aufgabe 1: Automatisierung mit PowerShell" in prompt and "Projekt 1: Azure Landing Zone" in prompt
    assert "Max Muster" not in prompt and "Projekt 3:" not in prompt     # Kubernetes-Cluster (im_cv: false) nicht wählbar
    hinweise: list = []
    tex = cv_build.build(root, cfg, stelle=STELLE, compile_pdf=False, hinweise=hinweise, ki_zuschnitt=zuschnitt)
    text = tex.read_text(encoding="utf-8")
    assert "Praxis in Entra ID und PowerShell" in text and "Website für Sportverein" not in text
    assert any("gegenlesen" in h.text for h in hinweise)
    # Bewerbungsseite: Knöpfe zeigen beim Bauen die KI-Ladeanzeige
    folder = bw.open_workspace(root, cfg, STELLE)
    assert 'value="lebenslauf" class="ghost" data-ki=' in app.bewerbung(folder.name).decode()
    # Ohne Schlüssel oder ausgeschaltet: kein KI-Zuschnitt
    cfg["ki"]["lebenslauf"] = False
    assert app.ki_lebenslauf(cfg, STELLE) == (None, "")


def test_nachholen_im_lauf(tmp_path, monkeypatch):
    cfg = load_config()
    state = State(tmp_path / "s.sqlite")
    aufrufe = []
    monkeypatch.setattr(nachbewertung, "nachbewerten",
                        lambda st, cv, c, f, ask=None, limit=None, stapel=False: aufrufe.append(limit) or
                        {"geprueft": 1, "aktualisiert": 1, "ohne_text": 0, "vorschlaege": Counter({"Jira": 1})})
    runner.ki_nachholen(state, {"profil": "x"}, cfg, None, {"abc"})          # ohne Anmeldung: nichts
    assert aufrufe == [] and nachbewertung.erledigt(state) == set()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    runner.ki_nachholen(state, {"profil": "x"}, cfg, None, {"abc", "def"})
    assert aufrufe == [10] and nachbewertung.erledigt(state) == {"abc", "def"}   # gelesene vorher vermerkt
    assert json.loads(state.get_meta("fit_vorschlaege")) == {"Jira": 1}
    cfg["fit"]["begriffe"]["Deutsch"] = []                                    # Begriffe geändert → neu bewerten
    runner.ki_nachholen(state, {"profil": "x"}, cfg, None, set())
    assert nachbewertung.erledigt(state) == set()
    runner.ki_nachholen(state, None, cfg, None, set())                         # ohne Lebenslauf: nichts
    assert aufrufe == [10, 10]


def test_suchprofil_mit_ki(root, mit_ki, monkeypatch):  # noqa: F811
    vorschlag = {"name": "Data", "art": "studium", "zielrolle": "Werkstudent Data Engineering",
                 "absicht": "eine Werkstudententätigkeit im Data Engineering", "ausblick": "",
                 "rollen": {"werkstudent": 30, "praktikum": 18}, "such_bundesagentur": [f"Werkstudent Data {i}"
                                                                                       for i in range(20)],
                 "such_stellenwerk": ["Data Engineering"], "fachgebiet": "eigen",
                 "fach": {"data engineering": 12, "python": 8, "sql": 6}, "fit_begriffe": {"SQL": ["postgres"]}}
    ask = Ask(json.dumps(vorschlag))
    monkeypatch.setattr(llm, "_ask", ask)
    app = App(root, compile_pdf=False)
    assert "Felder mit KI ausfüllen" in app.suchprofil().decode()
    assert "Bitte kurz beschreiben" in app.suchprofil_post({"aktion": "ki", "name": "", "wunsch": " "}).decode()
    html = app.suchprofil_post({"aktion": "ki", "name": "", "wunsch": "Werkstudent Data Engineering in Köln"}).decode()
    assert "Vorschlag der KI eingesetzt" in html and "Werkstudent Data 14" in html and "Werkstudent Data 15" not in html
    assert "data engineering: 12" in html and 'value="eigen" checked' in html and "SQL: postgres" in html
    assert "Werkstudent Data Engineering in Köln" in ask.prompts[0]
    assert "data" not in load_config(root / "config.yaml")["profile"]          # noch nicht gespeichert


def test_nachfrage_mit_ki(root, mit_ki, monkeypatch):  # noqa: F811
    vor = (date.today() - timedelta(days=30)).isoformat()
    tracking.save(root / "applications.csv", [{"firma": "Beispiel AG", "typ": "Stelle", "status": "beworben",
                                                "datum": vor, "link": "https://x/1", "notizen": "Werkstudent Cloud"}])
    ask = Ask(json.dumps({"betreff": "Nachfrage zu meiner Bewerbung", "text": "Guten Tag, ... Viele Grüße\n[Name]"}))
    monkeypatch.setattr(llm, "_ask", ask)
    app = App(root, compile_pdf=False)
    assert "Mit KI formulieren" in app.bewerbungen().decode()
    html = app.nachfassen_ki({"link": "https://x/1"}).decode()
    assert "mit KI formuliert" in html and "Entwurf für die Nachfrage (von der KI)" in html
    assert "Viele Grüße\nMax Muster" in html and "Max Muster" not in ask.prompts[0]
    assert "keine Nachfrage fällig" in app.nachfassen_ki({"link": "https://y"}).decode()


def test_profiltext_mit_ki(root, mit_ki, monkeypatch):  # noqa: F811
    from jobmonitor import gui_master as gm
    data = gm.load(root)
    monkeypatch.setattr(llm, "_ask", Ask("„Student mit Praxis in Entra ID und Azure. Ziel: Cloud-Engineering.“",
                                         "Experte für Kubernetes und AWS."))
    app = App(root, compile_pdf=False)
    assert "Profiltext mit KI vorschlagen" in app.master().decode()
    html = app.master_save({"aktion": "ki_profil", "data": json.dumps(data)}).decode()
    assert "KI-Vorschlag im Feld „Profil“ eingesetzt" in html and "Student mit Praxis in Entra ID und Azure." in html
    assert gm.load(root)["profil"] == data["profil"]                           # nicht gespeichert
    html = app.master_save({"aktion": "ki_profil", "data": json.dumps(data)}).decode()
    assert "nicht belegt – verworfen" in html


def test_ladeanzeige():
    assert "dataset.ki" in JS and "Sekunden" in JS and "requestAnimationFrame(() => requestAnimationFrame" in JS
