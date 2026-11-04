"""Weitere KI-Helfer der Oberfläche – alle nur auf Klick, mit deinem Schlüssel und Monatslimit (ki.fragen):

- Lebenslauf verstehen: welche Fit-Begriffe dein Master-CV belegt, ohne dass das Wort dasteht (Vorschläge zum
  Bestätigen, eingetragen wird erst auf Klick).
- Fit erklären: warum eine Stelle so viel Prozent hat, was du betonen und wie du Lücken ansprechen kannst.
- Portal-Fragen: Freitextfragen aus Bewerbungsportalen („Warum wir?“) mit Zeichengrenze beantworten.
- Lebenslauf-Check: Formulierungen konkreter machen – nichts erfinden, fehlende Zahlen als [Platzhalter].
- Muster aus Absagen: was abgelehnte und erfolgreiche Bewerbungen unterscheidet (ab 5 Absagen).

Gesendet werden Anzeigentexte und der fachliche Teil des Lebenslaufs, nie Name, Adresse, Kontakt oder Foto.
Ergebnisse liegen in .gui_ki.json (lokal).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from . import ki, llm

LEVEL = ("Grundkenntnisse", "gut", "sehr gut")
MIN_ABSAGEN = 5


def _stand(*teile) -> str:
    return hashlib.sha256(json.dumps(teile, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def _merken(root: Path, bereich: str, schluessel: str, wert) -> None:
    data = ki.laden(root)
    data.setdefault(bereich, {})[schluessel] = wert
    ki._speichern(root, data)


def gemerkt(root: Path, bereich: str, schluessel: str):
    return (ki.laden(root).get(bereich) or {}).get(schluessel)


def _explizit(cv: dict) -> set[str]:
    """Begriffe, die schon mit eigenem Level unter Kenntnisse oder Sprachen stehen."""
    namen = {str(s.get("sprache") or "").lower() for s in cv.get("sprachen") or [] if isinstance(s, dict)}
    for k in cv.get("kenntnisse") or []:
        for e in (k.get("eintraege") or []) if isinstance(k, dict) else []:
            namen.add(str(e.get("name") if isinstance(e, dict) else e).lower())
    return namen


# --- 1. Lebenslauf verstehen ---
def cv_verstehen(root: Path, cfg: dict, cv: dict, ask=None) -> list[dict]:
    """[{begriff, level, beleg}] – Fit-Begriffe, die der Lebenslauf belegt, ohne sie als Kenntnis zu nennen."""
    begriffe = cfg["fit"]["begriffe"]
    offen = [b for b in begriffe if b.lower() not in _explizit(cv)]
    antwort = llm.json_aus(ki.fragen(root, cfg, (
        "Prüfe einen Lebenslauf: Welche der unten genannten Kenntnisse belegt er der Sache nach, auch wenn das Wort "
        "selbst nicht dasteht (z. B. „Intune“ belegt Endpoint Management, ein Cyber-Security-Studium belegt "
        "Informationssicherheit)? Nur, was Stationen, Projekte, Zertifikate oder das Studium wirklich zeigen – im "
        "Zweifel weglassen. Einträge mit status „geplant“ zählen nicht.\n\n"
        f"KENNTNISSE ZUR AUSWAHL: {', '.join(offen)}\n\nLEBENSLAUF:\n{ki.cv_text(cv)}\n\n"
        'Antworte nur mit JSON: {"belegt": [{"begriff": "...", "level": "Grundkenntnisse|gut|sehr gut", '
        '"beleg": "wo es steht, höchstens 12 Wörter"}]}\n'
        "- begriff: genau ein Name aus der Liste.\n- level: vorsichtig – Studium allein = Grundkenntnisse, "
        "Praxis in einer Station = gut, sehr gut nur bei längerer, vertiefter Praxis."),
        effort="low", max_tokens=6000, ask=ask))
    namen = {b.lower(): b for b in offen}
    out = []
    for e in (antwort or {}).get("belegt") or []:
        if not isinstance(e, dict):
            continue
        b = namen.get(str(e.get("begriff") or "").lower())
        if b and e.get("level") in LEVEL and b not in {x["begriff"] for x in out}:
            out.append({"begriff": b, "level": e["level"], "beleg": str(e.get("beleg") or "")[:120]})
    _merken(root, "cv_verstehen", "letzter", {"stand": _stand(cv), "vorschlaege": out})
    return out


def cv_verstehen_html(root: Path, cv: dict, token: str, ki_an: bool, esc) -> str:
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    letzter = gemerkt(root, "cv_verstehen", "letzter") or {}
    vorschlaege = [v for v in letzter.get("vorschlaege") or [] if v["begriff"].lower() not in _explizit(cv)]
    knopf = (f'<button name="aktion" value="cv_verstehen" class="ghost small" data-ki="KI liest deinen Lebenslauf …">'
             f'{"Erneut prüfen" if letzter else "Mit KI prüfen"}</button>' if ki_an else
             '<a class="btn ghost small" href="/einstellungen#ki">KI einrichten</a>')
    zeilen = "".join(
        f'<tr><td><label class="check"><input type="checkbox" name="begriff:{esc(v["begriff"])}" value="1" checked> '
        f'<b>{esc(v["begriff"])}</b></label><br><span class="muted">{esc(v["beleg"])}</span></td><td>'
        f'<select name="level:{esc(v["begriff"])}" style="width:auto">'
        + "".join(f'<option{" selected" if lv == v["level"] else ""}>{lv}</option>' for lv in LEVEL)
        + '</select></td></tr>' for v in vorschlaege)
    liste = (f'<table>{zeilen}</table><div class="row" style="margin-top:8px"><button name="aktion" '
             f'value="cv_uebernehmen" class="small">Ausgewählte als Kenntnisse eintragen</button></div>'
             if zeilen else ('<p class="muted">Keine weiteren Vorschläge – dein Lebenslauf nennt alles schon.</p>'
                             if letzter else ""))
    return (f'<div class="card" id="cv-verstehen"><h2>Was dein Lebenslauf noch belegt</h2><p class="muted">Die KI '
            f'liest Stationen, Projekte und Studium und schlägt Kenntnisse vor, die dort der Sache nach stehen, aber '
            f'nicht als Kenntnis eingetragen sind (z. B. Intune → Endpoint Management). Du entscheidest, was übernommen '
            f'wird; das Level kannst du anpassen.</p><form method="post" action="/ki"><input type="hidden" '
            f'name="token" value="{token}"><div class="row" style="margin-bottom:8px">{knopf}</div>{liste}</form></div>')


# --- 3. Fit erklären ---
def fit_erklaeren(root: Path, cfg: dict, stelle: dict, passt: list[str], fehlt: list[str], fit_wert, anzeige: str,
                  cv: dict, ask=None) -> str:
    text = ki.fragen(root, cfg, (
        "Erkläre in 3 bis 5 kurzen Sätzen ohne Überschrift, wie gut dieser Lebenslauf zur Stelle passt: warum der "
        "Fit so ausfällt, welche 2 Punkte aus dem Lebenslauf die Person im Anschreiben betonen sollte und wie sie die "
        "wichtigste Lücke ehrlich ansprechen kann. Nichts erfinden.\n\n"
        f"FIT: {fit_wert if fit_wert is not None else 'zu wenig Angaben'} %\nPASST: {', '.join(passt) or '–'}\n"
        f"FEHLT: {', '.join(fehlt) or '–'}\n\n{ki._kopf(stelle, anzeige, cv)}"), effort="low", max_tokens=3000, ask=ask)
    _merken(root, "fit_erklaert", str(stelle.get("url") or stelle.get("id")), {"datum": date.today().isoformat(),
                                                                              "text": text})
    return text


def fit_erklaert_html(root: Path, stelle: dict, ziel: str, token: str, ki_an: bool, esc) -> str:
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    alt = gemerkt(root, "fit_erklaert", str(stelle.get("url") or stelle.get("id")))
    if not ki_an and not alt:
        return ""
    knopf = (f'<form method="post" action="{ziel}" style="margin-top:8px"><input type="hidden" name="token" '
             f'value="{token}"><button name="aktion" value="fit_erklaeren" class="ghost small" data-ki="KI erklärt den '
             f'Fit …">{"Neu erklären" if alt else "Fit erklären"}</button></form>' if ki_an else "")
    inhalt = ki.als_html(alt["text"], esc) if alt else '<p class="muted">Warum dieser Fit, was du betonen und wie du ' \
                                                       'Lücken ansprechen kannst.</p>'
    return f'<div class="card" id="fit-erklaert"><h2>Fit erklärt</h2>{inhalt}{knopf}</div>'


# --- 4. Freitextfragen aus Bewerbungsportalen ---
def portal_antwort(root: Path, cfg: dict, frage: str, grenze: int, stelle: dict, anzeige: str, cv: dict,
                   anschreiben: str, englisch: bool = False, ask=None) -> str:
    from .portal import kuerzen
    antwort = ki.fragen(root, cfg, (
        f"Beantworte diese Frage aus einem Online-Bewerbungsformular für die Person, höchstens {grenze - 20} Zeichen, "
        f"{'auf Englisch' if englisch else 'auf Deutsch'}, in der Ich-Form, konkret und ohne Floskeln. Nur Fakten aus "
        "Lebenslauf und Anschreiben; fehlt etwas, schreibe einen [Platzhalter]. Keine Anrede, keine Grußformel.\n\n"
        f"FRAGE: {frage[:600]}\n\nANSCHREIBEN (eigener Text der Person):\n{anschreiben[:3000]}\n\n"
        f"{ki._kopf(stelle, anzeige, cv)}\n\nGib nur die Antwort aus."), effort="low", max_tokens=3000, ask=ask)
    antwort = antwort.strip().strip('"„“').strip()
    return kuerzen(antwort, grenze) if len(antwort) > grenze else antwort


# --- 6. Lebenslauf-Check ---
def cv_check(root: Path, cfg: dict, cv: dict, ask=None) -> list[dict]:
    """[{wo, vorher, vorschlag, warum}] – höchstens 8 Formulierungen, die konkreter werden könnten."""
    antwort = llm.json_aus(ki.fragen(root, cfg, (
        "Du prüfst die Formulierungen eines Lebenslaufs (Stichpunkte zu Stationen und Projekten, Profiltext). Schlage "
        "höchstens 8 Verbesserungen vor, wo ein Punkt vage ist („Unterstützung bei …“, „zuständig für …“) und "
        "konkreter wirken kann: Tätigkeit, Werkzeug, Ergebnis. ERFINDE NICHTS – fehlen Zahlen oder Ergebnisse, setze "
        "einen [Platzhalter] wie [Anzahl Nutzer]. Keine Rechtschreib-Kleinigkeiten.\n\n"
        f"LEBENSLAUF:\n{ki.cv_text(cv)}\n\n"
        'Antworte nur mit JSON: {"vorschlaege": [{"wo": "z. B. Station 1, Aufgabe 2", "vorher": "...", '
        '"vorschlag": "...", "warum": "kurz"}]}'), effort="low", max_tokens=6000, ask=ask))
    out = [{k: str(v.get(k) or "")[:400] for k in ("wo", "vorher", "vorschlag", "warum")}
           for v in (antwort or {}).get("vorschlaege") or [] if isinstance(v, dict) and v.get("vorschlag")][:8]
    _merken(root, "cv_check", "letzter", {"stand": _stand(cv), "datum": date.today().isoformat(), "vorschlaege": out})
    return out


def cv_check_html(root: Path, cv: dict, token: str, ki_an: bool, esc) -> str:
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    letzter = gemerkt(root, "cv_check", "letzter") or {}
    if not ki_an and not letzter:
        return ""
    veraltet = letzter and letzter.get("stand") != _stand(cv)
    knopf = (f'<form method="post" action="/ki"><input type="hidden" name="token" value="{token}"><button '
             f'name="aktion" value="cv_check" class="ghost small" data-ki="KI prüft die Formulierungen …">'
             f'{"Erneut prüfen" if letzter else "Formulierungen prüfen"}</button></form>' if ki_an else "")
    punkte = "".join(
        f'<li><b>{esc(v["wo"])}</b>: <span class="muted">{esc(v["vorher"])}</span><br>→ {esc(v["vorschlag"])}'
        f'{" <span class=muted>(" + esc(v["warum"]) + ")</span>" if v["warum"] else ""}</li>'
        for v in letzter.get("vorschlaege") or [])
    return (f'<div class="card" id="cv-check"><h2>Lebenslauf-Check</h2><p class="muted">Vorschläge, wo Stichpunkte '
            f'konkreter werden können. Erfunden wird nichts – [Platzhalter] füllst du selbst. Übernehmen kannst du sie '
            f'oben im Editor.{" Stand vor deinen letzten Änderungen." if veraltet else ""}</p>'
            f'{"<ul>" + punkte + "</ul>" if punkte else ""}{knopf}</div>')


# --- 9. Muster aus Absagen ---
def absagen_muster(root: Path, cfg: dict, zeilen: list[dict], ask=None) -> str:
    """`zeilen`: [{titel, status, fit, typ, quelle, wochen}] – ohne Namen oder Kontaktdaten."""
    text = ki.fragen(root, cfg, (
        "Hier sind Bewerbungen einer Person mit Ergebnis. Was unterscheidet Absagen von Einladungen und Zusagen? "
        "Nenne 3 bis 5 Beobachtungen mit Zahl (z. B. „4 von 5 Absagen bei Fit unter 50 %“) und 2 bis 3 konkrete "
        "Vorschläge, worauf sie sich konzentrieren sollte. Nur, was die Daten hergeben – bei wenig Daten das ehrlich "
        "sagen. Format: „## Beobachtungen“ und „## Vorschläge“ mit Punkten „- “.\n\nBEWERBUNGEN (JSON):\n"
        + json.dumps(zeilen[:80], ensure_ascii=False)), effort="medium", max_tokens=4000, ask=ask)
    _merken(root, "absagen_muster", "letzter", {"datum": date.today().isoformat(), "text": text,
                                                "n": len(zeilen)})
    return text


def absagen_html(root: Path, n_absagen: int, token: str, ki_an: bool, esc) -> str:
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    letzter = gemerkt(root, "absagen_muster", "letzter")
    if n_absagen < MIN_ABSAGEN and not letzter:
        return (f'<div class="card"><h2>Muster aus Absagen</h2><p class="muted">Ab {MIN_ABSAGEN} Absagen sucht die KI '
                f'nach Mustern, was abgelehnte und erfolgreiche Bewerbungen unterscheidet (bisher {n_absagen}).</p>'
                f'</div>') if ki_an else ""
    knopf = (f'<form method="post" action="/ki"><input type="hidden" name="token" value="{token}"><button '
             f'name="aktion" value="absagen" class="ghost small" data-ki="KI sucht Muster …">'
             f'{"Neu auswerten" if letzter else "Muster suchen"}</button></form>' if ki_an else "")
    inhalt = ki.als_html(letzter["text"], esc) if letzter else ""
    stand = f'<p class="muted">Stand {date.fromisoformat(letzter["datum"]):%d.%m.%Y}, {letzter["n"]} Bewerbungen.</p>' \
        if letzter else ""
    return f'<div class="card" id="absagen"><h2>Muster aus Absagen</h2>{inhalt}{stand}{knopf}</div>'
