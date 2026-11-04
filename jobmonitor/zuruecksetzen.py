"""App zurücksetzen (Einstellungen → Neu einrichten): danach startet Job-Monitor wie frisch installiert.

Was passiert:
- sofort: KI-Schlüssel aller Anbieter aus dem Schlüsselbund bzw. der Windows-Anmeldeinformationsverwaltung entfernen
  (wenn gewünscht) und die tägliche Suche aus dem Zeitplan nehmen;
- nach dem Beenden: der Datenordner (Dokumente/Job-Monitor) wird gelöscht oder – Standard – als
  „Job-Monitor (alt JJJJ-MM-TT HHMM)“ daneben aufgehoben. Das erledigt ein kleines Hilfsskript, das wartet, bis die App
  beendet ist (geöffnete Dateien lassen sich unter Windows nicht löschen). Klappt das nicht, holt der nächste Start es
  nach (Merker .zuruecksetzen.json, siehe app_start.py).

Nur für den getrennten Datenordner der installierten App – nie für einen Entwicklungsordner, in dem Code und Daten
zusammen liegen.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .config import CODE

MARKE = ".zuruecksetzen.json"


class ZuruecksetzenError(Exception):
    pass


def moeglich(root: Path) -> bool:
    """Nur, wenn der Datenordner nicht zugleich der Programmordner ist."""
    try:
        return root.resolve() != CODE.resolve() and CODE.resolve() not in root.resolve().parents
    except OSError:
        return False


def sicherungsname(root: Path, jetzt: datetime | None = None) -> Path:
    return root.with_name(f"{root.name} (alt {(jetzt or datetime.now()):%Y-%m-%d %H%M})")


def schluessel_entfernen(run=subprocess.run, plattform: str | None = None) -> None:
    """KI-Schlüssel aller Anbieter entfernen (fehlende werden still übersprungen)."""
    from . import ki, ki_anbieter
    dienste = [ki.DIENST if a == "claude" else f"job-monitor-{a}" for a in ki_anbieter.ANBIETER]
    if (plattform or sys.platform) == "darwin":
        for dienst in dienste:
            try:
                run(["security", "delete-generic-password", "-s", dienst], capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
        return
    tresor = ki._keyring()
    for dienst in dienste:
        try:
            tresor and tresor.delete_password(dienst, "job-monitor")
        except Exception:   # nicht vorhanden – nichts zu tun
            pass


def startmenue_entfernen(plattform: str | None = None) -> None:
    """Windows: Startmenü-Eintrag entfernen (startet man die App wieder, legt sie ihn neu an)."""
    if (plattform or sys.platform) != "win32" or not os.environ.get("APPDATA"):
        return
    try:
        (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Job-Monitor.lnk").unlink()
    except OSError:
        pass


def vormerken(root: Path, sicherung: bool, schluessel: bool, run=subprocess.run) -> None:
    if not moeglich(root):
        raise ZuruecksetzenError("Im Entwicklungsordner nicht möglich – Code und Daten liegen dort zusammen.")
    if schluessel:
        schluessel_entfernen(run)
    try:
        from . import zeitplan
        zeitplan.ausschalten(root, run=run)
    except Exception:   # kein Zeitplan eingerichtet – nichts zu tun
        pass
    startmenue_entfernen()
    (root / MARKE).write_text(json.dumps({"sicherung": sicherung, "datum": datetime.now().isoformat()}),
                              encoding="utf-8")


def skript(root: Path, pid: int, sicherung: bool, plattform: str | None = None,
           jetzt: datetime | None = None) -> tuple[str, str]:
    """(Dateiname, Inhalt) des Hilfsskripts, das nach dem Beenden der App den Datenordner wegräumt."""
    ziel = sicherungsname(root, jetzt)
    if (plattform or sys.platform) == "darwin":
        aktion = f'mv "{root}" "{ziel}"' if sicherung else f'rm -rf "{root}"'
        return "zuruecksetzen.sh", ("#!/bin/bash\n"
                                    f"while kill -0 {pid} 2>/dev/null; do sleep 0.5; done\n"
                                    f"{aktion}\n"
                                    'rm -f "$0"\n')
    aktion = f'move "{root}" "{ziel}" >nul' if sicherung else f'rmdir /s /q "{root}"'
    return "zuruecksetzen.cmd", ("@echo off\r\n"
                                 ":warten\r\n"
                                 f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul && '
                                 f'(timeout /t 1 /nobreak >nul & goto warten)\r\n'
                                 f"{aktion}\r\n"
                                 '(goto) 2>nul & del "%~f0"\r\n')


def nach_beenden(root: Path, sicherung: bool) -> None:
    """Hilfsskript im Temp-Ordner starten; es läuft weiter, wenn sich die App beendet."""
    name, inhalt = skript(root, os.getpid(), sicherung)
    pfad = Path(tempfile.gettempdir()) / name
    pfad.write_text(inhalt, encoding="utf-8", newline="")
    if sys.platform == "darwin":
        pfad.chmod(0o755)
        subprocess.Popen(["/bin/bash", str(pfad)], start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(["cmd", "/c", str(pfad)], creationflags=flags, close_fds=True)


def beim_start(home: Path) -> str:
    """Vorgemerktes Zurücksetzen nachholen (falls das Hilfsskript es nicht geschafft hat). Vor allem anderen aufrufen,
    bevor Dateien im Datenordner geöffnet werden."""
    marke = home / MARKE
    if not marke.is_file() or not moeglich(home):
        return ""
    try:
        sicherung = bool(json.loads(marke.read_text(encoding="utf-8")).get("sicherung", True))
    except (OSError, ValueError):
        sicherung = True
    if sicherung:
        ziel = sicherungsname(home)
        home.rename(ziel)
        return f"Alte Daten aufgehoben in {ziel}"
    shutil.rmtree(home)
    return "Alte Daten gelöscht"


def karte(token: str, root: Path, esc) -> str:
    if not moeglich(root):
        return ""
    return (f'<div class="card" id="zuruecksetzen"><h2>Neu einrichten</h2><p>Setzt Job-Monitor zurück, als wäre die '
            f'App frisch installiert: Danach startet wieder der Einrichtungs-Assistent.</p>'
            f'<form method="post" action="/einstellungen"><input type="hidden" name="token" value="{token}">'
            f'<input type="hidden" name="aktion" value="zuruecksetzen">'
            f'<label class="check"><input type="checkbox" name="sicherung" value="1" checked> Alte Daten als Sicherung '
            f'aufheben (Ordner wird umbenannt in „{esc(sicherungsname(root).name)}“)</label>'
            f'<label class="check"><input type="checkbox" name="schluessel" value="1" checked> KI-Schlüssel vom '
            f'Rechner entfernen</label>'
            f'<p class="muted">Die tägliche Suche wird ausgeschaltet. Die App beendet sich danach; beim nächsten Start '
            f'beginnt alles neu. Ohne Sicherung werden Lebenslauf, Bewerbungen und Einstellungen endgültig gelöscht.</p>'
            f'<button class="ghost small" onclick="return confirm(\'Job-Monitor wirklich zurücksetzen? Die App beendet '
            f'sich danach.\')">Zurücksetzen und beenden</button></form></div>')
