import json

import responses

from jobmonitor.sources.bundesagentur import BundesagenturSource, parse_results
from tests.conftest import fixture

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc"


def test_parse_v6_fixture():
    jobs = parse_results(json.loads(fixture("ba_v6.json")))
    assert len(jobs) == 3
    first = jobs[0]
    assert first.company == "ARAG SE"
    assert first.location == "Düsseldorf"
    assert first.url.endswith("/jobdetail/10001-1003807105-S")
    assert first.distance_km is not None


def test_remote_only_filters_homeoffice():
    data = {"ergebnisliste": [
        {"stellenangebotsTitel": "A", "firma": "X", "referenznummer": "1", "homeofficemoeglich": True},
        {"stellenangebotsTitel": "B", "firma": "Y", "referenznummer": "2"},
    ]}
    jobs = parse_results(data, remote_only=True)
    assert [j.title for j in jobs] == ["A"] and jobs[0].remote


@responses.activate
def test_version_fallback(cfg, fetcher):
    bcfg = {**cfg["sources"]["bundesagentur"], "suchbegriffe": ["Werkstudent Cloud"], "bundesweit_remote": False,
            "api_versions": ["v7", "v6"]}
    responses.get(f"{BASE}/v7/jobs", status=403)
    responses.get(f"{BASE}/v6/jobs", body=fixture("ba_v6.json"), content_type="application/json")
    result = BundesagenturSource(bcfg, fetcher).fetch()
    assert len(result.jobs) == 3
    assert not result.errors
    assert any("v6" in n for n in result.notes)
    assert responses.calls[1].request.headers["X-API-Key"] == "jobboerse-jobsuche"


@responses.activate
def test_all_versions_down_reports_error(cfg, fetcher):
    bcfg = {**cfg["sources"]["bundesagentur"], "api_versions": ["v6"],
            "suchbegriffe": cfg["profile"]["werkstudent"]["suchbegriffe"]["bundesagentur"]}
    responses.get(f"{BASE}/v6/jobs", status=403)
    result = BundesagenturSource(bcfg, fetcher).fetch()
    assert result.failed
    assert len(result.errors) == 1  # bricht nach erster Suche ab statt 10x zu scheitern
