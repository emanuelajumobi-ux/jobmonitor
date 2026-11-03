"""Eckdaten-Filter, Prüfung vor dem Abschicken, Auswertung im Rückblick, Kenntnis-Trend, Nach dem Gespräch und
Angebote vergleichen. Die Claude-API wird nie aufgerufen (llm._ask gefälscht)."""
import json
from datetime import date, timedelta

import pytest

from jobmonitor import abschicken, fit, ki, llm, tracking
from jobmonitor import bewerbung as bw
from jobmonitor import gui_gespraech as ggs
from jobmonitor import gui_rueckblick as grb
from jobmonitor import gui_trend as gtr
from jobmonitor.config import load_config
from jobmonitor.gui import App
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)


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


def test_eckdaten_filter():
    assert fit.eckdaten_filter({"stunden": "16–20 h/Woche", "remote": "bis 3 Tage/Woche", "abschlussarbeit": True}) \
        == {"h": "16", "r": "1", "t": "1", "v": "", "vz": "0", "tz": "1"}
    assert fit.eckdaten_filter({"stunden": "25-30 Wochenstunden", "remote": "kein Homeoffice"}) \
        == {"h": "25", "r": "0", "t": "", "v": "", "vz": "0", "tz": "1"}
    assert fit.eckdaten_filter({"stunden": "Teilzeit"}) == {"h": "", "r": "", "t": "", "v": "", "vz": "", "tz": "1"}
    assert fit.eckdaten_filter({"stunden": "Vollzeit, 40 h", "verguetung": "52.000 €"}) \
        == {"h": "40", "r": "", "t": "", "v": "1", "vz": "1", "tz": "0"}


def test_filter_je_karrierestufe(root):  # noqa: F811
    from jobmonitor import gui, suchprofil
    assert 'data-eck="h"' in gui.eck_filter(["werkstudent"]) and 'data-eck="vz"' not in gui.eck_filter(["werkstudent"])
    einstieg = gui.eck_filter(["einstieg"])
    assert 'data-eck="vz"' in einstieg and 'data-eck="v"' in einstieg and 'data-eck="h"' not in einstieg
    beide = gui.eck_filter(["werkstudent", "einstieg"])
    assert beide.count('data-eck="r"') == 1 and 'data-eck="h"' in beide and 'data-eck="vz"' in beide
    p = suchprofil.Profil(key="junior", name="Junior", rollen={})
    assert suchprofil.stufe_von(p) == "einstieg"


def test_filter_in_der_stellenliste(root):  # noqa: F811
    html = App(root, compile_pdf=False).index().decode()
    assert 'data-eck="h"' in html and 'data-eck="r"' in html and 'data-eck="t"' in html


