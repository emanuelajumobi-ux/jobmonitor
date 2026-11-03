import shutil
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from http.server import HTTPServer

import pytest

from jobmonitor import tracking
from jobmonitor.config import ROOT
from jobmonitor.gui import App, handler_for
from jobmonitor.models import Job
from jobmonitor.state import State
from tests.conftest import FIXTURES

ANZEIGE = """Werkstudent Cloud Operations (m/w/d)
Deine Aufgaben: Betrieb unserer Azure-Umgebung und Pflege von Entra ID.
Du automatisierst mit Terraform und PowerShell. Erfahrung mit Kubernetes ist wünschenswert.
"""


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    shutil.copy(FIXTURES / "cv_master_example.yaml", tmp_path / "cv" / "cv_master.yaml")
    for name in ("template.tex.j2", "profile.example.yaml"):
        shutil.copy(ROOT / "cv" / name, tmp_path / "cv" / name)
    (tmp_path / "cv" / "profile.yaml").write_text("name: Max Muster\n", encoding="utf-8")
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    tracking.save(tmp_path / "applications.csv", [])
    state = State(tmp_path / "state" / "seen.sqlite")
    job = Job("Werkstudent Cloud <Azure>", "Beispiel AG", "https://x/1", "test")
    job.fit_anforderungen = {"Azure": 1.0, "Entra ID": 1.0, "Terraform": 1.0, "Kubernetes": 1.0}
    state.save_job_detail(job, date(2026, 11, 1).isoformat())
    state.close()
    return App(tmp_path, compile_pdf=False), job.short_id


def test_index_lists_saved_jobs_with_live_fit(app):
    app, job_id = app
    html = app.index().decode()
    assert job_id in html and "Werkstudent Cloud &lt;Azure&gt;" in html     # escaped
    assert 'title="Fit 58 %"' in html and "Kubernetes: fehlt" in html and app.token in html


def test_cv_for_found_job(app):
    app, job_id = app
    html = app.make_cv({"art": "job", "job_id": job_id}).decode()
    assert "Fertig" in html and f"lebenslauf-beispiel-ag-{job_id}.tex" in html and "Fit 58 %" in html


def test_cv_for_own_job_text(app):
    app, _ = app
    html = app.make_cv({"art": "eigene", "text": ANZEIGE, "firma": "Neue Firma", "link": "https://y/2"}).decode()
    assert "Werkstudent Cloud Operations" in html and "In applications.csv eingetragen" in html
    assert list((app.root / "cv" / "stellen").glob("neue-firma-*.txt"))       # Text bleibt lokal gespeichert
    assert tracking.load(app.root / "applications.csv")[0]["link"] == "https://y/2"


def test_own_job_errors_are_shown(app):
    app, _ = app
    assert "Bitte die Firma" in app.make_cv({"art": "eigene", "text": ANZEIGE}).decode()
    assert tracking.load(app.root / "applications.csv") == []              # ohne Firma kein Eintrag
    assert "Bitte Anzeigentext" in app.make_cv({"art": "eigene", "firma": "X"}).decode()
    assert "STELLE=" in app.make_cv({"art": "eigene", "firma": "X", "url": "https://www.linkedin.com/jobs/1"}).decode()
    assert "nicht gefunden" in app.make_cv({"art": "job", "job_id": "deadbeef"}).decode()


def test_pdf_path_rejects_traversal(app):
    app, _ = app
    out = app.root / "cv" / "out"
    out.mkdir()
    (out / "lebenslauf.pdf").write_bytes(b"%PDF")
    assert app.pdf_path("lebenslauf.pdf") == out / "lebenslauf.pdf"
    assert app.pdf_path("../../config.yaml") is None and app.pdf_path("..%2Fx.pdf") is None


def test_http_requires_token(app):
    app, job_id = app
    server_ref = []
    server = HTTPServer(("127.0.0.1", 0), handler_for(app, server_ref))
    server_ref.append(server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert job_id in urllib.request.urlopen(base + "/").read().decode()
        data = urllib.parse.urlencode({"art": "allgemein", "token": "falsch"}).encode()
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(base + "/cv", data=data)
        assert exc.value.code == 403
        data = urllib.parse.urlencode({"art": "allgemein", "token": app.token}).encode()
        assert "Allgemeiner Lebenslauf" in urllib.request.urlopen(base + "/cv", data=data).read().decode()
    finally:
        server.shutdown()
        server.server_close()


def test_layout_nav_and_own_job_page(app):
    app, _ = app
    html = app.eigene().decode()
    assert 'class="side"' in html and 'href="/eigene" class="active"' in html and 'name="firma" required' in html
    assert 'data-token="' + app.token + '"' in html


def test_open_file_only_known_pdfs(app, monkeypatch):
    app, _ = app
    out = app.root / "cv" / "out"
    out.mkdir()
    (out / "lebenslauf.pdf").write_bytes(b"%PDF")
    opened = []
    monkeypatch.setattr("jobmonitor.gui.subprocess.run", lambda cmd, **kw: opened.append(cmd))
    assert app.open_file("/pdf/lebenslauf.pdf") and opened == [["open", str(out / "lebenslauf.pdf")]]
    assert not app.open_file("/pdf/../../config.yaml") and not app.open_file("/etc/passwd")
    assert len(opened) == 1
