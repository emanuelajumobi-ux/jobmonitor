"""Neue Version mit einem Klick installieren (nur die installierte App unter macOS und Windows).

Ablauf: Paket der neuen Version vom öffentlichen Download-Repo laden (nur über die Release-Adresse von GitHub, mit
Prüfung der SHA-256-Prüfsumme, die GitHub zu jedem Release-Paket angibt), neben der App entpacken, ein kleines
Hilfsskript starten und die App beenden. Das Skript wartet, bis die App zu ist, tauscht den Programmordner aus
(die alte Fassung bleibt bis zum Erfolg als Sicherung) und startet die neue App. Die Daten im Datenordner
(Dokumente/Job-Monitor) werden nicht angefasst.

Geht etwas schief (keine Schreibrechte, kein Netz, Prüfsumme falsch), bleibt alles, wie es war – dann hilft der
Download-Link wie bisher.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from . import __version__

API = "https://api.github.com/repos/{repo}/releases/tags/v{version}"
ORDNER = ".job-monitor-update"


class UpdateError(Exception):
    pass


def paketname(plattform: str | None = None) -> str:
    return "Job-Monitor-Mac.zip" if (plattform or sys.platform) == "darwin" else "Job-Monitor-Windows.zip"


def programm(executable: str | None = None, plattform: str | None = None) -> Path:
    """Was ausgetauscht wird: unter macOS das .app-Paket, unter Windows der Programmordner."""
    exe = Path(executable or sys.executable).resolve()
    return exe.parents[2] if (plattform or sys.platform) == "darwin" else exe.parent


def moeglich() -> bool:
    if not getattr(sys, "frozen", False) or sys.platform not in ("darwin", "win32"):
        return False
    ziel = programm()
    return os.access(ziel.parent, os.W_OK) and os.access(ziel, os.W_OK)


def _paket(repo: str, version: str, get) -> tuple[str, str]:
    """(Download-Adresse, SHA-256) des passenden Pakets."""
    resp = get(API.format(repo=repo, version=version), timeout=10,
               headers={"Accept": "application/vnd.github+json", "User-Agent": f"job-monitor/{__version__}"})
    if resp.status_code != 200:
        raise UpdateError(f"Version {version} nicht gefunden (GitHub antwortet mit {resp.status_code}).")
    name = paketname()
    asset = next((a for a in resp.json().get("assets") or [] if a.get("name") == name), None)
    if asset is None:
        raise UpdateError(f"Im Release fehlt {name}.")
    url = str(asset.get("browser_download_url") or "")
    if not url.startswith(f"https://github.com/{repo}/releases/download/"):
        raise UpdateError("Unerwartete Download-Adresse – Update abgebrochen.")
    digest = str(asset.get("digest") or "")
    if not digest.startswith("sha256:"):
        raise UpdateError("GitHub nennt keine Prüfsumme für das Paket – Update abgebrochen.")
    return url, digest.removeprefix("sha256:")


def herunterladen(repo: str, version: str, get=None) -> Path:
    """Neue Version laden, prüfen und entpacken. Gibt den Pfad der entpackten App bzw. des Programmordners zurück."""
    import requests
    get = get or requests.get
    url, sha = _paket(repo, version, get)
    arbeit = programm().parent / ORDNER
    shutil.rmtree(arbeit, ignore_errors=True)
    arbeit.mkdir(parents=True)
    zip_pfad = arbeit / paketname()
    pruef = hashlib.sha256()
    try:
        with get(url, stream=True, timeout=60, headers={"User-Agent": f"job-monitor/{__version__}"}) as resp:
            if resp.status_code != 200:
                raise UpdateError(f"Download fehlgeschlagen (HTTP {resp.status_code}).")
            with open(zip_pfad, "wb") as fh:
                for block in resp.iter_content(1 << 16):
                    pruef.update(block)
                    fh.write(block)
    except requests.RequestException as exc:
        raise UpdateError(f"Download fehlgeschlagen ({exc.__class__.__name__}).") from None
    if pruef.hexdigest() != sha.lower():
        shutil.rmtree(arbeit, ignore_errors=True)
        raise UpdateError("Die Prüfsumme des Downloads stimmt nicht – Update abgebrochen.")
    return entpacken(zip_pfad, arbeit / "neu")


def entpacken(zip_pfad: Path, ziel: Path, plattform: str | None = None) -> Path:
    plattform = plattform or sys.platform
    ziel.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_pfad) as z:
        for name in z.namelist():   # keine Pfade außerhalb des Zielordners
            if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                raise UpdateError("Ungültiges Paket – Update abgebrochen.")
    if plattform == "darwin":       # ditto erhält Rechte und Verknüpfungen im .app-Paket
        subprocess.run(["ditto", "-x", "-k", str(zip_pfad), str(ziel)], check=True, timeout=300)
        neu = ziel / "Job-Monitor.app"
    else:
        with zipfile.ZipFile(zip_pfad) as z:
            z.extractall(ziel)
        neu = ziel / "Job-Monitor"
    if not neu.exists():
        raise UpdateError("Das Paket enthält keine App – Update abgebrochen.")
    return neu


def skript(alt: Path, neu: Path, pid: int, plattform: str | None = None) -> tuple[str, str]:
    """(Dateiname, Inhalt) des Hilfsskripts, das nach dem Beenden der App tauscht und neu startet."""
    arbeit = neu.parent.parent
    sicherung = alt.with_name(alt.name + ".alt")
    if (plattform or sys.platform) == "darwin":
        return "tauschen.sh", (
            "#!/bin/bash\n"
            f"while kill -0 {pid} 2>/dev/null; do sleep 0.5; done\n"
            f'rm -rf "{sicherung}"\n'
            f'if mv "{alt}" "{sicherung}"; then\n'
            f'  if mv "{neu}" "{alt}"; then rm -rf "{sicherung}" "{arbeit}"; else mv "{sicherung}" "{alt}"; fi\n'
            "fi\n"
            f'open "{alt}"\n')
    return "tauschen.cmd", (
        "@echo off\r\n"
        ":warten\r\n"
        f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul && (timeout /t 1 /nobreak >nul & goto warten)\r\n'
        f'if exist "{sicherung}" rmdir /s /q "{sicherung}"\r\n'
        f'move "{alt}" "{sicherung}" >nul || goto start\r\n'
        f'move "{neu}" "{alt}" >nul && rmdir /s /q "{sicherung}" || move "{sicherung}" "{alt}" >nul\r\n'
        ":start\r\n"
        f'start "" "{alt}\\Job-Monitor.exe"\r\n'
        f'rmdir /s /q "{arbeit}"\r\n')   # zuletzt: das Skript liegt selbst in diesem Ordner


def tauschen_starten(neu: Path) -> None:
    """Hilfsskript starten (läuft weiter, wenn die App sich beendet)."""
    alt = programm()
    name, inhalt = skript(alt, neu, os.getpid())
    pfad = neu.parent.parent / name
    pfad.write_text(inhalt, encoding="utf-8", newline="")
    if sys.platform == "darwin":
        pfad.chmod(0o755)
        subprocess.Popen(["/bin/bash", str(pfad)], start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(["cmd", "/c", str(pfad)], creationflags=flags, close_fds=True)
