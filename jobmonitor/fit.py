"""Fit-Rating: Wie gut passt dein Lebenslauf (cv_master.yaml) zu den Anforderungen einer Stelle?

Regelbasiert: Begriffe aus config.yaml (fit.begriffe, mit Synonymen) werden in Titel und Beschreibung gesucht.
Stehen sie in einem Satz mit "wünschenswert", "von Vorteil" usw., zählen sie halb. Fit = gewichtete
Abdeckung durch belegte Kenntnisse (Level-gewichtet). Score und Sortierung des Berichts bleiben unverändert.

Optional (fit.ki): Die KI liest den Anzeigentext zusätzlich, ordnet anders formulierte Anforderungen den Begriffen zu
(„Erfahrung mit Microsofts Cloud“ → Azure) und unterscheidet Pflicht und Wunsch. Ihr Ergebnis ergänzt die
Stichwortsuche; Anforderungen ohne passenden Begriff landen als Vorschlag im Bericht. Gesendet wird nur die Anzeige.
"""
from __future__ import annotations

import logging
import re
from collections import Counter

from . import llm
from .cv_data import covered_terms
from .models import Job
from .scoring import has

log = logging.getLogger(__name__)
KI_VERSION = 3          # erhöhen, wenn die KI mehr liest – gespeicherte Stellen werden nachbewertet (3: Eckdaten;
                       # 2 griff nicht, weil der Stand erst mit Version 2 zum ersten Mal gespeichert wurde)
KI_DEFAULTS = {"enabled": False, "model": "claude-haiku-5-5", "max_stellen": 30, "min_text": 300,
               "nachholen_je_lauf": 10}
SENTENCE_SPLIT = re.compile(r"[.!?;\n•·]|\s[-–]\s")


def requirements(text: str, begriffe: dict, optional_markers) -> dict[str, float]:
    """Kanonischer Begriff → Gewicht (1 = gefordert, 0.5 = optional)."""
    found: dict[str, float] = {}
    for sentence in SENTENCE_SPLIT.split(text.lower()):
        if not sentence.strip():
            continue
        optional = any(m in sentence for m in optional_markers)
        for term, synonyms in begriffe.items():
            variants = [term.lower()] + [s.lower() for s in synonyms or []]
            if any(has(sentence, v) for v in variants):
                found[term] = max(found.get(term, 0.0), 0.5 if optional else 1.0)
    return found


def rate(job: Job, covered: dict[str, float], cfg: dict) -> None:
    reqs = requirements(f"{job.title}\n{job.description}", cfg["begriffe"], cfg["optional_marker"])
    apply(job, reqs, covered, cfg)


def apply(job: Job, reqs: dict[str, float], covered: dict[str, float], cfg: dict) -> None:
    """Fit aus bereits erkannten Anforderungen (z. B. gespeichert in state/seen.sqlite)."""
    job.fit_anforderungen = reqs
    if len(reqs) < cfg["min_anforderungen"]:
        job.fit = None
        return
    total = sum(reqs.values())
    met = sum(weight * covered[term] for term, weight in reqs.items() if term in covered)
    job.fit = int(100 * met / total + 0.5 + 1e-9)   # kaufmännisch runden, robust gegen 57,4999…
    # Gefordertes zuerst, dann alphabetisch
    order = sorted(reqs, key=lambda t: (-reqs[t], t.lower()))
    job.fit_passt = [t for t in order if t in covered]
    job.fit_fehlt = [t for t in order if t not in covered]


def rate_all(jobs: list[Job], cv: dict, cfg: dict) -> None:
    covered = covered_terms(cv, cfg["begriffe"])
    for job in jobs:
        rate(job, covered, cfg)


def ki_system(begriffe: dict) -> str:
    """Gleichbleibender Teil (Anweisungen und Begriffsliste) – wird je Lauf zwischengespeichert."""
    liste = "\n".join(f"- {b}" + (f" (auch: {', '.join(s)})" if s else "") for b, s in begriffe.items())
    return (
        "Lies die Stellenanzeige und liste die fachlichen Anforderungen an Bewerber (Kenntnisse, Werkzeuge, "
        "Zertifikate, Sprachen). Keine Soft Skills, kein Studium oder Abschluss, keine Aufgabenbeschreibungen ohne "
        "Kenntnis dahinter.\n\n"
        "Lies außerdem die Eckdaten der Stelle, sofern die Anzeige sie nennt.\n\n"
        "Antworte nur mit JSON in dieser Form:\n"
        '{"anforderungen": [{"begriff": "Azure", "bekannt": true, "pflicht": true}], '
        '"eckdaten": {"stunden": "20 h/Woche", "verguetung": "16 €/h", "remote": "2 Tage/Woche", '
        '"start": "ab sofort", "abschlussarbeit": true}}\n'
        "- begriff: bei bekannt=true genau der Name aus der Liste unten (auch wenn die Anzeige es anders formuliert), "
        "sonst ein kurzer Name (1 bis 3 Wörter).\n"
        "- pflicht: false, wenn die Anzeige es nur wünscht (von Vorteil, idealerweise, nice to have …).\n"
        "- eckdaten: kurz (höchstens 25 Zeichen je Wert), nur was ausdrücklich in der Anzeige steht, sonst null. "
        "abschlussarbeit: true nur, wenn eine Bachelor- oder Masterarbeit ausdrücklich möglich ist.\n\n"
        f"BEKANNTE BEGRIFFE:\n{liste}")


