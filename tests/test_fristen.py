import sqlite3
from datetime import date

import pytest

from jobmonitor.fristen import find, label
from jobmonitor.models import Job
from jobmonitor.report import Report
from jobmonitor.state import State

TODAY = date(2026, 10, 31)


@pytest.mark.parametrize("text, expected", [
    ("Bewerbung bis spätestens 21.11.2026 an uns", date(2026, 11, 21)),
    ("Bewerbungsfrist: 15. November 2026", date(2026, 11, 15)),
    ("Bewerbungsschluss 30.11.", date(2026, 11, 30)),
    ("Bewerbungsschluss 05.01.", date(2027, 1, 5)),                       # ohne Jahr → nächstes passendes
    ("Sende deine Unterlagen inkl. Lebenslauf bis 20.12.2026", date(2026, 12, 20)),
    ("Start: 01.04.2027. Bewirb dich bis zum 20.12.2026!", date(2026, 12, 20)),
    ("Application deadline: 5 Dez 2026", date(2026, 12, 5)),
    ("Die Stelle ist befristet bis 31.08.2027", None),
    ("16 bis 20 Stunden pro Woche, Start spätestens zum 01.04.2027", None),
    ("Eintritt ab 01.03.2027", None),
    ("Bewerbungsfrist 31.02.2027", None),                                 # ungültiges Datum
])
def test_find(text, expected):
    assert find(text, TODAY) == expected


def test_label():
    assert label("2026-11-05", TODAY) == "Frist 05.11.2026 (in 5 Tagen)"
    assert label("2026-10-31", TODAY) == "Frist 31.10.2026 (heute)"
    assert label("2026-10-20", TODAY) == "Frist abgelaufen (20.10.2026)"
    assert label(None, TODAY) == ""


def test_state_migrates_old_db(tmp_path):
    path = tmp_path / "seen.sqlite"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE job_detail (id TEXT PRIMARY KEY, key TEXT, title TEXT, company TEXT, url TEXT, "
               "anforderungen_json TEXT, fit INTEGER, first_seen TEXT)")
    db.execute("INSERT INTO job_detail VALUES ('aaaa1111','k','Alt','A','https://a','{}',NULL,'2026-10-01')")
    db.commit()
    db.close()
    state = State(path)
    job = Job("Neu", "B", "https://b", "test")
    job.frist = "2026-11-21"
    state.save_job_detail(job, "2026-10-31")
    assert state.job_detail("aaaa1111")["frist"] is None
    assert state.job_detail(job.short_id)["frist"] == "2026-11-21"
    state.close()


def test_report_shows_deadline():
    job = Job("Werkstudent Cloud", "B", "https://b", "test", score=70)
    job.frist = "2026-11-05"
    text = Report(TODAY, [], [job]).render()
    assert "**Frist 05.11.2026 (in 5 Tagen)**" in text


def test_readonly_state_does_not_touch_old_db(tmp_path):
    """Oberfläche/make cv öffnen die Datenbank nur lesend – keine Migration, keine Änderung der Datei."""
    path = tmp_path / "seen.sqlite"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE job_detail (id TEXT PRIMARY KEY, key TEXT, title TEXT, company TEXT, url TEXT, "
               "anforderungen_json TEXT, fit INTEGER, first_seen TEXT)")
    db.execute("INSERT INTO job_detail VALUES ('aaaa1111','k','Alt','A','https://a','{}',NULL,'2026-10-01')")
    db.commit()
    db.close()
    before = path.read_bytes()
    state = State(path, readonly=True)
    assert state.job_details()[0]["frist"] is None and state.job_detail("aaaa")["title"] == "Alt"
    state.close()
    assert path.read_bytes() == before
    assert State(tmp_path / "fehlt.sqlite", readonly=True).job_details() == []
    assert not (tmp_path / "fehlt.sqlite").exists()
