"""Anki-Karten aus der Gesprächsvorbereitung, Mitteilung bei fehlgeschlagener Pipeline, KI-Nutzung der Pipeline,
Prompt-Caching, „Heute bewerben“ und Lernplan. Weder Anki noch die Claude-API werden echt aufgerufen."""
import json
from datetime import date
from types import SimpleNamespace

import pytest
import requests

from jobmonitor import anki, ki, llm, runner, tracking
from jobmonitor import benachrichtigung as bn
from jobmonitor import gui_heute as ghe
from jobmonitor import gui_wartung as gw
from jobmonitor.config import load_config
from jobmonitor.gui import App
from jobmonitor.state import State
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

# Gesprächstermin in zwei Tagen (relativ zu heute – ein festes Datum läge irgendwann in der Vergangenheit)
from datetime import date as _date, timedelta as _timedelta
TERMIN_TAG = _date.today() + _timedelta(days=2)
TERMIN = f"{TERMIN_TAG.isoformat()}T14:00"


VORBEREITUNG = """## Wahrscheinliche Fragen
- Wie würden Sie Benutzerkonten in Entra ID absichern? – Beispiel: MFA-Projekt in der Praxisphase
- **Was ist der Unterschied zwischen RBAC und ABAC?** Kurz erklären, dann Bezug zu Azure
## Deine Beispiele
- Situation – Aufgabe – Vorgehen – Ergebnis
## Ehrlich einordnen
- Kubernetes: kenne ich aus Kursen, lerne es gerade im Homelab
## Fragen an die Firma
- Wie sieht der erste Monat aus?
- Gibt es Möglichkeiten für die Bachelorarbeit?"""


class FakeAnki:
    def __init__(self, modelle=(), moeglich=None, fehler=None):
        self.aufrufe, self.modelle, self.moeglich, self.fehler = [], list(modelle), moeglich, fehler

    def __call__(self, url, json, timeout):
        assert url == "http://127.0.0.1:8765" and json["version"] == 6
        self.aufrufe.append((json["action"], json["params"]))
        result = {"modelNames": self.modelle, "canAddNotes": self.moeglich}.get(json["action"])
        return SimpleNamespace(json=lambda: {"result": result, "error": self.fehler})


def test_anki_karten_und_senden():
    karten = anki.karten(VORBEREITUNG, "Zurich")
    assert karten[0] == ("Wie würden Sie Benutzerkonten in Entra ID absichern?",
                         "Beispiel: MFA-Projekt in der Praxisphase")
    assert karten[1][0] == "Was ist der Unterschied zwischen RBAC und ABAC?"
    assert karten[2][0] == "Wie gehst du ehrlich mit der Lücke „Kubernetes“ um?"
    assert karten[3] == ("Welche Fragen stellst du Zurich?",
                         "• Wie sieht der erste Monat aus?<br>• Gibt es Möglichkeiten für die Bachelorarbeit?")
    post = FakeAnki(moeglich=[True, False, True, True])
    assert anki.senden("Zurich: IT", karten, post) == (3, 1, "Job-Monitor::Zurich  IT")
    aktionen = [a for a, _ in post.aufrufe]
    assert aktionen == ["modelNames", "createModel", "createDeck", "canAddNotes", "addNotes"]
    neu = post.aufrufe[-1][1]["notes"]
    assert len(neu) == 3 and neu[0]["modelName"] == "Job-Monitor Frage" and "job-monitor" in neu[0]["tags"]
    post = FakeAnki(modelle=["Job-Monitor Frage"], moeglich=[False] * 4)       # alles schon da
    assert anki.senden("Zurich", karten, post)[:2] == (0, 4)
    assert "createModel" not in [a for a, _ in post.aufrufe] and "addNotes" not in [a for a, _ in post.aufrufe]
    with pytest.raises(anki.AnkiError, match="AnkiConnect: kaputt"):
        anki.rufen("version", FakeAnki(fehler="kaputt"))

    def weg(*a, **k):
        raise requests.ConnectionError()
    with pytest.raises(anki.AnkiError, match="nicht erreichbar"):
        anki.rufen("version", weg)


