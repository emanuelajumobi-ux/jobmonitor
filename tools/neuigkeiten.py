"""Abschnitt einer Version aus NEUIGKEITEN.md (für den Release-Text in .github/workflows/build.yml).

    python tools/neuigkeiten.py 1.2.0
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DATEI = Path(__file__).resolve().parent.parent / "NEUIGKEITEN.md"


def abschnitt(version: str, text: str | None = None) -> str:
    text = text if text is not None else DATEI.read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(version)}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


if __name__ == "__main__":
    print(abschnitt(sys.argv[1]))
