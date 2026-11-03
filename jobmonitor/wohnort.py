"""Wohnort ändern (Einstellungen → Wohnort): Fahrzeit-Tabelle für eine andere Stadt von der KI und Speichern in
config.yaml.

Die Ortsbewertung (location.py) braucht für jede Stadt eine Tabelle „Ort → ÖPNV-Minuten“. Für Köln steht sie im Code;
für eine andere Stadt schätzt die KI sie einmalig (gesendet wird nur der Städtename). Gespeichert werden
ort.zentrum, ort.fahrzeiten und der Suchort der Bundesagentur und von Adzuna (sources.*.wo). Die Werte sind grobe
Schätzungen – nachsehen und bei Bedarf in config.yaml korrigieren.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import ki, llm

MAX_ORTE = 60
MAX_MINUTEN = 120


class WohnortError(Exception):
    pass


def _name(stadt: str) -> str:
    stadt = re.sub(r"\s+", " ", stadt or "").strip()
    if not stadt or len(stadt) > 40 or not re.fullmatch(r"[\wÄÖÜäöüß .()/-]+", stadt):
        raise WohnortError("Bitte einen Ortsnamen angeben (Buchstaben, höchstens 40 Zeichen).")
    return stadt


def ki_prompt(stadt: str) -> str:
    return (f"Schätze für Pendler aus {stadt} (Deutschland) die typische Fahrzeit mit Bahn/ÖPNV vom Hauptbahnhof von "
            f"{stadt} zu Städten und Gemeinden der Umgebung, bis etwa 75 Minuten. Nimm {stadt} selbst mit 0 Minuten "
            f"auf, dazu 20 bis {MAX_ORTE} Orte, vor allem solche mit vielen Arbeitgebern. Ortsnamen so, wie sie in "
            "Stellenanzeigen stehen (z. B. „Frankfurt“ statt „Frankfurt am Main Hbf“), bei englischem Namen beide "
            "(„München“ und „Munich“). Ganze Minuten, grob gerundet.\n\n"
            'Antworte nur mit JSON: {"orte": {"Ort": Minuten}}')


def tabelle_aus(antwort: str | None, stadt: str) -> dict[str, int]:
    data = llm.json_aus(antwort)
    orte = data.get("orte") if isinstance(data, dict) else None
    if not isinstance(orte, dict):
        raise ki.KiError("Die KI hat keine lesbare Fahrzeit-Tabelle geliefert.")
    out: dict[str, int] = {}
    for ort, minuten in orte.items():
        name = re.sub(r"\s+", " ", str(ort)).strip().lower()
        if not name or len(name) > 40 or not isinstance(minuten, (int, float)) or not 0 <= minuten <= MAX_MINUTEN:
            continue
        out[name] = int(round(minuten))
    out[stadt.lower()] = 0
    if len(out) < 5:
        raise ki.KiError("Die KI hat zu wenige Orte geliefert – bitte noch einmal versuchen.")
    return dict(sorted(out.items(), key=lambda kv: (kv[1], kv[0]))[:MAX_ORTE + 1])


def ki_fahrzeiten(root: Path, cfg: dict, stadt: str, ask=None) -> dict[str, int]:
    stadt = _name(stadt)
    return tabelle_aus(ki.fragen(root, cfg, ki_prompt(stadt), effort="low", max_tokens=6000, ask=ask), stadt)


def _yaml_text(wert: str) -> str:
    return '"' + wert.replace("\\", "\\\\").replace('"', '\\"') + '"'


def config_text(text: str, stadt: str, tabelle: dict[str, int]) -> str:
    """config.yaml mit neuem Wohnort: ort.zentrum und ort.fahrzeiten (ersetzt, falls vorhanden), sources.*.wo."""
    stadt = _name(stadt)
    m = re.search(r"^ort:[^\n]*\n", text, re.MULTILINE)
    if not m:
        raise WohnortError("Abschnitt „ort:“ nicht in config.yaml gefunden.")
    nxt = re.compile(r"^[^\s#\n]", re.MULTILINE).search(text, m.end())
    ende = nxt.start() if nxt else len(text)
    block = text[m.end():ende]
    block = re.sub(r"^  zentrum:[^\n]*\n", "", block, flags=re.MULTILINE)
    block = re.sub(r"^  fahrzeiten:[^\n]*\n(?:    [^\n]*\n)*", "", block, flags=re.MULTILINE)
    neu = (f"  zentrum: {_yaml_text(stadt)}           # Wohnort (Einstellungen → Wohnort)\n"
           "  fahrzeiten:                 # ÖPNV-Minuten ab dem Wohnort, von der KI geschätzt – gern korrigieren\n"
           + "".join(f"    {_yaml_text(ort)}: {minuten}\n" for ort, minuten in tabelle.items()))
    text = text[:m.end()] + neu + block + text[ende:]
    # Suchort der Quellen (nur eingerückte wo-Zeilen unter sources)
    s = re.search(r"^sources:[^\n]*\n", text, re.MULTILINE)
    s_ende = re.compile(r"^[^\s#\n]", re.MULTILINE).search(text, s.end()) if s else None
    if s and s_ende:
        teil = re.sub(r'^(    wo: )"?[^"\n#]*"?', lambda x: x.group(1) + _yaml_text(stadt),
                      text[s.end():s_ende.start()], flags=re.MULTILINE)
        text = text[:s.end()] + teil + text[s_ende.start():]
    return text


def speichern(root: Path, stadt: str, tabelle: dict[str, int]) -> Path:
    path = root / "config.yaml"
    from .gui_wartung import speichern as datei_speichern
    return datei_speichern(root, "config.yaml", config_text(path.read_text(encoding="utf-8"), stadt, tabelle))


def karte(token: str, ort_cfg: dict, ki_an: bool, esc) -> str:
    from .location import zentrum as wohnort
    zentrum = wohnort(ort_cfg)
    n = len(ort_cfg.get("fahrzeiten") or {}) or None
    stand = (f"{n} Orte im Umkreis (eigene Tabelle)" if n else "eingebaute Tabelle für Köln und Umgebung"
             if zentrum else "bis dahin zählen nur Remote-Stellen")
    zentrum = zentrum or "noch nicht festgelegt"
    knopf = (f'<button name="aktion" value="wohnort" class="small" data-ki="KI schätzt die Fahrzeiten …">Fahrzeiten '
             f'mit KI erstellen</button>' if ki_an else
             '<a href="#ki">Dafür API-Schlüssel hinterlegen</a>')
    return (f'<div class="card" id="wohnort"><h2>Wohnort</h2><p class="muted">Stellen zählen, wenn sie höchstens '
            f'{esc(ort_cfg.get("max_fahrzeit_min", 60))} Minuten mit Bahn/ÖPNV entfernt sind. Jetzt: '
            f'<b>{esc(zentrum)}</b> · {esc(stand)}.</p>'
            f'<form method="post" action="/einstellungen" class="row" style="gap:8px;flex-wrap:wrap">'
            f'<input type="hidden" name="token" value="{token}"><input name="stadt" placeholder="z. B. München" '
            f'style="width:220px" required maxlength="40">{knopf}</form>'
            f'<p class="muted">Gesendet wird nur der Städtename. Die Minuten sind Schätzungen; ändert auch den Suchort '
            f'der Bundesagentur.</p></div>')
