"""Ist die Anzeige noch online? Prüft die Links deiner Liste (applications.csv) sparsam in der Pipeline.

Geprüft werden Einträge mit Status neu, Entwurf, beworben, nachgefasst – je Link höchstens alle `pruef_tage` Tage,
höchstens `max_je_lauf` Links pro Lauf, mit robots.txt und ehrlichem User-Agent. LinkedIn, StepStone, Indeed & Co.
werden nie abgerufen. „Nicht mehr online“ heißt: HTTP 404/410 oder die Seite sagt selbst, dass die Stelle besetzt oder
nicht mehr verfügbar ist. Alles andere (Fehler, robots.txt-Verbot) zählt als „unbekannt“ und ändert nichts.
Ergebnis in state/anzeigen.json: Link → {geprueft, offline_seit}.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .eigene_stelle import BLOCKED_HOSTS
from .http import Fetcher, RobotsDisallowed

log = logging.getLogger(__name__)
DATEI = "state/anzeigen.json"
PRUEFEN = ("neu", "Entwurf", "beworben", "nachgefasst")
WEG = re.compile(
    r"(?:stelle|anzeige|stellenanzeige|position|job|ausschreibung)[^.<]{0,80}?(?:nicht mehr (?:verfügbar|verfuegbar|"
    r"online|aktiv|besetzbar)|bereits besetzt|ist abgelaufen|wurde (?:bereits )?besetzt|existiert nicht mehr)|"
    r"no longer (?:available|accepting applications|active)|(?:job|position|posting) (?:has expired|is closed|has been "
    r"filled)|this (?:job|position) is no longer", re.I)


def laden(root: Path) -> dict[str, dict]:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def speichern(root: Path, data: dict) -> None:
    (root / DATEI).parent.mkdir(parents=True, exist_ok=True)
    (root / DATEI).write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def offline(data: dict) -> dict[str, str]:
    """Link → Datum (ISO), seit dem die Anzeige nicht mehr online ist."""
    return {link: v["offline_seit"] for link, v in data.items() if isinstance(v, dict) and v.get("offline_seit")}


def faellig(rows: list[dict], data: dict, today: date, tage: int) -> list[str]:
    grenze = (today - timedelta(days=tage)).isoformat()
    out = []
    for r in rows:
        link = r.get("link") or ""
        host = urlsplit(link).netloc.lower()
        if r.get("status") not in PRUEFEN or not link.startswith("http") or any(b in host for b in BLOCKED_HOSTS):
            continue
        eintrag = data.get(link) or {}
        if eintrag.get("offline_seit") or eintrag.get("geprueft", "") > grenze or link in out:
            continue
        out.append(link)
    return out


def pruefe_link(fetcher: Fetcher, link: str) -> bool | None:
    """True = noch online, False = nicht mehr online, None = unklar (Fehler, robots.txt)."""
    try:
        resp = fetcher.get(link)
    except RobotsDisallowed:
        return None
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else 0
        return False if code in (404, 410) else None
    except requests.RequestException:
        return None
    return not WEG.search(re.sub(r"<[^>]+>", " ", resp.text[:300_000]))


def pruefen(root: Path, rows: list[dict], fetcher: Fetcher, today: date, cfg: dict) -> list[str]:
    """Fällige Links prüfen und speichern. Gibt die Links zurück, die in diesem Lauf als offline erkannt wurden."""
    data = laden(root)
    neu_offline = []
    for link in faellig(rows, data, today, cfg.get("pruef_tage", 3))[: cfg.get("max_je_lauf", 25)]:
        ergebnis = pruefe_link(fetcher, link)
        if ergebnis is None:
            continue
        eintrag = {"geprueft": today.isoformat()}
        if ergebnis is False:
            eintrag["offline_seit"] = today.isoformat()
            neu_offline.append(link)
        data[link] = eintrag
    speichern(root, data)
    if neu_offline:
        log.info("%d Anzeige(n) nicht mehr online", len(neu_offline))
    return neu_offline
