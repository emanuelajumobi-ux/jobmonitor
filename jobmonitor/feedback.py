"""Rückmeldung an den Entwickler: Fehler melden oder Idee vorschlagen – als vorausgefülltes GitHub-Issue im
öffentlichen Repo. Die App schickt selbst nichts: Der Link öffnet die Seite im Browser, man liest, ergänzt und sendet
selbst (dafür braucht es ein kostenloses GitHub-Konto). Vorausgefüllt sind nur Version und Betriebssystem, keine
persönlichen Daten.
"""
from __future__ import annotations

import platform
import sys
from html import escape
from urllib.parse import urlencode

from . import __version__

REPO = "https://github.com/emanuelajumobi-ux/jobmonitor"
ARTEN = {
    "fehler": ("[Fehler] ", "**Was ist passiert?**\n\n\n**Was hast du davor gemacht?**\n\n\n**Was hättest du erwartet?**\n\n"),
    "idee": ("[Idee] ", "**Was möchtest du tun können?**\n\n\n**Wofür brauchst du es?**\n\n"),
}


def system() -> str:
    gebaut = "installierte App" if getattr(sys, "frozen", False) else "aus dem Quellcode"
    return f"{platform.system()} {platform.release()} · Python {platform.python_version()} · {gebaut}"


def link(art: str) -> str:
    titel, vorlage = ARTEN.get(art, ARTEN["idee"])
    body = (f"{vorlage}---\nJob-Monitor {__version__} · {system()}\n\n"
            "_Bitte keine persönlichen Daten (Name, Adresse, Lebenslauf, API-Schlüssel) hineinschreiben – "
            "Issues sind öffentlich._")
    return f"{REPO}/issues/new?" + urlencode({"title": titel, "body": body})


def karte() -> str:
    return (f'<div class="card" id="feedback"><h2>Feedback</h2><p class="muted">Etwas funktioniert nicht oder du hast '
            f'eine Idee? Der Knopf öffnet eine vorausgefüllte Seite auf GitHub (öffentlich, kostenloses Konto nötig). '
            f'Mitgeschickt werden nur Version und Betriebssystem – du liest alles und sendest selbst.</p>'
            f'<div class="row"><a class="btn ghost small" href="{escape(link("fehler"))}" target="_blank" '
            f'rel="noopener">Fehler melden</a><a class="btn ghost small" href="{escape(link("idee"))}" target="_blank" '
            f'rel="noopener">Idee vorschlagen</a></div></div>')
