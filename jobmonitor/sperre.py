"""Nur eine Suche gleichzeitig: Sperrdatei state/suche.lock (vom Betriebssystem gehalten, solange der Prozess lebt).

Zwei Suchen zugleich (z. B. die alte App startet eine, dann kommt per Update die neue und startet die nächste)
schreiben in dieselbe Datenbank – die zweite scheiterte mit „database is locked“. Jetzt überspringt sie still.
Die Sperre löst sich von selbst, wenn der Prozess endet oder abstürzt (kein Aufräumen nötig).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DATEI = "suche.lock"


class Sperre:
    def __init__(self, root: Path):
        self.pfad = Path(root) / "state" / DATEI
        self.fh = None

    def holen(self) -> bool:
        """True, wenn diese Suche laufen darf (sonst läuft schon eine)."""
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.pfad, "a+")   # noqa: SIM115 – bleibt offen, solange die Suche läuft
        try:
            if sys.platform == "win32":
                import msvcrt
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.fh.close()
            self.fh = None
            return False
        self.fh.seek(0)
        self.fh.truncate()
        self.fh.write(str(os.getpid()))
        self.fh.flush()
        return True

    def freigeben(self) -> None:
        if self.fh is not None:
            try:
                self.fh.seek(0)
                self.fh.truncate()        # keine Prozessnummer mehr: es läuft nichts
                if sys.platform == "win32":
                    import msvcrt
                    self.fh.seek(0)
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
            finally:
                self.fh.close()
                self.fh = None


def laeuft(root: Path) -> bool:
    """Läuft gerade irgendwo eine Suche (auch aus einer früheren App-Sitzung)? Prüft nur die Prozessnummer in der
    Sperrdatei – ohne die Sperre selbst anzufassen, damit eine gerade startende Suche nicht übersprungen wird."""
    try:
        pid = int((Path(root) / "state" / DATEI).read_text().strip() or 0)
    except (OSError, ValueError):
        return False
    if pid <= 0 or pid == os.getpid() or sys.platform == "win32":
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
