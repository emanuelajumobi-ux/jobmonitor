"""Originalanzeige zu Stellen aus Job-Alert-Mails (LinkedIn, StepStone …) finden.

Alert-Mails enthalten nur Titel, Firma und Ort, keinen Anzeigentext. Viele dieser Stellen stehen aber auch auf der
Karriereseite der Firma oder bei der Bundesagentur. Gesucht wird nur in offiziellen Quellen:
1. unter den Treffern des laufenden Laufs (Firmen-Karriereseiten, BA, Hochschulbörsen) – ohne weitere Anfrage;
2. sonst in der Jobsuche der Bundesagentur (Titel + Ort, wenige Anfragen je Lauf).
Die Portal-Links selbst werden nie geöffnet. Bei einem Treffer übernimmt die Stelle Link und Text des Originals, damit
Fit, Frist und Zuschnitt funktionieren.
"""
from __future__ import annotations

import logging
import re
from dataclasses import replace

from .models import Job, normalize
from .sources import bundesagentur, mail_alerts

log = logging.getLogger(__name__)
RECHTSFORM = re.compile(r"\b(gmbh|ag|se|kg|co|mbh|ohg|e v|ev|group|gruppe|deutschland|germany|holding|kgaa)\b")
# Wörter, die in fast jedem Titel stehen und nichts über die Stelle sagen
FUELLWORT = {"m", "w", "d", "f", "x", "all", "gender", "genders", "und", "and", "in", "im", "bei", "der", "die", "das",
             "für", "for", "mit", "as", "als", "of", "the", "zur", "zum", "einer", "eine"}
# Allgemeine Namensteile, die allein keine gleiche Firma belegen
FIRMA_ALLGEMEIN = {"deutsche", "deutschland", "und", "the", "it", "consulting", "services", "service", "solutions",
                   "systems", "technologies", "technology", "digital", "international", "zentrale", "niederlassung",
                   "köln", "bonn", "düsseldorf", "bank", "versicherung", "adör", "aör", "partner"}
TITEL_AEHNLICH = 0.6   # gemeinsame Wörter / alle Wörter beider Titel („Consultant“ ≠ „Engineer“)


def firma_key(name: str) -> str:
    return re.sub(r"\s+", " ", RECHTSFORM.sub(" ", normalize(name))).strip()


def gleiche_firma(a: str, b: str) -> bool:
    """Gleich, wenn ein Name im anderen steckt oder beide einen unterscheidenden Namensteil teilen
    („Deutsche Post und DHL“ ~ „DHL AG Zentrale“, „EY“ ~ „EY Consulting GmbH“)."""
    ka, kb = firma_key(a), firma_key(b)
    if not (ka and kb):
        return False
    if ka == kb or f" {ka} " in f" {kb} " or f" {kb} " in f" {ka} ":
        return True
    teile = lambda k: {w for w in k.split() if len(w) >= 3 and w not in FIRMA_ALLGEMEIN}
    return bool(teile(ka) & teile(kb))


def _woerter(title: str) -> set[str]:
    return {w for w in normalize(title).split() if w not in FUELLWORT and len(w) > 1}


def titel_aehnlich(a: str, b: str) -> float:
    wa, wb = _woerter(a), _woerter(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def passt(alert: Job, kandidat: Job) -> bool:
    return gleiche_firma(alert.company, kandidat.company) and \
        titel_aehnlich(alert.title, kandidat.title) >= TITEL_AEHNLICH


def _uebernehmen(alert: Job, original: Job) -> Job:
    """Stelle mit Link und Text des Originals; die Alert-Herkunft bleibt in Quelle und Hinweis sichtbar."""
    flags = [f for f in alert.flags if not f.startswith("Ort nicht erkannt")]
    flags.append(f"Originalanzeige gefunden ({original.source}), Hinweis kam per Job-Alert")
    return replace(original, source=f"{original.source} + {mail_alerts.NAME}", flags=flags,
                   description=original.description or alert.description)


def _suchtitel(title: str) -> str:
    """Titel für die BA-Suche: ohne Gender-Zusatz und Klammern, höchstens sechs Wörter."""
    text = re.sub(r"\([^)]*\)|\s[|–—-]\s.*$|\s(?:bei|at)\s.*$", " ", title)
    return " ".join(text.split()[:6])


def ergaenzen(alerts: list[Job], andere: list[Job], ba: bundesagentur.BundesagenturSource | None,
              cfg: dict) -> tuple[list[Job], int]:
    """Gibt die Alert-Stellen zurück, wo möglich durch das Original ersetzt, und die Zahl der Funde.
    `andere`: Rohtreffer der übrigen Quellen dieses Laufs. `cfg`: sources.mail_alerts.originalsuche."""
    if not cfg.get("enabled", True):
        return alerts, 0
    out, gefunden, anfragen = [], 0, 0
    for job in alerts:
        original = next((k for k in andere if passt(job, k)), None)
        if original is None and ba is not None and anfragen < cfg.get("max_ba_anfragen", 15) \
                and not job.company.startswith("(über "):
            anfragen += 1
            try:
                data = ba._search({"was": _suchtitel(job.title), "wo": job.location or ba.cfg["wo"],
                                   "umkreis": ba.cfg["umkreis_km"], "size": 25, "page": 1})
                original = next((k for k in bundesagentur.parse_results(data) if passt(job, k)), None)
            except Exception as exc:   # Suche ist ein Zusatz; ohne Treffer bleibt die Alert-Stelle wie sie ist
                log.info("Originalsuche für „%s“ nicht möglich: %s", job.title, exc)
        if original is not None:
            gefunden += 1
            out.append(_uebernehmen(job, original))
        else:
            out.append(job)
    return out, gefunden
