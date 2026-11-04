"""Laden von config.yaml und companies.yaml (companies mit Round-Trip, damit Kommentare erhalten bleiben)."""
from __future__ import annotations

import copy
import os
from pathlib import Path

from ruamel.yaml import YAML

# Programmordner (Code, Vorlagen). Daten liegen im selben Ordner – außer JOBMONITOR_HOME zeigt woandershin
# (installierte App: z. B. ~/Documents/Job-Monitor, eingerichtet von erststart.py).
CODE = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ["JOBMONITOR_HOME"]).expanduser() if os.environ.get("JOBMONITOR_HOME") else CODE
MODI = {"aktiv": "Aktiv suchen", "ruhe": "Ruhemodus", "aus": "Angehalten"}


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096   # lange Werte (z. B. Karriere-URLs mit Parametern) nie umbrechen
    y.indent(mapping=2, sequence=4, offset=2)
    return y


_CACHE: dict = {}


def load_config(path: Path | None = None) -> dict:
    """Liest config.yaml. Gleiche Datei mit gleichem Stand (Änderungszeit und Größe) wird nur einmal geparst;
    jeder Aufruf bekommt eine eigene Kopie, Änderungen daran wirken also nicht zurück."""
    pfad = Path(path or ROOT / "config.yaml")
    st = pfad.stat()
    schluessel = (str(pfad.resolve()), st.st_mtime_ns, st.st_size)
    if _CACHE.get("schluessel") != schluessel:
        _CACHE.update(schluessel=schluessel, cfg=_load_config(pfad))
    return copy.deepcopy(_CACHE["cfg"])


def _load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        cfg = YAML(typ="safe").load(fh)
    # Fit-Begriffe der Suchprofile (z. B. eines Profils mit eigenem Fachgebiet) ergänzen fit.begriffe. Sie gelten für
    # alle Stellen: ein zusätzlich erkannter Begriff macht den Fit nur genauer.
    begriffe = (cfg.get("fit") or {}).get("begriffe")
    if isinstance(begriffe, dict):
        bekannt = {k.lower() for k in begriffe}
        for profil in (cfg.get("profile") or {}).values():
            for term, synonyme in ((profil or {}).get("fit_begriffe") or {}).items():
                if str(term).lower() not in bekannt:
                    begriffe[str(term)] = list(synonyme or [])
                    bekannt.add(str(term).lower())
    return cfg


def load_companies(path: Path | None = None):
    with open(path or ROOT / "companies.yaml", encoding="utf-8") as fh:
        return _yaml().load(fh)


def save_companies(data, path: Path | None = None) -> None:
    with open(path or ROOT / "companies.yaml", "w", encoding="utf-8") as fh:
        _yaml().dump(data, fh)


def modus(cfg: dict) -> str:
    """run.modus: aktiv (täglich), ruhe (wöchentlich, ohne Postfach und Mitteilungen) oder aus (Pipeline ruht)."""
    wert = (cfg.get("run") or {}).get("modus", "aktiv")
    return wert if wert in MODI else "aktiv"
