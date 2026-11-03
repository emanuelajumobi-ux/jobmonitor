from datetime import date

import responses

from jobmonitor.initiativ import find_initiativ_link, update_entry
from jobmonitor.sources.ats import jsonld, personio
from jobmonitor.sources.companies import CompaniesSource, detect_ats
from tests.conftest import fixture

INOVEX = "https://www.inovex.de/de/karriere/stellenangebote/"
RHEIN = "https://www.rheinenergie.com/karriere/jobs/stellenangebote/"


def test_detect_ats():
    assert detect_ats('<a href="https://usd-ag.jobs.personio.de/">Jobs</a>', "https://www.usd.de/karriere/") == \
        ("personio", "usd-ag")
    assert detect_ats('<script src="https://boards.greenhouse.io/embed/job_board?for=acme"></script>', "x") == \
        ("greenhouse", "acme")
    assert detect_ats("", "https://jobs.lever.co/foo") == ("lever", "foo")
    assert detect_ats('<script src="/rexx/js"></script>', "x") == ("rexx", None)
    assert detect_ats("<html></html>", "https://example.com/karriere") == ("jsonld", None)


def test_personio_feed():
    jobs = personio.parse(fixture("personio_usd.xml"), "usd-ag", "usd", "Firmen")
    assert len(jobs) == 8
    assert jobs[0].url == "https://usd-ag.jobs.personio.de/job/959522"
    assert jobs[0].location == "Neu-Isenburg"
    assert "Systemintegration" in jobs[0].title


def test_jsonld_detail_page():
    jobs = jsonld.parse_postings(fixture("inovex_detail.html"), "https://x/thesis", "inovex", "Firmen")
    assert len(jobs) == 1
    assert "Thesis" in jobs[0].title and "Cloud" in jobs[0].title
    assert "IAM" in jobs[0].description


def test_job_links_only_role_slugs():
    role, all_links = jsonld.job_links(fixture("inovex_jobs.html"), INOVEX)
    assert any("werkstudent" in u for u in role)
    assert any("thesis-bachelor" in u for u in role)
    assert not any("senior" in u for u in role)
    assert len(all_links) > len(role)


def test_initiativ_link_detection():
    assert find_initiativ_link(fixture("inovex_jobs.html"), INOVEX) == \
        "https://www.inovex.de/de/karriere/stellenangebote/initiativbewerbung/"
    assert find_initiativ_link(fixture("rheinenergie_stellen.html"), RHEIN) == \
        "https://www.rheinenergie.com/karriere/jobs/initiativbewerbung/"
    assert find_initiativ_link("<a href='/kontakt'>Kontakt</a>", "https://x") is None


def test_update_entry_keeps_manual_values():
    entry = {"initiativ": {"moeglich": "ja", "url": "https://bank/initiativ", "zuletzt_geprueft": None}}
    assert update_entry(entry, None, "2026-10-31") is False
    assert entry["initiativ"]["moeglich"] == "ja"
    entry2 = {"initiativ": {"moeglich": "unbekannt", "url": None, "zuletzt_geprueft": None}}
    assert update_entry(entry2, "https://x/initiativ", "2026-10-31") is True
    assert entry2["initiativ"] == {"moeglich": "ja", "url": "https://x/initiativ", "zuletzt_geprueft": "2026-10-31"}


@responses.activate
def test_companies_source_end_to_end(cfg, fetcher):
    for host in ("https://www.inovex.de", "https://www.rheinenergie.com", "https://www.usd.de"):
        responses.get(f"{host}/robots.txt", body="User-agent: *\nDisallow: /wp-admin/\n")
    responses.get(INOVEX, body=fixture("inovex_jobs.html"))
    # Alle Detailseiten liefern die Thesis-Seite
    import re
    responses.get(re.compile(r"https://www\.inovex\.de/de/karriere/stellenangebote/.+/"),
                  body=fixture("inovex_detail.html"))
    responses.get(RHEIN, body=fixture("rheinenergie_stellen.html"))
    responses.get("https://www.usd.de/karriere/", body='<a href="https://usd-ag.jobs.personio.de/">Jobs</a>')
    responses.get("https://usd-ag.jobs.personio.de/xml", body=fixture("personio_usd.xml"))

    doc = {"firmen": [
        {"name": "inovex", "karriereseite_url": INOVEX, "standorte": ["Köln", "Remote"]},
        {"name": "RheinEnergie", "karriereseite_url": RHEIN, "standorte": ["Köln"]},
        {"name": "usd", "karriereseite_url": "https://www.usd.de/karriere/"},
    ]}
    src = CompaniesSource(doc, cfg["sources"]["companies"], fetcher, date(2026, 10, 31))
    result = src.fetch()
    assert not result.errors
    by_company = {}
    for j in result.jobs:
        by_company.setdefault(j.company, []).append(j)
    assert len(by_company["usd"]) == 8
    assert by_company["inovex"]  # Detailseiten mit JSON-LD
    assert doc["firmen"][2]["ats"] == "personio" and doc["firmen"][2]["ats_id"] == "usd-ag"
    assert doc["firmen"][1]["initiativ"]["moeglich"] == "ja"
    assert any(m.startswith("RheinEnergie") for m in result.manual_check)
    assert src.outcomes["RheinEnergie"].initiativ_neu


@responses.activate
def test_robots_disallow_goes_to_manual_check(cfg, fetcher):
    responses.get("https://blocked.example/robots.txt", body="User-agent: *\nDisallow: /\n")
    doc = {"firmen": [{"name": "Blocked", "karriereseite_url": "https://blocked.example/jobs"}]}
    result = CompaniesSource(doc, cfg["sources"]["companies"], fetcher, date(2026, 10, 31)).fetch()
    assert result.manual_check and "robots.txt" in result.manual_check[0]
    assert len(responses.calls) == 1  # Karriereseite selbst wurde nicht abgerufen