def test_anki_in_der_app(root, monkeypatch):  # noqa: F811
    tracking.save(root / "applications.csv", [{"firma": "Zurich", "typ": "Stelle", "status": "Antwort",
                                                "datum": "2026-10-20", "link": "https://x/1", "notizen": "Werkstudent",
                                                "termin": TERMIN}])
    app = App(root, compile_pdf=False)
    assert "noch keine KI-Vorbereitung" in app.anki({"link": "https://x/1"}).decode()
    (root / ki.DATEI).write_text(json.dumps({"vorbereitung": {"https://x/1": VORBEREITUNG}}), encoding="utf-8")
    assert "Als Anki-Karten" in app.bewerbungen().decode()
    gesendet = []
    monkeypatch.setattr(anki, "senden", lambda firma, k: gesendet.append((firma, len(k))) or (4, 0, "Job-Monitor::Zurich"))
    assert "4 Karte(n) im Anki-Stapel „Job-Monitor::Zurich“ angelegt" in app.anki({"link": "https://x/1"}).decode()
    assert gesendet == [("Zurich", 4)]


LAEUFE_FEHLER = [{"status": "completed", "conclusion": "failure", "createdAt": "2026-11-03T05:20:00Z",
                  "url": "https://github.com/x/runs/2"},
                 {"status": "completed", "conclusion": "success", "createdAt": "2026-11-02T05:20:00Z",
                  "url": "https://github.com/x/runs/1"}]


def test_pipeline_meldung():
    cfg = load_config()
    titel, text, stand = bn.pipeline_meldung(LAEUFE_FEHLER, {}, "2026-11-03", cfg)
    assert titel == "Job-Monitor: Lauf fehlgeschlagen" and "03.11." in text and stand == {"fehler": LAEUFE_FEHLER[0]["url"]}
    assert bn.pipeline_meldung(LAEUFE_FEHLER, stand, "2026-11-03", cfg) is None              # nur einmal je Lauf
    ok = LAEUFE_FEHLER[1:]
    assert bn.pipeline_meldung(ok, {}, "2026-11-03", cfg) is None
    titel, text, stand = bn.pipeline_meldung(ok, {}, "2026-11-06", cfg)                        # 4 Tage nichts
    assert "seit 4 Tagen nicht gelaufen" in text and stand == {"stillstand": "2026-11-06"}
    assert bn.pipeline_meldung(ok, stand, "2026-11-07", cfg) is None                          # höchstens alle 3 Tage
    cfg["run"]["modus"] = "ruhe"
    assert bn.pipeline_meldung(ok, {}, "2026-11-06", cfg) is None                             # Ruhemodus: wöchentlich ok
    cfg["run"]["modus"] = "aus"
    assert bn.pipeline_meldung(LAEUFE_FEHLER, {}, "2026-11-03", cfg) is None


def test_pruefen_meldet_fehlgeschlagenen_lauf(tmp_path):
    from tests.test_benachrichtigung import Run, make_db
    quelle = tmp_path / "q.sqlite"
    make_db(quelle, [])

    def holen(root, ziel):
        ziel.write_bytes(quelle.read_bytes())
        (ziel.parent / "antworten.json").write_text("[]")
        return True
    run = Run()
    ergebnis = bn.pruefen(tmp_path, "2026-11-03", run=run, db_holen=holen, cfg=load_config(),
                          laeufe=lambda r: (LAEUFE_FEHLER, ""))
    assert ergebnis.startswith("1 Mitteilung(en) gesendet: Job-Monitor: Lauf fehlgeschlagen")
    assert any("Lauf fehlgeschlagen" in str(teil) for teil in run.calls[0])
    assert bn.pruefen(tmp_path, "2026-11-03", run=run, db_holen=holen, cfg=load_config(),
                      laeufe=lambda r: (LAEUFE_FEHLER, "")) == "Keine neuen Stellen und keine Antworten."


def test_ki_nutzung_der_pipeline(tmp_path, monkeypatch):
    state = State(tmp_path / "s.sqlite")
    monkeypatch.setattr(llm, "NUTZUNG", {"aufrufe": 3, "eingabe": 600, "ausgabe": 300, "cache_lesen": 3000,
                                         "cache_schreiben": 1500})
    runner.ki_nutzung_merken(state, date(2026, 11, 3))
    runner.ki_nutzung_merken(state, date(2026, 11, 4))
    daten = json.loads(state.get_meta("ki_nutzung"))
    assert daten["2026-11"]["aufrufe"] == 6 and daten["letzter_lauf"]["datum"] == "2026-11-04"
    s = ki.settings(load_config())
    zeile = gw.pipeline_ki(daten, "2026-11", s)
    assert "6 Aufrufe · 10.200 Eingabe-Tokens (davon 6.000 günstig aus dem Cache) · 600 Ausgabe-Tokens" in zeile
    assert 'class="muted"' in zeile
    assert "Achtung" in gw.pipeline_ki(daten, "2026-11", {**s, "pipeline_warnung_lauf": 1000})
    assert "noch keine KI-Aufrufe" in gw.pipeline_ki({}, "2026-11", s)


