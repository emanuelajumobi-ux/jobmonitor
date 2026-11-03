import json
import shutil

import pytest
import responses

from jobmonitor import __main__ as cli
from jobmonitor import tracking
from jobmonitor.config import ROOT
from jobmonitor.eigene_stelle import StelleError, from_file, from_url
from tests.conftest import FIXTURES

ANZEIGE = """Werkstudent Cloud Operations (m/w/d)
Deine Aufgaben: Betrieb unserer Azure-Umgebung und Pflege von Entra ID.
Du automatisierst mit Terraform und PowerShell. Erfahrung mit Kubernetes ist wünschenswert.
Gute Englischkenntnisse runden dein Profil ab.
"""
PROFILE = "name: Max Muster\n"


def posting_page(description: str) -> str:
    node = {"@context": "https://schema.org", "@type": "JobPosting", "title": "Werkstudent Cloud (m/w/d)",
            "description": description, "hiringOrganization": {"@type": "Organization", "name": "Beispiel AG"},
            "jobLocation": {"address": {"addressLocality": "Köln"}}}
    return f'<html><head><script type="application/ld+json">{json.dumps(node)}</script></head><body></body></html>'


def test_from_file_uses_first_line_and_file_name(tmp_path):
    path = tmp_path / "beispiel-ag.txt"
    path.write_text("\n\n" + ANZEIGE, encoding="utf-8")
    job = from_file(path)
    assert job.title == "Werkstudent Cloud Operations (m/w/d)" and job.company == "beispiel ag"
    assert job.url == "eigene:beispiel-ag.txt" and "Terraform" in job.description
    assert from_file(path, "Beispiel AG", "https://x/1").company == "Beispiel AG"
    with pytest.raises(StelleError, match="nicht gefunden"):
        from_file(tmp_path / "fehlt.txt")


@responses.activate
def test_from_url_reads_json_ld(fetcher):
    responses.get("https://firma.example/robots.txt", status=404)
    responses.get("https://firma.example/jobs/1", body=posting_page("<p>" + ANZEIGE * 2 + "</p>"))
    job = from_url("https://firma.example/jobs/1", fetcher)
    assert job.company == "Beispiel AG" and job.title == "Werkstudent Cloud (m/w/d)"
    assert job.url == "https://firma.example/jobs/1" and "Kubernetes" in job.description


@responses.activate
def test_from_url_falls_back_to_page_text(fetcher):
    responses.get("https://firma.example/robots.txt", status=404)
    body = f"<html><body><nav>Menü</nav><main><h1>Werkstudent IT</h1><p>{ANZEIGE * 2}</p></main></body></html>"
    responses.get("https://firma.example/jobs/2", body=body)
    job = from_url("https://firma.example/jobs/2", fetcher, firma="Firma GmbH")
    assert job.title == "Werkstudent IT" and job.company == "Firma GmbH" and "Menü" not in job.description


@pytest.mark.parametrize("url", ["https://www.linkedin.com/jobs/view/1", "https://www.stepstone.de/stellenangebote--x",
                                 "https://de.indeed.com/viewjob?jk=1"])
def test_job_boards_are_never_fetched(url, fetcher):
    with pytest.raises(StelleError, match="STELLE="):
        from_url(url, fetcher)        # ohne responses-Mock: jeder echte Abruf würde hier scheitern


@responses.activate
def test_login_robots_and_javascript_pages(fetcher):
    responses.get("https://login.example/robots.txt", status=404)
    responses.get("https://login.example/job", status=403)
    with pytest.raises(StelleError, match="Login"):
        from_url("https://login.example/job", fetcher)
    responses.get("https://robots.example/robots.txt", body="User-agent: *\nDisallow: /\n")
    with pytest.raises(StelleError, match="robots.txt"):
        from_url("https://robots.example/job", fetcher)
    responses.get("https://js.example/robots.txt", status=404)
    responses.get("https://js.example/job", body="<html><body><div id='app'></div></body></html>")
    with pytest.raises(StelleError, match="JavaScript"):
        from_url("https://js.example/job", fetcher)


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    (tmp_path / "cv").mkdir()
    shutil.copy(FIXTURES / "cv_master_example.yaml", tmp_path / "cv" / "cv_master.yaml")
    for name in ("template.tex.j2", "profile.example.yaml"):
        shutil.copy(ROOT / "cv" / name, tmp_path / "cv" / name)
    (tmp_path / "cv" / "profile.yaml").write_text(PROFILE, encoding="utf-8")
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    tracking.save(tmp_path / "applications.csv", [])
    monkeypatch.setattr("jobmonitor.config.ROOT", tmp_path)
    return tmp_path


def test_cli_with_own_job_file(project, capsys):
    anzeige = project / "beispiel.txt"
    anzeige.write_text(ANZEIGE, encoding="utf-8")
    args = ["cv", "--stelle", str(anzeige), "--firma", "Beispiel AG", "--link", "https://x/1", "--nur-tex"]
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert "Fit " in out and "fehlt: Kubernetes" in out and "applications.csv eingetragen" in out
    tex = next((project / "cv" / "out").glob("lebenslauf-beispiel-ag-*.tex")).read_text(encoding="utf-8")
    assert tex.index("Azure Landing Zone") < tex.index("Homelab")       # zugeschnitten
    rows = tracking.load(project / "applications.csv")
    assert [{k: v for k, v in r.items() if k != "termin"} for r in rows] == [{"firma": "Beispiel AG", "typ": "Stelle", "status": "neu", "datum": rows[0]["datum"],
                     "link": "https://x/1", "notizen": rows[0]["notizen"]}]
    assert "selbst eingetragen" in rows[0]["notizen"]
    assert cli.main(args) == 0                                            # zweiter Aufruf: kein Duplikat
    assert "Steht schon" in capsys.readouterr().out and len(tracking.load(project / "applications.csv")) == 1


def test_cli_refuses_job_board_url(project, capsys):
    assert cli.main(["cv", "--url", "https://www.linkedin.com/jobs/view/1", "--nur-tex"]) == 1
    assert "STELLE=" in capsys.readouterr().err
    assert tracking.load(project / "applications.csv") == []
