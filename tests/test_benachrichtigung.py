"""Tägliche Mitteilung bei neuen Stellen (benachrichtigung.py) und ihr Schalter in den Einstellungen."""
import json
import plistlib
import sqlite3
import subprocess
from pathlib import Path

import pytest

from jobmonitor import benachrichtigung as bn
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


def make_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE job_detail (id, key, title, company, url, anforderungen_json, fit, first_seen, frist, "
                "profil)")
    con.executemany("INSERT INTO job_detail (title, company, fit, first_seen) VALUES (?, ?, ?, ?)", rows)
    con.commit()
    con.close()


class Run:
    def __init__(self, code=0):
        self.calls, self.code = [], code

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.code, "", "")


def test_neue_stellen_und_text(tmp_path):
    db = tmp_path / "s.sqlite"
    make_db(db, [("Alt", "A", 90, "2026-10-30"), ("Werkstudent Cloud", "adesso", 85, "2026-11-02"),
                 ("Ohne Fit", "B", None, "2026-11-02"), ("Werkstudent IAM", "C", 60, "2026-11-01")])
    stellen = bn.neue_stellen(db, "2026-10-31")
    assert [s["title"] for s in stellen] == ["Werkstudent Cloud", "Ohne Fit", "Werkstudent IAM"]
    assert bn.text(stellen) == ("3 neue Stellen", "Werkstudent Cloud – adesso · Fit 85 %")
    assert bn.text(stellen[1:2]) == ("1 neue Stelle", "Ohne Fit – B")


def test_pruefen_meldet_einmal(tmp_path):
    quelle = tmp_path / "quelle.sqlite"
    make_db(quelle, [("Werkstudent Cloud", "adesso", 85, "2026-11-02"), ("Werkstudent IT", "B", 40, "2026-11-02")])
    antworten = []

    def holen(root, ziel):
        ziel.write_bytes(quelle.read_bytes())
        (ziel.parent / "antworten.json").write_text(json.dumps(antworten))
        return True
    run = Run()
    cfg = {"benachrichtigung": {"top_fit_ab": 75}}
    ergebnis = bn.pruefen(tmp_path, "2026-11-02", run=run, db_holen=holen, cfg=cfg)
    assert ergebnis == "2 Mitteilung(en) gesendet: Passt sehr gut · Fit 85 %, 2 neue Stellen"
    texte = [c[2] for c in run.calls]
    assert "Passt sehr gut · Fit 85 %" in texte[0] and "Werkstudent Cloud – adesso" in texte[0]
    assert "2 neue Stellen" in texte[1]
    assert json.loads((tmp_path / bn.STAND).read_text()) == {"bis": "2026-11-02", "antworten": []}
    # nächster Tag: eine neue Antwort, keine neuen Stellen
    antworten.append({"link": "https://x/1", "firma": "INFODAS", "datum": "2026-11-03", "art": "einladung",
                      "absender": "softgarden.io"})
    assert bn.pruefen(tmp_path, "2026-11-03", run=run, db_holen=holen, cfg=cfg) == "1 Mitteilung(en) gesendet: Antwort"
    assert "Antwort von INFODAS" in run.calls[-1][2] and "Einladung zum Gespräch" in run.calls[-1][2]
    assert bn.pruefen(tmp_path, "2026-11-04", run=run, db_holen=holen, cfg=cfg) == \
        "Keine neuen Stellen und keine Antworten."
    assert len(run.calls) == 3


def test_top_stellen_traumprofil():
    stellen = [{"title": "Werkstudent Cloud Security Azure", "company": "A", "fit": 60, "tag": "x",
                "anforderungen": ["Azure", "Cloud Security"]},
               {"title": "Werkstudent Vertrieb", "company": "B", "fit": 50, "tag": "x", "anforderungen": []}]
    from jobmonitor.config import load_config
    tops = bn.top_stellen(stellen, load_config())
    assert len(tops) == 1 and tops[0][1] == "Werkstudent Cloud Security Azure – A" and "Fit 60 %" in tops[0][0]


def test_senden_ueber_app(tmp_path):
    exe = tmp_path / "Job-Monitor.app" / "Contents" / "MacOS" / "Job-Monitor"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"#!/bin/zsh\n")              # nur Skript: AppleScript
    run = Run()
    assert bn.senden(tmp_path, "t", "x", run=run) == "osascript"
    exe.write_bytes(b"\xcf\xfa\xed\xfe")             # übersetztes Hauptprogramm: über open
    run = Run()
    assert bn.senden(tmp_path, "2 neue Stellen", "x", run=run) == "app"
    cmd = run.calls[0]
    assert cmd[:4] == ["open", "-n", "-g", "-W"] and cmd[-4:] == ["--args", "--notify", "2 neue Stellen", "x"]

    def verweigert(cmd, **kw):
        Path(cmd[cmd.index("--stderr") + 1]).write_text("NICHT_ERLAUBT\n")
        return subprocess.CompletedProcess(cmd, 0)
    with pytest.raises(bn.BenachrichtigungError, match="Systemeinstellungen"):
        bn.senden(tmp_path, "t", "x", run=verweigert)


def test_ein_und_ausschalten(tmp_path):
    agent = tmp_path / "agent.plist"
    run = Run()
    assert bn.status(agent) == {"an": False, "zeit": bn.STANDARD_ZEIT}
    assert "07:45" in bn.einschalten(tmp_path, "07:45", agent, run=run)
    data = plistlib.loads(agent.read_bytes())
    assert data["StartCalendarInterval"] == {"Hour": 7, "Minute": 45}
    assert data["ProgramArguments"][-2:] == ["jobmonitor", "benachrichtigen"]
    assert data["WorkingDirectory"] == str(tmp_path)
    assert [c[1] for c in run.calls] == ["bootout", "bootstrap"]
    assert bn.status(agent) == {"an": True, "zeit": "07:45"}
    with pytest.raises(bn.BenachrichtigungError):
        bn.einschalten(tmp_path, "25:00", agent, run=run)
    bn.ausschalten(agent, run=run)
    assert not agent.exists()


def test_einstellungen_zeigen_schalter(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr("sys.platform", "darwin")                 # die Karte gibt es nur auf dem Mac
    monkeypatch.setattr(bn, "status", lambda: {"an": True, "zeit": "09:15"})
    monkeypatch.setattr("jobmonitor.gui_wartung.pipeline_laeufe", lambda r: ([], ""))
    html = App(root, compile_pdf=False).einstellungen().decode()
    assert "Mitteilung bei neuen Stellen" in html and 'value="09:15"' in html and 'name="an" value="1" checked' in html
    assert "mit Mail" not in html
