"""Kalenderdatei (.ics) für Systeme ohne Apple-Kalender und -Erinnerungen (Windows, Linux).

Statt per AppleScript einzutragen, schreibt die App eine .ics-Datei nach .gui_aufgaben/kalender/ und öffnet sie mit
dem Standard-Kalender (Outlook, Windows-Kalender, Thunderbird …) – dort wird der Termin mit einem Klick übernommen.
Mit Hinweis (VALARM) vorher, wie beim Mac.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ORDNER = ".gui_aufgaben/kalender"


def verfuegbar() -> bool:
    return sys.platform.startswith("win") or sys.platform.startswith("linux")


def _text(wert: str) -> str:
    return re.sub(r"([,;\\])", r"\\\1", (wert or "").replace("\r", "")).replace("\n", "\\n")


def termin(titel: str, start: datetime, dauer_min: int = 60, notiz: str = "",
           hinweise_min: tuple[int, ...] = (60,)) -> str:
    """VCALENDAR mit einem Termin (Ortszeit ohne Zeitzone – so übernehmen ihn alle Kalender als lokale Zeit)."""
    fmt = "%Y%m%dT%H%M%S"
    alarme = "".join(f"BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:{_text(titel)}\r\nTRIGGER:-PT{m}M\r\n"
                     f"END:VALARM\r\n" for m in hinweise_min)
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Job-Monitor//DE\r\nBEGIN:VEVENT\r\n"
            f"UID:{uuid.uuid4()}@job-monitor\r\nDTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}\r\n"
            f"DTSTART:{start:{fmt}}\r\nDTEND:{start + timedelta(minutes=dauer_min):{fmt}}\r\n"
            f"SUMMARY:{_text(titel)}\r\nDESCRIPTION:{_text(notiz)}\r\n{alarme}END:VEVENT\r\nEND:VCALENDAR\r\n")


def oeffnen(root: Path, name: str, inhalt: str, run=subprocess.run) -> Path:
    ordner = root / ORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / (re.sub(r"[^\w.-]+", "-", name)[:60].strip("-") + ".ics")
    datei.write_text(inhalt, encoding="utf-8")
    try:
        if sys.platform.startswith("win"):
            os.startfile(datei)  # noqa: S606 – Standard-Kalender öffnet die Datei
        elif sys.platform.startswith("linux"):
            run(["xdg-open", str(datei)], capture_output=True)
    except OSError:          # kein Standard-Programm: die Datei liegt trotzdem bereit
        pass
    return datei
