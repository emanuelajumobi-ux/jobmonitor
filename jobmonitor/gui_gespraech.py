"""Nach dem Gespräch und Angebote vergleichen (Seite „Bewerbungen“).

- Nach dem Gespräch: Notizen (was gefragt wurde, offene Punkte) und Bauchgefühl je Bewerbung, dazu auf Wunsch ein
  KI-Entwurf für eine kurze Danke-Mail. Gesendet werden Firma, Stelle und deine Notizen, nie profile.yaml; dein Name
  kommt erst lokal hinein (Platzhalter [Name]). Verschickt wird nichts – du kopierst den Entwurf selbst.
  Notizen früherer Gespräche bei derselben Firma fließen in die nächste KI-Gesprächsvorbereitung ein.
- Angebote vergleichen: ab zwei Zusagen eine Tabelle mit Eckdaten der Anzeige, Fit und deinen Notizen.

Gespeichert lokal in .gui_gespraeche.json (gitignored, in der Sicherung enthalten): Link → {notizen, gefuehl,
datum, danke: [Betreff, Text]}.
"""
from __future__ import annotations

import json
import zlib
from datetime import date
from html import escape
from pathlib import Path

from . import ki, llm
from .models import normalize

DATEI = ".gui_gespraeche.json"
GEFUEHLE = {"gut": "gutes Gefühl", "mittel": "gemischt", "schlecht": "eher nicht"}


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def laden(root: Path) -> dict[str, dict]:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _speichern(root: Path, data: dict) -> None:
    (root / DATEI).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def notiz_speichern(root: Path, link: str, notizen: str, gefuehl: str, heute: date | None = None) -> None:
    data = laden(root)
    eintrag = data.setdefault(link, {})
    eintrag.update({"notizen": notizen.strip()[:4000], "gefuehl": gefuehl if gefuehl in GEFUEHLE else "",
                    "datum": (heute or date.today()).isoformat()})
    _speichern(root, data)


def danke(root: Path, cfg: dict, row: dict, titel: str, name: str, ask=None) -> tuple[str, str]:
    """(Betreff, Text) einer kurzen Danke-Mail nach dem Gespräch; gespeichert unter dem Link."""
    data = laden(root)
    notizen = (data.get(row.get("link", "")) or {}).get("notizen", "")
    antwort = llm.json_aus(ki.fragen(root, cfg, (
        "Schreibe eine kurze Danke-Mail nach einem Vorstellungsgespräch auf Deutsch (Sie-Form, 70 bis 120 Wörter, "
        "herzlich, aber ohne Floskeln und ohne Übertreibung). Greife höchstens ein, zwei konkrete Themen aus den "
        "Notizen auf, wenn sie passen; erfinde nichts. Unterschreibe mit genau [Name].\n\n"
        f"FIRMA: {row.get('firma')}\nSTELLE: {titel}\n"
        f"NOTIZEN ZUM GESPRÄCH:\n{notizen[:2000] or '(keine)'}\n\n"
        'Antworte nur mit JSON: {"betreff": "...", "text": "..."}'), effort="low", max_tokens=4000, ask=ask))
    if not isinstance(antwort, dict) or not antwort.get("betreff") or not antwort.get("text"):
        raise ki.KiError("Die KI hat keinen lesbaren Entwurf geliefert.")
    text = str(antwort["text"]).replace("[Name]", name or "[Name]")
    data.setdefault(row.get("link", ""), {})["danke"] = [str(antwort["betreff"]), text]
    _speichern(root, data)
    return str(antwort["betreff"]), text


def frueher_notizen(data: dict, rows: list[dict], firma: str, link: str) -> str:
    """Eigene Notizen aus früheren Gesprächen bei derselben Firma (für die KI-Vorbereitung)."""
    kern = normalize(firma or "")
    teile = []
    for r in rows:
        eintrag = data.get(r.get("link", "")) or {}
        if r.get("link") != link and kern and normalize(r.get("firma") or "") == kern and eintrag.get("notizen"):
            titel = (r.get("notizen") or "").split("\n")[0]
            teile.append(f"- {eintrag.get('datum', '')} {titel}: {eintrag['notizen'][:800]}")
    return "\n".join(teile)


