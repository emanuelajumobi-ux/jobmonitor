from pathlib import Path

from ruamel.yaml import YAML

from jobmonitor.cv_data import covered_terms
from jobmonitor.fit import rate_all, requirements
from jobmonitor.models import Job
from jobmonitor.report import fit_line

CV = YAML(typ="safe").load(Path(__file__).parent.joinpath("fixtures", "cv_master_example.yaml"))

DESC = """Deine Aufgaben: Betrieb unserer Azure-Umgebung und Pflege von Entra ID.
Du automatisierst mit Terraform und PowerShell. Erfahrung mit Kubernetes ist wünschenswert.
Gute Englischkenntnisse runden dein Profil ab."""


def job(desc=DESC, title="Werkstudent Cloud Operations"):
    return Job(title=title, company="Beispiel AG", url="https://x/1", source="test", description=desc)


def test_requirements_with_synonyms_and_optional(cfg):
    reqs = requirements("Erfahrung mit Azure AD. Docker wäre von Vorteil.", cfg["fit"]["begriffe"],
                        cfg["fit"]["optional_marker"])
    assert reqs == {"Entra ID": 1.0, "Azure": 1.0, "Docker": 0.5} or reqs == {"Entra ID": 1.0, "Docker": 0.5}


def test_covered_terms_use_levels(cfg):
    covered = covered_terms(CV, cfg["fit"]["begriffe"])
    assert covered["Azure"] == 0.85 and covered["Terraform"] == 0.6 and covered["Englisch"] == 1.0
    assert covered["CI/CD"] == 0.85     # über GitHub Actions im Projekt
    assert "Kubernetes" not in covered


def test_fit_score_and_gaps(cfg):
    j = job()
    rate_all([j], CV, cfg["fit"])
    assert j.fit is not None and 60 <= j.fit <= 95
    assert "Kubernetes" in j.fit_fehlt and "Azure" in j.fit_passt
    assert j.fit_anforderungen["Kubernetes"] == 0.5
    line = fit_line(j)
    assert line.startswith(f"Fit {j.fit} %") and "fehlt: Kubernetes" in line


def test_too_few_requirements(cfg):
    j = job(desc="Wir suchen motivierte Studierende.", title="Werkstudent IT")
    rate_all([j], CV, cfg["fit"])
    assert j.fit is None and fit_line(j) in ("Fit: –", "Fit: zu wenig Angaben in der Anzeige")


def test_short_id_is_stable():
    assert job().short_id == job().short_id and len(job().short_id) == 8


def test_activities_count_as_evidence(cfg):
    covered = covered_terms(CV, cfg["fit"]["begriffe"])
    assert covered["IAM"] == 0.85          # "Benutzer- und Rechteverwaltung in Entra ID" in den Tätigkeiten
    assert covered["Scripting"] == 0.85    # PowerShell
