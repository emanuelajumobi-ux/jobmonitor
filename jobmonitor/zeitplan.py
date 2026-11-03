"""Suche auf diesem Rechner statt auf GitHub (Einstellungen → Zeitplan).

Für alle ohne GitHub-Repo: Die tägliche Suche läuft lokal. Zwei Wege, die sich ergänzen:
- Solange die App offen ist, prüft sie alle STUNDE_S Sekunden, ob die Suche fällig ist, und startet sie im
  Hintergrund (`python -m jobmonitor run` – das Skript selbst entscheidet nach Kalendertag und Modus, ob es sucht).
- macOS: zusätzlich ein Startobjekt (LaunchAgent), das täglich zur gewählten Uhrzeit sucht, auch wenn die App
  geschlossen ist; ein verpasster Termin (Rechner im Ruhezustand) wird beim Aufwachen nachgeholt.
  Windows: Aufgabe in der Aufgabenplanung (schtasks). Beides lässt sich hier wieder entfernen.

Ist ein GitHub-Remote eingerichtet (wie bei der Pipeline), bleibt der lokale Zeitplan aus: Zwei Suchen würden sich
den Zustand (state/seen.sqlite) gegenseitig überschreiben.
Einstellung lokal in .gui_zeitplan.json: {an, uhrzeit}.
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import sys
import threading
from pathlib import Path

DATEI = ".gui_zeitplan.json"
LABEL = "de.jobmonitor.suche"
AUFGABE_WIN = "Job-Monitor Suche"
STUNDE_S = 3600
UHRZEIT = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ZeitplanError(Exception):
    pass


def laden(root: Path) -> dict:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def github_aktiv(root: Path, run=subprocess.run) -> bool:
    """Läuft die Suche über GitHub Actions (Repo mit Upstream und Workflow)?"""
    if not (root / ".github" / "workflows" / "monitor.yml").is_file():
        return False
    try:
        proc = run(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=root, capture_output=True, text=True)
    except OSError:
        return False
    return proc.returncode == 0


def befehl(root: Path) -> list[str]:
    from .prozess import befehl as prozess_befehl
    return prozess_befehl("run", "--mitteilung")


# --- macOS: LaunchAgent ---
def plist_pfad() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def plist_daten(root: Path, uhrzeit: str) -> dict:
    stunde, minute = (int(t) for t in uhrzeit.split(":"))
    log = str(root / ".gui_aufgaben" / "zeitplan.log")
    from .prozess import umgebung
    env = {k: v for k, v in umgebung().items() if k in ("PYTHONPATH", "JOBMONITOR_HOME")}
    return {"Label": LABEL, "ProgramArguments": befehl(root), "WorkingDirectory": str(root), "EnvironmentVariables": env,
            "StartCalendarInterval": {"Hour": stunde, "Minute": minute}, "StandardOutPath": log,
            "StandardErrorPath": log, "ProcessType": "Background"}


def _mac_einrichten(root: Path, uhrzeit: str, run) -> None:
    pfad = plist_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    (root / ".gui_aufgaben").mkdir(exist_ok=True)
    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", domain, str(pfad)], capture_output=True)       # alte Fassung entladen
    pfad.write_bytes(plistlib.dumps(plist_daten(root, uhrzeit)))
    proc = run(["launchctl", "bootstrap", domain, str(pfad)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ZeitplanError(f"Zeitplan nicht eingerichtet: {(proc.stderr or '').strip()[:200]}")


def _mac_entfernen(run) -> None:
    pfad = plist_pfad()
    run(["launchctl", "bootout", f"gui/{os.getuid()}", str(pfad)], capture_output=True)
    pfad.unlink(missing_ok=True)


# --- Windows: Aufgabenplanung ---
def _win_einrichten(root: Path, uhrzeit: str, run) -> None:
    befehl_text = f'cmd /c cd /d "{root}" && ' + " ".join(f'"{t}"' for t in befehl(root))
    proc = run(["schtasks", "/Create", "/F", "/SC", "DAILY", "/TN", AUFGABE_WIN, "/ST", uhrzeit, "/TR", befehl_text],
               capture_output=True, text=True)
    if proc.returncode != 0:
        raise ZeitplanError(f"Zeitplan nicht eingerichtet: {(proc.stderr or proc.stdout or '').strip()[:200]}")


def _win_entfernen(run) -> None:
    run(["schtasks", "/Delete", "/F", "/TN", AUFGABE_WIN], capture_output=True)


def einschalten(root: Path, uhrzeit: str = "07:00", run=subprocess.run, plattform: str = sys.platform) -> str:
    if not UHRZEIT.match(uhrzeit or ""):
        raise ZeitplanError("Uhrzeit bitte als HH:MM, z. B. 07:00.")
    if github_aktiv(root, run):
        raise ZeitplanError("Die Suche läuft über GitHub Actions – ein lokaler Zeitplan würde doppelt suchen.")
    if plattform == "darwin":
        _mac_einrichten(root, uhrzeit, run)
        wo = "auch bei geschlossener App (macOS-Startobjekt)"
    elif plattform.startswith("win"):
        _win_einrichten(root, uhrzeit, run)
        wo = "auch bei geschlossener App (Windows-Aufgabenplanung)"
    else:
        wo = "solange die App offen ist"
    (root / DATEI).write_text(json.dumps({"an": True, "uhrzeit": uhrzeit}), encoding="utf-8")
    return f"Die Suche läuft jetzt täglich um {uhrzeit} Uhr auf diesem Rechner, {wo}."


def ausschalten(root: Path, run=subprocess.run, plattform: str = sys.platform) -> str:
    if plattform == "darwin":
        _mac_entfernen(run)
    elif plattform.startswith("win"):
        _win_entfernen(run)
    (root / DATEI).write_text(json.dumps({"an": False, "uhrzeit": laden(root).get("uhrzeit", "07:00")}),
                              encoding="utf-8")
    return "Lokaler Zeitplan ausgeschaltet."


# --- solange die App offen ist ---
def wachen(root: Path, aufgaben, stop: threading.Event, intervall: float = STUNDE_S) -> None:
    """Hintergrund-Thread der App: stündlich fällige Suche starten (das Skript prüft selbst, ob heute schon)."""
    while not stop.wait(intervall):
        pruefen_und_starten(root, aufgaben)


def pruefen_und_starten(root: Path, aufgaben) -> bool:
    if not laden(root).get("an"):
        return False
    laufend = aufgaben.alle.get("zeitplan")
    if laufend is not None and laufend.laeuft:
        return False
    try:
        aufgaben.starten("zeitplan", "Tägliche Suche", befehl(root))
    except Exception:
        return False
    return True


def karte(root: Path, token: str, esc, github: bool) -> str:
    data = laden(root)
    if github:
        return ('<div class="card" id="zeitplan"><h2>Zeitplan</h2><p class="muted">Die Suche läuft täglich über '
                'GitHub Actions – ein lokaler Zeitplan ist nicht nötig.</p></div>')
    an, uhrzeit = bool(data.get("an")), data.get("uhrzeit", "07:00")
    feld = (f'<input type="hidden" name="token" value="{token}"><input type="time" name="uhrzeit" '
            f'value="{esc(uhrzeit)}" style="width:auto">')
    knopf = ('<button name="aktion" value="zeitplan_aus" class="ghost small">Ausschalten</button>' if an else
             '<button name="aktion" value="zeitplan_an" class="small">Täglich suchen</button>')
    stand = (f"An: täglich um {esc(uhrzeit)} Uhr auf diesem Rechner." if an else
             "Aus: Die Suche läuft nur, wenn du sie startest.")
    return (f'<div class="card" id="zeitplan"><h2>Zeitplan</h2><p>{stand}</p>'
            f'<form method="post" action="/einstellungen" class="row" style="gap:8px">{feld}{knopf}</form>'
            f'<p class="muted">Verpasste Termine (Rechner aus oder im Ruhezustand) holt die App nach, sobald sie '
            f'läuft. Den Bericht findest du unter „Letzter Bericht“.</p></div>')
