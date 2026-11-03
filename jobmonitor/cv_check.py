"""Lebenslauf-Prüfer: Hinweise zu Länge, Formatierung und Inhalt, nach jedem `make cv` und in der Oberfläche.

Geprüft wird nur Messbares, der Schreibstil nicht:
- Länge: Seitenzahl und wie voll die letzte Seite ist (aus dem PDF).
- Formatierung: Text über den Rand, fehlende Zeichen, fehlende Dateien (aus dem LaTeX-Log).
- Inhalt: lange oder viele Stichpunkte, Datumsformate, leere Abschnitte, doppelte Kenntnisse (cv_master.yaml).
- Zuschnitt: geforderte Begriffe, die du hast, die durch das Kürzen aber nicht im PDF stehen.
Grenzwerte: config.yaml → cv.pruefung.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .cv_data import _entries, covered_terms

DEFAULTS = {"max_seiten": 2, "min_zeilen_letzte_seite": 8, "max_zeichen_stichpunkt": 170,
            "max_stichpunkte": 5, "max_zeichen_profil": 450, "max_zeichen_projekt": 320, "overfull_pt": 2.0}
DATE_TOKEN = re.compile(r"\b(?:\d{1,2}[./-])?\d{2,4}(?:[./-]\d{1,2})?\b|\b(?:jan|feb|mär|mar|apr|mai|may|jun|jul|aug|"
                        r"sep|okt|oct|nov|dez|dec)[a-zä]*\.?\s+\d{2,4}\b", re.IGNORECASE)
GOOD_DATE = re.compile(r"^(?:\d{2}/\d{4}|\d{4})$")
OVERFULL = re.compile(r"^Overfull \\hbox \(([\d.]+)pt too wide\) (?:in paragraph|detected) at lines? (\d+)",
                      re.MULTILINE)
MISSING_CHAR = re.compile(r"Missing character: There is no (.+?) in font", re.IGNORECASE)
MISSING_FILE = re.compile(r"(?:LaTeX Warning: File|File) `([^']+)' not found")


@dataclass
class Hinweis:
    stufe: str    # "warnung" (sollte behoben werden) oder "tipp"
    text: str

    def __str__(self) -> str:
        return f"{'Warnung' if self.stufe == 'warnung' else 'Tipp'}: {self.text}"


def limits(cfg: dict) -> dict:
    return {**DEFAULTS, **((cfg.get("cv") or {}).get("pruefung") or {})}


def _short(text: str, n: int = 50) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + "…"


# --- Inhalt (cv_master.yaml bzw. zugeschnittene Fassung) ---
def check_content(cv: dict, cfg: dict) -> list[Hinweis]:
    lim, out = limits(cfg), []
    for key, label in (("stationen", "Berufserfahrung"), ("ausbildung", "Ausbildung"), ("kenntnisse", "Kenntnisse")):
        if not _entries(cv.get(key)):
            out.append(Hinweis("warnung", f"Abschnitt „{label}“ ist leer."))

    profil = str(cv.get("profil") or "")
    if len(profil) > lim["max_zeichen_profil"]:
        out.append(Hinweis("tipp", f"Profiltext hat {len(profil)} Zeichen; unter {lim['max_zeichen_profil']} "
                                   "liest er sich schneller."))

    bullets = []   # (wo, text, Grenze)
    for s in _entries(cv.get("stationen")):
        wo = s.get("rolle") or s.get("organisation") or "Station"
        aufgaben = [a for a in s.get("aufgaben") or [] if a]
        if not aufgaben:
            out.append(Hinweis("tipp", f"„{_short(wo)}“ hat keine Aufgaben-Stichpunkte."))
        elif len(aufgaben) > lim["max_stichpunkte"]:
            out.append(Hinweis("tipp", f"„{_short(wo)}“ hat {len(aufgaben)} Stichpunkte; "
                                       f"die stärksten {lim['max_stichpunkte']} reichen meist."))
        bullets += [(wo, a, lim["max_zeichen_stichpunkt"]) for a in aufgaben]
    for e in _entries(cv.get("ausbildung")):
        bullets += [(e.get("abschluss") or "Ausbildung", p, lim["max_zeichen_stichpunkt"])
                    for p in e.get("punkte") or [] if p]
    for p in _entries(cv.get("projekte")):   # Projektbeschreibungen sind Absätze, dürfen länger sein
        if p.get("im_cv") is not False and p.get("beschreibung"):
            bullets.append((p.get("name") or "Projekt", p["beschreibung"], lim["max_zeichen_projekt"]))
    for wo, text, grenze in bullets:
        if len(str(text)) > grenze:
            out.append(Hinweis("tipp", f"Langer Text bei „{_short(wo, 40)}“ ({len(str(text))} Zeichen, "
                                       f"über {grenze}): „{_short(text)}“"))

    seen, doppelt = {}, []
    for k in _entries(cv.get("kenntnisse")):
        for e in _entries(k.get("eintraege")) if "eintraege" in k else [k]:
            name = str(e.get("name") or "").strip()
            if name.lower() in seen and name.lower() not in doppelt:
                doppelt.append(name.lower())
            seen.setdefault(name.lower(), name)
    if doppelt:
        out.append(Hinweis("tipp", "Doppelt unter Kenntnisse: " + ", ".join(seen[d] for d in doppelt)))

    odd = sorted({tok for value in _dates(cv) for tok in _date_tokens(value) if not GOOD_DATE.match(tok)})
    if odd:
        out.append(Hinweis("warnung", "Uneinheitliche Datumsangaben (sonst MM/JJJJ): " + ", ".join(odd[:5])))
    return out


def _dates(cv: dict) -> list[str]:
    values = []
    for key, fields in (("stationen", ("von", "bis")), ("ausbildung", ("von", "bis")),
                        ("zertifikate", ("datum",)), ("projekte", ("zeitraum",))):
        for item in _entries(cv.get(key)):
            values += [str(item[f]) for f in fields if item.get(f)]
    return values


def _date_tokens(value: str) -> list[str]:
    return [m.group().strip() for m in DATE_TOKEN.finditer(value)]


# --- Formatierung (LaTeX-Log) ---
def check_log(log_text: str, cfg: dict) -> list[Hinweis]:
    lim, out = limits(cfg), []
    overfull = [(float(pt), line) for pt, line in OVERFULL.findall(log_text) if float(pt) > lim["overfull_pt"]]
    if overfull:
        worst = max(pt for pt, _ in overfull)
        out.append(Hinweis("warnung", f"{len(overfull)} Stelle(n) ragen über den Rand (bis {worst:.0f} pt), "
                                      "oft lange URLs oder Begriffe ohne Trennstelle."))
    chars = sorted(set(MISSING_CHAR.findall(log_text)))
    if chars:
        out.append(Hinweis("warnung", f"Zeichen fehlen in der Schrift und erscheinen nicht im PDF: {', '.join(chars)}"))
    files = sorted(set(MISSING_FILE.findall(log_text)))
    if files:
        out.append(Hinweis("warnung", f"Datei nicht gefunden: {', '.join(files)}"))
    return out


# --- Länge (PDF) ---
def check_pdf(pdf: Path, cfg: dict) -> list[Hinweis]:
    from pypdf import PdfReader

    lim, out = limits(cfg), []
    pages = PdfReader(str(pdf)).pages
    if len(pages) > lim["max_seiten"]:
        out.append(Hinweis("warnung", f"Der Lebenslauf hat {len(pages)} Seiten; für Werkstudenten- und "
                                      f"Junior-Stellen sind höchstens {lim['max_seiten']} üblich."))
    if len(pages) > 1:
        lines = [ln for ln in (pages[-1].extract_text() or "").splitlines() if ln.strip()]
        if len(lines) < lim["min_zeilen_letzte_seite"]:
            out.append(Hinweis("tipp", f"Die letzte Seite hat nur {len(lines)} Zeile(n); etwas Kürzen spart "
                                       "eine ganze Seite."))
    return out


# --- Zuschnitt auf eine Stelle ---
def check_tailoring(full_cv: dict, tailored_cv: dict, anforderungen: dict, begriffe: dict) -> list[Hinweis]:
    visible = {**full_cv, "projekte": [p for p in _entries(full_cv.get("projekte")) if p.get("im_cv") is not False]}
    lost = sorted((set(covered_terms(visible, begriffe)) & set(anforderungen))
                  - set(covered_terms(tailored_cv, begriffe)))
    if not lost:
        return []
    return [Hinweis("tipp", "Gefordert und in deinem Master-CV, aber nach dem Kürzen nicht im PDF: "
                            + ", ".join(lost) + " (cv.max_projekte_zugeschnitten erhöhen oder Projekt umsortieren).")]