def test_vor_dem_abschicken(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    daten = {"text": "Bei der Beispiel AG möchte ich als Werkstudent Cloud Operations [Thema] unterstützen.",
             "anrede": "Sehr geehrte Damen und Herren,", "empfaenger": ""}
    anlagen = [{"name": "Zeugnis", "pdfs": [], "pfad": "x"}]
    punkte = abschicken.pruefen(folder, daten, STELLE, cfg, anlagen, [], offline=True)
    texte = [(p.ok, p.text) for p in punkte]
    assert (False, "Noch 1 Platzhalter: [Thema]") in texte
    assert (False, "Noch keine Mappe gebaut („Speichern und Mappe bauen“)") in texte
    assert any(not ok and "Anlage fehlt: Zeugnis" in t for ok, t in texte)
    assert any(not ok and "nicht mehr online" in t for ok, t in texte)
    # Mappe gebaut, aber Anschreiben danach geändert und zu groß
    (folder / "bewerbungsmappe-beispiel.pdf").write_bytes(b"%PDF" + b"0" * 6_000_000)
    bw.save_letter(folder, daten["text"].replace(" [Thema]", ""), daten["anrede"], "")
    import os
    os.utime(folder / "bewerbungsmappe-beispiel.pdf", (0, 0))
    punkte = abschicken.pruefen(folder, bw.letter(folder), STELLE, cfg, [], [])
    texte = [(p.ok, p.text) for p in punkte]
    assert (True, "Keine Platzhalter mehr im Anschreiben") in texte and (True, "Alle Anlagen vorhanden") in texte
    assert any(not ok and "Mappe neu bauen" in t for ok, t in texte)
    assert any(not ok and "über 5 MB" in t for ok, t in texte)
    assert "Vor dem Abschicken" in abschicken.render(punkte, "tok", "/bewerbung/x", False)


def test_ki_durchsicht(root, mit_ki, monkeypatch):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    bw.save_letter(folder, "Hiermit bewerbe ich mich mit großem Interesse.", "Hallo,", "")
    ask = Ask(json.dumps({"fazit": "Solide, aber allgemein.", "hinweise": [
        {"art": "Floskel", "zitat": "mit großem Interesse", "vorschlag": "Direkt mit dem Bezug zur Stelle beginnen."}]}))
    monkeypatch.setattr(llm, "_ask", ask)
    monkeypatch.setattr(ki, "anzeige", lambda r, link, f, cache=None: "Wir suchen Unterstützung.")
    app = App(root, compile_pdf=False)
    assert "Anschreiben mit KI prüfen" in app.bewerbung(folder.name).decode()
    html = app.bewerbung_post(folder.name, {"aktion": "ki_pruefen"}).decode()
    assert "KI-Durchsicht des Anschreibens" in html and "Direkt mit dem Bezug" in html
    assert bw.letter(folder)["text"] == "Hiermit bewerbe ich mich mit großem Interesse."     # nichts überschrieben
    assert "Max Muster" not in ask.prompts[0]


def test_was_zum_gespraech_fuehrt():
    rows = [{"firma": "A", "typ": "Stelle", "status": "Antwort", "datum": "2026-10-01",
             "link": "https://www.arbeitsagentur.de/1", "termin": "2026-10-10T10:00"},
            {"firma": "B", "typ": "Initiativ", "status": "beworben", "datum": "2026-10-02", "link": "https://b.de/k",
             "termin": ""},
            {"firma": "C", "typ": "Stelle", "status": "Absage", "datum": "2026-10-03", "link": "https://c.de/1",
             "termin": ""}]
    stellen = [{"url": "https://www.arbeitsagentur.de/1", "fit": 80, "first_seen": "2026-10-01"},
               {"url": "https://c.de/1", "fit": 55, "first_seen": "2026-10-01"}]
    z = grb.zahlen(rows, [], stellen, date(2026, 11, 3))
    assert z["erfolg"]["Fit"] == [("Fit ab 75 %", 1, 1, 1), ("Fit 50–74 %", 1, 1, 0), ("ohne Fit", 1, 0, 0)]
    assert z["erfolg"]["Art"][0] == ("Stelle", 2, 2, 1)
    html = grb.render(z)
    assert "Was zum Gespräch führt" in html and "kaum aussagekräftig" in html


def test_kenntnis_trend():
    details = [{"first_seen": f"2026-{m:02d}-05",
                "anforderungen": {"Azure": 1, **({"Terraform": 1} if m >= 9 and i % 2 == 0 else {})}}
               for m in range(6, 12) for i in range(4)]
    v = gtr.verlauf(details, date(2026, 11, 3))
    zeilen = {z["term"]: z for z in v["zeilen"]}
    assert zeilen["Terraform"]["anteile"] == [0, 0, 0, 50, 50, 50] and zeilen["Terraform"]["trend"] == "steigend"
    assert zeilen["Azure"]["trend"] == "gleich" and [m for m, _ in v["monate"]][-1] == "2026-11"
    html = gtr.render(v, {"Azure": 1.0})
    assert "Gefragt im Verlauf" in html and "↑ steigend" in html and html.count("fehlt dir") == 1
    kurz = gtr.render(gtr.verlauf(details[-4:], date(2026, 11, 3)), {})
    assert "ab etwa drei Monaten" in kurz


def test_nach_dem_gespraech(root, mit_ki, monkeypatch):  # noqa: F811
    gestern = (date.today() - timedelta(days=3)).isoformat()
    tracking.save(root / "applications.csv", [
        {"firma": "Beispiel AG", "typ": "Stelle", "status": "Antwort", "datum": "2026-10-01", "link": "https://x/1",
         "notizen": "Werkstudent Cloud", "termin": f"{gestern}T10:00"},
        {"firma": "Beispiel AG", "typ": "Stelle", "status": "Antwort", "datum": "2026-10-20", "link": "https://x/2",
         "notizen": "Werkstudent IAM", "termin": "2099-01-05T09:00"}])
    ask = Ask(json.dumps({"betreff": "Danke für das Gespräch", "text": "Guten Tag, ... Viele Grüße\n[Name]"}),
              "## Wahrscheinliche Fragen\n- x")
    monkeypatch.setattr(llm, "_ask", ask)
    monkeypatch.setattr(ki, "anzeige", lambda r, link, f, cache=None: "")
    app = App(root, compile_pdf=False)
    html = app.bewerbungen().decode()
    assert "war am" in html and "Nach dem Gespräch" in html
    html = app.nachbereitung({"link": "https://x/1", "aktion": "speichern",
                              "notizen": "Fragen zu Terraform und Entra ID.", "gefuehl": "gut"}).decode()
    assert "Notizen gespeichert" in html and "Fragen zu Terraform" in html and "gutes Gefühl" in html
    html = app.nachbereitung({"link": "https://x/1", "aktion": "danke", "notizen": "Fragen zu Terraform und Entra ID.",
                              "gefuehl": "gut"}).decode()
    assert "Danke-Mail an Beispiel AG entworfen" in html and "Viele Grüße\nMax Muster" in html
    assert "Fragen zu Terraform" in ask.prompts[0] and "Max Muster" not in ask.prompts[0]
    # Nächste Vorbereitung bei derselben Firma kennt die Notizen
    app.vorbereitung({"link": "https://x/2"})
    assert "FRÜHEREN GESPRÄCHEN" in ask.prompts[1] and "Fragen zu Terraform" in ask.prompts[1]
    assert "nicht gefunden" in app.nachbereitung({"link": "https://y"}).decode()


def test_angebote_vergleichen():
    rows = [{"firma": "A", "status": "Zusage", "link": "https://a/1", "notizen": "Werkstudent Cloud"},
            {"firma": "B", "status": "Zusage", "link": "https://b/1", "notizen": ""},
            {"firma": "C", "status": "Absage", "link": "https://c/1", "notizen": ""}]
    stellen = {"https://a/1": {"title": "Werkstudent Cloud", "fit": 82,
                               "eckdaten": {"stunden": "20 h/Woche", "verguetung": "17 €/h"}}}
    liste = ggs.angebote(rows, stellen, {"https://b/1": {"gefuehl": "mittel", "notizen": "nettes Team"}})
    assert [a["firma"] for a in liste] == ["A", "B"]
    html = ggs.angebote_html(liste)
    assert "Angebote vergleichen" in html and "17 €/h" in html and "82 %" in html and "nettes Team" in html
    assert ggs.angebote_html(liste[:1]) == ""
