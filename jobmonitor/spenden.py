"""Freiwillige Unterstützung des Projekts: Link in Seitenleiste und Einstellungen, dazu freundlich bei der ersten
Einladung zu einem Gespräch (nur ein einziges Mal, gemerkt in .gui_spenden.json) und wenn jemand eine Zusage
einträgt. Nichts davon ist Pflicht oder schaltet etwas frei; die App bleibt kostenlos.

Der Link steht in config.yaml → spenden.url (z. B. GitHub Sponsors, Ko-fi oder PayPal.me). Ist er leer, zeigt die App
nichts an.
"""
from __future__ import annotations

import json
from datetime import date
from html import escape
from pathlib import Path

DATEI = ".gui_spenden.json"

ERLAUBT = ("https://github.com/sponsors/", "https://ko-fi.com/", "https://www.paypal.com/", "https://paypal.me/",
           "https://www.paypal.me/", "https://buymeacoffee.com/", "https://www.buymeacoffee.com/",
           "https://liberapay.com/")


def url(cfg: dict) -> str:
    wert = str((cfg.get("spenden") or {}).get("url") or "").strip()
    return wert if wert.startswith(ERLAUBT) else ""


def karte(cfg: dict) -> str:
    link = url(cfg)
    if not link:
        return ""
    return (f'<div class="card" id="unterstuetzen"><h2>Job-Monitor unterstützen</h2><p>Job-Monitor ist kostenlos und '
            f'quelloffen und wird in der Freizeit entwickelt. Wenn dir die App hilft, freut sich der Entwickler über '
            f'eine kleine Unterstützung – freiwillig, die App bleibt für alle kostenlos.</p>'
            f'<a class="btn ghost small" href="{escape(link)}" target="_blank" rel="noopener">Unterstützen</a></div>')


def zusage(cfg: dict, firma: str) -> str:
    """Glückwunsch beim Eintragen einer Zusage – mit dezenter Bitte, falls ein Link gesetzt ist."""
    link = url(cfg)
    bitte = (f'<p class="muted">Hat dir Job-Monitor dabei geholfen? Dann freut sich der Entwickler über eine kleine '
             f'Unterstützung – ganz freiwillig. <a href="{escape(link)}" target="_blank" rel="noopener">Unterstützen</a>'
             f'</p>' if link else "")
    return (f'<div class="card zusage"><h2>Herzlichen Glückwunsch zur Zusage{f" bei {escape(firma)}" if firma else ""}!'
            f'</h2><p>Viel Erfolg beim Start. Offene Bewerbungen bei anderen Firmen kannst du jetzt zurückziehen oder '
            f'auf „verworfen“ setzen.</p>{bitte}</div>')


def einladung(root: Path, cfg: dict, firma: str, heute: date | None = None) -> str:
    """Glückwunsch zur ersten Einladung zu einem Gespräch – mit dezenter Bitte. Nur ein einziges Mal (danach leer)."""
    pfad = root / DATEI
    try:
        data = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if data.get("einladung"):
        return ""
    data["einladung"] = (heute or date.today()).isoformat()
    pfad.write_text(json.dumps(data), encoding="utf-8")
    link = url(cfg)
    bitte = (f'<p class="muted">Hat dir Job-Monitor auf dem Weg dahin geholfen? Dann freut sich der Entwickler über '
             f'eine kleine Unterstützung – ganz freiwillig. <a href="{escape(link)}" target="_blank" rel="noopener">'
             f'Unterstützen</a></p>' if link else "")
    return (f'<div class="card zusage"><h2>Glückwunsch zur Einladung{f" bei {escape(firma)}" if firma else ""}!</h2>'
            f'<p>Deine erste Einladung zum Gespräch – das ist ein großer Schritt. Unter „Gespräche“ hilft dir '
            f'<b>Darauf vorbereiten</b> mit wahrscheinlichen Fragen und passenden Beispielen aus deinem Lebenslauf.'
            f'</p>{bitte}</div>')
