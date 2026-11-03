import shutil
from datetime import date

import pytest

from jobmonitor.config import ROOT
from jobmonitor.cv_build import CvBuildError, build, latex_escape, load_profile, render, tailor
from jobmonitor.cv_data import load_cv_master
from jobmonitor.models import Job
from jobmonitor.state import State
from tests.conftest import FIXTURES

PROFILE = ("name: Max Muster\nadresse: {strasse: Musterweg 1, plz: '50667', ort: Köln}\nemail: max@example.com\n"
           "telefon: '+49 221 0000000'\n")


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    shutil.copy(FIXTURES / "cv_master_example.yaml", tmp_path / "cv_master.yaml")
    (tmp_path / "cv").mkdir()
    shutil.copy(ROOT / "cv" / "template.tex.j2", tmp_path / "cv" / "template.tex.j2")
    shutil.copy(ROOT / "cv" / "profile.example.yaml", tmp_path / "cv" / "profile.example.yaml")
    (tmp_path / "cv" / "profile.yaml").write_text(PROFILE, encoding="utf-8")
    return tmp_path


def test_latex_escape():
    assert latex_escape("R&D 100% $5 #1 a_b {x} ~ ^ \\") == \
        r"R\&D 100\% \$5 \#1 a\_b \{x\} \textasciitilde{} \textasciicircum{} \textbackslash{}"
    assert latex_escape(None) == "" and latex_escape(2025) == "2025"


def test_render_general(project, cfg):
    tex = build(project, cfg, compile_pdf=False).read_text(encoding="utf-8")
    assert "Max Muster" in tex and r"Netzwerksegmentierung mit VLANs (100\% selbst gebaut)" in tex
    assert r"Virtualisierung \& Netzwerksegmentierung" in tex
    assert "Website für Sportverein" in tex and "Musterweg 1, 50667 Köln" in tex
    assert "Kubernetes-Cluster" not in tex and "Certified Kubernetes" not in tex   # im_cv: false
    assert "Grundkenntnisse in Terraform" in tex and "geboren" not in tex      # anzeigen.geburtsdatum fehlt


def test_profile_schema_fills_missing_fields(project, cfg):
    (project / "cv" / "profile.yaml").write_text("name: Nur Name\n", encoding="utf-8")
    tex = build(project, cfg, compile_pdf=False).read_text(encoding="utf-8")
    assert "Nur Name" in tex and "includegraphics" not in tex


def test_placeholder_warning(project, cfg, caplog):
    cv = (project / "cv_master.yaml").read_text(encoding="utf-8").replace('von: "03/2025"', 'von: "[Beginn]"')
    (project / "cv_master.yaml").write_text(cv, encoding="utf-8")
    build(project, cfg, compile_pdf=False)
    assert "stationen[0].von" in caplog.text and "[Beginn]" not in caplog.text


def test_tailored_puts_matching_projects_first(project, cfg):
    state = State(project / "state" / "seen.sqlite")
    job = Job("Werkstudent Cloud", "Beispiel AG", "https://x/1", "test")
    job.fit_anforderungen = {"Azure": 1.0, "Terraform": 1.0, "CI/CD": 0.5}
    state.save_job_detail(job, date(2026, 11, 1).isoformat())
    state.close()
    tex = build(project, {**cfg, "cv": {**cfg["cv"], "max_projekte_zugeschnitten": 2}}, job.short_id,
                compile_pdf=False).read_text(encoding="utf-8")
    assert tex.index("Azure Landing Zone") < tex.index("Homelab")
    assert "Sportverein" not in tex            # auf 2 Projekte begrenzt
    cv = tailor({"kenntnisse": [{"kategorie": "Web", "eintraege": ["HTML"]},
                                {"kategorie": "Cloud", "eintraege": ["Docker", "Azure"]}]},
                {"Azure": 1.0}, cfg["fit"]["begriffe"], 4)
    assert cv["kenntnisse"][0]["kategorie"] == "Cloud" and cv["kenntnisse"][0]["eintraege"][0]["name"] == "Azure"


def test_missing_profile_and_unknown_job(project, cfg):
    with pytest.raises(CvBuildError, match="nicht gefunden"):
        build(project, cfg, "deadbeef", compile_pdf=False)
    (project / "cv" / "profile.yaml").unlink()
    with pytest.raises(CvBuildError, match="profile.yaml fehlt"):
        build(project, cfg, compile_pdf=False)


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="LaTeX nur lokal installiert")
def test_pdf_build(project, cfg):
    pdf = build(project, cfg)
    assert pdf.exists() and pdf.stat().st_size > 1000


def test_repo_template_renders_repo_cv(tmp_path, monkeypatch):
    """Die echte cv/cv_master.yaml passt zur echten Vorlage (nur rendern, kein PDF)."""
    if not (ROOT / "cv" / "cv_master.yaml").exists():
        pytest.skip("keine cv/cv_master.yaml")
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    shutil.copy(ROOT / "cv" / "profile.example.yaml", tmp_path / "cv" / "profile.example.yaml")
    (tmp_path / "cv" / "profile.yaml").write_text(PROFILE, encoding="utf-8")
    cv, _ = load_cv_master(ROOT)
    tex = render(cv, load_profile(tmp_path), ROOT / "cv" / "template.tex.j2")
    assert r"\end{document}" in tex and "Max Muster" in tex
