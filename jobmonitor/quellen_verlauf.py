"""Quellen beobachten: merkt sich je Lauf, was jede Quelle und jede Firma geliefert hat, und warnt, wenn etwas
dauerhaft ausfällt oder nichts mehr liefert (Seite umgezogen, Feed abgeschaltet, Alert falsch eingestellt).

Status je Eintrag:
- ok: abgerufen (auch mit 0 Treffern – viele Firmen haben schlicht keine passende Stelle)
- fehler / ausfall: Abruf fehlgeschlagen
- veraltet: Stellenlinks gefunden, aber alle Detailseiten fehlten (z. B. HTTP 404)
- blockiert / manuell: dauerhaft nicht automatisch lesbar; dafür gibt es schon „Manuell prüfen“ → keine Warnung
Warnungen:
- seit `fehler_laeufe` Läufen in Folge fehler/ausfall/veraltet
- seit `leer_laeufe` Läufen in Folge 0 Rohtreffer, obwohl früher etwas kam
Grenzwerte: config.yaml → quellen_verlauf.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import SourceResult

DEFAULTS = {"fehler_laeufe": 2, "leer_laeufe": 3, "verlauf": 12}
BAD = {"fehler", "ausfall", "veraltet"}
STATUS_TEXT = {"fehler": "Fehler beim Abruf", "ausfall": "Ausfall", "veraltet": "Stellenlinks führen ins Leere"}


@dataclass
class Warnung:
    art: str      # "quelle" oder "firma"
    name: str
    text: str

    def __str__(self) -> str:
        return f"{self.name}: {self.text}"


def limits(cfg: dict) -> dict:
    return {**DEFAULTS, **(cfg.get("quellen_verlauf") or {})}


def source_status(result: SourceResult) -> str:
    return "ausfall" if result.failed else ("fehler" if result.errors else "ok")


def record(state, datum: str, results: list[SourceResult], firmen: dict | None = None) -> None:
    """Ergebnisse der abgefragten Quellen dieses Laufs speichern (ohne reine Hinweislisten wie Hochschulen ohne
    Anbindung). `firmen`: Name → CompanyOutcome (Firmen-Karriereseiten)."""
    for r in results:
        state.record_source(datum, "quelle", r.name, len(r.jobs), source_status(r))
    for name, outcome in (firmen or {}).items():
        state.record_source(datum, "firma", name, len(outcome.jobs), outcome.status)


def _streak(entries: list[tuple[str, int, str]], test) -> int:
    n = 0
    for entry in entries:
        if not test(entry):
            break
        n += 1
    return n


def warnungen(history: dict, cfg: dict, aktuell: set[tuple[str, str]] | None = None) -> list[Warnung]:
    """Warnungen aus dem Verlauf (neueste zuerst). `aktuell`: nur diese (art, name) prüfen, z. B. Firmen,
    die noch in companies.yaml stehen und aktiv sind."""
    lim, out = limits(cfg), []
    for (art, name), entries in sorted(history.items()):
        if aktuell is not None and (art, name) not in aktuell:
            continue
        bad = _streak(entries, lambda e: e[2] in BAD)
        if bad >= lim["fehler_laeufe"]:
            text = f"{STATUS_TEXT[entries[0][2]]} – seit {bad} Läufen in Folge (seit {_datum(entries[bad - 1][0])})."
            if art == "firma":
                text += " Karriereseite prüfen und ggf. die URL in companies.yaml anpassen."
            out.append(Warnung(art, name, text))
            continue
        leer = _streak(entries, lambda e: e[2] == "ok" and e[1] == 0)
        frueher = [e for e in entries[leer:] if e[1] > 0]
        if leer >= lim["leer_laeufe"] and frueher:
            zuletzt = frueher[0]
            hint = ("Seite umgezogen oder Stellenliste anders aufgebaut?" if art == "firma"
                    else "Suchbegriffe, Alert oder Quelle prüfen.")
            out.append(Warnung(art, name, f"seit {leer} Läufen keine Rohtreffer, zuletzt {zuletzt[1]} am "
                                          f"{_datum(zuletzt[0])}. {hint}"))
    return out


def _datum(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"
