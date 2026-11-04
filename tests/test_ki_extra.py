"""KI-Helfer der Oberfläche: Lebenslauf verstehen und prüfen, Fit erklären, Portal-Fragen, Muster aus Absagen,
Hinweise je Stelle."""
import json

from jobmonitor import bewerbung as bw
from jobmonitor import fit, ki, ki_extra, portal
from jobmonitor.config import load_config
from jobmonitor.cv_data import load_cv_master
from jobmonitor.gui import App
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)
from tests.test_ki import FakeAsk


def _ki(monkeypatch, antwort):
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    monkeypatch.setattr(ki.llm, "_ask", FakeAsk(antwort))


def test_cv_verstehen_und_uebernehmen(root, monkeypatch):  # noqa: F811
    _ki(monkeypatch, json.dumps({"belegt": [
        {"begriff": "Informationssicherheit", "level": "gut", "beleg": "Studium Cyber Security"},
        {"begriff": "Azure", "level": "gut", "beleg": "steht schon da"},           # schon eingetragen → raus
        {"begriff": "Erfunden", "level": "gut", "beleg": "x"},                     # kein Fit-Begriff → raus
        {"begriff": "Linux", "level": "Experte", "beleg": "x"}]}))                 # ungültiges Level → raus
    app = App(root, compile_pdf=False)
    html = app.ki_aktion({"aktion": "cv_verstehen"}).decode()
    assert "1 Vorschläge" in html and 'name="begriff:Informationssicherheit"' in html and "begriff:Erfunden" not in html
    html = app.ki_aktion({"aktion": "cv_uebernehmen", "begriff:Informationssicherheit": "1",
                          "level:Informationssicherheit": "sehr gut"}).decode()
    assert "1 Kenntnis(se)" in html
    cv, _ = load_cv_master(root)
    assert any(e.get("name") == "Informationssicherheit" and e.get("level") == "sehr gut"
               for k in cv["kenntnisse"] for e in k.get("eintraege") or [])


def test_cv_check(root, monkeypatch):  # noqa: F811
    _ki(monkeypatch, json.dumps({"vorschlaege": [{"wo": "Station 1", "vorher": "Unterstützung im Support",
                                                  "vorschlag": "[Anzahl] Tickets pro Woche gelöst", "warum": "konkret"}]}))
    html = App(root, compile_pdf=False).ki_aktion({"aktion": "cv_check"}).decode()
    assert "1 Vorschläge" in html and "[Anzahl] Tickets pro Woche gelöst" in html


def test_fit_erklaeren_und_portal_frage(root, monkeypatch):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    (folder / "anzeige.txt").write_text("Anzeigentext", encoding="utf-8")
    app = App(root, compile_pdf=False)
    _ki(monkeypatch, "Der Fit ist gut, weil Azure passt. Betone dein Projekt.")
    html = app.bewerbung_post(folder.name, {"aktion": "fit_erklaeren"}).decode()
    assert "Fit erklärt" in html and "weil Azure passt" in html
    assert "Bitte die Frage" in app.bewerbung_post(folder.name, {"aktion": "portal_frage", "frage": " "}).decode()
    _ki(monkeypatch, "Weil ich dort Cloud-Betrieb lernen will. " * 30)
    html = app.bewerbung_post(folder.name, {"aktion": "portal_frage", "frage": "Warum wir?"}).decode()
    gespeichert = portal.gekuerzt(folder)["fragen"][0]
    assert gespeichert["frage"] == "Warum wir?" and len(gespeichert["antwort"]) <= 500 and "Warum wir?" in html


def test_absagen(root, monkeypatch):  # noqa: F811
    app = App(root, compile_pdf=False)
    _ki(monkeypatch, "## Beobachtungen\n- 4 von 5 Absagen bei Fit unter 50 %")
    assert "Ab 5 Absagen" in app.rueckblick().decode()
    html = app.ki_aktion({"aktion": "absagen"}).decode()
    assert "4 von 5 Absagen" in html


def test_hinweise_je_stelle():
    antwort = json.dumps({"anforderungen": [{"begriff": "Azure", "bekannt": True}], "eckdaten": {},
                          "hinweise": ["verlangt 2 Jahre Berufserfahrung", "nur Pflichtpraktikum", "dritter"]})
    bekannt, weitere, eck = fit.ki_auswerten(antwort, {"Azure": []})
    assert eck == {"hinweise": ["verlangt 2 Jahre Berufserfahrung", "nur Pflichtpraktikum"]}
    assert fit.eckdaten_text(eck) == [] and fit.eckdaten_filter(eck)["h"] == ""
