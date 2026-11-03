import pytest

from jobmonitor.config import ROOT
from jobmonitor.cv_data import CvDataError, check_no_personal_data, covered_terms, load_cv_master
from tests.conftest import FIXTURES


def test_missing_file_disables_fit(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    assert load_cv_master(tmp_path) == (None, "keine cv_master.yaml")


def test_file_in_cv_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    (tmp_path / "cv" / "cv_master.yaml").write_text((FIXTURES / "cv_master_example.yaml").read_text("utf-8"),
                                                     encoding="utf-8")
    data, origin = load_cv_master(tmp_path)
    assert data["kenntnisse"] and origin == "cv/cv_master.yaml"


def test_secret_has_priority(tmp_path, monkeypatch):
    (tmp_path / "cv_master.yaml").write_text("kenntnisse: [Datei]\n", encoding="utf-8")
    monkeypatch.setenv("CV_MASTER_YAML", "kenntnisse: [Secret]\n")
    data, origin = load_cv_master(tmp_path)
    assert data["kenntnisse"] == ["Secret"] and "Secret" in origin


@pytest.mark.parametrize("data", [
    {"adresse": "x"},
    {"stationen": [{"foto": "bild.jpg"}]},
    {"profil": "Erreichbar unter max.muster@example.com"},
    {"projekte": [{"beschreibung": "Ruf an: +49 221 1234567"}]},
    {"Geburtsdatum": "01.01.2000"},
])
def test_personal_data_guard(data):
    with pytest.raises(CvDataError) as exc:
        check_no_personal_data(data)
    assert "1234567" not in str(exc.value) and "max.muster" not in str(exc.value)   # Werte nie in der Meldung


def test_dates_are_not_phone_numbers():
    check_no_personal_data({"stationen": [{"von": "03/2025", "bis": "2026-01-15", "jahr": 2025}]})
    check_no_personal_data({"projekte": [{"zeitraum": "10/2026 – 01/2027"}, {"zeitraum": "07/2021 - 07/2024"}],
                            "ausbildung": [{"bis": "voraussichtlich 02/2028"}], "datum": "09/2026, 01/2025"})


def test_repo_cv_master_has_no_personal_data(monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    if not (ROOT / "cv" / "cv_master.yaml").exists():
        pytest.skip("keine cv/cv_master.yaml")
    data, origin = load_cv_master(ROOT)      # wirft CvDataError, falls etwas Persönliches drinsteht
    assert origin == "cv/cv_master.yaml" and data["kenntnisse"]


def test_planned_entries_do_not_count(cfg):
    cv = {"projekte": [{"name": "X", "status": "geplant", "technologien": ["Terraform"]}],
          "zertifikate": [{"name": "AZ-104 Azure Administrator", "status": "geplant"}],
          "sprachen": [{"sprache": "Englisch", "niveau": "B2/C1"}]}
    covered = covered_terms(cv, cfg["fit"]["begriffe"])
    assert "Terraform" not in covered and "Azure" not in covered and covered["Englisch"] == 0.85


def test_invalid_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_MASTER_YAML", "kenntnisse: [unclosed\n")
    with pytest.raises(CvDataError):
        load_cv_master(tmp_path)