def ki_prompt(job: Job) -> str:
    return f"ANZEIGE: {job.title} bei {job.company}\n{job.description[:6000]}"


ECKDATEN = ("stunden", "verguetung", "remote", "start")


def eckdaten(roh) -> dict:
    """Eckdaten aus der KI-Antwort säubern: nur kurze Texte, abschlussarbeit nur als True."""
    out = {k: str(roh[k]).strip()[:30] for k in ECKDATEN
           if isinstance(roh, dict) and roh.get(k) not in (None, "", "null") and str(roh[k]).strip()}
    if isinstance(roh, dict) and roh.get("abschlussarbeit") is True:
        out["abschlussarbeit"] = True
    return out


def eckdaten_text(e: dict) -> list[str]:
    """Für Anzeige und Bericht, z. B. ["20 h/Woche", "16 €/h", "Remote: 2 Tage/Woche", "Abschlussarbeit möglich"]."""
    teile = [e[k] for k in ("stunden", "verguetung") if e.get(k)]
    teile += [f"Remote: {e['remote']}"] if e.get("remote") else []
    teile += [f"Start: {e['start']}"] if e.get("start") else []
    return teile + (["Abschlussarbeit möglich"] if e.get("abschlussarbeit") else [])


STUNDEN = re.compile(r"(\d{1,2})(?:[,.]\d)?\s*(?:[-–]\s*\d{1,2}\s*)?(?:h\b|std|stunden|wochenstunden)", re.I)
KEIN_REMOTE = re.compile(r"\b(?:kein|keine|nein|nicht|vor ort|präsenz)\b", re.I)


def eckdaten_filter(e: dict) -> dict[str, str]:
    """Werte für den Eckdaten-Filter der Stellenliste: h = kleinste genannte Wochenstundenzahl, r = Remote (1/0),
    t = Abschlussarbeit (1). Leer heißt „steht nicht in der Anzeige“ – solche Stellen bleiben beim Filtern sichtbar."""
    m = STUNDEN.search(str(e.get("stunden") or ""))
    remote = str(e.get("remote") or "")
    return {"h": m.group(1) if m else "", "r": ("0" if KEIN_REMOTE.search(remote) else "1") if remote else "",
            "t": "1" if e.get("abschlussarbeit") else ""}


def ki_anforderungen(job: Job, begriffe: dict, model: str, ask=None) -> tuple[dict[str, float], list[str], dict] | None:
    """(bekannte Begriffe → Gewicht, weitere Anforderungen ohne Begriff, Eckdaten) oder None, wenn die KI nicht
    antwortet."""
    # Großzügiges Budget: Haiku denkt vor der Antwort (adaptive thinking), das zählt mit
    antwort = (ask or llm._ask)(model, ki_prompt(job), effort="low", max_tokens=8000, system=ki_system(begriffe))
    data = llm.json_aus(antwort)
    if not isinstance(data, dict) or not isinstance(data.get("anforderungen"), list):
        log.info("KI-Anforderungen für „%s“ nicht lesbar (%s)", job.title[:60],
                 "keine Antwort" if not antwort else f"{len(antwort)} Zeichen ohne gültiges JSON")
        return None
    namen = {b.lower(): b for b in begriffe}
    bekannt: dict[str, float] = {}
    weitere: list[str] = []
    for a in data["anforderungen"]:
        if not isinstance(a, dict) or not str(a.get("begriff") or "").strip():
            continue
        name, gewicht = str(a["begriff"]).strip(), 1.0 if a.get("pflicht", True) is not False else 0.5
        if name.lower() in namen:
            b = namen[name.lower()]
            bekannt[b] = max(bekannt.get(b, 0.0), gewicht)
        elif len(name) <= 40 and name not in weitere:
            weitere.append(name)
    return bekannt, weitere, eckdaten(data.get("eckdaten"))


def mit_ki(jobs: list[Job], cv: dict, cfg: dict, ask=None, gelesen: set | None = None) -> Counter:
    """Fit der Stellen mit KI-Anforderungen neu berechnen (nach rate_all). Gibt die Anforderungen ohne Begriff
    (über alle Stellen gezählt) zurück – Kandidaten für fit.begriffe. `gelesen` bekommt die IDs der Stellen, die die
    KI wirklich gelesen hat; die übrigen holt nachbewertung.nachbewerten in einem späteren Lauf nach."""
    k = {**KI_DEFAULTS, **(cfg.get("ki") or {})}
    vorschlaege: Counter = Counter()
    if not k["enabled"] or (ask is None and not llm.verfuegbar()):
        return vorschlaege
    covered = covered_terms(cv, cfg["begriffe"])
    geprueft = 0
    for job in jobs:
        if geprueft >= k["max_stellen"] or len(job.description) < k["min_text"]:
            continue
        geprueft += 1
        ergebnis = ki_anforderungen(job, cfg["begriffe"], k["model"], ask)
        if ergebnis is None:
            continue
        bekannt, weitere, job.eckdaten = ergebnis
        # Stichwortsuche + KI: Die KI entscheidet bei gemeinsamen Begriffen über Pflicht/Wunsch, findet weitere dazu
        apply(job, {**job.fit_anforderungen, **bekannt}, covered, cfg)
        vorschlaege.update(weitere)
        if gelesen is not None:
            gelesen.add(job.short_id)
    if geprueft:
        log.info("KI-Anforderungen für %d Stelle(n) gelesen", geprueft)
    return vorschlaege
