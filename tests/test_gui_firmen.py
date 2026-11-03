import difflib
import shutil
from datetime import date

import pytest

from jobmonitor import gui_firmen as gf
from jobmonitor import tracking
from jobmonitor.config import ROOT, load_companies
from jobmonitor.gui import App

REPORT = """# Job-Monitor – 31.10.2026

## Status der Quellen

- ✅ **Firmen-Karriereseiten**: 127 Rohtreffer

**Manuell prüfen:**

- Seven Principles: keine maschinenlesbaren Stellen gefunden – https://7p-group.com/karriere/
- Zurich: Fehler beim Abruf, bitte manuell prüfen
- Uni Bonn: Login für Studierende – https://www.uni-bonn.de/jobs

## Neue Stellen (0)
"""


@pytest.fixture
def root(tmp_path):
    shutil.copy(ROOT / "companies.yaml", tmp_path / "companies.yaml")
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "2026-10-31.md").write_text(REPORT, encoding="utf-8")
    tracking.save(tmp_path / "applications.csv", [])
    return tmp_path


def test_add_company_and_rules(root):
    from jobmonitor.config import save_companies
    save_companies(load_companies(root / "companies.yaml"), root / "companies.yaml")   # einmal normalisieren
    before = (root / "companies.yaml").read_text(encoding="utf-8")
    assert gf.add(root, {"name": "Test GmbH", "karriereseite_url": "https://test.example/jobs",
                         "standorte": "Köln, Remote", "fokus": ""}) == "Test GmbH"
    after = (root / "companies.yaml").read_text(encoding="utf-8")
    diff = [d for d in difflib.ndiff(before.splitlines(), after.splitlines()) if d[:1] in "+-"]
    assert diff and all(d.startswith("+ ") for d in diff)            # nur neue Zeilen, Rest unverändert
    entry = load_companies(root / "companies.yaml")["firmen"][-1]
    assert entry["standorte"] == ["Köln", "Remote"] and entry["initiativ"]["moeglich"] == "unbekannt"
    assert entry["kategorie"] == "sonstige" and "aktiv" not in entry
    for form, match in (({"name": "test gmbh", "karriereseite_url": "https://x.example"}, "schon"),
                        ({"name": "X", "karriereseite_url": "https://www.linkedin.com/company/x/jobs"}, "Jobbörse"),
                        ({"name": "Y", "karriereseite_url": "firma.de"}, "http"),
                        ({"name": "", "karriereseite_url": "https://x.example"}, "Name")):
        with pytest.raises(gf.FirmaError, match=match):
            gf.add(root, form)


def test_toggle_active(root):
    assert gf.set_active(root, "inovex", False)
    assert load_companies(root / "companies.yaml")["firmen"][0]["aktiv"] is False
    assert gf.set_active(root, "inovex", True)
    assert "aktiv" not in load_companies(root / "companies.yaml")["firmen"][0]
    assert not gf.set_active(root, "Gibt es nicht", True)


def test_manual_entries_and_due(root):
    entries = gf.manual_entries(root)
    assert [e["name"] for e in entries] == ["Seven Principles", "Zurich", "Uni Bonn"]
    assert entries[0]["url"] == "https://7p-group.com/karriere/"
    zurich = next(f for f in load_companies(root / "companies.yaml")["firmen"] if f["name"] == "Zurich")
    assert entries[1]["url"] == zurich["karriereseite_url"]          # aus companies.yaml ergänzt
    today = date(2026, 11, 20)
    assert gf.due(root, today, 14) == []                       # noch nie besucht: keine Warnung
    gf.mark_visited(root, "Zurich", date(2026, 11, 10))
    gf.mark_visited(root, "Uni Bonn", date(2026, 11, 1))
    assert [e["name"] for e in gf.due(root, today, 14)] == ["Uni Bonn"]


def test_pages(root):
    (root / ".gui_eingerichtet.json").write_text("{}")              # sonst zeigt die Startseite den Assistenten
    app = App(root, compile_pdf=False)
    html = app.firmen().decode()
    assert "Seven Principles" in html and "noch nicht besucht" in html and "Alle Firmen" in html
    assert "solltest du mal wieder" not in app.index().decode()        # nie besucht → kein Dauerhinweis
    gf.mark_visited(root, "Zurich", date(2026, 1, 1))
    assert "1 Karriereseite(n) solltest du mal wieder" in app.index().decode()
    html = app.firmen_besucht({"name": "Seven Principles"}).decode()
    assert "als besucht markiert" in html
    html = app.firmen_neu({"name": "Neu AG", "karriereseite_url": "https://neu.example/jobs"}).decode()
    assert "„Neu AG“ hinzugefügt" in html and "Neu AG" in html
    assert "Nicht hinzugefügt" in app.firmen_neu({"name": "Neu AG", "karriereseite_url": "https://n.example"}).decode()
    assert "deaktiviert" in app.firmen_aktiv({"name": "Neu AG", "aktiv": ""}).decode()


