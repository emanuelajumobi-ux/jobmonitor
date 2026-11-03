"""Remote nur in Deutschland, „passt nicht“ mit Grund und Ausschluss-Vorschläge, gepackte und Text-Sitemaps."""
import gzip
import re

import pytest
import responses

from jobmonitor import ablehnung
from jobmonitor.config import load_config
from jobmonitor.gui import App
from jobmonitor.gui_sync import SyncResult
from jobmonitor.http import Fetcher
from jobmonitor.location import im_ausland, location_points
from jobmonitor.sources.ats import sitemap
from jobmonitor.state import State
from jobmonitor.models import Job
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)

ORT = {"max_fahrzeit_min": 60, "punkte_koeln": 15, "punkte_umkreis": 10, "punkte_grenze": 5, "punkte_remote": 12}


def test_remote_nur_in_deutschland():
    for ausland in ["Zürich", "Paris HQ, Île de France", "Amsterdam", "Wien, Österreich", "Manchester"]:
        assert im_ausland(ausland) and location_points(ausland, True, ORT) is None
    for inland in ["Remote job", "Berlin", "Germany, Remote", "Köln", "Bernkastel-Kues", "Rheinfelden", ""]:
        assert not im_ausland(inland)
    assert location_points("Berlin", True, ORT) == (12, "Remote/Homeoffice")
    assert location_points("Zürich", True, {**ORT, "remote_nur_deutschland": False}) == (12, "Remote/Homeoffice")


def test_vorschlaege_aus_ablehnungen():
    data = {"stellen": {
        "a": {"titel": "Werkstudent Recruiting (m/w/d)", "grund": "fach"},
        "b": {"titel": "Working Student Recruiting & HR", "grund": "fach"},
        "c": {"titel": "Werkstudent Azure Administration", "grund": "zeit"},
        "d": {"titel": "Werkstudent Azure Cloud", "grund": "ort"},
        "e": {"titel": "Werkstudent Einkauf", "grund": "fach"}}}
    liste = ablehnung.vorschlaege(data, ["Werkstudent Cloud Operations"], ["senior"], {"Azure", "azure ad"})
    assert liste == [("recruiting", 2, ["anderes Fachgebiet"])]          # Azure geschützt, Einkauf nur 1×
    assert ablehnung.vorschlaege(data, ["Werkstudent Recruiting Tech"], [], {"azure"}) == []   # sichtbare Stelle hat es
    assert ablehnung.vorschlaege({**data, "ignoriert": ["recruiting"]}, [], [], {"azure"}) == []


def test_ausschliessen_in_config(root):  # noqa: F811
    vorher = (root / "config.yaml").read_text(encoding="utf-8")
    cfg = load_config(root / "config.yaml")
    ablehnung.ausschliessen(root, "Lagerlogistik", cfg["filter"]["ausschluss_titel"] or [])
    neu = load_config(root / "config.yaml")["filter"]["ausschluss_titel"]
    assert neu[-1] == "lagerlogistik" and neu[:-1] == (cfg["filter"]["ausschluss_titel"] or [])
    assert (root / "config.yaml").read_text(encoding="utf-8").replace("    - lagerlogistik\n", "", 1) == vorher
    with pytest.raises(ablehnung.AblehnungError, match="schon"):
        ablehnung.ausschliessen(root, "lagerlogistik", neu)
    with pytest.raises(ablehnung.AblehnungError):
        ablehnung.ausschliessen(root, "a: b", neu)


def test_passt_nicht_in_der_app(root, monkeypatch):  # noqa: F811
    state = State(root / "state" / "seen.sqlite")
    ids = []
    for i, titel in enumerate(["Werkstudent Lagerlogistik", "Werkstudent Lagerlogistik Team", "Werkstudent Cloud Azure"]):
        job = Job(titel, f"Firma {i}", f"https://x/{i}", "BA", location="Köln")
        job.fit_anforderungen = {"Azure": 1.0}
        state.save_job_detail(job, "2026-11-01")
        ids.append(job.short_id)
    state.close()
    monkeypatch.setattr("jobmonitor.gui.sync", lambda r: SyncResult(True, "ok"))
    app = App(root, compile_pdf=False)
    html = app.markieren({"job_id": ids[0], "aktion": "ausblenden"}).decode()
    assert "Warum passt sie nicht?" in html and 'value="fach"' in html
    assert "gemerkt" in app.markieren({"job_id": ids[0], "aktion": "grund", "grund": "fach"}).decode()
    app.markieren({"job_id": ids[1], "aktion": "ausblenden"})
    html = app.markieren({"job_id": ids[1], "aktion": "grund", "grund": "fach"}).decode()
    assert "Aus deinen Ablehnungen gelernt" in html and "<b>lagerlogistik</b>" in html
    html = app.ablehnung({"wort": "lagerlogistik", "aktion": "ausschliessen"}).decode()
    assert "ab dem nächsten Lauf aussortiert" in html and "<b>lagerlogistik</b>" not in html
    assert "lagerlogistik" in load_config(root / "config.yaml")["filter"]["ausschluss_titel"]
    assert "Unbekannter Grund" in app.markieren({"job_id": ids[2], "aktion": "grund", "grund": "x"}).decode()


@responses.activate
def test_gepackte_und_text_sitemaps():
    f = Fetcher("job-monitor-test/0.1", min_delay=0, sleep=lambda s: None)
    responses.get("https://a.de/robots.txt", body="User-agent: *\nDisallow:\n")
    xml = (b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           b'<url><loc>https://a.de/karriere/jobs/werkstudent-cloud-123</loc></url></urlset>')
    responses.get("https://a.de/s1.xml.gz", body=gzip.compress(xml))
    responses.get("https://a.de/s2.txt", body="https://a.de/karriere/jobs/werkstudent-iam-9\nhttps://a.de/impressum\n")
    links, _ = sitemap.collect(f, "https://a.de/karriere", "A", "Firmen", ["https://a.de/s1.xml.gz",
                                                                          "https://a.de/s2.txt"])
    assert links == ["https://a.de/karriere/jobs/werkstudent-cloud-123", "https://a.de/karriere/jobs/werkstudent-iam-9"]
    assert re.search("cloud", links[0])
