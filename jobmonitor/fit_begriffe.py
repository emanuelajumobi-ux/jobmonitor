"""Fit-Begriffe (config.yaml → fit.begriffe) in der App ergänzen: Vorschläge der KI übernehmen oder ausblenden,
eigene Begriffe hinzufügen.

Vorschläge sind Anforderungen, die die KI in Anzeigen fand, für die es aber noch keinen Fit-Begriff gibt (fit.mit_ki,
nachbewertung). Die Pipeline zählt sie in state/seen.sqlite (meta „fit_vorschlaege“); ältere stehen nur im Bericht
und werden von dort gelesen. Ausgeblendetes merkt sich die App lokal (.gui_fit_ignoriert.json).

Gespeichert wird als neue Zeile am Ende von fit.begriffe; der Rest von config.yaml bleibt Zeichen für Zeichen gleich.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

META = "fit_vorschlaege"
IGNORIERT = ".gui_fit_ignoriert.json"
BERICHT = re.compile(r"KI fand Anforderungen ohne Fit-Begriff: (.+?) – ")
EINTRAG = re.compile(r"^(.+) \((\d+)×\)$")


class BegriffError(Exception):
    pass


def merken(state, vorschlaege: Counter) -> None:
    """Vorschläge eines Laufs zu den gespeicherten addieren (Pipeline)."""
    if not vorschlaege:
        return
    try:
        alt = Counter(json.loads(state.get_meta(META) or "{}"))
    except ValueError:
        alt = Counter()
    alt.update(vorschlaege)
    state.set_meta(META, json.dumps(dict(alt.most_common(200)), ensure_ascii=False, sort_keys=True))


def aus_bericht(text: str) -> Counter:
    m = BERICHT.search(text or "")
    if not m:
        return Counter()
    teile = (EINTRAG.match(teil.strip()) for teil in m.group(1).split(", "))
    return Counter({e.group(1).strip(): int(e.group(2)) for e in teile if e})


def ignoriert(root: Path) -> set[str]:
    try:
        return {str(x).lower() for x in json.loads((root / IGNORIERT).read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return set()


def ignorieren(root: Path, term: str) -> None:
    (root / IGNORIERT).write_text(json.dumps(sorted(ignoriert(root) | {term.lower()}), ensure_ascii=False),
                                  encoding="utf-8")


def bekannt(begriffe: dict) -> set[str]:
    return {str(b).lower() for b in begriffe} | {str(s).lower() for syn in begriffe.values() for s in syn or []}


def offen(gespeichert: Counter, bericht: Counter, begriffe: dict, ausgeblendet: set[str]) -> list[tuple[str, int]]:
    """Vorschläge, die weder Fit-Begriff noch Synonym noch ausgeblendet sind – häufigste zuerst."""
    alle = Counter(gespeichert)
    for term, n in bericht.items():
        alle[term] = max(alle[term], n)
    weg = bekannt(begriffe) | ausgeblendet
    return [(t, n) for t, n in alle.most_common() if t.lower() not in weg]


def _yaml_wert(text: str) -> str:
    return text if re.fullmatch(r"[\wÄÖÜäöüß][\wÄÖÜäöüß .+#/&()-]*", text) and not text.endswith(" ") \
        else json.dumps(text, ensure_ascii=False)


def hinzufuegen(root: Path, term: str, synonyme: list[str], begriffe: dict) -> Path:
    """Neue Zeile `    Begriff: [synonym, …]` am Ende von fit.begriffe in config.yaml."""
    term = term.strip()
    synonyme = [s.strip().lower() for s in synonyme if s.strip()]
    if not term or len(term) > 50:
        raise BegriffError("Bitte einen Begriff angeben (höchstens 50 Zeichen).")
    if term.lower() in bekannt(begriffe):
        raise BegriffError(f"„{term}“ gibt es schon als Fit-Begriff oder Synonym.")
    path = root / "config.yaml"
    text = path.read_text(encoding="utf-8")
    fit = re.search(r"^fit:[^\n]*\n", text, re.MULTILINE)
    block = re.compile(r"^  begriffe:[^\n]*\n", re.MULTILINE).search(text, fit.end()) if fit else None
    if not block:
        raise BegriffError("Abschnitt fit.begriffe nicht in config.yaml gefunden.")
    ende = block.end()
    for zeile in text[block.end():].splitlines(keepends=True):
        if zeile.strip() and not zeile.startswith("    "):
            break
        ende += len(zeile)
    while text[:ende].endswith("\n\n"):        # Leerzeilen am Blockende gehören zum nächsten Abschnitt
        ende -= 1
    zeile = f"    {_yaml_wert(term)}: [{', '.join(_yaml_wert(s) for s in synonyme)}]\n"
    neu = text[:ende] + zeile + text[ende:]
    from .gui_wartung import speichern
    return speichern(root, "config.yaml", neu)