def test_suggestions(root):
    details = [
        {"company": "Neue Firma GmbH", "title": "Werkstudent Cloud", "url": "https://neue-firma.jobs.personio.de/job/1"},
        {"company": "Neue Firma", "title": "Werkstudent IT", "url": "https://www.stellenwerk.de/koeln/x"},
        {"company": "Andere AG", "title": "Praktikum", "url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/1"},
        {"company": "inovex GmbH", "title": "Thesis", "url": "https://www.inovex.de/x"},          # schon bekannt
        {"company": "Ausgeschlossen GmbH", "title": "Werkstudent", "url": "https://ausgeschlossen.example/x"},  # aus
        {"company": "(über LinkedIn)", "title": "Werkstudent", "url": "https://x"},
    ]
    found = gf.suggestions(root, details, ["ausgeschlossen"])
    assert [(s["name"], s["anzahl"]) for s in found] == [("Neue Firma GmbH", 2), ("Andere AG", 1)]
    assert found[0]["url"] == "https://neue-firma.jobs.personio.de/" and found[1]["url"] == ""   # Börse ≠ Karriereseite
    gf.ignore(root, "Andere AG")
    assert [s["name"] for s in gf.suggestions(root, details, ["ausgeschlossen"])] == ["Neue Firma GmbH"]


def test_beobachten_mit_aktionen(tmp_path):
    from jobmonitor import gui_firmen as gf
    from jobmonitor import gui_wartung as gw
    from jobmonitor.quellen_verlauf import Warnung
    (tmp_path / "companies.yaml").write_text(
        "firmen:\n  - name: Zurich\n    karriereseite_url: https://zurich.de/karriere\n", encoding="utf-8")
    html = gf.render(tmp_path, "t", date(2026, 11, 2), 14, beobachten=[
        Warnung("firma", "Zurich", "3 Läufe in Folge Fehler"),
        Warnung("quelle", "Bundesagentur für Arbeit (Junior)", "3 Läufe ohne Treffer")])
    assert 'href="https://zurich.de/karriere"' in html and "Karriereseite öffnen" in html
    assert "/einstellungen/datei?name=companies.yaml&amp;suche=name%3A%20Zurich" in html
    assert "/einstellungen/datei?name=config.yaml&amp;suche=bundesagentur%3A" in html
    seite = gw.render_datei("t", "companies.yaml", "firmen:\n  - name: Zurich\n", suche="name: Zurich")
    assert 'data-suche="name: Zurich"' in seite and "setSelectionRange" in seite
    assert "setSelectionRange" not in gw.render_datei("t", "companies.yaml", "x")


def test_vermerk_nach_aenderung(tmp_path, monkeypatch):
    from jobmonitor.quellen_verlauf import Warnung
    w = Warnung("firma", "Zurich", "Fehler seit 3 Läufen")
    verlauf = {("firma", "Zurich"): [("2026-11-02", 0, "fehler")]}
    monkeypatch.setattr(gf, "_verlauf", lambda root, cfg: verlauf)
    monkeypatch.setattr(gf, "warnungen", lambda root, cfg, history=None: [w] if verlauf[("firma", "Zurich")][0][2] != "ok" else [])
    assert gf.beobachten(tmp_path, {}) == ([w], {}, [])
    gf.vermerken(tmp_path, "firma:Zurich", date(2026, 11, 2))
    gf.vermerken(tmp_path, "unsinn", date(2026, 11, 2))                       # falsches Format: ignoriert
    _, status, _ = gf.beobachten(tmp_path, {})
    assert status["firma:Zurich"][0] == "pruefung" and "wird beim nächsten Lauf überprüft" in status["firma:Zurich"][1]
    html = gf.render(tmp_path, "t", date(2026, 11, 2), 14, beobachten=[w], status=status)
    assert "watch-item pruefung" in html and "von=firma%3AZurich" in html
    verlauf[("firma", "Zurich")] = [("2026-11-03", 0, "fehler")]                  # nächster Lauf: weiter Fehler
    assert gf.beobachten(tmp_path, {})[1]["firma:Zurich"][0] == "offen"
    verlauf[("firma", "Zurich")] = [("2026-11-04", 5, "ok")]                      # danach behoben
    liste, status, behoben = gf.beobachten(tmp_path, {})
    assert liste == [] and behoben == [("Zurich", "läuft wieder (geprüft beim Lauf am 04.11.)")]
    assert "watch-item done" in gf.render(tmp_path, "t", date(2026, 11, 4), 14, behoben=behoben)


def test_speichern_schliesst_editor(tmp_path):
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    (tmp_path / "companies.yaml").write_text(
        "firmen:\n  - name: Zurich\n    karriereseite_url: https://alt.de\n", encoding="utf-8")
    app = App(tmp_path, compile_pdf=False)
    html = app.datei_post({"name": "companies.yaml", "von": "firma:Zurich",
                           "text": "firmen:\n  - name: Zurich\n    karriereseite_url: https://neu.de\n"}).decode()
    assert "<h1>Firmen</h1>" in html and "beim nächsten Lauf überprüft" in html
    assert gf.vermerke(tmp_path) == {"firma:Zurich": date.today().isoformat()}
    fehler = app.datei_post({"name": "companies.yaml", "von": "firma:Zurich", "text": "firmen: x\n"}).decode()
    assert "Nicht gespeichert" in fehler and 'name="von" value="firma:Zurich"' in fehler
