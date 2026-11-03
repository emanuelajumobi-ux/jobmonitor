"""Gesprächstermine in den Apple-Kalender eintragen (auf Knopfdruck, nur lokal auf dem Mac per AppleScript).

Der Termin landet im Kalender aus config.yaml → kalender.name (wird bei Bedarf angelegt), mit Hinweisen einen Tag
und eine Stunde vorher. Beim ersten Mal fragt macOS, ob Job-Monitor den Kalender steuern darf. Eingetragenes merkt
sich die Oberfläche in .gui_kalender.json (gitignored); geändert oder gelöscht wird im Kalender nie etwas.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

LOG = ".gui_kalender.json"
DEFAULTS = {"name": "Job-Monitor", "dauer_minuten": 60}
SCRIPT = """
on run argv
    set calName to item 1 of argv
    set evTitle to item 2 of argv
    set evNotes to item 3 of argv
    set startD to current date
    set day of startD to 1
    set year of startD to (item 4 of argv) as integer
    set month of startD to (item 5 of argv) as integer
    set day of startD to (item 6 of argv) as integer
    set hours of startD to (item 7 of argv) as integer
    set minutes of startD to (item 8 of argv) as integer
    set seconds of startD to 0
    set endD to startD + ((item 9 of argv) as integer) * 60
    tell application "Calendar"
        if not (exists calendar calName) then make new calendar with properties {name:calName}
        tell calendar calName
            if (count of (events whose summary is evTitle and start date is startD)) > 0 then return "exists"
            set ev to make new event with properties {summary:evTitle, start date:startD, end date:endD, description:evNotes}
            tell ev
                make new display alarm at end with properties {trigger interval:-1440}
                make new display alarm at end with properties {trigger interval:-60}
            end tell
        end tell
    end tell
    return "ok"
end run
"""


class KalenderError(Exception):
    pass


def settings(cfg: dict) -> dict:
    return {**DEFAULTS, **(cfg.get("kalender") or {})}


def verfuegbar() -> bool:
    from . import ics
    return sys.platform == "darwin" or ics.verfuegbar()


def eingetragen(root: Path) -> set[str]:
    try:
        return set(json.loads((root / LOG).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def schluessel(link: str, termin: str) -> str:
    return f"gespraech:{link}:{termin}"


def anlegen(root: Path, cfg: dict, link: str, titel: str, start: datetime, notiz: str, run=subprocess.run) -> str:
    """Termin eintragen. Gibt „neu“ oder „vorhanden“ zurück; KalenderError bei Problemen."""
    key = schluessel(link, start.isoformat(timespec="minutes"))
    if key in eingetragen(root):
        return "vorhanden"
    if not verfuegbar():
        raise KalenderError("Den Kalender gibt es nur auf dem Mac.")
    s = settings(cfg)
    if sys.platform != "darwin":       # Windows/Linux: Kalenderdatei, die der Standard-Kalender übernimmt
        from . import ics
        ics.oeffnen(root, f"gespraech-{start:%Y-%m-%d-%H%M}", ics.termin(titel, start, int(s["dauer_minuten"]), notiz,
                                                                         (24 * 60, 60)))
        (root / LOG).write_text(json.dumps(sorted(eingetragen(root) | {key}), ensure_ascii=False, indent=1),
                                encoding="utf-8")
        return "neu"
    args = [s["name"], titel, notiz, str(start.year), str(start.month), str(start.day), str(start.hour),
            str(start.minute), str(int(s["dauer_minuten"]))]
    try:
        proc = run(["osascript", "-e", SCRIPT, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise KalenderError(f"Kalender nicht erreichbar ({exc}).") from None
    if proc.returncode != 0:
        if "-1743" in proc.stderr or "not allowed" in proc.stderr.lower() or "nicht erlaubt" in proc.stderr.lower():
            raise KalenderError("macOS hat den Zugriff auf den Kalender nicht erlaubt. Systemeinstellungen → "
                                "Datenschutz & Sicherheit → Automation → Job-Monitor → Kalender einschalten.")
        raise KalenderError(f"Termin nicht eingetragen: {proc.stderr.strip() or proc.stdout.strip()}")
    (root / LOG).write_text(json.dumps(sorted(eingetragen(root) | {key}), ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return "vorhanden" if proc.stdout.strip() == "exists" else "neu"


def vorbereitung(passt: list[str], fehlt: list[str]) -> list[str]:
    """Kurze Liste „Darauf vorbereiten“ aus den Anforderungen der Anzeige und deinem Master-CV."""
    out = []
    if passt:
        out.append(f"Je ein konkretes Beispiel parat haben: {', '.join(passt[:6])}")
    if fehlt:
        out.append(f"Ehrlich einordnen, was du davon kennst und wie du es lernst: {', '.join(fehlt[:6])}")
    out.append("Eigene Fragen zum Team, zu Aufgaben im ersten Monat und zur Bachelorarbeit/Übernahme notieren")
    return out
