"""Kopierhilfe für Bewerbungsportale: die Felder, die Online-Formulare immer wieder abfragen, fertig zum Kopieren.

Viele Firmen nehmen Bewerbungen nur über ein Portal an (Workday, SuccessFactors, Personio …) und wollen dort Kurzprofil,
Motivation, Verfügbarkeit oder Gehaltsvorstellung in Textfeldern mit Zeichengrenze. Diese Seite stellt alles aus
Master-CV, Profil und Anschreiben zusammen; lange Texte lassen sich auf eine Grenze kürzen (an der Satzgrenze, auf
Wunsch mit KI). Ausgefüllt und abgeschickt wird nichts – das macht die Person selbst im Portal.

Kontaktdaten kommen aus profile.yaml und bleiben lokal; an die KI geht beim Kürzen nur der jeweilige Text.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

GRENZEN = (300, 500, 1000, 2000)
DATEI = "portal.json"        # mit KI gekürzte Fassungen je Feld und Grenze (im Bewerbungsordner)
SATZ = re.compile(r"(?<=[.!?])\s+")


def kuerzen(text: str, grenze: int) -> str:
    """Auf höchstens `grenze` Zeichen, an der letzten Satzgrenze; ohne Satzgrenze am letzten Wort mit „…“."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= grenze:
        return text
    out = ""
    for satz in SATZ.split(text):
        if len(out) + len(satz) + (1 if out else 0) > grenze:
            break
        out = f"{out} {satz}".strip()
    if out:
        return out
    return text[:grenze - 1].rsplit(" ", 1)[0].rstrip(",;:–-") + "…"


def _sprachen(cv: dict) -> str:
    return ", ".join(f"{s.get('sprache')} ({s.get('niveau')})" if s.get("niveau") else str(s.get("sprache"))
                     for s in cv.get("sprachen") or [] if isinstance(s, dict) and s.get("sprache"))


def _kenntnisse(cv: dict) -> str:
    namen = []
    for k in cv.get("kenntnisse") or []:
        for e in (k.get("eintraege") or []) if isinstance(k, dict) else []:
            name = e.get("name") if isinstance(e, dict) else e
            if name and name not in namen:
                namen.append(str(name))
    return ", ".join(namen)


def _anschreiben(data: dict | None, gruss: str, name: str) -> str:
    if not data or not data.get("text"):
        return ""
    return f"{data.get('anrede') or ''}\n\n{data['text']}\n\n{gruss}\n{name}".strip()


def motivation(text: str) -> str:
    """Kurzfassung für „Warum bewerben Sie sich?“: Anschreiben ohne Platzhalter-Absätze, als ein Absatz."""
    absaetze = [a for a in re.split(r"\n\s*\n", text or "") if a.strip() and "[" not in a]
    return re.sub(r"\s+", " ", " ".join(absaetze)).strip()


def felder(profile: dict, cv: dict, letter: dict | None, zeitraum: str | None, englisch: bool = False) -> list[dict]:
    """[{key, label, wert, lang}] – `lang`: langer Text mit Zeichengrenze."""
    adr = profile.get("adresse") or {}
    links = profile.get("links") or {}
    name = str(profile.get("name") or "").strip()
    vorname, _, nachname = name.rpartition(" ")
    ausbildung = next((a for a in cv.get("ausbildung") or [] if isinstance(a, dict)), {})
    aktuell = next((s for s in cv.get("stationen") or [] if isinstance(s, dict) and not s.get("bis")), None)
    gruss = "Kind regards" if englisch else "Mit freundlichen Grüßen"
    roh = [
        ("vorname", "Vorname", vorname or name, False), ("nachname", "Nachname", nachname, False),
        ("email", "E-Mail", profile.get("email"), False), ("telefon", "Telefon", profile.get("telefon"), False),
        ("strasse", "Straße", adr.get("strasse"), False), ("plz", "PLZ", adr.get("plz"), False),
        ("ort", "Ort", adr.get("ort"), False), ("linkedin", "LinkedIn", links.get("linkedin"), False),
        ("github", "GitHub", links.get("github"), False),
        ("studium", "Studium / Abschluss", profile.get("studium") or " – ".join(
            str(x) for x in (ausbildung.get("abschluss"), ausbildung.get("institution")) if x), False),
        ("position", "Aktuelle Tätigkeit", f"{aktuell.get('rolle')} – {aktuell.get('organisation')}" if aktuell
         else "", False),
        ("verfuegbar", "Verfügbarkeit (ab wann, Stunden)", zeitraum, False),
        ("gehalt", "Gehaltsvorstellung", profile.get("gehalt"), False),
        ("sprachen", "Sprachen", _sprachen(cv), False),
        ("kenntnisse", "Kenntnisse", _kenntnisse(cv), True),
        ("kurzprofil", "Kurzprofil", cv.get("profil"), True),
        ("motivation", "Motivation (aus dem Anschreiben)", motivation((letter or {}).get("text", "")), True),
        ("anschreiben", "Anschreiben als Text (für Textfelder statt PDF-Upload)", _anschreiben(letter, gruss, name),
         True),
    ]
    return [{"key": k, "label": label, "wert": str(wert or "").strip(), "lang": lang} for k, label, wert, lang in roh]