def test_prompt_caching(monkeypatch):
    aufrufe = []

    class Messages:
        def create(self, **kw):
            aufrufe.append(kw)
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="ok")],
                                   usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=900,
                                                         cache_creation_input_tokens=0))
    monkeypatch.setattr(llm, "_client", lambda key: SimpleNamespace(beta=SimpleNamespace(messages=Messages())))
    monkeypatch.setattr(llm, "NUTZUNG", {k: 0 for k in llm.NUTZUNG})
    usage = []
    assert llm._ask("claude-haiku-5-5", "Anzeige", system="Begriffe", usage=usage) == "ok"
    assert aufrufe[0]["system"] == [{"type": "text", "text": "Begriffe", "cache_control": {"type": "ephemeral"}}]
    assert usage == [(1000, 20)] and llm.NUTZUNG["cache_lesen"] == 900 and llm.NUTZUNG["aufrufe"] == 1
    llm._ask("claude-haiku-5-5", "ohne System")
    assert "system" not in aufrufe[1]


def test_heute_bewerben():
    heute = date(2026, 11, 3)
    jobs = [{"id": "a", "url": "u/a", "title": "A", "company": "X", "fit": 70, "first_seen": "2026-10-01"},
            {"id": "b", "url": "u/b", "title": "B", "company": "X", "fit": 60, "first_seen": "2026-11-02",
             "frist": "2026-11-06"},
            {"id": "c", "url": "u/c", "title": "C", "company": "X", "fit": 90, "first_seen": "2026-10-01"},
            {"id": "d", "url": "u/d", "title": "D", "company": "X", "fit": 95, "first_seen": "2026-10-01"},
            {"id": "e", "url": "u/e", "title": "E", "company": "X", "fit": 85, "frist": "2026-11-01"},
            {"id": "f", "url": "u/f", "title": "F", "company": "X", "fit": 40, "traum": True},
            {"id": "g", "url": "u/g", "title": "G", "company": "X", "fit": None}]
    status = {"u/c": "beworben", "u/a": "Entwurf"}
    wahl = ghe.auswahl(jobs, status, {"u/d": "2026-11-01"}, heute)
    assert [d["id"] for _, d, _ in wahl] == ["b", "a"]          # c beworben, d offline, e Frist vorbei, f/g zu wenig Fit
    assert wahl[0][0] == 60 + 15 + 10 and "Frist in 3 Tagen" in wahl[0][2]
    assert "Entwurf liegt schon bereit" in wahl[1][2]
    html = ghe.render(wahl)
    assert "Heute bewerben" in html and 'href="/bewerbung?job=b"' in html and ghe.render([]) == ""


def test_lernplan(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    prompts = []

    def ask(model, prompt, **kw):
        prompts.append(prompt)
        kw["usage"].append((10, 10))
        return "## Reihenfolge\n- Woche 1–4: AZ-104 vorbereiten\n## Hinweise\n- Preise prüfen"
    zeilen = [{"term": "Kubernetes", "gefordert": 5, "optional": 1, "stand": None, "gewinn": {"Grundkenntnisse": 4.0}},
              {"term": "Azure", "gefordert": 9, "optional": 0, "stand": 0.85, "gewinn": {}}]
    text = ki.lernplan(root, load_config(root / "config.yaml"), zeilen, {"profil": "x"}, {"Kubernetes": [{"name": "KCNA"}]},
                       date(2026, 11, 3), ask)
    assert "AZ-104" in text and "Kubernetes: in 5 Anzeigen gefordert" in prompts[0] and "KCNA" in prompts[0]
    assert "Azure:" not in prompts[0]                            # ohne Fit-Gewinn nicht im Plan
    assert ki.gespeicherter_lernplan(root)["datum"] == "2026-11-03"
    with pytest.raises(ki.KiError, match="Keine Lücken"):
        ki.lernplan(root, load_config(root / "config.yaml"), zeilen[1:], {}, {}, ask=ask)
    html = App(root, compile_pdf=False).luecken().decode()
    assert "<h2>Lernplan</h2>" in html and "Woche 1–4: AZ-104 vorbereiten" in html and "Lernplan neu erstellen" in html
