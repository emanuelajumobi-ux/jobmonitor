"""Job-Monitor weiterempfehlen: Karte in den Einstellungen, Eintrag in der Seitenleiste und ein kurzer Satz in den
Glückwunsch-Karten (erste Einladung, Zusage, erste fertige Mappe – Letzteres nur einmal).

Die App verschickt nichts und liest keine Kontakte: Die Knöpfe öffnen WhatsApp, LinkedIn oder das Mailprogramm mit
einem vorausgefüllten Text, abschicken tut man selbst. Geteilt wird die Website (großer Download-Knopf, Vorschaubild),
nicht das GitHub-Repo.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from urllib.parse import quote, urlencode

WEBSITE = "https://emanuelajumobi-ux.github.io/jobmonitor/"
DATEI = ".gui_spenden.json"   # gemeinsam mit spenden.py: dort steht schon, was einmalig gezeigt wurde
TEXT = ("Kennst du Job-Monitor? Kostenlose App für Mac und Windows: findet passende Stellen, zeigt, wie gut sie zum "
        "Lebenslauf passen, und hilft bei der Bewerbung.")
TEXT_EN = ("Have you heard of Job-Monitor? A free app for Mac and Windows that finds matching jobs, shows how well they "
           "fit your CV and helps with your application.")


def links(sprache: str = "de") -> dict[str, str]:
    nachricht = f"{TEXT_EN if sprache == 'en' else TEXT} {WEBSITE}"
    return {
        "whatsapp": "https://wa.me/?" + urlencode({"text": nachricht}),
        "linkedin": "https://www.linkedin.com/sharing/share-offsite/?" + urlencode({"url": WEBSITE}),
        "mail": "mailto:?subject=" + quote("Tip: Job-Monitor" if sprache == "en" else "Tipp: Job-Monitor") + "&body=" + quote(nachricht),
    }


def knoepfe(feld_id: str = "teilen-link", sprache: str = "de") -> str:
    l = links(sprache)
    return (f'<input type="text" id="{feld_id}" value="{WEBSITE}" readonly tabindex="-1" aria-hidden="true" style="position:absolute;left:-9999px">'
            f'<div class="row"><button type="button" class="ghost small" data-copy="{feld_id}">Link kopieren</button>'
            f'<a class="btn ghost small" href="{escape(l["whatsapp"])}" target="_blank" rel="noopener">WhatsApp</a>'
            f'<a class="btn ghost small" href="{escape(l["linkedin"])}" target="_blank" rel="noopener">LinkedIn</a>'
            f'<a class="btn ghost small" href="{escape(l["mail"])}" target="_blank" rel="noopener">E-Mail</a></div>')


def karte(sprache: str = "de") -> str:
    return (f'<div class="card" id="teilen"><h2>Weiterempfehlen</h2><p>Kennst du jemanden, der gerade sucht – einen '
            f'Minijob, eine Ausbildung, eine Werkstudentenstelle oder den ersten Job? Teilen ist die einfachste Art, '
            f'Job-Monitor zu unterstützen.</p><p class="muted">Die Knöpfe öffnen WhatsApp, LinkedIn oder dein '
            f'Mailprogramm mit einem fertigen Text und dem Link zur Website. Abschicken tust du selbst; die App '
            f'verschickt nichts.</p>{knoepfe(sprache=sprache)}</div>')


def satz(feld_id: str = "teilen-gruss", sprache: str = "de") -> str:
    """Kurzer Absatz für Glückwunsch-Karten."""
    return f'<p class="muted">Kennst du jemanden, der auch sucht? Teile Job-Monitor.</p>{knoepfe(feld_id, sprache)}'


def erste_mappe(root: Path, sprache: str = "de") -> str:
    """Nach der ersten fertigen Mappe einmalig der Teilen-Satz, danach leer."""
    pfad = root / DATEI
    try:
        data = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if data.get("teilen_mappe"):
        return ""
    data["teilen_mappe"] = True
    try:
        pfad.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        return ""
    return (f'<div class="card"><h2>Deine erste Mappe ist fertig</h2>'
            f'<p class="muted">Kennst du jemanden, der auch sucht? Teile Job-Monitor.</p>{knoepfe("teilen-mappe", sprache)}</div>')
