"""Oberfläche auf Englisch: übersetzt die fertig gebaute Seite anhand eines Wörterbuchs (i18n_en.py).

Die App baut ihre Seiten auf Deutsch; ist in den Einstellungen Englisch gewählt (config.yaml → gui.sprache: en), ersetzt
`seite` Textstücke zwischen Tags und sichtbare Attribute (placeholder, title, aria-label, data-ki, Rückfragen in
confirm(…)) durch ihre englische Fassung. Nicht angefasst werden Eingaben und Daten: Inhalte von <textarea>, <pre>,
<style>, value-Attribute – Stellentitel, Lebenslauf oder Anschreiben bleiben also, wie sie sind.

Gesucht wird erst wörtlich (Leerraum zusammengefasst), dann über Muster mit Platzhaltern wie „Noch {} Platzhalter“.
Was fehlt, bleibt deutsch. JOBMONITOR_I18N_SAMMELN=<datei> schreibt fehlende Stücke in eine Datei (zum Ergänzen).
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

SPRACHEN = {"de": "Deutsch", "en": "English"}
TAG = re.compile(r"(<!--.*?-->|<[^>]+>)", re.S)
ROH = {"script", "style", "textarea", "pre", "code", "title"}   # title: eigens übersetzt
ATTR = re.compile(r'\b(placeholder|title|aria-label|alt|data-ki)="([^"]*)"')
CONFIRM = re.compile(r"((?:confirm|alert)\(')((?:[^'\\]|\\.)*)(')")
DEUTSCH = re.compile(r"[äöüÄÖÜß]|\b(?:und|der|die|das|nicht|mit|für|oder|noch|ist|sind|wird|werden|bitte|keine?|"
                     r"auf|aus|zum|zur|dein|deine|deinen|ein|eine|einen|bei|nach|vom|von|im|Stellen?)\b")


def sprache(cfg: dict | None) -> str:
    wert = str(((cfg or {}).get("gui") or {}).get("sprache") or "de")
    return wert if wert in SPRACHEN else "de"


@lru_cache(maxsize=1)
def _woerterbuch() -> tuple[dict, list]:
    from .i18n_en import MUSTER, TEXTE
    normal = {" ".join(k.split()): v for k, v in TEXTE.items()}
    muster = []
    for de, en in MUSTER:
        teile = re.split(r"(\{n?\})", " ".join(de.split()))
        regex = "".join(r"(\d[\d.,]*)" if t == "{n}" else "(.+?)" if t == "{}" else re.escape(t) for t in teile)
        muster.append((re.compile(f"^{regex}$", re.S), en))
    return normal, muster


CHIPS = re.compile(r"^(?:[^:]{1,60}: (?:erfüllt|fehlt|optional)\s*)+$")


def text(stueck: str, sammeln: set | None = None) -> str:
    """Ein Textstück (ohne Tags) übersetzen; Leerraum am Rand bleibt erhalten."""
    kern = " ".join(stueck.split())
    if not kern:
        return stueck
    normal, muster = _woerterbuch()
    neu = normal.get(kern)
    if neu is None and CHIPS.match(kern):
        neu = kern.replace(": erfüllt", ": met").replace(": fehlt", ": missing")
    if neu is None:
        for regex, en in muster:
            m = regex.match(kern)
            if m:
                neu = en
                for wert in m.groups():
                    neu = neu.replace("{}", text(wert), 1)
                break
    if neu is None:
        if sammeln is not None and re.search(r"[A-Za-zÄÖÜäöü]{2}", kern):
            sammeln.add(kern)
        return stueck
    links = stueck[:len(stueck) - len(stueck.lstrip())]
    rechts = stueck[len(stueck.rstrip()):]
    return f"{links}{neu}{rechts}"


def _knoten(teil: str, sammeln: set | None) -> str:
    from html import escape, unescape
    roh = unescape(teil)
    neu = text(roh, sammeln)
    return teil if neu == roh else escape(neu, quote=False)


def _attr(tag: str, sammeln: set | None) -> str:
    from html import escape, unescape

    tag = ATTR.sub(lambda m: f'{m.group(1)}="{escape(text(unescape(m.group(2)), sammeln), quote=True)}"', tag)
    if "confirm(" in tag or "alert(" in tag:
        tag = CONFIRM.sub(lambda m: m.group(1) + text(m.group(2).replace("\\'", "'"), sammeln).replace("'", "\\'")
                          + m.group(3), tag)
    return tag


def _skript(inhalt: str) -> str:
    from .i18n_en import SKRIPT
    for de, en in SKRIPT.items():
        inhalt = inhalt.replace(de, en)
    return inhalt


def seite(html: str) -> str:
    """Ganze HTML-Seite ins Englische."""
    pfad = os.environ.get("JOBMONITOR_I18N_SAMMELN")
    sammeln: set | None = set() if pfad else None
    out, roh = [], None
    for teil in TAG.split(html):
        if not teil:
            continue
        if teil.startswith("<"):
            name = re.match(r"</?\s*([a-zA-Z0-9]+)", teil)
            name = name.group(1).lower() if name else ""
            if teil.startswith("</"):
                if name == roh:
                    roh = None
            elif name in ROH and not teil.endswith("/>"):
                roh = name
            if teil.startswith("<html"):
                teil = teil.replace('lang="de"', 'lang="en"')
            out.append(_attr(teil, sammeln) if not teil.startswith("<!--") else teil)
            continue
        if roh == "script":
            out.append(_skript(teil))
        elif roh == "title":
            vorne, _, hinten = teil.partition(" · ")
            out.append(text(vorne, sammeln) + (" · " + hinten if hinten else ""))
        elif roh:
            out.append(teil)
        else:
            out.append(_knoten(teil, sammeln))
    if sammeln:
        with open(pfad, "a", encoding="utf-8") as fh:
            fh.writelines(f"{s}\n" for s in sorted(sammeln))
    return "".join(out)


# --- Einstellung ---
GUI_RE = re.compile(r"^gui:[^\n]*\n((?:[ \t]+[^\n]*\n|[ \t]*\n)*)", re.M)


def gui_setzen(root, schluessel: str, wert: str, kommentar: str) -> None:
    """gui.<schluessel> in config.yaml setzen, ohne den Rest der Datei neu zu formatieren (alter Stand als .bak)."""
    from .gui_wartung import speichern
    path = root / "config.yaml"
    text = path.read_text(encoding="utf-8")
    zeile = f"  {schluessel}: {wert}".ljust(30) + f"# {kommentar}\n"
    block = GUI_RE.search(text)
    if block is None:
        text = text.rstrip("\n") + f"\n\ngui:\n{zeile}"
    else:
        alt = re.compile(rf"^  {schluessel}:[^\n]*\n", re.M)
        inhalt = block.group(1)
        inhalt = alt.sub(zeile, inhalt, count=1) if alt.search(inhalt) else zeile + inhalt
        text = text[:block.start(1)] + inhalt + text[block.end(1):]
    speichern(root, "config.yaml", text)


def setzen(root, code: str) -> None:
    """Sprache der Oberfläche (gui.sprache)."""
    from .gui_wartung import WartungError
    if code not in SPRACHEN:
        raise WartungError("Unbekannte Sprache.")
    gui_setzen(root, "sprache", code, "Oberfläche: de | en (Einstellungen → Sprache)")


DARSTELLUNG = ("auto", "hell", "dunkel")


def darstellung(cfg: dict | None) -> str:
    wert = str(((cfg or {}).get("gui") or {}).get("darstellung") or "auto")
    return wert if wert in DARSTELLUNG else "auto"


def darstellung_setzen(root, wert: str) -> None:
    from .gui_wartung import WartungError
    if wert not in DARSTELLUNG:
        raise WartungError("Unbekannte Darstellung.")
    gui_setzen(root, "darstellung", wert, "auto | hell | dunkel (Schalter unten in der Seitenleiste)")


def systemsprache(run=None) -> str:
    """„en“, wenn das Betriebssystem nicht auf Deutsch eingestellt ist (für den ersten Start), sonst „de“."""
    import locale
    import subprocess
    import sys
    kennung = ""
    if sys.platform == "darwin":
        try:
            kennung = (run or subprocess.run)(["defaults", "read", "-g", "AppleLocale"], capture_output=True,
                                              text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            kennung = ""
    if not kennung:
        try:
            kennung = locale.getlocale()[0] or ""
        except ValueError:
            kennung = ""
    if not kennung:
        return "de"
    return "de" if kennung.lower().startswith(("de", "german")) else "en"


def karte(token: str, aktuell: str, ziel: str = "/einstellungen") -> str:
    """Auswahl der Oberflächensprache – zweisprachig beschriftet, damit man sie in jeder Sprache findet."""
    optionen = "".join(f'<option value="{k}"{" selected" if k == aktuell else ""}>{v}</option>'
                       for k, v in SPRACHEN.items())
    return (f'<div class="card" id="sprache"><h2>Sprache · Language</h2>'
            f'<form method="post" action="{ziel}" class="row" style="gap:8px"><input type="hidden" name="token" '
            f'value="{token}"><select name="sprache" style="width:auto">{optionen}</select><button name="aktion" '
            f'value="sprache_gui" class="ghost small">OK</button></form><p class="muted">Oberfläche der App. '
            f'Stellenanzeigen, deine Texte und die Anleitung im Detail bleiben, wie sie sind.</p></div>')
