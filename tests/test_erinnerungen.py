"""Apple-Erinnerungen: Fälligkeit, AppleScript-Aufruf (gefälscht), Dopplungen, Fehler, Knöpfe in der Oberfläche."""
import subprocess
from datetime import date, datetime, timedelta

import pytest

from jobmonitor import erinnerungen as er
from jobmonitor import gui_firmen as gf
from jobmonitor.config import load_config
from jobmonitor.gui import App
from jobmonitor.models import Job
from jobmonitor.state import State
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

JOB = {"title": "Werkstudent Cloud", "company": "Beispiel AG", "url": "https://x/1", "frist": "2026-11-20"}


class FakeOsascript:
    def __init__(self, stdout="ok", returncode=0, stderr=""):
        self.calls, self.stdout, self.returncode, self.stderr = [], stdout, returncode, stderr

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)


def test_due_dates(cfg):
    e = er.fuer_frist(JOB, cfg, date(2026, 11, 1))
    assert e.faellig == datetime(2026, 11, 17, 9, 0) and e.schluessel == "frist:https://x/1"
    assert e.titel == "Bewerbungsfrist 20.11.: Werkstudent Cloud – Beispiel AG" and "https://x/1" in e.notiz
    assert er.fuer_frist(JOB, cfg, date(2026, 11, 19)).faellig == datetime(2026, 11, 19, 9, 0)   # frühestens heute
    assert er.fuer_frist(JOB, cfg, date(2026, 11, 21)) is None and er.fuer_frist({**JOB, "frist": None}, cfg) is None
    own = {**cfg, "erinnerungen": {"vorlauf_tage": 1, "uhrzeit": "18:30"}}
    assert er.fuer_frist(JOB, own, date(2026, 11, 1)).faellig == datetime(2026, 11, 19, 18, 30)
    b = er.fuer_besuch("TÜV", "https://tuev.example", date(2026, 11, 15), cfg)
    assert b.titel == "Karriereseite ansehen: TÜV" and b.schluessel == "besuch:TÜV:2026-11-15"


def test_create_and_no_duplicates(tmp_path, cfg, monkeypatch):
    monkeypatch.setattr(er, "verfuegbar", lambda: True)
    monkeypatch.setattr("sys.platform", "darwin")                 # Mac-Weg (AppleScript), nicht die .ics-Datei
    fake = FakeOsascript()
    e = er.fuer_frist(JOB, cfg, date(2026, 11, 1))
    assert er.anlegen(tmp_path, cfg, e, fake) == "neu"
    cmd = fake.calls[0]
    assert cmd[:2] == ["osascript", "-e"] and cmd[3:] == ["Job-Monitor", e.titel, e.notiz, "2026", "11", "17", "9", "0"]
    assert er.anlegen(tmp_path, cfg, e, fake) == "vorhanden" and len(fake.calls) == 1      # lokal gemerkt
    assert er.eingetragen(tmp_path) == {"frist:https://x/1"}
    other = er.fuer_frist({**JOB, "url": "https://x/2"}, cfg, date(2026, 11, 1))
    assert er.anlegen(tmp_path, cfg, other, FakeOsascript("exists")) == "vorhanden"        # stand schon in der App


def test_errors(tmp_path, cfg, monkeypatch):
    e = er.fuer_frist(JOB, cfg, date(2026, 11, 1))
    monkeypatch.setattr(er, "verfuegbar", lambda: False)
    with pytest.raises(er.ErinnerungError, match="nur auf dem Mac"):
        er.anlegen(tmp_path, cfg, e, FakeOsascript())
    monkeypatch.setattr(er, "verfuegbar", lambda: True)
    monkeypatch.setattr("sys.platform", "darwin")
    with pytest.raises(er.ErinnerungError, match="Automation"):
        er.anlegen(tmp_path, cfg, e, FakeOsascript("", 1, "execution error: Not authorized to send Apple events "
                                                          "to Reminders. (-1743)"))
    with pytest.raises(er.ErinnerungError, match="kaputt"):
        er.anlegen(tmp_path, cfg, e, FakeOsascript("", 1, "kaputt"))
    assert er.eingetragen(tmp_path) == set()                                                  # nichts gemerkt


def test_script_compiles():
    import shutil
    if not shutil.which("osacompile"):
        pytest.skip("nur auf dem Mac")
    proc = subprocess.run(["osacompile", "-o", "/dev/null", "-e", er.SCRIPT], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_gui_buttons_and_flow(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(er, "verfuegbar", lambda: True)
    monkeypatch.setattr("sys.platform", "darwin")                 # Mac-Weg (AppleScript), nicht die .ics-Datei
    fake = FakeOsascript()
    real = er.anlegen
    monkeypatch.setattr(er, "anlegen", lambda r, c, e, run=None: real(r, c, e, fake))
    frist = (date.today() + timedelta(days=10)).isoformat()
    state = State(root / "state" / "seen.sqlite")
    for i, f in enumerate([frist, None]):
        job = Job(f"Werkstudent Cloud {i}", "Beispiel AG", f"https://x/{i}", "test")
        job.frist = f
        state.save_job_detail(job, date.today().isoformat())
    state.close()
    app = App(root, compile_pdf=False)
    html = app.index().decode()
    assert "1 Bewerbungsfrist(en) noch nicht in deinen Erinnerungen" in html
    assert html.count('value="frist"') == 1 and "Frist in Erinnerungen eintragen" in html
    html = app.erinnern({"art": "fristen"}).decode()
    assert "1 Erinnerung(en) in der Liste „Job-Monitor“ angelegt" in html and len(fake.calls) == 1
    assert "noch nicht in deinen Erinnerungen" not in html and " · in Erinnerungen" in html
    assert "Nichts einzutragen" in app.erinnern({"art": "frist", "job_id": "gibtsnicht"}).decode()
    assert "Nichts einzutragen" in app.erinnern({"art": "fristen"}).decode()


def test_gui_besuch(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(er, "verfuegbar", lambda: True)
    monkeypatch.setattr("sys.platform", "darwin")                 # Mac-Weg (AppleScript), nicht die .ics-Datei
    fake = FakeOsascript()
    real = er.anlegen
    monkeypatch.setattr(er, "anlegen", lambda r, c, e, run=None: real(r, c, e, fake))
    monkeypatch.setattr(gf, "manual_entries", lambda r: [{"name": "TÜV", "grund": "JavaScript",
                                                         "url": "https://tuev.example"}])
    (root / "companies.yaml").write_text("firmen: []\n", encoding="utf-8")
    cfg = load_config(root / "config.yaml")
    gf.mark_visited(root, "TÜV", date.today() - timedelta(days=4))
    assert gf.next_visit(root, "TÜV", date.today(), 14) == date.today() + timedelta(days=10)
    assert gf.next_visit(root, "Neu", date.today(), 14) == date.today()
    html = gf.render(root, "tok", date.today(), 14, cfg=cfg)
    assert 'value="besuch"' in html and "Erinnern</button>" in html
    app = App(root, compile_pdf=False)
    html = app.erinnern({"art": "besuch", "name": "TÜV"}).decode()
    assert "1 Erinnerung(en)" in html and "in Erinnerungen</span>" in html
    assert fake.calls[0][4] == "Karriereseite ansehen: TÜV"
