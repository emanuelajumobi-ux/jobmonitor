"""Startpunkt der installierten App (PyInstaller, Mac und Windows).

Ohne Argumente: Datenordner vorbereiten (Standard: Dokumente/Job-Monitor, änderbar über JOBMONITOR_HOME) und das
App-Fenster öffnen. Mit Argumenten verhält sich die App wie `python -m jobmonitor …` – so starten Zeitplan,
Probelauf und PDF-Erzeugung ihre Hintergrund-Prozesse (prozess.befehl).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _protokoll(home: Path) -> None:
    """Fenster-Apps (vor allem unter Windows) haben keine Konsole: Ausgabe und Fehler in eine Datei im Datenordner,
    statt sie zu verlieren oder einen blockierenden Fehlerdialog zu zeigen."""
    for strom in (sys.stdout, sys.stderr):     # Windows-Konsole (cp1252) kennt ✅ und „“ nicht
        if strom is not None and hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    if sys.stdout is not None and sys.stderr is not None:
        return
    (home / ".gui_aufgaben").mkdir(parents=True, exist_ok=True)
    datei = open(home / ".gui_aufgaben" / "app.log", "a", encoding="utf-8", buffering=1)   # noqa: SIM115
    sys.stdout = sys.stdout or datei
    sys.stderr = sys.stderr or datei


def main() -> int:
    os.environ.setdefault("JOBMONITOR_HOME", str(Path.home() / "Documents" / "Job-Monitor"))
    _protokoll(Path(os.environ["JOBMONITOR_HOME"]).expanduser())
    try:
        return _start()
    except SystemExit as exc:
        return int(exc.code or 0) if isinstance(exc.code, int) or exc.code is None else 1
    except BaseException:
        import traceback
        traceback.print_exc()
        return 1


def _start() -> int:
    from jobmonitor import erststart
    from jobmonitor.__main__ import main as cli      # erst jetzt: config.ROOT liest JOBMONITOR_HOME beim Import
    from jobmonitor.config import ROOT
    erststart.vorbereiten(ROOT)                      # legt nur Fehlendes an, auch vor Zeitplan-Läufen
    return cli(sys.argv[1:] if len(sys.argv) > 1 else ["desktop"])


if __name__ == "__main__":
    sys.exit(main())
