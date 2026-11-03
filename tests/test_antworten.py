"""Antworten von Firmen erkennen (antworten.py) und in der App übernehmen. Beispiele nach echten Mustern, anonymisiert."""
import json
from datetime import date

from jobmonitor import antworten as aw
from jobmonitor import gui_bewerbungen as gb
from jobmonitor import tracking
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

ROWS = [
    {"firma": "INFODAS GmbH", "typ": "Stelle", "status": "beworben", "datum": "2026-04-01",
     "link": "https://www.stellenwerk.de/koeln/werkstudent-1", "notizen": "Werkstudent Softwareentwicklung (Score 70)"},
    {"firma": "Remondis", "typ": "Stelle", "status": "beworben", "datum": "2026-04-10",
     "link": "https://www.arbeitsagentur.de/jobsuche/jobdetail/1", "notizen": ""},
    {"firma": "Flossbach von Storch SE", "typ": "Stelle", "status": "beworben", "datum": "2026-04-15",
     "link": "https://www.stellenwerk.de/koeln/2",
     "notizen": "Werkstudent – IT-Governance & Architektur (m/w/d) (Score 61)"},
    {"firma": "adesso", "typ": "Stelle", "status": "nachgefasst", "datum": "2026-04-01",
     "link": "https://jobs.adesso-group.com/job/3", "notizen": ""},
    {"firma": "Alte Firma", "typ": "Stelle", "status": "Absage", "datum": "2026-01-01",
     "link": "https://alt.de/job", "notizen": ""},
]
ABSAGE = ("Sehr geehrter Herr X, herzlichen Dank für Ihre Bewerbung. Leider müssen wir Ihnen mitteilen, dass wir Sie "
          "im Bewerbungsverfahren nicht weiter berücksichtigen können.")
EINGANG = ("wir bedanken uns fuer Ihr Interesse und bestaetigen Ihnen hiermit den Eingang Ihrer Bewerbung. "
           "Ihre Unterlagen sind sicher bei uns eingegangen.")


def mail(von, betreff, text, datum="2026-04-16"):
    return {"von": von, "betreff": betreff, "text": text, "datum": datum}


def test_klassifizieren():
    assert aw.klassifizieren("Ihre Bewerbung", ABSAGE) == "absage"
    assert aw.klassifizieren("Ihre Bewerbung", EINGANG) == "eingang"
    assert aw.klassifizieren("Einladung zum Vorstellungsgespräch", "Wir möchten Sie gern kennenlernen.") == "einladung"
    assert aw.klassifizieren("Your application", "Unfortunately we decided to move forward with others") == "absage"
    assert aw.klassifizieren("Vertragsangebot", "Wir freuen uns, Ihnen eine Zusage zu geben.") == "zusage"
    assert aw.klassifizieren("Rückfrage", "Können Sie uns noch Ihr Zeugnis schicken?") == "nachricht"


def test_zuordnen_ueber_ats_namen_titel_und_domain():
    # 1. ATS mit Firmenname im Anzeigenamen
    a = aw.zuordnen(mail("INFODAS (via softgarden) <notifications@app.softgarden.io>",
                         "Ihre Bewerbung als Werkstudent Softwareentwicklung", ABSAGE), ROWS, {})
    assert [(x.firma, x.art, x.absender) for x in a] == [("INFODAS GmbH", "absage", "app.softgarden.io")]
    # 2. ATS, Firma nur in der Absenderadresse
    a = aw.zuordnen(mail("Personalabteilung <no-reply-remondis@concludis.de>", "Ihre Bewerbung", EINGANG), ROWS, {})
    assert [(x.firma, x.art, x.status) for x in a] == [("Remondis", "eingang", None)]
    # 3. eigene Firmenadresse ohne Namen, aber mit Stellentitel im Betreff
    a = aw.zuordnen(mail("Karriere <karriere@fvs.com>", "Ihre Bewerbung als Werkstudent – IT-Governance & Architektur "
                         "(m/w/d)", "Wir laden Sie herzlich zu einem Kennenlerngespräch ein."), ROWS, {})
    assert [(x.firma, x.art, x.status) for x in a] == [("Flossbach von Storch SE", "einladung", "Antwort")]
    # 4. Domain der Firma (Link der Stelle) genügt, auch ohne Bewerbungswort
    a = aw.zuordnen(mail("Max <max@adesso-group.com>", "Kurze Frage", "Hätten Sie Zeit für ein Telefonat?"), ROWS, {})
    assert [(x.firma, x.art) for x in a] == [("adesso", "einladung")]


