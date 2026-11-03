"""Arbeitnow (freie Job-Board-API) und Adzuna (offizielle Such-API mit eigenem Zugang) – ohne echte Abfragen."""
import re
import time

import responses

from jobmonitor.http import Fetcher
from jobmonitor.models import SourceResult
from jobmonitor.report import Report
from jobmonitor.sources import adzuna, arbeitnow

JETZT = 1_793_000_000


def fetcher():
    return Fetcher("job-monitor-test/0.1", min_delay=0, sleep=lambda s: None)


def an_item(i, alter_tage, **kw):
    return {"slug": f"job-{i}", "company_name": "Beispiel GmbH", "title": f"Werkstudent Cloud {i}",
            "description": "<p>Du arbeitest mit <b>Azure</b> und Terraform.</p>", "remote": False,
            "url": f"https://www.arbeitnow.com/jobs/companies/beispiel/job-{i}", "tags": ["Cloud"],
            "job_types": ["working student"], "location": "Köln", "created_at": JETZT - alter_tage * 86400, **kw}


@responses.activate
def test_arbeitnow_liest_bis_zur_altersgrenze():
    responses.get("https://www.arbeitnow.com/robots.txt", body="User-agent: *\nDisallow:\n")
    responses.get(re.compile(r"https://www\.arbeitnow\.com/api/job-board-api\?page=1$"), json={
        "data": [an_item(1, 1), an_item(2, 3, remote=True, location="Berlin")], "links": {"next": "x"}})
    responses.get(re.compile(r"https://www\.arbeitnow\.com/api/job-board-api\?page=2$"), json={
        "data": [an_item(3, 10), an_item(4, 20)], "links": {"next": "x"}})
    result = arbeitnow.ArbeitnowSource({"tage": 14, "max_seiten": 10}, fetcher(), jetzt=JETZT).fetch()
    assert [j.title for j in result.jobs] == ["Werkstudent Cloud 1", "Werkstudent Cloud 2", "Werkstudent Cloud 3"]
    assert len(responses.calls) == 3                         # robots.txt + 2 Seiten, Seite 3 nicht mehr nötig
    j = result.jobs[0]
    assert j.description.startswith("Du arbeitest mit Azure und Terraform.") and "Cloud" in j.description
    assert j.location == "Köln" and j.kind == "working student" and result.jobs[1].remote
    assert j.posted == time.strftime("%Y-%m-%d", time.gmtime(JETZT - 86400))


@responses.activate
def test_arbeitnow_seitenlimit_und_robots():
    responses.get("https://www.arbeitnow.com/robots.txt", body="User-agent: *\nDisallow: /api\n")
    result = arbeitnow.ArbeitnowSource({"tage": 14, "max_seiten": 2}, fetcher(), jetzt=JETZT).fetch()
    assert result.jobs == [] and "robots.txt verbietet" in result.errors[0]


ADZ = {"results": [{"id": 4711, "title": "Junior <strong>Cloud</strong> Security Engineer (m/w/d)",
                    "company": {"display_name": "Beispiel AG"}, "location": {"display_name": "Köln, Nordrhein-Westfalen"},
                    "description": "Wir suchen ... Azure, Entra ID, hybrides Arbeiten / Homeoffice möglich",
                    "redirect_url": "https://www.adzuna.de/land/ad/4711?se=x", "created": "2026-11-02T08:00:00Z",
                    "contract_time": "full_time"}]}


@responses.activate
def test_adzuna_ohne_zugang_wird_uebersprungen(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    result = adzuna.AdzunaSource({}, fetcher(), ["Junior Cloud"]).fetch()
    assert result.jobs == [] and not result.errors and "kein Zugang" in result.notes[0]
    assert len(responses.calls) == 0


@responses.activate
def test_adzuna_suche(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "geheim456")
    responses.get(re.compile(r"https://api\.adzuna\.com/v1/api/jobs/de/search/1\?.*"), json=ADZ)
    src = adzuna.AdzunaSource({"max_begriffe": 2, "wo": "Köln", "umkreis_km": 50, "tage": 7}, fetcher(),
                              ["Junior Cloud", "Junior IAM", "Junior DevOps"], "Junior")
    result = src.fetch()
    assert src.name == "Adzuna (Junior)" and len(responses.calls) == 2      # nur max_begriffe Abfragen
    j = result.jobs[0]
    assert j.title == "Junior Cloud Security Engineer (m/w/d)" and j.company == "Beispiel AG" and j.remote
    assert j.posted == "2026-11-02" and j.url.startswith("https://www.adzuna.de/")
    q = responses.calls[0].request.url
    assert "what=Junior+Cloud" in q and "distance=50" in q and "max_days_old=7" in q and "robots" not in q


@responses.activate
def test_adzuna_fehler_ohne_schluessel_im_text(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "geheim456")
    responses.get(re.compile(r"https://api\.adzuna\.com/.*"), status=401)
    result = adzuna.AdzunaSource({}, fetcher(), ["A", "B"]).fetch()
    assert len(result.errors) == 1 and "401" in result.errors[0]           # nach 401 keine weiteren Suchen
    assert "geheim456" not in result.errors[0] and "id123" not in result.errors[0]


def test_ruecklink_im_bericht():
    from datetime import date
    text = Report(date(2026, 11, 3), [SourceResult(n, notes=["x"]) for n in
                                      ("Arbeitnow", "Adzuna (Junior)", "Bundesagentur für Arbeit")], []).render()
    assert "[Arbeitnow](https://www.arbeitnow.com)" in text and "[Adzuna (Junior)](https://www.adzuna.de)" in text
    assert "**Bundesagentur für Arbeit**" in text
