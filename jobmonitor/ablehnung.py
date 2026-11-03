"""„Passt nicht“: Grund beim Ausblenden einer Stelle und Vorschläge für Ausschluss-Begriffe daraus.

Nach dem Ausblenden fragt die Stellenliste kurz nach dem Grund (ein Klick, freiwillig). Gespeichert lokal in
.gui_ablehnungen.json (gitignored): Stellen-ID → {titel, firma, grund, datum}, dazu „ignoriert“ für abgelehnte
Vorschläge. Kommt ein Wort in mindestens `MIN_TREFFER` abgelehnten Titeln vor, aber in keiner Stelle, die du noch in der
Liste hast, und ist es kein Fach- oder Fit-Begriff, schlägt die App es als Ausschluss-Begriff vor. Übernehmen hängt es
an filter.ausschluss_titel in config.yaml an – ab dem nächsten Lauf fliegen solche Titel raus.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

DATEI = ".gui_ablehnungen.json"
GRUENDE = {"fach": "anderes Fachgebiet", "vertrieb": "Vertrieb/Marketing", "senior": "zu viel Erfahrung verlangt",
           "zeit": "Stunden/Vollzeit", "ort": "Ort", "anderes": "anderes"}
MIN_TREFFER = 2
WORT = re.compile(r"[a-zäöüß][a-zäöüß0-9+#.-]{3,}")
# Wörter, die in fast jedem Titel stehen oder zu deiner Suche gehören – nie als Ausschluss vorschlagen
STOPP = {"werkstudent", "werkstudentin", "werkstudierende", "working", "student", "junior", "trainee", "praktikum",
         "praktikant", "praktikantin", "bachelorarbeit", "abschlussarbeit", "thesis", "intern", "internship", "graduate",
         "einsteiger", "berufseinsteiger", "bereich", "team", "mitarbeiter", "mitarbeiterin", "specialist", "spezialist",
         "manager", "engineer", "consultant", "berater", "beraterin", "support", "teilzeit", "vollzeit", "remote",
         "hybrid", "köln", "cologne", "germany", "deutschland", "gmbh", "unterstützung", "unterstuetzung", "für", "fuer",
         "with", "and", "und", "oder", "the", "m-w-d", "w-m-d", "d-m-w"}


class AblehnungError(Exception):
    pass


def laden(root: Path) -> dict:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _speichern(root: Path, data: dict) -> None:
    (root / DATEI).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def merken(root: Path, job: dict, grund: str, heute: date | None = None) -> None:
    if grund not in GRUENDE:
        raise AblehnungError("Unbekannter Grund.")
    data = laden(root)
    data.setdefault("stellen", {})[job["id"]] = {"titel": job.get("title", ""), "firma": job.get("company", ""),
                                                 "grund": grund, "datum": (heute or date.today()).isoformat()}
    _speichern(root, data)


def ignorieren(root: Path, wort: str) -> None:
    data = laden(root)
    data["ignoriert"] = sorted(set(data.get("ignoriert") or []) | {wort.lower()})
    _speichern(root, data)


def woerter(titel: str) -> set[str]:
    return {w.strip(".-") for w in WORT.findall(titel.lower())} - STOPP


def vorschlaege(data: dict, sichtbare_titel: list[str], ausschluss: list[str], geschuetzt: set[str],
                limit: int = 5) -> list[tuple[str, int, list[str]]]:
    """[(Wort, Anzahl abgelehnter Stellen, Gründe)] – nur Wörter, die keine sichtbare Stelle im Titel hat."""
    zaehler: Counter = Counter()
    gruende: dict[str, Counter] = {}
    for eintrag in (data.get("stellen") or {}).values():
        for w in woerter(eintrag.get("titel", "")):
            zaehler[w] += 1
            gruende.setdefault(w, Counter())[GRUENDE.get(eintrag.get("grund"), "")] += 1
    sichtbar = set().union(*(woerter(t) for t in sichtbare_titel)) if sichtbare_titel else set()
    schon = {a.lower() for a in ausschluss}
    tabu = {g.lower() for g in geschuetzt} | set(data.get("ignoriert") or [])
    out = []
    for w, n in zaehler.most_common():
        if n < MIN_TREFFER or w in sichtbar or w in tabu or any(a in w or w in a for a in schon) \
                or any(w in t or t in w for t in tabu if len(t) >= 3):
            continue
        out.append((w, n, [g for g, _ in gruende[w].most_common(2) if g]))
    return out[:limit]


def ausschliessen(root: Path, wort: str, ausschluss: list[str]) -> Path:
    """Neue Zeile `    - wort` am Ende von filter.ausschluss_titel in config.yaml (Rest der Datei unverändert)."""
    wort = wort.strip().lower()
    if not wort or len(wort) > 40 or not WORT.fullmatch(wort):
        raise AblehnungError("Ungültiger Begriff.")
    if wort in {a.lower() for a in ausschluss}:
        raise AblehnungError(f"„{wort}“ steht schon in der Ausschluss-Liste.")
    path = root / "config.yaml"
    text = path.read_text(encoding="utf-8")
    filt = re.search(r"^filter:[^\n]*\n", text, re.MULTILINE)
    block = re.compile(r"^  ausschluss_titel:[^\n]*\n", re.MULTILINE).search(text, filt.end()) if filt else None
    if not block:
        raise AblehnungError("filter.ausschluss_titel nicht in config.yaml gefunden.")
    ende = block.end()
    for zeile in text[block.end():].splitlines(keepends=True):
        if not zeile.startswith("    - "):
            break
        ende += len(zeile)
    neu = text[:ende] + f"    - {wort}\n" + text[ende:]
    from .gui_wartung import speichern
    return speichern(root, "config.yaml", neu)


def grund_html(job_id: str, token: str, esc) -> str:
    knoepfe = "".join(f'<button name="grund" value="{k}" class="ghost small">{esc(v)}</button>' for k, v in GRUENDE.items())
    return (f'<form method="post" action="/markieren" class="row" style="margin-top:6px;gap:6px;flex-wrap:wrap">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="job_id" value="{esc(job_id)}">'
            f'<input type="hidden" name="aktion" value="grund"><span class="muted">Warum passt sie nicht? (freiwillig, '
            f'daraus lernt der Filter)</span>{knoepfe}</form>')


def karte(liste: list[tuple[str, int, list[str]]], token: str, esc) -> str:
    if not liste:
        return ""
    form = lambda wort, aktion, label, cls: (  # noqa: E731
        f'<form method="post" action="/ablehnung" style="display:inline"><input type="hidden" name="token" '
        f'value="{token}"><input type="hidden" name="wort" value="{esc(wort)}"><input type="hidden" name="aktion" '
        f'value="{aktion}"><button class="{cls}">{label}</button></form>')
    zeilen = "".join(
        f'<li><div><b>{esc(w)}</b> <span class="muted">· in {n} abgelehnten Titeln'
        f'{" · " + esc(", ".join(g)) if g else ""}</span></div>'
        f'<div class="row">{form(w, "ausschliessen", "Ausschließen", "small")}'
        f'{form(w, "ignorieren", "Nein", "ghost small")}</div></li>' for w, n, g in liste)
    return (f'<div class="card"><div class="head"><h2>Aus deinen Ablehnungen gelernt</h2><span class="muted">Titel mit '
            f'diesem Wort ab dem nächsten Lauf aussortieren?</span></div><ul class="follow">{zeilen}</ul></div>')
