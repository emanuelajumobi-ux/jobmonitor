"""Lücken der installierten App: Mail-Bericht an sich selbst, Stellenwerk-Portale für den Wohnort, Kalenderdateien
und Mitteilungen unter Windows, Wartungsknöpfe nur im Entwicklungsordner."""
import json
import os
import subprocess
import sys
from datetime import datetime

from jobmonitor import benachrichtigung, erststart, hochschulboersen, ics, kalender, mailzugang
from jobmonitor import gui_wartung as gw
from jobmonitor.config import load_companies
from jobmonitor.erinnerungen import Erinnerung
from jobmonitor import erinnerungen


def test_bericht_per_mail(tmp_path, monkeypatch):
    for k in ("IMAP_USER", "SMTP_USER", "MAIL_TO", "SMTP_HOST"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / mailzugang.DATEI).write_text(json.dumps({"anbieter": "gmx", "host": "imap.gmx.net",
                                                         "benutzer": "lena@gmx.de"}))
    monkeypatch.setattr(mailzugang, "passwort", lambda b, run=None: "app-pw")
    assert "nur an dich" in mailzugang.bericht_schalten(tmp_path, True)
    assert mailzugang.umgebung_setzen(tmp_path)
    assert os.environ["SMTP_HOST"] == "mail.gmx.net" and os.environ["MAIL_TO"] == "lena@gmx.de"
    assert os.environ["SMTP_PASSWORD"] == "app-pw" and os.environ["JOBMONITOR_BERICHT_MAIL"] == "1"
    assert mailzugang.smtp_host({"anbieter": "anderer", "host": "imap.example.de"}) == "smtp.example.de"
    for k in ("IMAP_USER", "IMAP_HOST", "IMAP_PASSWORD", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
              "MAIL_FROM", "MAIL_TO", "JOBMONITOR_BERICHT_MAIL"):
        monkeypatch.delenv(k, raising=False)
    mailzugang.bericht_schalten(tmp_path, False)
    mailzugang.umgebung_setzen(tmp_path)
    assert "IMAP_USER" in os.environ and "SMTP_USER" not in os.environ


def test_stellenwerk_portale(tmp_path):
    erststart.vorbereiten(tmp_path)
    nah = hochschulboersen.vorschlaege("Köln", {"köln": 0, "bonn": 30, "düsseldorf": 30, "aachen": 70})
    assert [k for k, _ in nah] == ["bonn-rhein-sieg", "duesseldorf", "koeln"]
    assert hochschulboersen.eintragen(tmp_path, ["koeln", "gibtsnicht"]) == ["Köln"]
    assert hochschulboersen.eintragen(tmp_path, ["koeln"]) == []                     # nicht doppelt
    h = load_companies(tmp_path / "companies.yaml")["hochschulen"]
    assert h[0]["quelle"] == "stellenwerk" and h[0]["karriereseite_url"] == "https://www.stellenwerk.de/koeln"


def test_kalenderdatei(tmp_path, monkeypatch):
    text = ics.termin("Gespräch, Beispiel AG; Raum 2", datetime(2026, 11, 12, 14), 60, "Zeile 1\nZeile 2", (60,))
    assert "DTSTART:20261112T140000" in text and "DTEND:20261112T150000" in text
    assert r"SUMMARY:Gespräch\, Beispiel AG\; Raum 2" in text and "TRIGGER:-PT60M" in text
    monkeypatch.setattr(sys, "platform", "linux")
    geoeffnet = []
    monkeypatch.setattr(ics, "oeffnen", lambda root, name, inhalt, run=None: geoeffnet.append(name))
    assert kalender.verfuegbar() and erinnerungen.verfuegbar()
    assert kalender.anlegen(tmp_path, {}, "https://x/1", "Vorstellungsgespräch", datetime(2026, 11, 12, 14), "") == "neu"
    assert kalender.anlegen(tmp_path, {}, "https://x/1", "Vorstellungsgespräch", datetime(2026, 11, 12, 14), "") \
        == "vorhanden"
    e = Erinnerung("frist:x", "Frist: Beispiel AG", datetime(2026, 11, 20, 9))
    assert erinnerungen.anlegen(tmp_path, {}, e) == "neu"
    assert geoeffnet[0].startswith("gespraech-2026-11-12") and geoeffnet[1].startswith("erinnerung-2026-11-20")


def test_mitteilung_windows(tmp_path, monkeypatch):
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "2026-11-03.md").write_text("## Neue Stellen – Werkstudent (2)\n## Neue Stellen – Junior (1)\n")
    assert benachrichtigung.neue_im_bericht(tmp_path, "2026-11-03") == 3
    assert benachrichtigung.neue_im_bericht(tmp_path, "2026-11-04") == 0
    monkeypatch.setattr(sys, "platform", "win32")
    aufrufe = []
    run = lambda cmd, **kw: aufrufe.append((cmd, kw)) or subprocess.CompletedProcess(cmd, 0)  # noqa: E731
    assert benachrichtigung.senden(tmp_path, "3 neue Stellen", "Öffne Job-Monitor", run=run) == "windows"
    cmd, kw = aufrufe[0]
    assert cmd[0] == "powershell" and kw["env"]["JM_TEXT"] == "Öffne Job-Monitor" and "ShowBalloonTip" in cmd[-1]


def test_wartung_in_der_installierten_app(monkeypatch):
    class A:
        alle = {}

        def laeuft(self):
            return False
    html = gw.render("t", "", A(), [], "")
    assert "Pakete installieren" in html and "Selbsttest" in html
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    html = gw.render("t", "", A(), [], "")
    assert "Pakete installieren" not in html and "Selbsttest" not in html and "App neu bauen" not in html
    assert "Neue Versionen gibt es als Download" in html
