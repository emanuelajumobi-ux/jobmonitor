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
