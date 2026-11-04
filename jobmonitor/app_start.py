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


def startbild_schliessen() -> None:
    """Startbild unter Windows (PyInstaller --splash) schließen – sobald das Fenster da ist oder etwas schiefging."""
    try:
        import pyi_splash   # gibt es nur in der Windows-App mit Startbild
        pyi_splash.close()
    except Exception:
        pass


def _freigeben() -> None:
    """Windows: Dateien aus einer heruntergeladenen ZIP tragen die Markierung „aus dem Internet“ (Zone.Identifier).
    .NET lädt so markierte DLLs nicht – dann scheitert das App-Fenster (pythonnet: „Failed to resolve
    Python.Runtime.Loader.Initialize“). Wie „Eigenschaften → Zulassen“: Markierung an den eigenen Programmdateien
    entfernen. Betrifft nur den Programmordner der App."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False) or os.environ.get("JOBMONITOR_OHNE_FREIGABE"):
        return
    ordner = Path(sys.executable).resolve().parent
    stichprobe = ordner / "_internal" / "pythonnet" / "runtime" / "Python.Runtime.dll"
    if stichprobe.exists() and not os.path.exists(f"{stichprobe}:Zone.Identifier"):
        return     # schon freigegeben (schneller Start); nach neuem Entpacken ist die Markierung wieder da
    n = 0
    for datei in ordner.rglob("*"):
        if datei.suffix.lower() in (".dll", ".exe", ".pyd") and datei.is_file():
            try:
                os.remove(f"{datei}:Zone.Identifier")
                n += 1
            except OSError:
                pass
    if n:
        print(f"Internet-Markierung an {n} Programmdateien entfernt", flush=True)


def _meldung(text: str) -> None:
    """Windows: Fehler beim Start als Meldungsfenster zeigen – sonst sieht man nach dem Doppelklick gar nichts.
    Nur beim Start per Doppelklick (ohne Argumente) und nicht in GitHub Actions (dort würde der Dialog hängen)."""
    if sys.platform != "win32" or len(sys.argv) > 1 or os.environ.get("CI"):
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "Job-Monitor", 0x10)
    except Exception:
        pass


def main() -> int:
    os.environ.setdefault("JOBMONITOR_HOME", str(Path.home() / "Documents" / "Job-Monitor"))
    home = Path(os.environ["JOBMONITOR_HOME"]).expanduser()
    try:                                          # Einstellungen → Neu einrichten, falls noch nicht erledigt
        from jobmonitor.zuruecksetzen import beim_start
        if (meldung := beim_start(home)):
            print(meldung, flush=True)
    except Exception:
        pass
    _protokoll(home)
    _freigeben()
    log = home / ".gui_aufgaben" / "app.log"
    try:
        code = _start()
    except SystemExit as exc:
        code = int(exc.code or 0) if isinstance(exc.code, int) or exc.code is None else 1
    except BaseException as exc:
        import traceback
        traceback.print_exc()
        startbild_schliessen()
        _meldung(f"Job-Monitor konnte nicht starten:\n\n{type(exc).__name__}: {exc}\n\nDetails stehen in:\n{log}\n\n"
                 "Bitte diese Datei (ohne persönliche Daten) unter „Fehler melden“ oder per Nachricht schicken.")
        return 1
    startbild_schliessen()
    if code:
        _meldung(f"Job-Monitor wurde mit Fehler {code} beendet.\n\nDetails stehen in:\n{log}")
    return code


STARTMENUE_PS = (
    "$p = Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Job-Monitor.lnk';"
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p);"
    "if ($s.TargetPath -ne $env:JM_EXE) {"
    " $s.TargetPath = $env:JM_EXE; $s.WorkingDirectory = (Split-Path $env:JM_EXE);"
    " $s.IconLocation = \"$env:JM_EXE,0\"; $s.Description = 'Job-Monitor'; $s.Save() }")


def startmenue(exe: str | None = None, run=None) -> bool:
    """Windows: Eintrag im Startmenü (Benutzer, ohne Admin), damit die Windows-Suche „Job-Monitor“ findet. Zeigt er
    noch auf einen alten Ort (App verschoben oder neu entpackt), wird er auf die laufende Datei umgebogen. Ohne Fehler
    nach außen: Der Eintrag ist nur Komfort."""
    import subprocess
    exe = exe or sys.executable
    run = run or subprocess.run
    try:
        run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", STARTMENUE_PS],
            env={**os.environ, "JM_EXE": exe}, capture_output=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


def _start() -> int:
    from jobmonitor import __version__, erststart
    print(f"Job-Monitor {__version__} · {sys.platform} · Start mit {sys.argv[1:] or ['desktop']}", flush=True)
    from jobmonitor.__main__ import main as cli      # erst jetzt: config.ROOT liest JOBMONITOR_HOME beim Import
    from jobmonitor.config import ROOT
    erststart.vorbereiten(ROOT)                      # legt nur Fehlendes an, auch vor Zeitplan-Läufen
    if sys.platform == "win32" and getattr(sys, "frozen", False) and len(sys.argv) <= 1 and not os.environ.get("CI"):
        import threading
        threading.Thread(target=startmenue, daemon=True).start()   # im Hintergrund, verzögert den Start nicht
    return cli(sys.argv[1:] if len(sys.argv) > 1 else ["desktop"])


if __name__ == "__main__":
    sys.exit(main())
