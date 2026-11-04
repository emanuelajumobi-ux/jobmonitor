"""KI-Hilfen (ki.py): Anschreiben-Entwurf und Gesprächsvorbereitung auf Knopfdruck, Schlüssel, Limit, Datenschutz.
Die Claude-API wird nie aufgerufen; llm._ask ist gefälscht."""
import json
import re
import subprocess
from datetime import date

import pytest
import responses

from jobmonitor import bewerbung as bw
from jobmonitor import ki, suchprofil, tracking
from jobmonitor.config import load_config
from jobmonitor.cv_data import load_cv_master
from jobmonitor.gui import App
from jobmonitor.http import Fetcher
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)

ECHT = (ki.schluessel, ki.herkunft)       # vor dem Abschirmen in conftest.ohne_echte_ki gemerkt

ENTWURF = """Sehr geehrte Damen und Herren,

als Student der Cyber Security bringe ich Erfahrung mit Azure mit.

Die Stelle passt zu meinem Fokus. Verfügbar bin ich [Zeitraum].

Mit freundlichen Grüßen
Max"""


class FakeAsk:
    def __init__(self, antwort=ENTWURF):
        self.prompts, self.kwargs, self.antwort = [], [], antwort

    def __call__(self, model, prompt, **kw):
        self.prompts.append(prompt)
        self.kwargs.append(kw)
        kw["usage"].append((1200, 300))
        return self.antwort


@pytest.fixture
def mit_schluessel(monkeypatch):
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    monkeypatch.setattr(ki, "herkunft", lambda run=None: "Schlüsselbund")


def test_anschreiben_nur_cv_und_anzeige(root, mit_schluessel):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    cv, _ = load_cv_master(root)
    ask = FakeAsk()
    ziel = suchprofil.get(cfg, None)
    text = ki.anschreiben(root, cfg, STELLE, "Wir suchen Unterstützung für Azure und Terraform.", cv, ziel,
                          "ab März 2027 mit 20 Stunden pro Woche", ask=ask)
    assert not text.startswith("Sehr geehrte") and "Grüßen" not in text and not text.endswith("Max")
    assert "Verfügbar bin ich ab März 2027 mit 20 Stunden pro Woche." in text
    prompt = ask.prompts[0]
    assert "Wir suchen Unterstützung für Azure" in prompt and "Beispiel AG" in prompt and "[Zeitraum]" in prompt
    for privat in ("Max Muster", "Musterweg", "max@example.com", "0000000", "März 2027"):
        assert privat not in prompt                                    # nichts aus profile.yaml
    assert ask.kwargs[0]["api_key"] == "sk-ant-test"
    assert ki.nutzung(root) == {"aufrufe": 1, "eingabe": 1200, "ausgabe": 300}


def test_limit_und_fehlender_schluessel(root, monkeypatch):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    cfg["ki"]["max_aufrufe_monat"] = 1
    monkeypatch.setattr(ki, "schluessel", lambda run=None: None)
    with pytest.raises(ki.KiError, match="Kein API-Schlüssel"):
        ki.fragen(root, cfg, "x", ask=FakeAsk())
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    ki.fragen(root, cfg, "x", ask=FakeAsk("ok"))
    with pytest.raises(ki.KiError, match="Monatslimit von 1"):
        ki.fragen(root, cfg, "x", ask=FakeAsk())
    assert ki.nutzung(root, date(2030, 1, 1))["aufrufe"] == 0       # neuer Monat, neues Limit
    with pytest.raises(ki.KiError, match="nicht geantwortet"):
        ki.fragen(root, cfg, "x", ask=FakeAsk(None), heute=date(2030, 1, 1))


def test_schluessel_im_schluesselbund(monkeypatch):
    aufrufe = []

    def run(cmd, **kw):
        aufrufe.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "sk-ant-aus-dem-bund\n", "")
    monkeypatch.setattr(ki, "schluessel", ECHT[0])
    monkeypatch.setattr(ki, "herkunft", ECHT[1])
    monkeypatch.setattr(ki.sys, "platform", "darwin")
    assert ki.schluessel(run) == "sk-ant-aus-dem-bund" and aufrufe[0][:2] == ["security", "find-generic-password"]
    with pytest.raises(ki.KiError, match="sk-ant-"):
        ki.schluessel_speichern("hallo", run)
    ki.schluessel_speichern(" sk-ant-api03-" + "a" * 30 + " ", run)
    assert aufrufe[-1][:3] == ["security", "add-generic-password", "-U"] and aufrufe[-1][-1].endswith("a" * 30)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    assert ki.schluessel(run) == "sk-ant-env" and ki.herkunft(run) == ".env"


