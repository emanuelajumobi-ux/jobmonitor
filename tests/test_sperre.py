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
