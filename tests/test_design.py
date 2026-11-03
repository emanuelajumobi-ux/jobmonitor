"""Design-Audit (apple-design): App-Fenster-Klasse, Rückgängig beim Ausblenden, Bedienungshilfen im CSS."""
from datetime import date

from jobmonitor import gui_bewerbungen as gb
from jobmonitor import gui_layout as layout
from jobmonitor import tracking
from jobmonitor.gui import App
from jobmonitor.models import Job
from jobmonitor.state import State
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

JOB = {"title": "Werkstudent Cloud", "company": "Beispiel AG", "url": "https://x/1"}


def test_native_class_only_with_sidebar():
    assert b'<html lang="de" class="native">' in layout.document("T", "x", side="<aside></aside>", native=True)
    assert b'class="native"' not in layout.document("T", "x", native=True)          # Startseite ohne Leiste
    assert b'class="native"' not in layout.document("T", "x", side="<aside></aside>")


def test_css_accessibility_and_feedback():
    css = layout.CSS
    for needle in ("prefers-reduced-motion", "prefers-reduced-transparency", "prefers-contrast",
                   "button:active", ":focus-visible", "backdrop-filter", "html.native .side"):
        assert needle in css, needle
    assert "e.defaultPrevented" in layout.JS and "400" in layout.JS                 # verzögertes Overlay


def test_undo_hide():
    rows = []
    gb.mark(rows, JOB, "ausblenden", date(2026, 11, 1))
    assert gb.undo_hide(rows, JOB, "") == "„Werkstudent Cloud“ wird wieder angezeigt." and rows == []
    rows = [{"firma": "Beispiel AG", "typ": "Stelle", "status": "neu", "datum": "", "link": "https://x/1",
             "notizen": ""}]
    gb.mark(rows, JOB, "ausblenden", date(2026, 11, 1))
    gb.undo_hide(rows, JOB, "neu")
    assert rows[0]["status"] == "neu"
    assert "nicht ausgeblendet" in gb.undo_hide(rows, JOB, "neu")


def test_hide_offers_undo(root):  # noqa: F811
    state = State(root / "state" / "seen.sqlite")
    job = Job("Werkstudent Cloud", "Beispiel AG", "https://x/1", "test")
    state.save_job_detail(job, "2026-11-01")
    state.close()
    app = App(root, compile_pdf=False)
    app.native = True
    html = app.markieren({"job_id": job.short_id, "aktion": "ausblenden"}).decode()
    assert "Rückgängig" in html and 'class="native"' in html
    html = app.markieren({"job_id": job.short_id, "aktion": "rueckgaengig", "vorher": ""}).decode()
    assert "wird wieder angezeigt" in html and tracking.load(root / "applications.csv") == []
