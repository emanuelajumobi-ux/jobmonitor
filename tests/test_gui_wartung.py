"""Seite Einstellungen: Pipeline (gh gefälscht), Probelauf/Aufgaben, Suchprofile, Dateien, Aufräumen, Sync-Liste."""
import json
import shutil
import subprocess
import sys

import pytest

from jobmonitor import gui_sync
from jobmonitor import gui_wartung as gw
from jobmonitor.config import ROOT, load_config
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


class FakeRun:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.calls, self.stdout, self.returncode, self.stderr = [], stdout, returncode, stderr

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)


def test_pipeline_runs_and_start(tmp_path, monkeypatch):
    monkeypatch.setattr(gw, "gh", lambda: "/usr/bin/gh")
    runs = [{"status": "completed", "conclusion": "success", "createdAt": "2026-11-01T05:17:00Z", "event": "schedule",
             "url": "https://github.com/x/actions/runs/1", "displayTitle": "Job-Monitor"}]
    laeufe, fehler = gw.pipeline_laeufe(tmp_path, FakeRun(json.dumps(runs)))
    assert laeufe == runs and fehler == ""
    assert gw.pipeline_laeufe(tmp_path, FakeRun("", 1, "HTTP 401"))[1] == "HTTP 401"
    fake = FakeRun()
    assert "gestartet" in gw.pipeline_starten(tmp_path, True, fake)
    assert fake.calls[0][1:] == ["workflow", "run", "monitor.yml", "-f", "force=true", "-f", "no_mail=true"]
    with pytest.raises(gw.WartungError, match="kaputt"):
        gw.pipeline_starten(tmp_path, False, FakeRun("", 1, "kaputt"))
    monkeypatch.setattr(gw, "gh", lambda: None)
    assert "nicht gefunden" in gw.pipeline_laeufe(tmp_path)[1]


def test_background_tasks(tmp_path):
    tasks = gw.Aufgaben(tmp_path)
    a = tasks.starten("probe", "Probe", [sys.executable, "-c", "print('hallo'); import time; time.sleep(0.3)"])
    assert a.laeuft and tasks.laeuft()
    with pytest.raises(gw.WartungError, match="läuft noch"):
        tasks.starten("probe", "Probe", [sys.executable, "-c", "pass"])
    a.proc.wait(5)
    assert not tasks.laeuft() and "hallo" in a.ausgabe() and a.ausgabe().startswith("$ ")
    assert (tmp_path / gw.TASK_DIR / "probe.log").exists()
    assert gw.probelauf_cmd("companies")[-2:] == ["--only", "companies"] and "--dry-run" in gw.probelauf_cmd("")
    with pytest.raises(gw.WartungError):
        gw.probelauf_cmd("; rm -rf /")


def test_files_and_profiles(tmp_path):
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    gw.profil_setzen(tmp_path, "junior", False)
    cfg = load_config(tmp_path / "config.yaml")
    assert cfg["profile"]["junior"]["enabled"] is False and cfg["profile"]["werkstudent"]["enabled"] is True
    assert (tmp_path / "config.yaml.bak").exists()
    old = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    gw.profil_setzen(tmp_path, "junior", True)
    new = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert sum(a != b for a, b in zip(old.splitlines(), new.splitlines())) == 1   # nur eine Zeile geändert
    for bad in ("gibtsnicht", "../x"):
        with pytest.raises(gw.WartungError):
            gw.profil_setzen(tmp_path, bad, True)
    with pytest.raises(gw.WartungError, match="Kein gültiges YAML"):
        gw.speichern(tmp_path, "config.yaml", "run: [kaputt\n")
    with pytest.raises(gw.WartungError, match="Pflichtabschnitte"):
        gw.speichern(tmp_path, "config.yaml", "run: {}\n")
    with pytest.raises(gw.WartungError, match="nicht bearbeitet"):
        gw.speichern(tmp_path, ".env", "SMTP_PASSWORD=x")
    assert load_config(tmp_path / "config.yaml")["profile"]["junior"]["enabled"] is True   # unverändert
    (tmp_path / "cv").mkdir()
    gw.speichern(tmp_path, "cv/nachfassen_vorlage.txt", "Betreff\r\n\r\nText")
    assert (tmp_path / "cv" / "nachfassen_vorlage.txt").read_text(encoding="utf-8") == "Betreff\n\nText\n"


def test_cleanup_and_log(tmp_path, cfg):
    (tmp_path / "cv" / "out").mkdir(parents=True)
    assert "schon leer" in gw.cv_out_aufraeumen(tmp_path, cfg, tmp_path / "Trash")
    (tmp_path / "cv" / "out" / "lebenslauf.pdf").write_bytes(b"%PDF")
    assert "Papierkorb" in gw.cv_out_aufraeumen(tmp_path, cfg, tmp_path / "Trash")
    assert not (tmp_path / "cv" / "out").exists() and len(list((tmp_path / "Trash").iterdir())) == 1
    log = tmp_path / "x.log"
    log.write_text("\n".join(f"Zeile {i}" for i in range(100)), encoding="utf-8")
    assert gw.protokoll(3, log) == "Zeile 97\nZeile 98\nZeile 99" and gw.protokoll(3, tmp_path / "fehlt") == ""