@responses.activate
def test_anzeige_lesen_und_merken(tmp_path):
    posting = {"@context": "https://schema.org", "@type": "JobPosting", "title": "Werkstudent Cloud",
               "description": "<p>Du betreust Azure und Terraform.</p>" + "<p>Weitere Aufgaben im Team.</p>" * 10,
               "hiringOrganization": {"name": "Beispiel"}}
    responses.get("https://firma.de/robots.txt", body="")
    responses.get("https://firma.de/job/1", body=f'<script type="application/ld+json">{json.dumps(posting)}</script>')
    f = Fetcher("test", 0, 5, 0)
    assert "Azure und Terraform" in ki.anzeige(tmp_path, "https://firma.de/job/1", f)
    assert "Azure und Terraform" in ki.anzeige(tmp_path, "https://firma.de/job/1", f)
    assert len([c for c in responses.calls if "job/1" in c.request.url]) == 1      # zweites Mal aus dem Speicher
    assert ki.anzeige(tmp_path, "https://www.linkedin.com/jobs/view/1", f) == ""   # nie LinkedIn & Co.
    cache = tmp_path / "anzeige.txt"
    cache.write_text("aus dem Ordner", encoding="utf-8")
    assert ki.anzeige(tmp_path, "https://firma.de/job/2", f, cache) == "aus dem Ordner"


def test_als_html():
    html = ki.als_html("## Fragen\n- Warum **Cloud**?\n1. Zweitens\nText <b>", lambda s: s.replace("<", "&lt;"))
    assert html == "<h3>Fragen</h3><ul><li>Warum Cloud?</li><li>Zweitens</li></ul><p>Text &lt;b></p>"


def test_bewerbung_mit_ki(root, mit_schluessel, monkeypatch):  # noqa: F811
    ask = FakeAsk()
    monkeypatch.setattr("jobmonitor.llm._ask", ask)
    monkeypatch.setattr(ki, "anzeige", lambda root, link, fetcher, cache=None: "Azure-Team sucht Unterstützung")
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    app = App(root, compile_pdf=False)
    assert "Entwurf mit KI</button>" in app.bewerbung(folder.name).decode()
    html = app.bewerbung_post(folder.name, {"aktion": "ki", "anrede": "Hallo Team,", "empfaenger": ""}).decode()
    assert "KI-Entwurf erstellt (aus Anzeigentext und Master-CV)" in html and "Prüfung des Anschreibens" in html
    data = bw.letter(folder)
    assert data["anrede"] == "Hallo Team," and "ab März 2027 mit 20 Stunden pro Woche" in data["text"]
    assert (folder / "anschreiben.json.bak").is_file()                  # vorheriger Text gesichert
    monkeypatch.setattr(ki, "schluessel", lambda run=None: None)
    html = app.bewerbung(folder.name).decode()
    # ohne KI: Knopf sichtbar, aber ausgegraut (Klick erklärt die Einrichtung unter Einstellungen → KI)
    assert re.search(r'<button[^>]*data-ki-aus[^>]*>Entwurf mit KI</button>', html) and "/einstellungen#ki" in html


def test_gespraech_vorbereiten(root, mit_schluessel, monkeypatch):  # noqa: F811
    ask = FakeAsk("## Wahrscheinliche Fragen\n- Wie würden Sie Azure absichern?\n## Fragen an die Firma\n- Team?")
    monkeypatch.setattr("jobmonitor.llm._ask", ask)
    monkeypatch.setattr(ki, "anzeige", lambda root, link, fetcher, cache=None: "")
    tracking.save(root / "applications.csv", [{"firma": "Beispiel AG", "typ": "Stelle", "status": "Antwort",
                                                "datum": "2026-10-20", "link": "https://x/1",
                                                "notizen": "Werkstudent Cloud", "termin": "2026-11-12T14:00"}])
    app = App(root, compile_pdf=False)
    html = app.bewerbungen().decode()
    assert "Mit KI vorbereiten" in html
    html = app.vorbereitung({"link": "https://x/1"}).decode()
    assert "Vorbereitung für Beispiel AG erstellt" in html and "Die Anzeige selbst war nicht lesbar" in html
    assert "<details open>" in html and "<h3>Wahrscheinliche Fragen</h3>" in html and "Neu mit KI erstellen" in html
    assert "Werkstudent Cloud bei Beispiel AG" in ask.prompts[0] and "Max Muster" not in ask.prompts[0]
    assert "Wie würden Sie Azure absichern?" in app.bewerbungen().decode()      # bleibt gespeichert
    assert "Bewerbung nicht gefunden" in app.vorbereitung({"link": "https://y"}).decode()


def test_einstellungen_ki(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr("jobmonitor.gui_wartung.pipeline_laeufe", lambda r: ([], ""))
    monkeypatch.setattr(ki, "herkunft", lambda run=None: "")
    gespeichert = []
    monkeypatch.setattr(ki, "schluessel_speichern", lambda wert, run=None: gespeichert.append(wert))
    app = App(root, compile_pdf=False)
    html = app.einstellungen().decode()
    assert 'id="ki"' in html and 'type="password" name="schluessel"' in html and "0 von höchstens" in html
    html = app.einstellungen_post({"aktion": "ki_schluessel", "schluessel": "sk-ant-x"}).decode()
    assert "Schlüssel sicher gespeichert" in html and gespeichert == ["sk-ant-x"]
    assert "sk-ant-x" not in html                                        # Schlüssel wird nie angezeigt
    monkeypatch.setattr(ki, "herkunft", lambda run=None: "Schlüsselbund")
    assert "Schlüssel entfernen" in app.einstellungen().decode()
