"""Sicherung der Daten, die nur auf diesem Mac liegen (nicht auf GitHub): persönliche Angaben, Zeugnisse, Bewerbungs-
ordner, lokale Zustände der Oberfläche – dazu zur Vollständigkeit Master-CV, config.yaml, Firmen- und Bewerbungsliste.

Mit Passwort: verschlüsseltes Disk-Image (.dmg, AES-256, macOS-Bordmittel hdiutil; das Passwort geht nur über stdin an
hdiutil, nie in eine Datei oder ins Protokoll). Ohne Passwort: ZIP. Nicht enthalten: .env und der API-Schlüssel
(Schlüsselbund) – die richtest du auf einem neuen Mac neu ein. Wiederherstellen: Image öffnen bzw. ZIP entpacken und die
Dateien in den Job-Monitor-Ordner kopieren.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ZIEL = Path.home() / "Documents" / "Job-Monitor Sicherungen"
DATEIEN = ["cv/profile.yaml", "profile.yaml", "cv/cv_master.yaml", "config.yaml", "companies.yaml", "applications.csv",
           "lernpfade.yaml", "cv/anschreiben_vorlage.txt", "cv/nachfassen_vorlage.txt"]
ORDNER = ["cv/private", "cv/bewerbungen", "cv/stellen", "drafts"]
MIN_PASSWORT = 8


class SicherungError(Exception):
    pass


def inhalt(root: Path) -> list[Path]:
    """Relative Pfade der Dateien, die gesichert werden."""
    out = [Path(f) for f in DATEIEN if (root / f).is_file()]
    out += sorted(p.relative_to(root) for p in root.glob(".gui_*.json") if p.is_file())
    for ordner in ORDNER:
        if (root / ordner).is_dir():
            out += sorted(p.relative_to(root) for p in (root / ordner).rglob("*")
                          if p.is_file() and p.name != ".DS_Store")
    return out


def erstellen(root: Path, passwort: str = "", ziel: Path = ZIEL, run=subprocess.run,
              jetzt: datetime | None = None) -> Path:
    dateien = inhalt(root)
    if not dateien:
        raise SicherungError("Nichts zu sichern gefunden.")
    if passwort and len(passwort) < MIN_PASSWORT:
        raise SicherungError(f"Das Passwort braucht mindestens {MIN_PASSWORT} Zeichen.")
    if passwort and sys.platform != "darwin":
        raise SicherungError("Verschlüsselte Sicherungen gibt es nur auf dem Mac.")
    ziel.mkdir(parents=True, exist_ok=True)
    name = f"Job-Monitor-Sicherung-{(jetzt or datetime.now()):%Y-%m-%d-%H%M}"
    with tempfile.TemporaryDirectory() as tmp:
        quelle = Path(tmp) / "Job-Monitor"
        for rel in dateien:
            (quelle / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, quelle / rel)
        (quelle / "LIESMICH.txt").write_text(
            "Sicherung von Job-Monitor. Zum Wiederherstellen die Dateien in den Job-Monitor-Ordner kopieren "
            "(gleiche Unterordner). Nicht enthalten: .env und der API-Schlüssel – neu einrichten.\n", encoding="utf-8")
        if not passwort:
            return Path(shutil.make_archive(str(ziel / name), "zip", tmp, "Job-Monitor"))
        dmg = ziel / f"{name}.dmg"
        proc = run(["hdiutil", "create", "-quiet", "-encryption", "AES-256", "-stdinpass", "-volname",
                    "Job-Monitor Sicherung", "-fs", "APFS", "-srcfolder", str(quelle), "-ov", str(dmg)],
                   input=passwort, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise SicherungError(f"Disk-Image nicht erstellt: {proc.stderr.strip()[:200] or 'hdiutil-Fehler'}")
        return dmg


def vorhandene(ziel: Path = ZIEL) -> list[Path]:
    if not ziel.is_dir():
        return []
    return sorted((p for p in ziel.iterdir() if p.suffix in (".zip", ".dmg")), key=lambda p: p.stat().st_mtime,
                  reverse=True)
