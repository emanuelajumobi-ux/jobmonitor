"""Übungsgespräch: Fragen, Antworten mit Rückmeldung, Zusammenfassung nach FRAGEN Fragen, neu beginnen."""
import json

from jobmonitor import bewerbung as bw
from jobmonitor import ki, uebung
from jobmonitor.config import load_config
from jobmonitor.gui import App
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)


class Gespraech:
    def __init__(self):
        self.n, self.prompts = 0, []

    def __call__(self, model, prompt, **kw):
        self.prompts.append(prompt)
        kw["usage"].append((100, 50))
        self.n += 1
        if "Beginne mit" in prompt:
            return "Guten Tag! Warum möchten Sie zu Beispiel AG?"
        if '"abschluss"' in prompt:
            return json.dumps({"feedback": "Gut.", "abschluss": "## Stärken\n- klar"})
        return json.dumps({"feedback": f"Rückmeldung {self.n}", "naechste_frage": f"Frage {self.n + 1}?"})


def test_uebungsgespraech(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    ask = Gespraech()
    monkeypatch.setattr(ki.llm, "_ask", ask)
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    (folder / "anzeige.txt").write_text("Anzeigentext mit Azure", encoding="utf-8")
    app = App(root, compile_pdf=False)
    link = STELLE["url"]
    html = app.uebung_seite(link).decode()
    assert "Gespräch beginnen" in html and "Übungsgespräch" in html
    html = app.uebung_post({"link": link, "aktion": "start"}).decode()
    assert "Warum möchten Sie zu Beispiel AG?" in html and "Antwort senden" in html
    assert "Bitte eine Antwort" in app.uebung_post({"link": link, "aktion": "antwort", "antwort": " "}).decode()
    for i in range(uebung.FRAGEN):
        html = app.uebung_post({"link": link, "aktion": "antwort", "antwort": f"Meine Antwort {i}"}).decode()
    assert "Zusammenfassung" in html and "Stärken" in html and "Antwort senden" not in html
    assert "Meine Antwort 4" in ask.prompts[-1] and "Anzeigentext mit Azure" in ask.prompts[0]
    assert len(uebung.laden(root, link)["verlauf"]) == uebung.FRAGEN
    app.uebung_post({"link": link, "aktion": "neu"})
    assert uebung.laden(root, link) is None
    assert "Bewerbung nicht gefunden" in app.uebung_seite("https://example.com/unbekannt").decode()
