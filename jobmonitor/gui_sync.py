"""Automatisches Synchronisieren der Oberfläche mit GitHub (beim Start und Beenden).

Reihenfolge: lokale Änderungen an den Dateien aus SYNC_FILES committen → `git pull --rebase` (holt
neue Stellen der Pipeline) → `git push`. Andere lokale Dateien werden nie committet. Bei einem Konflikt wird der
Rebase abgebrochen; deine Änderungen bleiben als lokaler Commit erhalten und nichts wird überschrieben.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

SYNC_FILES = ("applications.csv", "cv/cv_master.yaml", "companies.yaml", "config.yaml", "lernpfade.yaml",
              "cv/anschreiben_vorlage.txt", "cv/nachfassen_vorlage.txt")
LABELS = {"applications.csv": "Bewerbungen", "cv/cv_master.yaml": "Master-CV", "companies.yaml": "Firmen",
          "config.yaml": "Einstellungen", "lernpfade.yaml": "Lernvorschläge",
          "cv/anschreiben_vorlage.txt": "Anschreiben-Vorlage", "cv/nachfassen_vorlage.txt": "Nachfass-Vorlage"}


@dataclass
class SyncResult:
    ok: bool
    message: str
    log: str = ""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def sync(root: Path) -> SyncResult:
    if not (root / ".git").exists():     # installierte App: Daten nur lokal, Git oft gar nicht installiert
        return SyncResult(True, "Kein Git-Repo – Synchronisieren übersprungen.")
    try:
        if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
            return SyncResult(True, "Kein Git-Repo – Synchronisieren übersprungen.")
    except OSError:
        return SyncResult(True, "Git ist nicht installiert – Synchronisieren übersprungen.")
    log: list[str] = []

    def run(*args: str) -> subprocess.CompletedProcess:
        proc = _git(root, *args)
        log.append(f"$ git {' '.join(args)}\n{proc.stdout}{proc.stderr}".strip())
        return proc

    changed = [f for f in SYNC_FILES if (root / f).exists() and _git(root, "diff", "--quiet", "HEAD", "--", f).returncode]
    if changed:
        names = " und ".join(LABELS[f] for f in changed)
        if run("commit", "-m", f"{names} aktualisiert (Oberfläche)", "--", *changed).returncode != 0:
            return SyncResult(False, "Lokale Änderungen konnten nicht committet werden.", "\n\n".join(log))

    if _git(root, "rev-parse", "--abbrev-ref", "@{u}").returncode != 0:
        msg = "Lokal gespeichert. Kein GitHub-Remote eingerichtet, daher nichts hochgeladen."
        return SyncResult(True, msg, "\n\n".join(log))
    before = _git(root, "rev-parse", "@{u}").stdout.strip()
    pull = run("pull", "--rebase", "--autostash")
    if pull.returncode != 0:
        if (root / ".git" / "rebase-merge").exists() or (root / ".git" / "rebase-apply").exists():
            run("rebase", "--abort")
        msg = ("Holen von GitHub fehlgeschlagen (offline oder Konflikt mit der Pipeline). Deine Änderungen sind "
               "lokal gesichert; beim nächsten Synchronisieren wird es erneut versucht.")
        return SyncResult(False, msg, "\n\n".join(log))
    after = _git(root, "rev-parse", "@{u}").stdout.strip()
    pulled = int(_git(root, "rev-list", "--count", f"{before}..{after}").stdout.strip() or 0) if before != after else 0

    ahead = int(_git(root, "rev-list", "--count", "@{u}..HEAD").stdout.strip() or 0)
    if ahead and run("push").returncode != 0:
        return SyncResult(False, "Hochladen fehlgeschlagen. Deine Änderungen sind lokal gesichert.", "\n\n".join(log))

    parts = []
    if pulled:
        parts.append(f"{pulled} neue Änderung(en) von GitHub geholt")
    if changed:
        parts.append(f"{' und '.join(changed)} hochgeladen")
    return SyncResult(True, ("Synchronisiert: " + ", ".join(parts) + ".") if parts else "Alles aktuell.",
                      "\n\n".join(log))
