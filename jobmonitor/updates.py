"""Neue Versionen der installierten App anzeigen (kein automatisches Installieren).

Höchstens einmal am Tag, im Hintergrund beim Start: GET https://api.github.com/repos/{repo}/releases/latest auf das
öffentliche Download-Repo (config.yaml → updates.repo). Dabei sieht GitHub die IP-Adresse, sonst wird nichts gesendet.
Ist die Version dort neuer, zeigt die Startseite einen Hinweis mit „Was ist neu“ und Download-Link; installiert wird
durch Ersetzen der App – die Daten im Datenordner bleiben. Abschaltbar unter Einstellungen → App (oder
updates.enabled: false). Im Entwicklungsordner (git) aus: dort kommen neue Stände per Synchronisieren.
Stand lokal in .gui_update.json: {geprueft, neueste: {version, url, notizen}, aus}.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from html import escape
from pathlib import Path

from . import __version__

DATEI = ".gui_update.json"
API = "https://api.github.com/repos/{repo}/releases/latest"
REPO = re.compile(r"^[\w.-]+/[\w.-]+$")


def laden(root: Path) -> dict:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _speichern(root: Path, data: dict) -> None:
    (root / DATEI).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def version_tupel(text: str) -> tuple[int, ...]:
    return tuple(int(t) for t in re.findall(r"\d+", text or "")[:3]) or (0,)


def aktiv(root: Path, cfg: dict) -> bool:
    u = cfg.get("updates") or {}
    return bool(getattr(sys, "frozen", False) and u.get("enabled", True) and REPO.match(str(u.get("repo") or ""))
                and not laden(root).get("aus"))


def pruefen(root: Path, cfg: dict, get=None, heute: date | None = None) -> dict | None:
    """Neueste Version holen (höchstens einmal am Tag); gibt sie zurück, wenn sie neuer ist als diese App."""
    data = laden(root)
    tag = (heute or date.today()).isoformat()
    if data.get("geprueft") != tag:
        import requests
        try:
            resp = (get or requests.get)(API.format(repo=(cfg.get("updates") or {})["repo"]), timeout=6,
                                         headers={"Accept": "application/vnd.github+json",
                                                  "User-Agent": f"job-monitor/{__version__}"})
            if resp.status_code == 200:
                r = resp.json()
                data["neueste"] = {"version": str(r.get("tag_name") or "").lstrip("v"),
                                   "url": str(r.get("html_url") or ""), "notizen": str(r.get("body") or "")[:2000]}
            data["geprueft"] = tag
            _speichern(root, data)
        except Exception:       # offline: morgen erneut
            pass
    neueste = data.get("neueste") or {}
    if neueste.get("version") and version_tupel(neueste["version"]) > version_tupel(__version__):
        return neueste
    return None


def schalten(root: Path, an: bool) -> str:
    data = laden(root)
    data["aus"] = not an
    _speichern(root, data)
    return "Die App sucht wieder nach neuen Versionen." if an else "Keine Suche nach neuen Versionen mehr."


def hinweis(neu: dict | None) -> str:
    if not neu:
        return ""
    url = neu["url"] if neu.get("url", "").startswith("https://github.com/") else ""
    notizen = notizen_html(neu.get("notizen", ""))
    return (f'<div class="card info"><div class="row" style="justify-content:space-between;gap:12px"><p style="margin:0">'
            f'<b>Version {escape(neu["version"])} ist da</b> (du hast {escape(__version__)}). Neue App laden und die '
            f'alte ersetzen – deine Daten bleiben.</p>'
            + (f'<a class="btn small" href="{escape(url)}" target="_blank" rel="noopener">Herunterladen</a>' if url else "")
            + '</div>' + (f'<details><summary>Was ist neu</summary>{notizen}</details>' if notizen else "") + '</div>')


def notizen_html(text: str) -> str:
    """Release-Text (Abschnitt aus NEUIGKEITEN.md) als kleine Liste; die Installationshinweise danach entfallen."""
    import re
    text = text.split("Installieren:")[0].strip()[:2500]
    punkte = [z.strip()[2:] for z in text.splitlines() if z.strip().startswith(("- ", "* "))]
    fett = lambda t: re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(t))  # noqa: E731
    if punkte:
        return '<ul class="muted">' + "".join(f"<li>{fett(p)}</li>" for p in punkte) + "</ul>"
    return f'<p class="muted">{fett(text)}</p>' if text else ""


def karte(root: Path, cfg: dict, token: str) -> str:
    """Zeile für Einstellungen → App: Version und Schalter."""
    if not getattr(sys, "frozen", False):
        return f'<p class="muted">Version {escape(__version__)} (Entwicklungsordner – Updates per Synchronisieren).</p>'
    aus = bool(laden(root).get("aus"))
    knopf = (f'<form method="post" action="/einstellungen" style="display:inline"><input type="hidden" name="token" '
             f'value="{token}"><button name="aktion" value="{"updates_an" if aus else "updates_aus"}" class="ghost small">'
             f'{"Wieder nach Updates suchen" if aus else "Nicht nach Updates suchen"}</button></form>')
    return (f'<p>Version {escape(__version__)} · {"keine Update-Suche" if aus else "sucht einmal am Tag nach neuen Versionen"} '
            f'{knopf}</p><p class="muted">Dabei fragt die App nur die öffentliche Versionsliste bei GitHub ab '
            f'(GitHub sieht deine IP-Adresse).</p>')
