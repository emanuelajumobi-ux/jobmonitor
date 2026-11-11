"""Nur eine Suche gleichzeitig."""
import os

from jobmonitor import sperre


def test_zweite_suche_wartet_nicht_sondern_ueberspringt(tmp_path):
    a, b = sperre.Sperre(tmp_path), sperre.Sperre(tmp_path)
    assert a.holen()
    assert not b.holen()                                     # zweite Suche: übersprungen
    assert (tmp_path / "state" / sperre.DATEI).read_text() == str(os.getpid())
    a.freigeben()
    assert b.holen()
    b.freigeben()


def test_laeuft_prueft_nur_die_prozessnummer(tmp_path):
    assert not sperre.laeuft(tmp_path)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / sperre.DATEI).write_text("1")       # Prozess 1 (launchd/init) lebt immer
    assert sperre.laeuft(tmp_path)
    (tmp_path / "state" / sperre.DATEI).write_text("999999")
    assert not sperre.laeuft(tmp_path)


def test_runner_ueberspringt_wenn_schon_eine_laeuft(tmp_path, monkeypatch, caplog):
    import logging
    from jobmonitor import runner
    andere = sperre.Sperre(tmp_path)
    assert andere.holen()
    opts = runner.Options(root=tmp_path) if hasattr(runner, "Options") else None
    monkeypatch.setattr(runner, "_run", lambda o: 99)
    with caplog.at_level(logging.INFO):
        assert runner.run(opts) == 0 and "läuft schon eine Suche" in caplog.text
    andere.freigeben()
    assert runner.run(opts) == 99


def test_zwei_schreiber_sperren_sich_nicht_gegenseitig(tmp_path):
    """Früher hielt die Suche eine offene Schreib-Transaktion – eine zweite Verbindung bekam „database is locked“."""
    from jobmonitor.state import State
    pfad = tmp_path / "seen.sqlite"
    a, b = State(pfad), State(pfad)
    a.set_meta("x", "1")                        # erste Suche schreibt (z. B. während der Quellenabfrage)
    b.db.execute("PRAGMA busy_timeout = 200")
    b.set_meta("y", "2")                        # zweite schreibt gleich danach – ohne zu warten oder zu scheitern
    a.close(), b.close()
    c = State(pfad, readonly=True)
    assert c.get_meta("x") == "1" and c.get_meta("y") == "2"
    c.close()


def test_entwurf_mit_adresse_als_abschnitt(tmp_path):
    """Lena: Adresse im Einrichtungs-Assistenten eingetragen (strasse/plz/ort) – der Entwurf brach die Suche ab."""
    from datetime import date
    from jobmonitor import drafts
    (tmp_path / "cv").mkdir()
    (tmp_path / "cv" / "profile.yaml").write_text(
        "name: Lena Brandt\nadresse:\n  strasse: Karl-Liebknecht-Straße 112\n  plz: '04275'\n  ort: Leipzig\n",
        encoding="utf-8")
    profil = drafts.load_profile(tmp_path)
    text = drafts.render({"name": "Muster GmbH"}, profil, {}, date(2026, 11, 9))
    assert "Leipzig, 09.11.2026" in text and "Karl-Liebknecht-Straße 112, 04275 Leipzig" in text


def test_toter_host_wird_im_lauf_uebersprungen():
    """Leipziger Gruppe: Server antwortet nie – früher je Abruf 25 s gewartet (robots.txt, Seite, Wiederholungen)."""
    import pytest
    import requests
    from jobmonitor.http import Fetcher
    aufrufe = []

    class Sitzung:
        headers = {}

        def get(self, url, **kw):
            aufrufe.append(url)
            raise requests.ConnectTimeout("timed out")

        def request(self, method, url, **kw):
            aufrufe.append(url)
            raise requests.ConnectTimeout("timed out")
    f = Fetcher("test", 0, 1, 2, session=Sitzung(), sleep=lambda s: None)
    for _ in range(3):
        with pytest.raises(requests.ConnectionError):
            f.get("https://tot.example/karriere/")
    assert aufrufe == ["https://tot.example/robots.txt"]            # ein Versuch, danach sofort übersprungen


def test_beschaedigte_datenbank(tmp_path):
    from jobmonitor.state import State
    pfad = tmp_path / "seen.sqlite"
    pfad.write_bytes(b"keine datenbank")
    lesen = State(pfad, readonly=True)                     # Oberfläche: leere Liste statt Absturz
    assert lesen.job_details() == [] and lesen.last_success() is None
    lesen.close()
    schreiben = State(pfad)                                # Suche: kaputte Datei beiseite, neu beginnen
    schreiben.set_meta("x", "1")
    schreiben.close()
    assert (tmp_path / "seen.kaputt.sqlite").read_bytes() == b"keine datenbank"
    assert State(pfad, readonly=True).get_meta("x") == "1"


