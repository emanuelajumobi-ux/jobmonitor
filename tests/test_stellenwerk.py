from datetime import date

import responses

from jobmonitor.sources.stellenwerk import StellenwerkSource, interesting, search_links
from jobmonitor.state import State
from tests.conftest import fixture

SEARCH = ('<a href="/koeln/werkstudent-cloud-security-mwd-261020-278900">x</a>'
          '<a href="/koeln/spass-am-waffel-backen-dann-komm-zu-uns-ins-waffelhaus-261016-278467">y</a>'
          '<a href="/koeln/events">z</a>')


def test_search_links_and_filter():
    links = search_links(SEARCH, "koeln")
    assert len(links) == 2
    assert [interesting(u) for u in links] == [True, False]


@responses.activate
def test_fetch_reads_detail_once(cfg, fetcher, tmp_path):
    scfg = {**cfg["sources"]["stellenwerk"], "suchbegriffe": ["Cloud"]}
    responses.get("https://www.stellenwerk.de/koeln", body=SEARCH)
    responses.get("https://www.stellenwerk.de/koeln/werkstudent-cloud-security-mwd-261020-278900",
                  body=fixture("inovex_detail.html"))
    state = State(tmp_path / "s.sqlite")
    portals = [{"name": "Stellenwerk Köln", "karriereseite_url": "https://www.stellenwerk.de/koeln"}]
    src = StellenwerkSource(portals, scfg, fetcher, state, date(2026, 10, 31))
    first = src.fetch()
    assert len(first.jobs) == 1 and not first.errors
    assert not any("robots.txt" in c.request.url for c in responses.calls)
    second = src.fetch()   # Detailseite ist jetzt bekannt
    assert second.jobs == []


@responses.activate
def test_utf8_without_charset_header(fetcher):
    responses.get("https://x.example/robots.txt", status=404)
    responses.get("https://x.example/a", body="Köln".encode("utf-8"), content_type="text/html")
    assert fetcher.get("https://x.example/a").text == "Köln"
