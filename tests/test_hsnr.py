import re
from datetime import date

import responses

from jobmonitor.sources import hsnr
from jobmonitor.state import State
from tests.conftest import fixture

URL = "https://www.hs-niederrhein.de/stellenboerse/"


def test_parse_list():
    rows, nxt = hsnr.parse_list(fixture("hsnr_page1.html"), URL)
    assert len(rows) >= 10
    first = rows[0]
    assert first.stellentyp == "Werkstudentenstellen"
    assert first.titel == "Werkstudent*in Informatik"
    assert first.standort == "41066 Mönchengladbach"
    assert first.url.startswith("https://www.hs-niederrhein.de/fileadmin/") and first.url.endswith(".pdf")
    assert nxt and "currentPage%5D=2" in nxt


def _source(cfg, fetcher, state, max_pages=1):
    scfg = {**cfg["sources"]["hsnr"], "max_pages": max_pages}
    return hsnr.HsnrSource(scfg, cfg["filter"]["fach"], fetcher, state, date(2026, 10, 31))


@responses.activate
def test_fetch_reads_pdf_only_for_it_rows(cfg, fetcher, tmp_path, monkeypatch):
    responses.get(URL + "robots.txt", status=404)
    responses.get(URL, body=fixture("hsnr_page1.html"))
    pdf_calls = []

    def pdf_callback(request):
        pdf_calls.append(request.url)
        return 200, {}, b"%PDF"

    responses.add_callback(responses.GET, re.compile(r"https://www\.hs-niederrhein\.de/.*\.pdf"), callback=pdf_callback)
    monkeypatch.setattr(hsnr, "pdf_text", lambda data: "Wir nutzen Azure und Terraform. Homeoffice möglich.")
    state = State(tmp_path / "s.sqlite")
    result = _source(cfg, fetcher, state).fetch()
    assert not result.errors
    titles = [j.title for j in result.jobs]
    assert "Werkstudent*in Informatik" in titles
    assert "Praktikant (M/w/d) im Social Media Management" not in titles  # kein IT-Bezug → kein PDF
    assert len(pdf_calls) == len(result.jobs)
    assert result.jobs[0].remote


@responses.activate
def test_incremental_stops_at_known_entries(cfg, fetcher, tmp_path, monkeypatch):
    responses.get(URL + "robots.txt", status=404)
    responses.get(URL, body=fixture("hsnr_page1.html"))
    monkeypatch.setattr(hsnr.HsnrSource, "_to_job", lambda self, row, res: None)
    state = State(tmp_path / "s.sqlite")
    rows, _ = hsnr.parse_list(fixture("hsnr_page1.html"), URL)
    for r in rows[1:]:
        state.mark_crawled("hsnr", r.url, "2026-10-28")
    result = _source(cfg, fetcher, state, max_pages=5).fetch()
    # Nur Seite 1 wird geladen, weil dort bereits bekannte Einträge stehen
    assert sum(1 for c in responses.calls if c.request.url.startswith(URL) and "robots" not in c.request.url) == 1
    assert "1 Seite(n) gelesen" in result.notes