def gekuerzt(folder: Path) -> dict:
    try:
        return json.loads((folder / DATEI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ki_kuerzen(root: Path, cfg: dict, folder: Path, key: str, text: str, grenze: int, englisch: bool = False,
               ask=None) -> str:
    """Text mit KI auf `grenze` Zeichen bringen (Sinn erhalten, nichts dazuerfinden); wird im Ordner gemerkt."""
    from . import ki
    sprache = "Englisch" if englisch else "Deutsch"
    antwort = ki.fragen(root, cfg, (
        f"Kürze diesen Bewerbungstext auf höchstens {grenze - 20} Zeichen für ein Textfeld in einem Bewerbungsportal. "
        "Behalte die wichtigsten konkreten Aussagen, erfinde nichts dazu, keine Anrede und keine Grußformel. "
        f"Sprache: {sprache}. Gib nur den gekürzten Text aus.\n\nTEXT:\n{text[:6000]}"),
        effort="low", max_tokens=2000, ask=ask).strip().strip('"„“').strip()
    if len(antwort) > grenze:
        antwort = kuerzen(antwort, grenze)
    data = gekuerzt(folder)
    data[f"{key}:{grenze}"] = antwort
    (folder / DATEI).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return antwort


def render(felder_: list[dict], token: str, ziel: str, grenze: int, ki_an: bool, ki_texte: dict) -> str:
    """Karte „Für Bewerbungsportale“ mit Kopier-Knöpfen; lange Felder mit Zeichenzähler und Grenze."""
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    zeilen, kurz = [], []
    for f in felder_:
        if not f["wert"]:
            continue
        fid = f"portal-{f['key']}"
        if not f["lang"]:
            kurz.append(f'<div class="pf"><label for="{fid}">{escape(f["label"])}</label><div class="row">'
                        f'<input id="{fid}" value="{escape(f["wert"])}" readonly>'
                        f'<button type="button" class="ghost small" data-copy="{fid}">Kopieren</button></div></div>')
            continue
        ki_text = ki_texte.get(f"{f['key']}:{grenze}")
        wert = ki_text or (f["wert"] if f["key"] == "anschreiben" else kuerzen(f["wert"], grenze))
        hinweis = ("mit KI gekürzt" if ki_text else
                   "an der Satzgrenze gekürzt" if len(wert) < len(re.sub(r"\s+", " ", f["wert"])) - 1 else "")
        ki_knopf = (f'<button name="aktion" value="portal_ki" class="ghost small" formnovalidate '
                    f'data-ki="KI kürzt den Text …" onclick="this.form.feld.value=\'{f["key"]}\'">Mit KI kürzen</button>'
                    if ki_an and f["key"] in ("kurzprofil", "motivation") and len(f["wert"]) > grenze else "")
        zeilen.append(f'<div class="pf"><label for="{fid}">{escape(f["label"])} <span class="muted" data-zaehler='
                      f'"{fid}">{len(wert)} Zeichen</span>{" · " + hinweis if hinweis else ""}</label>'
                      f'<textarea id="{fid}" rows="{8 if f["key"] == "anschreiben" else 4}">{escape(wert)}</textarea>'
                      f'<div class="row"><button type="button" class="ghost small" data-copy="{fid}">Kopieren</button>'
                      f'{ki_knopf}</div></div>')
    optionen = "".join(f'<option value="{g}"{" selected" if g == grenze else ""}>{g} Zeichen</option>' for g in GRENZEN)
    return (f'<div class="card" id="portal"><details{" open" if ki_texte else ""}><summary><h2 style="display:inline">'
            f'Für Bewerbungsportale</h2> <span class="muted">– Felder zum Kopieren</span></summary>'
            f'<p class="muted">Für Online-Formulare: Wert kopieren und im Portal einfügen. Lange Texte sind auf die '
            f'gewählte Grenze gekürzt; du kannst sie hier noch anpassen, bevor du kopierst. Abgeschickt wird nichts.</p>'
            f'<form method="post" action="{ziel}#portal" class="row" style="gap:8px;margin-bottom:12px">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="feld" value="">'
            f'<label style="margin:0">Zeichengrenze der Textfelder</label><select name="grenze" style="width:auto" '
            f'onchange="this.form.submit()">{optionen}</select>'
            f'<input type="hidden" name="aktion" value="portal_grenze"></form>'
            f'<div class="pf-grid">{"".join(kurz)}</div>'
            f'<form method="post" action="{ziel}#portal"><input type="hidden" name="token" value="{token}">'
            f'<input type="hidden" name="grenze" value="{grenze}"><input type="hidden" name="feld" value="">'
            f'{"".join(zeilen)}</form>'
            f'<p class="muted">Fehlt etwas (z. B. Gehaltsvorstellung)? Unter <a href="/profil">Profil</a> ergänzen.</p>'
            f'{fragen_html(ki_texte.get("fragen") or [], token, ziel, grenze, ki_an)}</details></div>')


def fragen_html(fragen: list[dict], token: str, ziel: str, grenze: int, ki_an: bool) -> str:
    """Freitextfragen des Portals („Warum möchten Sie bei uns arbeiten?“) mit KI-Antwort zum Kopieren."""
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    if not ki_an and not fragen:
        return ""
    liste = "".join(
        f'<div class="pf"><label for="pfrage-{i}"><b>{escape(f["frage"])}</b> <span class="muted" '
        f'data-zaehler="pfrage-{i}">{len(f["antwort"])} Zeichen</span></label><textarea id="pfrage-{i}" rows="5">'
        f'{escape(f["antwort"])}</textarea><div class="row"><button type="button" class="ghost small" '
        f'data-copy="pfrage-{i}">Kopieren</button></div></div>' for i, f in enumerate(fragen[:10]))
    formular = (f'<form method="post" action="{ziel}#portal-fragen"><input type="hidden" name="token" value="{token}">'
                f'<label>Frage aus dem Portal einfügen – die KI entwirft eine Antwort (höchstens {grenze} Zeichen)'
                f'</label><textarea name="frage" rows="2" placeholder="z. B. Warum möchten Sie bei uns arbeiten?">'
                f'</textarea><button name="aktion" value="portal_frage" class="ghost small" style="margin-top:6px" '
                f'data-ki="KI beantwortet die Frage …">Antwort entwerfen</button></form>' if ki_an else "")
    return (f'<div id="portal-fragen" style="margin-top:16px"><h3>Fragen im Portal</h3>{formular}{liste}</div>')


CSS = """
.pf-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:10px 16px; margin-bottom:14px; }
.pf label { font-size:13px; } .pf .row { gap:6px; flex-wrap:nowrap; } .pf input { flex:1; min-width:0; }
.pf textarea { min-height:0; } .pf + .pf { margin-top:10px; }
#portal summary { cursor:pointer; list-style:none; } #portal summary::-webkit-details-marker { display:none; }
#portal summary::before { content:"▸ "; color:var(--muted); } #portal details[open] summary::before { content:"▾ "; }
"""

JS = """
document.querySelectorAll('[data-zaehler]').forEach(z => {
  const feld = document.getElementById(z.dataset.zaehler);
  feld.addEventListener('input', () => { z.textContent = feld.value.length + ' Zeichen'; });
});
"""