def test_keine_falschen_treffer():
    # Newsletter einer Firma ohne Bewerbungsbezug, Mail vor der Bewerbung, abgeschlossene Bewerbung
    assert aw.zuordnen(mail("INFODAS News <news@infodas-news.de>", "Unser Herbst-Newsletter", "Neues Produkt"),
                       ROWS, {}) == []
    assert aw.zuordnen(mail("INFODAS (via softgarden) <n@app.softgarden.io>", "Ihre Bewerbung", ABSAGE,
                            datum="2026-03-01"), ROWS, {}) == []
    assert aw.zuordnen(mail("HR <hr@alt.de>", "Ihre Bewerbung", ABSAGE), ROWS, {}) == []
    # Jobbörse im Link ist keine Firmendomain
    assert aw.domains(ROWS[0], {}) == set() and aw.domains(ROWS[3], {}) == {"adesso-group.com"}
    companies = {"firmen": [{"name": "Remondis SE", "karriereseite_url": "https://www.remondis-karriere.de/jobs"}]}
    assert aw.domains(ROWS[1], companies) == {"remondis-karriere.de"}


def test_ablage_und_nachfassen(tmp_path):
    a1 = aw.Antwort(ROWS[0]["link"], "INFODAS GmbH", "2026-04-16", "absage", "app.softgarden.io")
    a2 = aw.Antwort(ROWS[1]["link"], "Remondis", "2026-04-13", "eingang", "concludis.de")
    assert aw.speichern(tmp_path, [a1, a2, a1]) == [a1, a2]
    assert aw.speichern(tmp_path, [a1]) == []
    gespeichert = json.loads((tmp_path / aw.DATEI).read_text())
    assert set(gespeichert[0]) == {"link", "firma", "datum", "art", "absender"}       # kein Betreff, kein Text
    # Nachfassen: nicht bei echter Antwort, wohl aber nach bloßer Eingangsbestätigung
    due = tracking.follow_ups(ROWS, date(2026, 6, 1), 21, aw.beantwortet(aw.laden(tmp_path)))
    assert {r["firma"] for r in due} == {"Remondis", "Flossbach von Storch SE"}


def test_app_uebernehmen_und_abhaken(root):  # noqa: F811
    rows = [{**ROWS[0]}, {**ROWS[1]}]
    tracking.save(root / "applications.csv", rows)
    a1 = aw.Antwort(ROWS[0]["link"], "INFODAS GmbH", "2026-04-16", "absage", "app.softgarden.io")
    a2 = aw.Antwort(ROWS[1]["link"], "Remondis", "2026-04-13", "eingang", "concludis.de")
    aw.speichern(root, [a1, a2])
    app = App(root, compile_pdf=False)
    html = app.bewerbungen().decode()
    assert "Antworten von Firmen" in html and "Status „Absage“ setzen" in html and "Eingang bestätigt" in html
    assert app.badges()["bewerbungen"][0] >= 2
    html = app.antwort({"schluessel": a1.schluessel, "aktion": "uebernehmen"}).decode()
    assert "Status auf „Absage“ gesetzt" in html
    row = tracking.load(root / "applications.csv")[0]
    assert row["status"] == "Absage" and "Absage am 2026-04-16 (aus dem Postfach erkannt)" in row["notizen"]
    app.antwort({"schluessel": a2.schluessel, "aktion": "erledigt"})
    assert gb.offene_antworten(root, tracking.load(root / "applications.csv")) == []
    assert "Antworten von Firmen</h2>" not in app.bewerbungen().decode()


def test_bericht_zeigt_antworten():
    from jobmonitor import gui_bericht as gbe
    from jobmonitor.report import Report
    a = aw.Antwort("https://x/1", "INFODAS GmbH", "2026-11-03", "einladung", "softgarden.io")
    rep = Report(date(2026, 11, 3), [], [], [], [], "", "Traumprofil", {"werkstudent": "Werkstudent"}, [], [a])
    text = rep.render()
    assert "## Antworten von Firmen (1)" in text and "- **INFODAS GmbH**: Einladung zum Gespräch am 03.11." in text
    assert "1 Antwort(en) von Firmen" in rep.subject("Job-Monitor")
    b = gbe.parse(text)
    assert any(g.titel.startswith("Antworten von Firmen") and g.zeilen for g in b.gruppen)
