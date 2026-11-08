"""Einrichtung nicht verlieren, App zurücksetzen, Startmenü-Eintrag (Windows)."""
import json
from datetime import datetime
from pathlib import Path

import pytest

from jobmonitor import app_start, erststart, gui_ki as gki, zuruecksetzen
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


# --- Einrichtungs-Assistent ---
def test_begonnen_bleibt_unfertig_bis_fertig(tmp_path):
    erststart.vorbereiten(tmp_path)
    assert not erststart.eingerichtet(tmp_path)
    erststart.beginnen(tmp_path)
    (tmp_path / "cv" / "profile.yaml").write_text("name: Test\n", encoding="utf-8")   # Schritt 1 erledigt
    assert not erststart.eingerichtet(tmp_path) and erststart.unfertig(tmp_path)
    daten = json.loads((tmp_path / erststart.ASSISTENT).read_text(encoding="utf-8"))
    (tmp_path / erststart.ASSISTENT).write_text(json.dumps({**daten, "fertig": "2026-11-05"}), encoding="utf-8")
    assert erststart.eingerichtet(tmp_path) and not erststart.unfertig(tmp_path)


def test_alte_staende_ohne_merker_gelten_als_eingerichtet(tmp_path):
    (tmp_path / "cv").mkdir()
    (tmp_path / "cv" / "cv_master.yaml").write_text("x: 1\n", encoding="utf-8")
    erststart.beginnen(tmp_path)                                   # ändert bei bestehenden Nutzern nichts
    assert erststart.eingerichtet(tmp_path) and not (tmp_path / erststart.ASSISTENT).exists()


def test_rueckweg_und_hinweis(tmp_path):
    erststart.vorbereiten(tmp_path)
    app = App(tmp_path, compile_pdf=False)
    assert "/ki-anleitung?von=einrichten" in app.einrichten().decode()
    seite = app.ki_anleitung("gemini", "einrichten").decode()
    assert seite.count('href="/einrichten"') >= 2 and "Dashboard" in seite and "Playground" in seite
    assert "Weiter einrichten" in app.einstellungen().decode()      # Weg zurück von jeder Seite
    assert 'href="/einrichten">Zurück' not in gki.ANLEITUNG_GEMINI   # ohne von=einrichten wie bisher


# --- Zurücksetzen ---
def test_nicht_im_entwicklungsordner():
    from jobmonitor.config import CODE
    assert not zuruecksetzen.moeglich(CODE)
    with pytest.raises(zuruecksetzen.ZuruecksetzenError):
        zuruecksetzen.vormerken(CODE, True, False)


def test_vormerken_und_beim_start_mit_sicherung(tmp_path):
    home = tmp_path / "Job-Monitor"
    erststart.vorbereiten(home)
    aufrufe = []
    zuruecksetzen.vormerken(home, sicherung=True, schluessel=True, run=lambda *a, **k: aufrufe.append(a[0]))
    assert (home / zuruecksetzen.MARKE).is_file()
    meldung = zuruecksetzen.beim_start(home)
    assert "aufgehoben" in meldung and not home.exists()
    assert [p.name for p in tmp_path.iterdir()][0].startswith("Job-Monitor (alt ")


def test_beim_start_ohne_sicherung_loescht(tmp_path):
    home = tmp_path / "Job-Monitor"
    erststart.vorbereiten(home)
    zuruecksetzen.vormerken(home, sicherung=False, schluessel=False, run=lambda *a, **k: None)
    assert zuruecksetzen.beim_start(home) == "Alte Daten gelöscht" and not home.exists()
    assert zuruecksetzen.beim_start(home) == ""                    # nichts vorgemerkt: nichts tun


def test_skripte():
    jetzt = datetime(2026, 11, 5, 9, 30)
    name, sh = zuruecksetzen.skript(Path("/Users/x/Documents/Job-Monitor"), 42, True, "darwin", jetzt)
    assert name.endswith(".sh") and "kill -0 42" in sh and 'mv "/Users/x/Documents/Job-Monitor"' in sh
    assert "Job-Monitor (alt 2026-11-05 0930)" in sh
    name, cmd = zuruecksetzen.skript(Path(r"C:\Users\x\Documents\Job-Monitor"), 42, False, "win32", jetzt)
    assert name.endswith(".cmd") and 'PID eq 42' in cmd and r'rmdir /s /q "C:\Users\x\Documents\Job-Monitor"' in cmd


def test_karte_nur_ausserhalb_des_codes(tmp_path):
    import html
    assert 'value="zuruecksetzen"' in zuruecksetzen.karte("t", tmp_path / "Job-Monitor", html.escape)
    from jobmonitor.config import CODE
    entwicklung = zuruecksetzen.karte("t", CODE, html.escape)
    assert 'href="/einrichten"' in entwicklung and 'value="zuruecksetzen"' not in entwicklung


# --- Startmenü ---
def test_startmenue_ruft_powershell_mit_pfad():
    gesehen = {}

    def run(cmd, env=None, **kw):
        gesehen.update(cmd=cmd, exe=env["JM_EXE"])
    assert app_start.startmenue(r"C:\Apps\Job-Monitor\Job-Monitor.exe", run=run)
    assert gesehen["cmd"][0] == "powershell" and "Job-Monitor.lnk" in gesehen["cmd"][-1]
    assert gesehen["exe"] == r"C:\Apps\Job-Monitor\Job-Monitor.exe"
