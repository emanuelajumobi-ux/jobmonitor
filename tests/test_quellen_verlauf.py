"""Quellen beobachten: Verlauf speichern, Warnregeln, Firmen-Status, Bericht und Oberfläche."""
import re
import shutil
from datetime import date

import responses

from jobmonitor import gui_firmen as gf
from jobmonitor import quellen_verlauf as qv
from jobmonitor.config import ROOT
from jobmonitor.models import SourceResult
from jobmonitor.report import Report
from jobmonitor.sources.companies import CompaniesSource, CompanyOutcome
from jobmonitor.state import State


def hist(*entries):
    """Einträge älteste zuerst angeben, wie man sie liest; der Verlauf ist neueste zuerst."""
    days = [f"2026-10-{i + 1:02d}" for i in range(len(entries))]
    return [(d, roh, status) for d, (roh, status) in reversed(list(zip(days, entries)))]


def texts(warnungen):
    return " | ".join(str(w) for w in warnungen)


def test_errors_in_a_row(cfg):
    assert qv.warnungen({("firma", "A"): hist((3, "ok"), (0, "fehler"))}, cfg) == []
    [w] = qv.warnungen({("firma", "A"): hist((3, "ok"), (0, "fehler"), (0, "veraltet"))}, cfg)
    assert w.art == "firma" and "seit 2 Läufen" in w.text and "02.10.2026" in w.text and "ins Leere" in w.text
    assert "companies.yaml" in w.text
    [q] = qv.warnungen({("quelle", "Bundesagentur"): hist((0, "ausfall"), (0, "ausfall"))}, cfg)
    assert q.text.startswith("Ausfall") and "companies.yaml" not in q.text


def test_empty_after_results(cfg):
    assert qv.warnungen({("firma", "B"): hist((0, "ok"), (0, "ok"), (0, "ok"), (0, "ok"))}, cfg) == []   # nie Treffer
    assert qv.warnungen({("firma", "B"): hist((5, "ok"), (0, "ok"), (0, "ok"))}, cfg) == []           # erst 2 leer
    [w] = qv.warnungen({("firma", "B"): hist((5, "ok"), (2, "ok"), (0, "ok"), (0, "ok"), (0, "ok"))}, cfg)
    assert "seit 3 Läufen keine Rohtreffer, zuletzt 2 am 02.10.2026" in w.text and "umgezogen" in w.text
    [q] = qv.warnungen({("quelle", "Mail-Alerts"): hist((4, "ok"), (0, "ok"), (0, "ok"), (0, "ok"))}, cfg)
    assert "Alert" in q.text


def test_known_manual_states_and_filter(cfg):
    history = {("firma", "C"): hist((2, "ok"), (0, "manuell"), (0, "manuell"), (0, "blockiert")),
               ("firma", "Alt"): hist((0, "fehler"), (0, "fehler"))}
    assert [w.name for w in qv.warnungen(history, cfg)] == ["Alt"]
    assert qv.warnungen(history, cfg, aktuell={("firma", "C")}) == []      # „Alt“ steht nicht mehr in der Liste
    strict = {**cfg, "quellen_verlauf": {"fehler_laeufe": 3}}
    assert qv.warnungen(history, strict) == []


def test_record_and_history(tmp_path):
    state = State(tmp_path / "seen.sqlite")
    ok = SourceResult("Bundesagentur", jobs=[object(), object()])
    kaputt = SourceResult("Stellenwerk", errors=["Timeout"])
    outcome = CompanyOutcome("Firma A", status="veraltet")
    qv.record(state, "2026-11-01", [ok, kaputt], {"Firma A": outcome})
    qv.record(state, "2026-11-01", [SourceResult("Bundesagentur", jobs=[object()])])   # gleicher Tag ersetzt
    qv.record(state, "2026-11-04", [SourceResult("Bundesagentur")])
    history = state.source_history()
    assert history[("quelle", "Bundesagentur")] == [("2026-11-04", 0, "ok"), ("2026-11-01", 1, "ok")]
    assert history[("quelle", "Stellenwerk")] == [("2026-11-01", 0, "ausfall")]
    assert history[("firma", "Firma A")] == [("2026-11-01", 0, "veraltet")]
    assert len(state.source_history(runs=1)[("quelle", "Bundesagentur")]) == 1
    state.close()


