import shutil
from datetime import date

import pytest

from jobmonitor import gui_bewerbungen as gb
from jobmonitor import tracking
from jobmonitor.config import ROOT
from jobmonitor.gui import App
from jobmonitor.models import Job
from jobmonitor.state import State
from tests.conftest import FIXTURES

TODAY = date(2026, 11, 20)
ROWS = [
    {"firma": "A", "typ": "Stelle", "status": "neu", "datum": "2026-10-01", "link": "https://a", "notizen": ""},
    {"firma": "B", "typ": "Stelle", "status": "beworben", "datum": "2026-10-20", "link": "https://b", "notizen": "x"},
]


def form_for(rows, **changes):
    form = {}
    for i, r in enumerate(rows):
        form.update({f"link_{i}": r["link"], f"status_{i}": r["status"], f"datum_{i}": r["datum"],
                     f"notizen_{i}": r["notizen"]})
    form.update(changes)
    return form


def test_status_beworben_sets_today():
    rows, changes = gb.apply(ROWS, form_for(ROWS, status_0="beworben"), TODAY)
    assert changes == 1 and rows[0]["status"] == "beworben" and rows[0]["datum"] == "2026-11-20"
    rows, _ = gb.apply(ROWS, form_for(ROWS, status_0="beworben", datum_0="2026-11-15"), TODAY)
    assert rows[0]["datum"] == "2026-11-15"                       # selbst gesetztes Datum bleibt


def test_delete_notes_and_stale_rows():
    rows, changes = gb.apply(ROWS, form_for(ROWS, loeschen_0="1", notizen_1="Gespräch am Montag"), TODAY)
    assert changes == 2 and [r["firma"] for r in rows] == ["B"] and rows[0]["notizen"] == "Gespräch am Montag"
    stale = form_for(ROWS, status_0="Absage")
    stale["link_0"] = "https://anders"                            # Datei hat sich inzwischen geändert
    rows, changes = gb.apply(ROWS, stale, TODAY)
    assert changes == 0 and rows[0]["status"] == "neu"


def test_mark_and_hide():
    rows = [dict(r) for r in ROWS]
    job = {"title": "Cloud", "company": "C", "url": "https://c"}
    assert "gemerkt" in gb.mark(rows, job, "merken", TODAY) and rows[-1]["status"] == "neu"
    assert "ausgeblendet" in gb.mark(rows, job, "ausblenden", TODAY) and rows[-1]["status"] == "verworfen"
    assert "gemerkt" in gb.mark(rows, job, "merken", TODAY) and rows[-1]["status"] == "neu"
    assert "steht schon" in gb.mark(rows, {**job, "url": "https://b"}, "merken", TODAY)
    assert len(rows) == 3
    # Pipeline trägt eine verworfene Stelle nicht erneut ein
    gb.mark(rows, job, "ausblenden", TODAY)
    assert not tracking.add_if_missing(rows, "C", "Stelle", "https://c", TODAY)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    shutil.copy(FIXTURES / "cv_master_example.yaml", tmp_path / "cv" / "cv_master.yaml")
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    # B: vor wenigen Tagen beworben (relativ zu heute – ein festes Datum würde irgendwann „nachfassen“ auslösen)
    from datetime import timedelta
    zeilen = [dict(r) for r in ROWS]
    zeilen[1]["datum"] = (date.today() - timedelta(days=3)).isoformat()
    tracking.save(tmp_path / "applications.csv", zeilen)
    state = State(tmp_path / "state" / "seen.sqlite")
    for title, url in (("Werkstudent Cloud", "https://x/1"), ("Werkstudent IT", "https://x/2")):
        job = Job(title, "Beispiel AG", url, "test")
        job.fit_anforderungen = {"Azure": 1.0}
        state.save_job_detail(job, "2026-11-01")
    state.close()
    return App(tmp_path, compile_pdf=False)


def test_index_hide_and_show(app):
    job_id = next(d["id"] for d in app.jobs() if d["url"] == "https://x/2")
    html = app.markieren({"job_id": job_id, "aktion": "ausblenden"}).decode()
    assert "ausgeblendet" in html and "Werkstudent IT</a>" not in html and "Ausgeblendet<span>1</span>" in html
    hidden = app.index(show_hidden=True).decode()
    assert "Werkstudent IT</a>" in hidden and "Werkstudent Cloud</a>" not in hidden


def test_bewerbungen_page_and_save(app):
    html = app.bewerbungen().decode()
    assert "Nachfassen" not in html                              # B erst seit drei Tagen beworben
    html = app.bewerbungen_save(form_for(tracking.load(app.root / "applications.csv"), notizen_0="Telefonat")).decode()
    assert "1 Änderung(en)" in html
    assert tracking.load(app.root / "applications.csv")[0]["notizen"] == "Telefonat"


def test_new_since_last_visit(app):
    app.remember_visit()                              # erster Besuch: nichts als neu markieren
    assert app.new_ids == set()
    state = State(app.root / "state" / "seen.sqlite")
    job = Job("Werkstudent Neu", "Neu AG", "https://x/3", "test")
    job.fit_anforderungen = {"Azure": 1.0}
    state.save_job_detail(job, "2026-11-05")
    state.close()
    app.remember_visit()
    assert app.new_ids == {job.short_id}
    html = app.index().decode()
    assert "1 neue Stelle(n) seit deinem letzten Besuch" in html and '<span class="chip new">neu</span>' in html


def test_report_view(app):
    (app.root / "reports").mkdir()
    (app.root / "reports" / "2026-11-01.md").write_text("# Alt\n", encoding="utf-8")
    (app.root / "reports" / "2026-11-04.md").write_text("# Job-Monitor\n\n## Neue Stellen (1)\n", encoding="utf-8")
    html = app.bericht().decode()
    assert '<div class="group"><span>Neue Stellen</span><span>1</span></div>' in html and "/bericht/2026-11-01" in html
    assert "Alt" in app.bericht_tag("2026-11-01").decode()        # unbekanntes Format: Markdown wie bisher
    assert app.bericht_tag("../config") is None


def test_deadline_badges(app):
    from datetime import timedelta
    state = State(app.root / "state" / "seen.sqlite")
    for title, url, days in (("Werkstudent Frist", "https://x/9", 5), ("Werkstudent Vorbei", "https://x/8", -3)):
        job = Job(title, "F AG", url, "test")
        job.fit_anforderungen = {"Azure": 1.0}
        job.frist = (date.today() + timedelta(days=days)).isoformat()
        state.save_job_detail(job, "2026-11-02")
    state.close()
    html = app.index().decode()
    assert "(in 5 Tagen)" in html and "Frist abgelaufen" in html and 'class="job expired"' in html