def test_sync_includes_editable_files():
    assert set(gw.DATEIEN) <= set(gui_sync.SYNC_FILES) and set(gui_sync.SYNC_FILES) <= set(gui_sync.LABELS)


def test_page_flow(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(gw, "pipeline_laeufe", lambda r: ([], "GitHub-CLI (gh) nicht gefunden."))
    app = App(root, compile_pdf=False)
    html = app.einstellungen().decode()
    assert "Pipeline auf GitHub" not in html and 'id="postfach"' in html          # ohne GitHub: lokaler Betrieb
    monkeypatch.setattr("jobmonitor.zeitplan.github_aktiv", lambda r, run=None: True)
    html = app.einstellungen().decode()
    assert "Pipeline auf GitHub" in html and "Probelauf auf diesem Rechner" in html and "/einstellungen/laeufe" in html
    assert 'id="postfach"' not in html
    assert "gh) nicht gefunden" not in html                                # Läufe kommen erst nachgeladen
    assert "gh) nicht gefunden" in app.pipeline_laeufe().decode()
    assert 'href="/einstellungen/datei?name=config.yaml"' in html and "Werkstudent" in html
    html = app.einstellungen_post({"aktion": "profil", "key": "junior", "an": ""}).decode()
    assert "Suchprofil geändert" in html
    assert load_config(root / "config.yaml")["profile"]["junior"]["enabled"] is False
    assert "Unbekannte Aktion" in app.einstellungen_post({"aktion": "rm"}).decode()
    assert "Unbekannte Quelle" in app.einstellungen_post({"aktion": "probelauf", "quelle": "x"}).decode()
    assert app.datei(".env") is None and "config.yaml" in app.datei("config.yaml").decode()
    html = app.datei_post({"name": "config.yaml", "text": "run: [kaputt"}).decode()
    assert "Nicht gespeichert" in html and "run: [kaputt" in html            # Eingabe bleibt erhalten
    assert app.datei_post({"name": "../x", "text": ""}) is None
    text = (root / "config.yaml").read_text(encoding="utf-8").replace("nachfassen_nach_tagen: 21",
                                                                        "nachfassen_nach_tagen: 14")
    html = app.datei_post({"name": "config.yaml", "text": text}).decode()
    assert "config.yaml gespeichert" in html and "<h1>Einstellungen</h1>" in html   # Editor schließt sich
    assert load_config(root / "config.yaml")["tracking"]["nachfassen_nach_tagen"] == 14


def test_companies_yaml_bearbeiten(tmp_path):
    from jobmonitor import gui_wartung as gw
    assert "companies.yaml" in gw.DATEIEN
    gut = "firmen:\n  - name: A\n    karriereseite_url: https://a.de/jobs\nhochschulen: []\n"
    gw.pruefen("companies.yaml", gut)
    for text, fehler in [("hochschulen: []\n", "firmen"),
                         ("firmen:\n  - karriereseite_url: https://a.de\n", "name"),
                         ("firmen:\n  - name: A\n    karriereseite_url: a.de\n", "https"),
                         ("firmen:\n  - {name: A, karriereseite_url: 'https://a'}\n  - {name: a, karriereseite_url: 'https://b'}\n",
                          "doppelt")]:
        with pytest.raises(gw.WartungError, match=fehler):
            gw.pruefen("companies.yaml", text)
    (tmp_path / "companies.yaml").write_text(gut, encoding="utf-8")
    gw.speichern(tmp_path, "companies.yaml", gut.replace("A", "B"))
    assert (tmp_path / "companies.yaml.bak").read_text(encoding="utf-8") == gut
    assert 'href="/firmen">zurück' in gw.render_datei("t", "companies.yaml", gut)


def test_laeufe_nachgeladen_und_zwischengespeichert(root, monkeypatch):  # noqa: F811
    aufrufe = []
    runs = [{"status": "completed", "conclusion": "success", "createdAt": "2026-11-02T05:20:00Z", "event": "schedule",
             "url": "https://github.com/x/actions/runs/1", "displayTitle": "Job-Monitor"}]
    monkeypatch.setattr(gw, "pipeline_laeufe", lambda r: aufrufe.append(r) or (runs, ""))
    monkeypatch.setattr(gw, "pipeline_starten", lambda r, ohne_mail: "gestartet")
    app = App(root, compile_pdf=False)
    app.einstellungen()
    assert not aufrufe                                                     # Seite wartet nicht auf GitHub
    assert "2026-11-02 05:20 UTC" in app.pipeline_laeufe().decode() and "success" in app.pipeline_laeufe().decode()
    assert len(aufrufe) == 1                                               # zweiter Aufruf aus dem Zwischenspeicher
    app.einstellungen_post({"aktion": "pipeline_ohne_mail"})
    app.pipeline_laeufe()
    assert len(aufrufe) == 2                                               # nach „Lauf starten“ frisch geladen