def test_readonly_old_database_without_table(tmp_path):
    import sqlite3
    path = tmp_path / "seen.sqlite"
    sqlite3.connect(path).execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)").connection.commit()
    state = State(path, readonly=True)
    assert state.source_history() == {}
    state.close()


@responses.activate
def test_company_status_stale_detail_pages(cfg, fetcher):
    html = ('<html><a href="/karriere/jobs/werkstudent-cloud-1">Werkstudent Cloud</a>'
            '<a href="/karriere/jobs/werkstudent-it-2">Werkstudent IT</a></html>')
    responses.get("https://firma.example/robots.txt", status=404)
    responses.get("https://firma.example/karriere", body=html)
    responses.get(re.compile(r"https://firma\.example/karriere/jobs/.*"), status=404)
    responses.get("https://kaputt.example/robots.txt", status=404)
    responses.get("https://kaputt.example/karriere", status=500)
    doc = {"firmen": [{"name": "Firma", "karriereseite_url": "https://firma.example/karriere", "ats": "jsonld"},
                      {"name": "Kaputt", "karriereseite_url": "https://kaputt.example/karriere", "ats": "jsonld"}]}
    src = CompaniesSource(doc, cfg["sources"]["companies"], fetcher, date(2026, 11, 1))
    src.fetch()
    firma = src.outcomes["Firma"]
    assert firma.status == "veraltet" and firma.detail_links == firma.detail_fehler == 2
    assert src.outcomes["Kaputt"].status == "fehler"


def test_report_section_and_subject():
    w = qv.Warnung("firma", "TÜV", "seit 3 Läufen keine Rohtreffer")
    report = Report(date(2026, 11, 1), [SourceResult("Bundesagentur", jobs=[])], [], gesundheit=[w])
    text = report.render()
    assert "**Quellen beobachten**" in text and "- Firma **TÜV**: seit 3 Läufen" in text
    assert "🔎 1 Quelle(n) beobachten" in report.subject("[Job-Monitor]")
    assert "Quellen beobachten" not in Report(date(2026, 11, 1), [], []).render()


def test_gui_firmen_page(tmp_path, cfg):
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    (tmp_path / "companies.yaml").write_text(
        "firmen:\n  - {name: TÜV, karriereseite_url: 'https://tuev.example/jobs', kategorie: pruefung}\n"
        "  - {name: Weg, karriereseite_url: 'https://weg.example', kategorie: sonstige, aktiv: false}\n",
        encoding="utf-8")
    state = State(tmp_path / "state" / "seen.sqlite")
    for i, (roh, status) in enumerate([(4, "ok"), (0, "ok"), (0, "ok"), (0, "ok")]):
        day = f"2026-10-{i * 3 + 1:02d}"
        state.record_source(day, "firma", "TÜV", roh, status)
        state.record_source(day, "firma", "Weg", 0, "fehler")                  # inaktiv → keine Warnung
        state.record_source(day, "quelle", "Bundesagentur", 10, "ok")
    state.record_source("2026-09-01", "quelle", "Alte Quelle", 0, "fehler")   # nicht mehr im letzten Lauf
    state.record_source("2026-09-02", "quelle", "Alte Quelle", 0, "fehler")
    state.close()
    warnungen = gf.warnungen(tmp_path, cfg)
    assert [w.name for w in warnungen] == ["TÜV"]
    html = gf.render(tmp_path, "tok", date(2026, 11, 1), 14, beobachten=warnungen)
    assert "Quellen beobachten" in html and "https://tuev.example/jobs" in html and ">beobachten</span>" in html
    assert "Quellen beobachten" not in gf.render(tmp_path, "tok", date(2026, 11, 1), 14)
