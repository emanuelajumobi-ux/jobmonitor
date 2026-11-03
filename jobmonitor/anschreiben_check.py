"""Anschreiben-Prüfer: Hinweise zu Firma, Stelle, Anrede, Länge und Layout, beim Bauen von Anschreiben und Mappe.

Wie beim Lebenslauf (cv_check.py) wird nur Messbares geprüft, nicht der Stil:
- Firma: kommt der Firmenname im Text vor? Steht dort der Name einer anderen Firma (kopiertes Anschreiben)?
- Stelle: kommt der Stellentitel bzw. sein Kern im Text vor (der Betreff nennt ihn ohnehin)?
- Anrede: Komma am Ende, „Sehr geehrte Frau“ / „Sehr geehrter Herr“, Name nicht leer.
- Länge: Wörter im Text; im PDF mehr als eine Seite. Dazu viele Sätze, die mit „Ich“ beginnen.
- Frist: Bewerbungsfrist abgelaufen.
- Layout: Text über den Rand, fehlende Zeichen (LaTeX-Log, wie beim Lebenslauf).
Platzhalter in [eckigen Klammern] zeigt die Bewerbungsseite schon selbst an.
Grenzwerte: config.yaml → cv.pruefung_anschreiben.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .cv_check import Hinweis
from .models import normalize

DEFAULTS = {"max_woerter": 380, "min_woerter": 120, "max_ich_saetze": 4}
LEGAL = re.compile(r"\b(gmbh|mbh|ag|se|kg|kgaa|co|ohg|ug|e v|ev|gbr|inc|ltd|llc|group|gruppe|holding|"
                   r"deutschland|germany)\b")
GENERIC = {"deutsche", "digital", "services", "service", "consulting", "solutions", "systems", "company", "partner",
           "stadtwerke", "technologies", "international", "it"}
TITLE_NOISE = {"werkstudent", "werkstudentin", "working", "student", "junior", "praktikum", "praktikant", "bachelor",
               "bachelorarbeit", "thesis", "im", "in", "der", "die", "das", "und", "fuer", "für", "bereich", "mit",
               "m", "w", "d"}


def limits(cfg: dict) -> dict:
    return {**DEFAULTS, **((cfg.get("cv") or {}).get("pruefung_anschreiben") or {})}


def _core(company: str) -> str:
    return re.sub(r"\s+", " ", LEGAL.sub(" ", normalize(company))).strip()


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÄÖÜäöüß0-9][\wÄÖÜäöüß-]*", text)


def check_text(data: dict, stelle: dict, cfg: dict, andere_firmen: list[str] | None = None,
               today: date | None = None) -> list[Hinweis]:
    """`data`: anschreiben.json (text, anrede, empfaenger); `stelle`: stelle.json; `andere_firmen`: Firmen der
    übrigen Bewerbungsordner (für kopierte Anschreiben)."""
    lim, out = limits(cfg), []
    text, anrede = data.get("text") or "", (data.get("anrede") or "").strip()
    norm = f" {normalize(text)} "

    core = _core(stelle.get("company") or "")
    markant = [w for w in core.split() if len(w) >= 3 and w not in GENERIC] or core.split()
    if core and not any(f" {w} " in norm for w in markant):
        out.append(Hinweis("warnung", f"Der Firmenname „{stelle['company']}“ kommt im Text nicht vor."))
    for firma in sorted(set(andere_firmen or [])):
        other = _core(firma)
        if other and other not in core and core not in other and f" {other} " in norm:
            out.append(Hinweis("warnung", f"Im Text steht „{firma}“ – Anschreiben aus einer anderen Bewerbung "
                                          "übernommen?"))

    kern = [w for w in normalize(re.sub(r"\(.*?\)", " ", stelle.get("title") or "")).split()
            if len(w) >= 3 and w not in TITLE_NOISE]
    if kern and not any(f" {w} " in norm for w in kern):
        out.append(Hinweis("tipp", "Der Stellentitel kommt im Text nicht vor (nur im Betreff). Ein Bezug zur "
                                   "konkreten Stelle wirkt weniger nach Serienbrief."))

    if not anrede.endswith(","):
        out.append(Hinweis("warnung", f"Die Anrede „{anrede}“ endet nicht mit einem Komma."))
    m = re.match(r"(?i)sehr geehrte(r?)\s+(frau|herr)\b\s*(.*?),?$", anrede)
    if m:
        endung, wer, name = m.group(1), m.group(2).lower(), m.group(3).strip()
        if (wer == "herr") != (endung == "r"):
            richtig = "Sehr geehrter Herr" if wer == "herr" else "Sehr geehrte Frau"
            out.append(Hinweis("warnung", f"Anrede: „{richtig} …“ statt „{anrede}“."))
        if not name:
            out.append(Hinweis("warnung", "In der Anrede fehlt der Name der Ansprechperson."))

    words = len(_words(text))
    if words > lim["max_woerter"]:
        out.append(Hinweis("tipp", f"Der Text hat {words} Wörter; mit bis zu {lim['max_woerter']} passt das "
                                   "Anschreiben sicher auf eine Seite und wird eher ganz gelesen."))
    elif 0 < words < lim["min_woerter"]:
        out.append(Hinweis("tipp", f"Der Text hat nur {words} Wörter; ein konkretes Beispiel aus Projekt oder Job "
                                   "macht ihn überzeugender."))
    saetze = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    ich = sum(1 for s in saetze if re.match(r"(?i)ich\b", s))
    if ich > lim["max_ich_saetze"]:
        out.append(Hinweis("tipp", f"{ich} Sätze beginnen mit „Ich“; ein paar umzustellen liest sich flüssiger."))

    frist = stelle.get("frist")
    if frist and date.fromisoformat(frist) < (today or date.today()):
        out.append(Hinweis("warnung", f"Die Bewerbungsfrist ({date.fromisoformat(frist):%d.%m.%Y}) ist abgelaufen."))
    return out


def check_pdf(pdf: Path) -> list[Hinweis]:
    from pypdf import PdfReader

    pages = len(PdfReader(str(pdf)).pages)
    if pages > 1:
        return [Hinweis("warnung", f"Das Anschreiben hat {pages} Seiten; es sollte auf eine Seite passen.")]
    return []
