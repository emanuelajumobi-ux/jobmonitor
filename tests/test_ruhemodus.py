"""Suche aktiv / Ruhemodus / angehalten (config.yaml → run.modus): Pipeline, Mitteilungen und Schalter in der App."""
import json
import shutil
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import responses

from jobmonitor import benachrichtigung as bn
from jobmonitor import gui_wartung as gw
from jobmonitor import runner
from jobmonitor.config import ROOT, load_config, modus
from jobmonitor.gui import App
from jobmonitor.gui_sync import SyncResult
from jobmonitor.state import State
from tests.test_benachrichtigung import Run, make_db
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


def test_modus_aus_config():
    assert modus({}) == "aktiv" and modus({"run": {"modus": "quatsch"}}) == "aktiv"
    assert modus({"run": {"modus": "ruhe"}}) == "ruhe"
    assert modus(load_config()) == "aktiv"                         # mitgelieferte config.yaml


def test_modus_setzen(root):  # noqa: F811
    gw.modus_setzen(root, "ruhe")
    text = (root / "config.yaml").read_text(encoding="utf-8")
    assert "  modus: ruhe                 # aktiv | ruhe | aus" in text  # Kommentar bleibt in seiner Spalte
    assert load_config(root / "config.yaml")["run"]["modus"] == "ruhe"
    # Ältere config.yaml ohne die Zeile: wird im Abschnitt run angelegt
    (root / "config.yaml").write_text(text.replace("  modus: ruhe", "  # weg"), encoding="utf-8")
    gw.modus_setzen(root, "aus")
    cfg = load_config(root / "config.yaml")
    assert cfg["run"]["modus"] == "aus" and cfg["run"]["interval_days"] == 1
    with pytest.raises(gw.WartungError):
        gw.modus_setzen(root, "rm -rf")


@responses.activate                                                 # keine Anfrage darf rausgehen
def test_pipeline_angehalten_und_ruhemodus(root):  # noqa: F811
    shutil.copy(ROOT / "companies.yaml", root / "companies.yaml")
    gw.modus_setzen(root, "aus")
    assert runner.run(runner.Options(no_mail=True, root=root)) == 0
    assert not (root / "reports").exists()
    # Ruhemodus: letzter Lauf vor 2 Tagen → noch nicht fällig (aktiv wäre er es)
    gw.modus_setzen(root, "ruhe")
    (root / "state").mkdir(exist_ok=True)
    state = State(root / "state" / "seen.sqlite")
    state.set_last_success(datetime.now(ZoneInfo("Europe/Berlin")) - timedelta(days=2))
    state.close()
    assert runner.run(runner.Options(no_mail=True, root=root)) == 0
    assert not (root / "reports").exists() and not responses.calls


def test_ruhemodus_ohne_postfach(root, monkeypatch):  # noqa: F811
    def nie(*a, **kw):
        raise AssertionError("Postfach darf im Ruhemodus nicht gelesen werden")
    monkeypatch.setattr(runner.antworten, "postfach", nie)
    cfg = load_config(root / "config.yaml")
    cfg["run"]["modus"] = "ruhe"
    assert runner.antworten_suchen([], {}, cfg, None, runner.Options(root=root)) == []


def test_mitteilungen_im_ruhemodus(tmp_path):
    quelle = tmp_path / "quelle.sqlite"
    make_db(quelle, [("Werkstudent Cloud", "adesso", 85, "2026-11-02")])

    def holen(root, ziel):
        ziel.write_bytes(quelle.read_bytes())
        (ziel.parent / "antworten.json").write_text("[]")
        return True
    run = Run()
    ruhe = {"run": {"modus": "ruhe"}}
    assert bn.pruefen(tmp_path, "2026-11-02", run=run, db_holen=holen, cfg=ruhe) == "Ruhemodus: keine Mitteilungen."
    assert not run.calls
    # Stand rückt trotzdem vor: nach dem Wiedereinschalten kommt kein Stapel alter Stellen
    assert json.loads((tmp_path / bn.STAND).read_text())["bis"] == "2026-11-02"
    assert bn.pruefen(tmp_path, "2026-11-03", run=run, db_holen=holen, cfg={}) == \
        "Keine neuen Stellen und keine Antworten."


def test_schalter_in_der_app(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(gw, "pipeline_laeufe", lambda r: ([], ""))
    monkeypatch.setattr("sys.platform", "darwin")                 # Mitteilungs-Karte gibt es nur auf dem Mac
    monkeypatch.setattr(bn, "status", lambda: {"an": True, "zeit": "08:30"})
    monkeypatch.setattr("jobmonitor.zeitplan.github_aktiv", lambda *a, **k: True)   # Karte nur mit GitHub-Suche
    gesynct = []
    monkeypatch.setattr("jobmonitor.gui.sync", lambda r: gesynct.append(r) or SyncResult(True, "Synchronisiert: config.yaml hochgeladen."))
    app = App(root, compile_pdf=False)
    html = app.einstellungen().decode()
    assert "<h2>Suche</h2>" in html and 'value="aktiv" checked' in html and "Ruhemodus" in html
    assert "Suche steht auf" not in app.index().decode()
    html = app.einstellungen_post({"aktion": "modus", "modus": "ruhe"}).decode()
    assert "Suche steht auf „Ruhemodus“. Synchronisiert: config.yaml hochgeladen. Gilt ab" in html
    assert gesynct == [root]
    assert 'value="ruhe" checked' in html and "pausiert, solange die Suche auf „Ruhemodus“ steht" in html
    assert load_config(root / "config.yaml")["run"]["modus"] == "ruhe"
    assert "Suche steht auf „Ruhemodus“ – einmal pro Woche" in app.index().decode()
    monkeypatch.setattr("jobmonitor.gui.sync", lambda r: SyncResult(False, "offline"))
    html = app.einstellungen_post({"aktion": "modus", "modus": "aus"}).decode()
    assert "Hochladen hat nicht geklappt (offline)" in html
    assert "Unbekannter Modus" in app.einstellungen_post({"aktion": "modus", "modus": "x"}).decode()
