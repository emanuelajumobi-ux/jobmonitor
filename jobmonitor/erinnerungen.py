"""Apple-Erinnerungen: Bewerbungsfristen und „Karriereseite mal wieder ansehen“ auf Knopfdruck in die
Erinnerungen-App eintragen, damit sie auch auf dem iPhone auftauchen. Nur lokal auf dem Mac (AppleScript).

Beim ersten Mal fragt macOS, ob Job-Monitor die Erinnerungen-App steuern darf. Eingetragenes merkt sich die
Oberfläche in .gui_erinnerungen.json (gitignored), damit nichts doppelt landet; zusätzlich prüft das Skript, ob
es in der Liste schon eine offene Erinnerung mit gleichem Titel gibt. Gelöscht oder geändert wird dort nie etwas.
Einstellungen: config.yaml → erinnerungen.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

LOG = ".gui_erinnerungen.json"
DEFAULTS = {"liste": "Job-Monitor", "vorlauf_tage": 3, "uhrzeit": "09:00"}
# Argumente statt Textbausteine im Skript: Titel und Notiz können beliebige Zeichen enthalten
SCRIPT = """
on run argv
    set listName to item 1 of argv
    set rTitle to item 2 of argv
    set rBody to item 3 of argv
    set dueD to current date
    set day of dueD to 1
    set year of dueD to (item 4 of argv) as integer
    set month of dueD to (item 5 of argv) as integer
    set day of dueD to (item 6 of argv) as integer
    set hours of dueD to (item 7 of argv) as integer
    set minutes of dueD to (item 8 of argv) as integer
    set seconds of dueD to 0
    tell application "Reminders"
        if not (exists list listName) then make new list with properties {name:listName}
        tell list listName
            if (count of (reminders whose name is rTitle and completed is false)) > 0 then return "exists"
            make new reminder with properties {name:rTitle, body:rBody, due date:dueD, remind me date:dueD}
        end tell
    end tell
    return "ok"
end run
"""


class ErinnerungError(Exception):
    pass


@dataclass
class Erinnerung:
    schluessel: str      # für das lokale Protokoll (keine Dopplungen)
    titel: str
    faellig: datetime
    notiz: str = ""


def verfuegbar() -> bool:
    from . import ics
    return sys.platform == "darwin" or ics.verfuegbar()


def settings(cfg: dict) -> dict:
    return {**DEFAULTS, **(cfg.get("erinnerungen") or {})}


def _uhrzeit(cfg: dict) -> time:
    h, _, m = str(settings(cfg)["uhrzeit"]).partition(":")
    return time(int(h), int(m or 0))


def fuer_frist(job: dict, cfg: dict, today: date | None = None) -> Erinnerung | None:
    """Erinnerung `vorlauf_tage` vor der Bewerbungsfrist (frühestens heute); None, wenn keine oder abgelaufen."""
    if not job.get("frist"):
        return None
    today = today or date.today()
    frist = date.fromisoformat(job["frist"])
    if frist < today:
        return None
    tag = max(today, frist - timedelta(days=int(settings(cfg)["vorlauf_tage"])))
    return Erinnerung(f"frist:{job['url']}", f"Bewerbungsfrist {frist:%d.%m.}: {job['title']} – {job['company']}",
                      datetime.combine(tag, _uhrzeit(cfg)), f"Frist: {frist:%d.%m.%Y}\n{job['url']}")


def fuer_besuch(name: str, url: str, faellig: date, cfg: dict) -> Erinnerung:
    """„Karriereseite ansehen“ für Firmen, die das Tool nicht automatisch lesen kann."""
    return Erinnerung(f"besuch:{name}:{faellig.isoformat()}", f"Karriereseite ansehen: {name}",
                      datetime.combine(faellig, _uhrzeit(cfg)),
                      f"{url}\nDanach in Job-Monitor → Firmen auf „Besucht“ klicken.")


def eingetragen(root: Path) -> set[str]:
    try:
        return set(json.loads((root / LOG).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _merken(root: Path, schluessel: str) -> None:
    done = eingetragen(root) | {schluessel}
    (root / LOG).write_text(json.dumps(sorted(done), ensure_ascii=False, indent=1), encoding="utf-8")


def anlegen(root: Path, cfg: dict, e: Erinnerung, run=subprocess.run) -> str:
    """In die Erinnerungen-App eintragen. Gibt „neu“ oder „vorhanden“ zurück; ErinnerungError bei Problemen."""
    if e.schluessel in eingetragen(root):
        return "vorhanden"
    if not verfuegbar():
        raise ErinnerungError("Erinnerungen gibt es nur auf dem Mac.")
    f = e.faellig
    if sys.platform != "darwin":       # Windows/Linux: Termin mit Hinweis als Kalenderdatei
        from . import ics
        ics.oeffnen(root, f"erinnerung-{f:%Y-%m-%d}-{e.titel[:30]}", ics.termin(e.titel, f, 15, e.notiz, (0,)))
        _merken(root, e.schluessel)
        return "neu"
    args = [settings(cfg)["liste"], e.titel, e.notiz, str(f.year), str(f.month), str(f.day), str(f.hour),
            str(f.minute)]
    try:
        proc = run(["osascript", "-e", SCRIPT, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ErinnerungError(f"Erinnerungen-App nicht erreichbar ({exc}).") from None
    if proc.returncode != 0:
        if "-1743" in proc.stderr or "not allowed" in proc.stderr.lower() or "nicht erlaubt" in proc.stderr.lower():
            raise ErinnerungError("macOS hat den Zugriff auf Erinnerungen nicht erlaubt. Systemeinstellungen → "
                                  "Datenschutz & Sicherheit → Automation → Job-Monitor (bzw. Python) → Erinnerungen "
                                  "einschalten, dann erneut versuchen.")
        raise ErinnerungError(f"Erinnerung nicht angelegt: {proc.stderr.strip() or proc.stdout.strip()}")
    _merken(root, e.schluessel)
    return "vorhanden" if proc.stdout.strip() == "exists" else "neu"