def test_leere_firmenliste_und_falsch_bearbeiteter_lebenslauf(tmp_path):
    import pytest
    from jobmonitor.config import load_companies
    from jobmonitor.cv_data import CvDataError, load_cv_master
    (tmp_path / "companies.yaml").write_text("", encoding="utf-8")
    assert load_companies(tmp_path / "companies.yaml")["firmen"] == []
    (tmp_path / "cv").mkdir()
    cv = tmp_path / "cv" / "cv_master.yaml"
    cv.write_text("profil: Text\nsprachen: 5\n", encoding="utf-8")
    with pytest.raises(CvDataError, match="sprachen"):
        load_cv_master(tmp_path)
    cv.write_text("profil: Text\nprojekte:\nkenntnisse:\n  - kategorie: Office\n    eintraege: [{name: Excel}]\n", encoding="utf-8")
    daten, _ = load_cv_master(tmp_path)
    assert daten["projekte"] == [] and daten["kenntnisse"][0]["eintraege"][0]["name"] == "Excel"


def test_entwurf_ohne_feste_it_schwerpunkte():
    """Die Vorlage nannte fest „Cloud (Azure), Entra ID, DevSecOps“ – bei einer BWL-Studentin falsch."""
    from datetime import date
    from jobmonitor import drafts
    cv = {"kenntnisse": [{"kategorie": "Office", "eintraege": [{"name": "Excel"}, {"name": "Power BI"}, {"name": "SAP"}]}]}
    text = drafts.render({"name": "Muster GmbH", "standorte": ["Leipzig"]}, {"name": "Lena"},
                         {"zielrolle": "Werkstudentin Marketing", "absicht": "eine Werkstudentenstelle"},
                         date(2026, 11, 11), cv)
    assert "Azure" not in text and "Cloud" not in text and "Entra" not in text
    assert "Meine Schwerpunkte sind Excel, Power BI und SAP." in text and "Werkstudentin Marketing" in text
    assert "Ich suche eine Werkstudentenstelle." in text
    eigen = drafts.render({"name": "X"}, {"studium": "BWL, Uni Leipzig", "zeitraum": "April"},
                          {"schwerpunkt": "Mein Schwerpunkt ist Controlling."}, date(2026, 11, 11), cv)
    assert "Mein Schwerpunkt ist Controlling." in eigen and "Ich studiere BWL, Uni Leipzig und suche ab April" in eigen


def test_zeitplan_folgt_der_verschobenen_app(tmp_path, monkeypatch):
    """App von „Downloads“ nach „Programme“ verschoben: der Zeitplan muss auf den neuen Ort zeigen."""
    from jobmonitor import zeitplan
    ort = ["/alt/Job-Monitor.app/Contents/MacOS/Job-Monitor"]
    monkeypatch.setattr(zeitplan, "befehl", lambda root: [ort[0], "run", "--mitteilung"])
    monkeypatch.setattr(zeitplan, "plist_pfad", lambda: tmp_path / "x.plist")
    aufrufe = []

    def run(cmd, **kw):
        aufrufe.append(cmd[:2])
        return __import__("subprocess").CompletedProcess(cmd, 0, "", "")
    zeitplan.einschalten(tmp_path, "07:30", run, "darwin")
    assert not zeitplan.auffrischen(tmp_path, run, "darwin")           # gleicher Ort: nichts zu tun
    ort[0] = "/Applications/Job-Monitor.app/Contents/MacOS/Job-Monitor"
    n = len(aufrufe)
    assert zeitplan.auffrischen(tmp_path, run, "darwin") and len(aufrufe) > n
    assert zeitplan.laden(tmp_path)["befehl"][0] == ort[0] and zeitplan.laden(tmp_path)["uhrzeit"] == "07:30"
    assert b"/Applications/Job-Monitor.app" in (tmp_path / "x.plist").read_bytes()
    from jobmonitor import verschieben

    def unbekannt(*a):
        raise verschieben.VerschiebenError("echter Ort unbekannt")
    monkeypatch.setattr(verschieben, "original", unbekannt)
    monkeypatch.setattr("sys.platform", "darwin")
    ort[0] = "/private/var/folders/x/AppTranslocation/A/d/Job-Monitor.app/Contents/MacOS/Job-Monitor"
    assert not zeitplan.auffrischen(tmp_path, run, "darwin")           # flüchtiger Ort: nie eintragen
    monkeypatch.setattr(verschieben, "original", lambda *a: __import__("pathlib").Path("/Users/x/Downloads/Job-Monitor.app"))
    assert zeitplan.befehl_dauerhaft(tmp_path)[0] == "/Users/x/Downloads/Job-Monitor.app/Contents/MacOS/Job-Monitor"
