"""macOS: App aus „Downloads“ in den Programme-Ordner verschieben (ein Klick in der App).

Öffnet man Job-Monitor direkt nach dem Download (Safari entpackt das ZIP und startet die App gern gleich), führt macOS
die App aus einem schreibgeschützten Ort aus („App Translocation“). Dann bleibt sie in Downloads liegen, erscheint
nicht in Launchpad und kann sich nicht selbst aktualisieren. Hier fragt die App macOS nach ihrem echten Ort, legt sich
nach /Programme (darf der Benutzer das nicht: nach ~/Programme, ohne Passwort) und startet von dort neu. Eine ältere
Job-Monitor.app am Ziel wandert in den Papierkorb. Die Download-Markierung entfernt die App dabei, damit macOS sie
am neuen Ort nicht erneut schreibgeschützt startet – geöffnet und bestätigt hat man die App an dieser Stelle schon.
Die Daten (Dokumente/Job-Monitor) bleiben, wo sie sind.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import selbstupdate


class VerschiebenError(Exception):
    pass


def noetig() -> bool:
    return bool(getattr(sys, "frozen", False)) and sys.platform == "darwin" and selbstupdate.verschoben()


def original(app: Path | None = None) -> Path:
    """Wo die App wirklich liegt (macOS: SecTranslocateCreateOriginalPathForURL)."""
    app = app or selbstupdate.programm()
    try:
        import Foundation
        import objc
        funktionen: dict = {}
        objc.loadBundleFunctions(Foundation.NSBundle.bundleWithIdentifier_("com.apple.security"), funktionen,
                                 [("SecTranslocateCreateOriginalPathForURL", b"@@o^@")])
        url, _fehler = funktionen["SecTranslocateCreateOriginalPathForURL"](
            Foundation.NSURL.fileURLWithPath_(str(app)), None)
        pfad = Path(str(url.path())) if url is not None else None
    except Exception as exc:   # noqa: BLE001 – ohne den echten Ort geht es nicht
        raise VerschiebenError(f"Den Ort der App konnte macOS nicht nennen ({exc.__class__.__name__}).") from None
    if pfad is None or not pfad.exists() or "/AppTranslocation/" in str(pfad):
        raise VerschiebenError("Den Ort der App konnte macOS nicht nennen.")
    return pfad


def zielordner(programme: Path = Path("/Applications")) -> Path:
    """/Programme, wenn der Benutzer dort schreiben darf; sonst sein eigener Programme-Ordner (~/Applications)."""
    if os.access(programme, os.W_OK):
        return programme
    eigen = Path.home() / "Applications"
    eigen.mkdir(exist_ok=True)
    return eigen


def _papierkorb(pfad: Path) -> None:
    try:
        import Foundation
        ok, _, fehler = Foundation.NSFileManager.defaultManager().trashItemAtURL_resultingItemURL_error_(
            Foundation.NSURL.fileURLWithPath_(str(pfad)), None, None)
        if ok:
            return
    except Exception:   # noqa: BLE001
        pass
    raise VerschiebenError(f"Am Ziel liegt schon {pfad.name}, und sie ließ sich nicht in den Papierkorb legen. "
                           "Bitte die alte App selbst löschen und noch einmal versuchen.")


def verschieben(quelle: Path, ziel_ordner: Path, run=subprocess.run) -> Path:
    """Quelle nach ziel_ordner verschieben (vorhandene ältere App in den Papierkorb). Gibt den neuen Pfad zurück."""
    ziel = ziel_ordner / quelle.name
    if ziel.resolve() == quelle.resolve():
        return ziel
    if ziel.exists():
        _papierkorb(ziel)
    try:
        shutil.move(str(quelle), str(ziel))
    except OSError as exc:
        raise VerschiebenError(f"Verschieben nach {ziel_ordner} ging nicht ({exc.strerror or exc}).") from None
    run(["xattr", "-dr", "com.apple.quarantine", str(ziel)], capture_output=True, timeout=60)
    return ziel


def neu_starten(app: Path, pid: int | None = None) -> None:
    """Nach dem Beenden dieser App die verschobene starten (kleines Hilfsskript im Temp-Ordner)."""
    skript = Path(tempfile.gettempdir()) / "job-monitor-verschieben.sh"
    skript.write_text("#!/bin/bash\n"
                      f"while kill -0 {pid or os.getpid()} 2>/dev/null; do sleep 0.5; done\n"
                      f'open "{app}"\n'
                      'rm -f "$0"\n', encoding="utf-8")
    skript.chmod(0o755)
    subprocess.Popen(["/bin/bash", str(skript)], start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def karte(token: str) -> str:
    """Hinweis oben auf jeder Seite, solange die App aus Downloads läuft."""
    if not noetig():
        return ""
    return ('<div class="card info verschieben"><div class="row" style="justify-content:space-between;gap:12px;'
            'flex-wrap:wrap"><p style="margin:0"><b>Job-Monitor läuft gerade aus „Downloads“.</b> <span class="muted">'
            'Verschiebe die App in den Ordner „Programme“: Dann findest du sie in Launchpad und Spotlight, und Updates '
            'gehen mit einem Klick. Deine Daten bleiben.</span></p>'
            f'<form method="post" action="/verschieben" style="margin:0"><input type="hidden" name="token" '
            f'value="{token}"><button class="small" data-laden="Job-Monitor wird verschoben …" '
            'data-laden-info="Die App startet gleich aus dem Ordner Programme neu.">In Programme verschieben</button>'
            '</form></div></div>')