def nachbereitung_html(link: str, eintrag: dict | None, token: str, ki_an: bool) -> str:
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    eintrag = eintrag or {}
    hidden = (f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="link" '
              f'value="{esc(link)}">')
    wahl = "".join(f'<label class="check"><input type="radio" name="gefuehl" value="{k}"'
                   f'{" checked" if eintrag.get("gefuehl") == k else ""}> {esc(v)}</label>' for k, v in GEFUEHLE.items())
    danke_html = ""
    if eintrag.get("danke"):
        betreff, text = eintrag["danke"]
        feld = f"danke-{zlib.crc32(link.encode()):08x}"
        danke_html = (f'<label>Betreff</label><input value="{esc(betreff)}" readonly>'
                      f'<label>Danke-Mail (Entwurf von der KI – lesen, anpassen, selbst senden)</label>'
                      f'<textarea id="{feld}" rows="8">{esc(text)}</textarea>'
                      f'<div class="row"><button type="button" class="ghost small" data-copy="{feld}">Kopieren</button>'
                      f'</div>')
    knopf = (f'<button name="aktion" value="danke" class="ghost small" data-ki="KI schreibt die Danke-Mail …" '
             f'onclick="return confirm(\'Danke-Mail mit KI entwerfen? Gesendet werden Firma, Stelle und deine Notizen '
             f'– keine Daten aus profile.yaml.\')">{"Danke-Mail neu entwerfen" if eintrag.get("danke") else "Danke-Mail mit KI entwerfen"}</button>'
             if ki_an else "")
    stand = f' <span class="muted">· {esc(GEFUEHLE.get(eintrag.get("gefuehl"), ""))}</span>' if eintrag.get("gefuehl") else ""
    return (f'<details><summary>Nach dem Gespräch{stand}</summary>'
            f'<form method="post" action="/bewerbungen/nachbereitung">{hidden}'
            f'<label>Notizen: Was wurde gefragt, was ist offen, wer war dabei?</label>'
            f'<textarea name="notizen" rows="5">{esc(eintrag.get("notizen", ""))}</textarea>'
            f'<div class="row" style="margin-top:6px"><span class="muted">Bauchgefühl:</span>{wahl}</div>'
            f'<div class="row" style="margin-top:8px"><button name="aktion" value="speichern" class="small">'
            f'Notizen speichern</button>{knopf}</div></form>{danke_html}'
            f'<p class="muted">Deine Notizen fließen bei derselben Firma in die nächste Gesprächsvorbereitung ein.</p>'
            f'</details>')


# --- Angebote vergleichen ---
def angebote(rows: list[dict], stellen: dict[str, dict], data: dict) -> list[dict]:
    """Zusagen mit Eckdaten (aus der Anzeige), Fit und Notizen; ab zwei Zusagen sinnvoll."""
    out = []
    for r in rows:
        if r.get("status") != "Zusage":
            continue
        s = stellen.get(r.get("link", "")) or {}
        e = s.get("eckdaten") or {}
        eintrag = data.get(r.get("link", "")) or {}
        out.append({"firma": r.get("firma", ""), "titel": s.get("title") or (r.get("notizen") or "").split("\n")[0],
                    "link": r.get("link", ""), "stunden": e.get("stunden", ""), "verguetung": e.get("verguetung", ""),
                    "remote": e.get("remote", ""), "start": e.get("start", ""), "fit": s.get("fit"),
                    "gefuehl": GEFUEHLE.get(eintrag.get("gefuehl"), ""), "notizen": eintrag.get("notizen", "")})
    return out


def angebote_html(liste: list[dict]) -> str:
    if len(liste) < 2:
        return ""
    zeilen = [("Stelle", lambda a: esc(a["titel"]) or "–"), ("Stunden", lambda a: esc(a["stunden"]) or "–"),
              ("Vergütung", lambda a: esc(a["verguetung"]) or "–"), ("Remote", lambda a: esc(a["remote"]) or "–"),
              ("Start", lambda a: esc(a["start"]) or "–"),
              ("Fit", lambda a: f'{a["fit"]} %' if a["fit"] is not None else "–"),
              ("Bauchgefühl", lambda a: esc(a["gefuehl"]) or "–"),
              ("Notizen", lambda a: esc(a["notizen"][:300]) or "–")]
    kopf = "".join(f'<th><a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["firma"])}</a></th>'
                   for a in liste)
    body = "".join(f'<tr><th>{name}</th>' + "".join(f"<td>{wert(a)}</td>" for a in liste) + "</tr>"
                   for name, wert in zeilen)
    return (f'<div class="card"><h2>Angebote vergleichen</h2><p class="muted">{len(liste)} Zusagen nebeneinander. '
            f'Eckdaten laut Anzeige (von der KI gelesen) – was im Vertrag steht, zählt. Fahrzeit kennt die App nicht.'
            f'</p><div style="overflow-x:auto"><table class="vergleich"><thead><tr><th></th>{kopf}</tr></thead>'
            f'<tbody>{body}</tbody></table></div></div>')


CSS = """
.vergleich { border-collapse:collapse; font-size:13px; min-width:100%; }
.vergleich th, .vergleich td { text-align:left; padding:6px 10px 6px 0; border-top:1px solid var(--line); vertical-align:top; }
.vergleich tbody th { color:var(--muted); font-weight:500; white-space:nowrap; }
"""
