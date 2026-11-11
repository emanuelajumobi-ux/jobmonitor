"""Tote Anzeigen (anzeigen_check.py), Gespräche mit Kalender (kalender.py) und Rückblick (gui_rueckblick.py)."""
import re
import subprocess
from datetime import date, datetime

import responses

from jobmonitor import anzeigen_check as ac
from jobmonitor import antworten as aw
from jobmonitor import gui_bewerbungen as gb
from jobmonitor import gui_rueckblick as grb
from jobmonitor import kalender, tracking
from jobmonitor.gui import App
from jobmonitor.http import Fetcher
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

# Gesprächstermin in zwei Tagen (relativ zu heute – ein festes Datum läge irgendwann in der Vergangenheit)
from datetime import date as _date, timedelta as _timedelta
TERMIN_TAG = _date.today() + _timedelta(days=2)
TERMIN = f"{TERMIN_TAG.isoformat()}T14:00"


ROWS = [
    {"firma": "A", "typ": "Stelle", "status": "neu", "datum": "2026-10-01", "link": "https://a.de/job/1", "notizen": ""},
    {"firma": "B", "typ": "Stelle", "status": "beworben", "datum": "2026-10-20", "link": "https://b.de/job/2",
     "notizen": "Werkstudent Cloud"},
    {"firma": "C", "typ": "Stelle", "status": "beworben", "datum": "2026-10-21", "link": "https://c.de/job/3",
     "notizen": ""},
    {"firma": "D", "typ": "Stelle", "status": "Absage", "datum": "2026-10-02", "link": "https://d.de/job/4",
     "notizen": ""},
    {"firma": "E", "typ": "Stelle", "status": "neu", "datum": "2026-10-03", "link": "https://www.linkedin.com/jobs/view/5",
     "notizen": ""},
]


@responses.activate
def test_tote_anzeigen(tmp_path):
    responses.get(re.compile(r"https://[a-d]\.de/robots\.txt"), body="")
    responses.get("https://a.de/job/1", status=404)
    responses.get("https://b.de/job/2", body="<p>Leider ist diese Stelle bereits besetzt.</p>")
    responses.get("https://c.de/job/3", body="<h1>Werkstudent IT</h1><p>Jetzt bewerben</p>")
    f = Fetcher("test", 0, 5, 0)
    assert ac.faellig(ROWS, {}, date(2026, 11, 2), 3) == ["https://a.de/job/1", "https://b.de/job/2",
                                                          "https://c.de/job/3"]       # D: Absage, E: LinkedIn
    weg = ac.pruefen(tmp_path, ROWS, f, date(2026, 11, 2), {})
    assert weg == ["https://a.de/job/1", "https://b.de/job/2"]
    data = ac.laden(tmp_path)
    assert ac.offline(data) == {"https://a.de/job/1": "2026-11-02", "https://b.de/job/2": "2026-11-02"}
    assert ac.faellig(ROWS, data, date(2026, 11, 3), 3) == []                         # C erst in 3 Tagen wieder
    assert ac.faellig(ROWS, data, date(2026, 11, 6), 3) == ["https://c.de/job/3"]


def test_gespraeche_und_kalender(root, monkeypatch):  # noqa: F811
    rows = [{**r} for r in ROWS[1:3]]
    tracking.save(root / "applications.csv", rows)
    app = App(root, compile_pdf=False)
    html = app.termin({"link": "https://b.de/job/2", "aktion": "setzen", "termin": TERMIN}).decode()
    assert f"Gespräch am {TERMIN_TAG:%d.%m.%Y} um 14:00 Uhr eingetragen" in html
    row = tracking.load(root / "applications.csv")[0]
    assert row["termin"] == TERMIN and row["status"] == "Antwort"
    assert "Gespräche</h2>" in html and "Darauf vorbereiten" in html and "In Kalender eintragen" in html
    assert "Bitte Datum" in app.termin({"link": "https://b.de/job/2", "aktion": "setzen", "termin": ""}).decode()

    aufrufe = []
    monkeypatch.setattr(kalender, "verfuegbar", lambda: True)    # osascript ist gefälscht, läuft also auch auf Linux
    monkeypatch.setattr("sys.platform", "darwin")                 # Mac-Weg (AppleScript), nicht die .ics-Datei

    def run(cmd, **kw):
        aufrufe.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "ok", "")
    wann = datetime(TERMIN_TAG.year, TERMIN_TAG.month, TERMIN_TAG.day, 14)
    ergebnis = kalender.anlegen(root, {}, "https://b.de/job/2", "Vorstellungsgespräch B", wann, "Notiz", run=run)
    assert ergebnis == "neu" and aufrufe[0][-9:] == ["Job-Monitor", "Vorstellungsgespräch B", "Notiz",
                                                      str(wann.year), str(wann.month), str(wann.day), "14", "0", "60"]
    assert kalender.anlegen(root, {}, "https://b.de/job/2", "x", wann, "", run=run) == "vorhanden"
    html = app.bewerbungen().decode()
    assert "im Kalender" in html
    assert "Termin entfernt" in app.termin({"link": "https://b.de/job/2", "aktion": "entfernen"}).decode()
    assert gb.gespraeche(tracking.load(root / "applications.csv"), date(2026, 11, 2))[0]["firma"] == "B"   # Antwort ohne Termin
    assert kalender.vorbereitung(["Azure"], ["SIEM"])[0].endswith("Azure")


def test_rueckblick(root):  # noqa: F811
    rows = [{**r} for r in ROWS] + [{"firma": "F", "typ": "Stelle", "status": "Zusage", "datum": "2026-10-22",
                                     "link": "https://arbeitsagentur.de/x", "notizen": "", "termin": "2026-10-28T10:00"}]
    antworten = [aw.Antwort("https://b.de/job/2", "B", "2026-10-30", "einladung", "b.de"),
                 aw.Antwort("https://c.de/job/3", "C", "2026-10-22", "eingang", "c.de")]
    stellen = [{"url": "https://www.arbeitsagentur.de/1", "first_seen": "2026-10-30"},
               {"url": "https://jobs.adesso-group.com/2", "first_seen": "2026-10-31"},
               {"url": "https://www.stellenwerk.de/3", "first_seen": "2025-01-01"}]
    z = grb.zahlen(rows, antworten, stellen, date(2026, 11, 2))
    assert z["beworben"] == 4                                     # B, C, D (Absage), F (Zusage)
    assert z["quote"] == 75                                       # B (Einladung), D, F – C nur Eingangsbestätigung
    assert z["dauer"] == 10                                       # B: 20.10. → 30.10.
    assert dict(z["weg"])["Gespräch"] == 1 and dict(z["weg"])["Zusage"] == 1
    assert dict(z["herkunft_stellen"]) == {"Bundesagentur": 1, "Firmenseiten": 1}
    assert sum(n for _, n in z["wochen"]) == 4                    # alle vier liegen in den letzten 8 Wochen
    html = grb.render(z)
    assert "Rückblick" in html and "75 %" in html and "10 Tage" in html
    page = App(root, compile_pdf=False).rueckblick().decode()
    assert "Vom Fund zur Zusage" in page and 'href="/rueckblick"' in page
