import shutil
from datetime import date

import pytest

from jobmonitor import tracking
from jobmonitor.config import ROOT, load_config
from jobmonitor.gui import App
from jobmonitor.models import Job
from jobmonitor.report import Report
from jobmonitor.state import State
from jobmonitor.traumjob import classify
from tests.conftest import FIXTURES


@pytest.fixture
def traum_cfg():
    return load_config()["traumprofil"]


@pytest.mark.parametrize("title, text, stufe", [
    ("Werkstudent Cloud Security (m/w/d)", "", 2),
    ("Werkstudent DevSecOps", "", 2),
    ("Werkstudent IAM Azure", "", 2),
    ("Werkstudent DevOps", "Wir sichern die Azure-Umgebung mit Defender und Sentinel ab.", 1),
    ("Werkstudent IT-Sicherheit", "Du arbeitest mit Terraform und Kubernetes.", 1),
    ("Werkstudent Informationssicherheit", "ISO 27001, Richtlinien, Audits", 0),
    ("Werkstudent IT Service Desk", "Microsoft 365, Intune, Security-Updates einspielen", 0),
    ("Werkstudent Cloud Operations", "Monitoring und Betrieb", 0),
])
def test_classify(traum_cfg, title, text, stufe):
    assert classify(title, text, traum_cfg)[0] == stufe


def test_disabled(traum_cfg):
    assert classify("Werkstudent Cloud Security", "", {**traum_cfg, "enabled": False}) == (0, "")


def test_report_section_and_subject():
    stark = Job("Werkstudent Cloud Security", "A", "https://a", "t", score=80)
    stark.traum, stark.traum_grund = 2, "„cloud security“ im Titel"
    normal = Job("Werkstudent IT", "B", "https://b", "t", score=60)
    report = Report(date(2026, 11, 1), [], [normal, stark])
    text = report.render()
    assert "## ⭐ Cloud Security (1)" in text and "- ⭐⭐ [Werkstudent Cloud Security](https://a)" in text
    assert text.index("## ⭐ Cloud Security") < text.index("## Neue Stellen")
    assert "### 80 · ⭐⭐ [Werkstudent Cloud Security]" in text
    assert "⭐ 1× Cloud Security" in report.subject("[Job-Monitor]")


def test_gui_badge_filter_and_gaps(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    shutil.copy(FIXTURES / "cv_master_example.yaml", tmp_path / "cv" / "cv_master.yaml")
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    tracking.save(tmp_path / "applications.csv", [])
    state = State(tmp_path / "state" / "seen.sqlite")
    for title, url, reqs in (("Werkstudent Cloud Security", "https://x/1", {"Azure": 1, "IAM": 1, "Kubernetes": 1}),
                             ("Werkstudent IT Support", "https://x/2", {"IT-Support": 1, "Windows": 1, "SQL": 1})):
        job = Job(title, "F AG", url, "test")
        job.fit_anforderungen = reqs
        state.save_job_detail(job, "2026-11-01")
    state.close()
    app = App(tmp_path, compile_pdf=False)
    html = app.index().decode()
    assert '<span class="mark" title=' in html and "Cloud Security<span>1</span></a>" in html
    only = app.index(nur_traum=True).decode()
    assert "Werkstudent Cloud Security</a>" in only and "Werkstudent IT Support</a>" not in only
    gaps = app.luecken(nur_traum=True).decode()
    assert "nur Cloud Security-Stellen" in gaps and "Kubernetes" in gaps and "Windows" not in gaps
