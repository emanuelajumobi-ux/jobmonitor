import shutil
from pathlib import Path
from datetime import date, datetime, timedelta

import responses

from jobmonitor import tracking
from jobmonitor.config import ROOT
from jobmonitor.models import Job, SourceResult
from jobmonitor.report import Report
from jobmonitor.runner import Options, dedupe, run
from jobmonitor.state import State
from tests.conftest import fixture


def test_is_due(tmp_path):
    s = State(tmp_path / "s.sqlite")
    now = datetime(2026, 10, 31, 7, 0)
    assert s.is_due(now, 3)
    s.set_last_success(now - timedelta(days=2))
    assert not s.is_due(now, 3, 3)
    s.set_last_success(now - timedelta(days=3, minutes=-30))   # Cron ein paar Minuten früher als letztes Mal
    assert s.is_due(now, 3, 3)


def test_hand_lauf_am_abend_blockiert_den_morgen_nicht(tmp_path):
    from zoneinfo import ZoneInfo
    berlin = ZoneInfo("Europe/Berlin")
    s = State(tmp_path / "s.sqlite")
    s.set_last_success(datetime(2026, 11, 2, 21, 17, tzinfo=berlin))
    assert not s.is_due(datetime(2026, 11, 2, 23, 50, tzinfo=berlin), 1)
    assert s.is_due(datetime(2026, 11, 3, 0, 30, tzinfo=berlin), 1)
    assert s.is_due(datetime(2026, 11, 3, 0, 30, tzinfo=ZoneInfo("UTC")).astimezone(berlin), 1)


def test_dedupe_merges_sources():
    a = Job("Werkstudent Cloud (m/w/d)", "inovex GmbH", "u1", "BA", score=70)
    b = Job("Werkstudent*in Cloud", "inovex", "u2", "Firmen", score=80)
    out = dedupe([a, b])
    assert len(out) == 1 and out[0].url == "u2" and out[0].source == "Firmen + BA"


def test_follow_ups():
    rows = [{"firma": "A", "typ": "Stelle", "status": "beworben", "datum": "2026-10-01", "link": ""},
            {"firma": "B", "typ": "Stelle", "status": "beworben", "datum": "2026-10-25", "link": ""},
            {"firma": "C", "typ": "Stelle", "status": "Absage", "datum": "2026-09-01", "link": ""}]
    due = tracking.follow_ups(rows, date(2026, 10, 31), 21)
    assert [r["firma"] for r in due] == ["A"]


def test_report_lists_errors_first():
    r = Report(date(2026, 10, 31), [SourceResult("BA", errors=["403"]),
                                    SourceResult("Firmen", manual_check=["X: JavaScript"])], [])
    text = r.render()
    assert text.index("❌ **BA**") < text.index("## Neue Stellen")
    assert "Manuell prüfen" in text and "X: JavaScript" in text
    assert "ausgefallen" in r.subject("Job-Monitor")


