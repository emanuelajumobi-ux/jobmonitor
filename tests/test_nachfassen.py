"""Nachfassen: Entwurf aus Vorlage, Bewerbungsordner und profile.yaml; Markieren; Seite Bewerbungen."""
import shutil
from datetime import date, timedelta

from jobmonitor import bewerbung as bw
from jobmonitor import nachfassen, tracking
from jobmonitor.config import ROOT, load_config
from jobmonitor.gui import App
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)

ROW = {"firma": "Beispiel AG", "typ": "Stelle", "status": "beworben", "datum": "2026-10-01", "link": "https://x/1",
       "notizen": ""}


def test_draft_from_workspace(root):  # noqa: F811
    shutil.copy(ROOT / "cv" / "nachfassen_vorlage.txt", root / "cv" / "nachfassen_vorlage.txt")
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    bw.save_letter(folder, "Text", "Sehr geehrte Frau Schmidt,", "")
    betreff, text = nachfassen.entwurf(root, cfg, ROW)
    assert betreff == "Nachfrage zu meiner Bewerbung als Werkstudent Cloud Operations"
    assert text.startswith("Sehr geehrte Frau Schmidt,") and "am 01.10.2026 habe ich mich" in text
    assert text.endswith("Max Muster") and "{" not in text and "#" not in text
    assert "Unterlagen oder Informationen" in text                   # aus cv/nachfassen_vorlage.txt


def test_draft_without_workspace(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    row = {**ROW, "link": "https://y/2", "notizen": "Junior Cloud Engineer (m/w/d) (Score 72)\nRückruf erbeten"}
    betreff, text = nachfassen.entwurf(root, cfg, row)
    assert betreff.endswith("als Junior Cloud Engineer") and text.startswith("Sehr geehrte Damen und Herren,")
    betreff, text = nachfassen.entwurf(root, cfg, {**row, "notizen": "", "typ": "Initiativ", "datum": "kaputt"})
    assert betreff == "Nachfrage zu meiner Bewerbung (Initiativbewerbung)"
    assert "am [Datum] habe ich mich bei Ihnen initiativ beworben" in text
    assert "[Stellentitel]" in nachfassen.entwurf(root, cfg, {**row, "notizen": ""})[0]


def test_draft_without_template_file(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    cfg["tracking"]["nachfassen_vorlage"] = "gibt/es/nicht.txt"
    betreff, text = nachfassen.entwurf(root, cfg, {**ROW, "link": "https://y/2", "notizen": "Werkstudent IT"})
    assert betreff == "Nachfrage zu meiner Bewerbung als Werkstudent IT" and "Max Muster" in text


def test_mark_keeps_application_date():
    rows = [dict(ROW, notizen="Telefonat geplant"), dict(ROW, link="https://z/3", status="Absage")]
    row = nachfassen.markieren(rows, "https://x/1", date(2026, 11, 1))
    assert row["status"] == "nachgefasst" and row["datum"] == "2026-10-01"
    assert row["notizen"] == "Telefonat geplant\nNachgefasst am 01.11.2026"
    assert nachfassen.markieren(rows, "https://x/1", date(2026, 11, 2)) is None     # schon nachgefasst
    assert nachfassen.markieren(rows, "https://z/3", date(2026, 11, 2)) is None     # nicht „beworben“
    assert tracking.follow_ups(rows, date(2026, 12, 1), 21) == []
    assert "nachgefasst" in tracking.STATUSES


def test_page_shows_draft_and_marks(root):  # noqa: F811
    old = (date.today() - timedelta(days=30)).isoformat()
    tracking.save(root / "applications.csv", [dict(ROW, datum=old, notizen="Werkstudent IT <b>"),
                                              dict(ROW, link="https://y/2", datum=date.today().isoformat())])
    app = App(root, compile_pdf=False)
    html = app.bewerbungen().decode()
    assert "Entwurf für die Nachfrage" in html and "Nachfrage zu meiner Bewerbung als Werkstudent IT &lt;b&gt;" in html
    assert html.count("Als nachgefasst markieren") == 1 and 'data-copy="nf-t0"' in html
    html = app.nachgefasst({"link": "https://x/1"}).decode()
    assert "als nachgefasst markiert" in html and "Entwurf für die Nachfrage" not in html
    assert tracking.load(root / "applications.csv")[0]["status"] == "nachgefasst"
    assert "nicht gefunden" in app.nachgefasst({"link": "https://x/1"}).decode()
