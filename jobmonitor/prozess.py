"""Befehle für Hintergrund-Prozesse (Probelauf, Zeitplan, PDF): im Entwicklungsordner `python -m jobmonitor …`,
in der installierten App (PyInstaller, sys.frozen) die App selbst mit dem Unterbefehl als Argument."""
from __future__ import annotations

import os
import sys

from .config import CODE


def befehl(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "jobmonitor", *args]


def umgebung() -> dict[str, str]:
    """Umgebung für Hintergrund-Prozesse: Programmordner im Suchpfad (Start aus dem Datenordner) und derselbe
    Datenordner wie die App."""
    env = dict(os.environ)
    if not getattr(sys, "frozen", False):
        env["PYTHONPATH"] = os.pathsep.join(p for p in (str(CODE), env.get("PYTHONPATH", "")) if p)
    return env