@responses.activate
def test_full_run_offline(tmp_path, monkeypatch):
    for name in ("config.yaml", "companies.yaml"):
        shutil.copy(ROOT / name, tmp_path / name)
    (tmp_path / "applications.csv").write_text("firma,typ,status,datum,link,notizen,termin\n", encoding="utf-8")
    # Nur die drei MVP-Firmen, damit der Test keine weiteren Seiten braucht
    from jobmonitor.config import load_companies, save_companies
    doc = load_companies(tmp_path / "companies.yaml")
    keep = {"inovex", "usd", "RheinEnergie"}
    for i in reversed(range(len(doc["firmen"]))):
        if doc["firmen"][i]["name"] not in keep:
            del doc["firmen"][i]
    save_companies(doc, tmp_path / "companies.yaml")
    import re
    responses.get(re.compile(r"https://rest\.arbeitsagentur\.de/.*/v6/jobs.*"), json={"ergebnisliste": [{
        "stellenangebotsTitel": "Werkstudent Cloud Security Azure (m/w/d)", "firma": "Beispiel AG",
        "referenznummer": "123-S", "stellenlokationen": [{"adresse": {"ort": "Köln"}}], "entfernung": 2,
        "homeofficemoeglich": True}]})
    responses.get(re.compile(r"https://[^/]+/robots\.txt"), status=404)
    responses.get("https://www.hs-niederrhein.de/stellenboerse/", body=fixture("hsnr_page1.html"))
    responses.get(re.compile(r"https://www\.hs-niederrhein\.de/.*"), body=fixture("hsnr_page1.html"))
    responses.get("https://www.inovex.de/de/karriere/stellenangebote/", body=fixture("inovex_jobs.html"))
    responses.get(re.compile(r"https://www\.inovex\.de/de/karriere/stellenangebote/.+/"),
                  body=fixture("inovex_detail.html"))
    responses.get("https://www.usd.de/karriere/", body='<a href="https://usd-ag.jobs.personio.de/">Jobs</a>')
    responses.get(re.compile(r"https://usd-ag\.jobs\.personio\.de/xml.*"), body=fixture("personio_usd.xml"))
    responses.get("https://www.rheinenergie.com/karriere/jobs/stellenangebote/", body=fixture("rheinenergie_stellen.html"))
    monkeypatch.setattr("jobmonitor.sources.hsnr.pdf_text", lambda data: "")
    monkeypatch.setattr("jobmonitor.http.time.sleep", lambda s: None)
    for var in ("SMTP_USER", "IMAP_USER", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    assert run(Options(force=True, no_mail=True, root=tmp_path)) == 0
    reports = list((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "Werkstudent Cloud Security Azure" in text
    assert "## Initiativ möglich" in text and "RheinEnergie" in text
    assert "ats: personio" in (tmp_path / "companies.yaml").read_text(encoding="utf-8")
    assert "# Firmen und Hochschul-Stellenbörsen." in (tmp_path / "companies.yaml").read_text(encoding="utf-8")
    assert "Fit-Rating aus: keine cv_master.yaml" in text   # ohne Lebenslauf läuft alles wie bisher
    assert list((tmp_path / "drafts").glob("*rheinenergie.md"))

    # Zweiter Lauf ohne --force: übersprungen. Mit --force: keine Stelle doppelt gemeldet.
    assert run(Options(no_mail=True, root=tmp_path)) == 0
    assert run(Options(force=True, no_mail=True, root=tmp_path)) == 0
    text2 = reports[0].read_text(encoding="utf-8")
    assert "Werkstudent Cloud Security Azure" not in text2


def test_telekom_warning_flag():
    from jobmonitor.runner import add_warnings
    doc = {"firmen": [{"name": "Deutsche Telekom", "match_namen": ["Telekom"], "warnhinweis": "Vorgabe des Arbeitgebers prüfen"},
                      {"name": "T-Systems", "match_namen": ["T-Systems"], "warnhinweis": "Vorgabe des Arbeitgebers prüfen"}]}
    jobs = [Job("Werkstudent Cloud", "Telekom Deutschland GmbH", "u1", "BA"),
            Job("Werkstudent Cloud", "T-Systems International GmbH", "u2", "BA"),
            Job("Werkstudent Cloud", "inovex", "u3", "BA")]
    add_warnings(jobs, doc)
    assert [bool(j.flags) for j in jobs] == [True, True, False]


@responses.activate
def test_full_run_with_cv_master_shows_fit(tmp_path, monkeypatch):
    import re
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    (tmp_path / "applications.csv").write_text("firma,typ,status,datum,link,notizen,termin\n", encoding="utf-8")
    (tmp_path / "companies.yaml").write_text("firmen: []\nhochschulen: []\n", encoding="utf-8")
    shutil.copy(Path(__file__).parent / "fixtures" / "cv_master_example.yaml", tmp_path / "cv_master.yaml")
    responses.get(re.compile(r"https://rest\.arbeitsagentur\.de/.*/v6/jobs.*"), json={"ergebnisliste": [{
        "stellenangebotsTitel": "Werkstudent Cloud Security Azure (m/w/d)", "firma": "Beispiel AG",
        "referenznummer": "123-S", "stellenlokationen": [{"adresse": {"ort": "Köln"}}], "entfernung": 2,
        "alleBerufe": ["Azure", "Entra ID", "Terraform", "Kubernetes"]}]})
    for var in ("SMTP_USER", "IMAP_USER", "ANTHROPIC_API_KEY", "CV_MASTER_YAML"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("jobmonitor.http.time.sleep", lambda s: None)
    assert run(Options(force=True, no_mail=True, root=tmp_path, only="bundesagentur")) == 0
    text = next((tmp_path / "reports").glob("*.md")).read_text(encoding="utf-8")
    assert "Fit 58 %" in text   # (0,85 Azure + 0,85 Entra ID + 0,6 Terraform + 0 Kubernetes) / 4
    assert "fehlt: Kubernetes" in text and "ID `" in text
    state = State(tmp_path / "state" / "seen.sqlite")
    job_id = re.search(r"ID `([0-9a-f]{8})`", text).group(1)
    assert state.job_detail(job_id)["anforderungen"]["Kubernetes"] == 1.0


@responses.activate
def test_ba_details_feed_fit(tmp_path, monkeypatch):
    """Nur die Berufsbezeichnungen reichen nicht für den Fit; der nachgeladene Anzeigentext schon."""
    import base64
    import re
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    (tmp_path / "applications.csv").write_text("firma,typ,status,datum,link,notizen,termin\n", encoding="utf-8")
    (tmp_path / "companies.yaml").write_text("firmen: []\nhochschulen: []\n", encoding="utf-8")
    shutil.copy(Path(__file__).parent / "fixtures" / "cv_master_example.yaml", tmp_path / "cv_master.yaml")
    responses.get(re.compile(r"https://rest\.arbeitsagentur\.de/.*/v6/jobs.*"), json={"ergebnisliste": [{
        "stellenangebotsTitel": "Werkstudent Cloud Security Azure (m/w/d)", "firma": "Beispiel AG",
        "referenznummer": "123-S", "stellenlokationen": [{"adresse": {"ort": "Köln"}}], "entfernung": 2,
        "alleBerufe": ["IT-Sicherheit"]}]})
    b64 = base64.b64encode(b"123-S").decode()
    detail = responses.get(f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{b64}",
                           body=fixture("ba_jobdetails_v4.json"))
    for var in ("SMTP_USER", "IMAP_USER", "ANTHROPIC_API_KEY", "CV_MASTER_YAML"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("jobmonitor.http.time.sleep", lambda s: None)
    assert run(Options(force=True, no_mail=True, root=tmp_path, only="bundesagentur")) == 0
    text = next((tmp_path / "reports").glob("*.md")).read_text(encoding="utf-8")
    assert detail.call_count == 1
    assert "fehlt: Kubernetes" in text and "passt: Azure" in text


@responses.activate
def test_ba_partner_page_fallback(fetcher):
    from jobmonitor.config import load_config
    from jobmonitor.models import Job
    from jobmonitor.sources.bundesagentur import NAME, BundesagenturSource
    import re
    responses.get(re.compile(r".*/v4/jobdetails/.*"), status=404)
    responses.get("https://partner.example/robots.txt", status=404)
    responses.get("https://partner.example/job/1", body="<html><body><main><h1>Werkstudent</h1><p>"
                  + "Du arbeitest mit Azure und Terraform. " * 10 + "</p></main></body></html>")
    jobs = [Job("Werkstudent", "X", "https://partner.example/job/1", NAME, external_id="1-S"),
            Job("Werkstudent", "Y", "https://www.linkedin.com/jobs/view/1", NAME, external_id="2-S")]
    src = BundesagenturSource(load_config()["sources"]["bundesagentur"], fetcher)
    assert src.add_details(jobs) == 1
    assert "Terraform" in jobs[0].description and "Terraform" not in jobs[1].description


@responses.activate
def test_pipeline_does_not_fill_applications_by_default(tmp_path, monkeypatch):
    import re
    from jobmonitor import tracking
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    tracking.save(tmp_path / "applications.csv", [])
    (tmp_path / "companies.yaml").write_text("firmen: []\nhochschulen: []\n", encoding="utf-8")
    responses.get(re.compile(r"https://rest\.arbeitsagentur\.de/.*/v6/jobs.*"), json={"ergebnisliste": [{
        "stellenangebotsTitel": "Werkstudent Cloud Security Azure (m/w/d)", "firma": "Beispiel AG",
        "referenznummer": "123-S", "stellenlokationen": [{"adresse": {"ort": "Köln"}}], "entfernung": 2,
        "alleBerufe": ["Azure", "Entra ID", "Terraform"]}]})
    for var in ("SMTP_USER", "IMAP_USER", "ANTHROPIC_API_KEY", "CV_MASTER_YAML"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("jobmonitor.http.time.sleep", lambda s: None)
    assert run(Options(force=True, no_mail=True, root=tmp_path, only="bundesagentur")) == 0
    assert "Werkstudent Cloud Security" in next((tmp_path / "reports").glob("*.md")).read_text(encoding="utf-8")
    assert tracking.load(tmp_path / "applications.csv") == []


def test_firmenfehler_nur_bei_der_firma():
    from jobmonitor import quellen_verlauf
    r = SourceResult("Firmen-Karriereseiten", jobs=[Job("Werkstudent", "A", "https://a/1", "x")],
                     teilfehler=["Zurich: 404 Client Error"])
    assert quellen_verlauf.source_status(r) == "ok" and not r.failed
    assert SourceResult("Firmen-Karriereseiten", teilfehler=["Zurich: 404"]).failed     # alle Firmen kaputt: Ausfall
    text = Report(date(2026, 11, 3), [r], [], [], [], "", "Traumprofil", {"werkstudent": "Werkstudent"}, []).render()
    assert "- ✅ **Firmen-Karriereseiten**: 1 Rohtreffer" in text and "  - Nicht erreichbar: Zurich: 404" in text
    from jobmonitor import gui_bericht as gbe
    b = gbe.parse(text)
    assert b.quellen[0].status == "ok" and b.quellen[0].teilfehler == ["Zurich: 404 Client Error"]
    html = gbe.render(b, [], "")
    assert "Nicht erreichbar: Zurich" in html and 'class="err"' not in html
