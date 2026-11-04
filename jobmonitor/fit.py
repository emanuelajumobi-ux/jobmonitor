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
KI_VERSION = 4          # erhöhen, wenn die KI mehr liest – gespeicherte Stellen werden nachbewertet (3: Eckdaten;
                       # 2 griff nicht, weil der Stand erst mit Version 2 zum ersten Mal gespeichert wurde)
KI_DEFAULTS = {"enabled": False, "model": "claude-haiku-5-5", "max_stellen": 30, "min_text": 300,
               "nachholen_je_lauf": 10, "stapel": True}   # stapel: Nachbewerten per Batch-Schnittstelle (halber Preis)
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
    reqs = {t: g for t, g in reqs.items() if t not in ALT}
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
        "Programmiersprachen, Zertifikate, Sprachen, Fachgebiete). Keine Soft Skills (Teamfähigkeit, Eigeninitiative …), "
        "kein Studium oder Abschluss, keine Aufgaben ohne Kenntnis dahinter, nichts Allgemeines wie „Dokumentation“ "
        "oder „Richtlinien einhalten“. Je Anforderung ein kurzer, üblicher Name (z. B. „Java“, „SAP S/4HANA“, "
        "„Buchhaltung“), höchstens 8 außerhalb der bekannten Begriffe.\n\n"
        "Lies außerdem die Eckdaten der Stelle, sofern die Anzeige sie nennt.\n\n"
        "Antworte nur mit JSON in dieser Form:\n"
        '{"anforderungen": [{"begriff": "Azure", "bekannt": true, "pflicht": true}], '
        '"eckdaten": {"stunden": "20 h/Woche", "verguetung": "16 €/h", "remote": "2 Tage/Woche", '
        '"start": "ab sofort", "abschlussarbeit": true}, "hinweise": ["verlangt 2 Jahre Berufserfahrung"]}\n'
        "- begriff: bei bekannt=true genau der Name aus der Liste unten (auch wenn die Anzeige es anders formuliert), "
        "sonst ein kurzer Name (1 bis 3 Wörter).\n"
        "- pflicht: false, wenn die Anzeige es nur wünscht (von Vorteil, idealerweise, nice to have …).\n"
        "- eckdaten: kurz (höchstens 25 Zeichen je Wert), nur was ausdrücklich in der Anzeige steht, sonst null. "
        "abschlussarbeit: true nur, wenn eine Bachelor- oder Masterarbeit ausdrücklich möglich ist.\n"
        "- hinweise: höchstens 2 kurze Warnungen (je höchstens 60 Zeichen), wenn die Stelle nicht hält, was der Titel "
        "verspricht – z. B. Berufserfahrung trotz Werkstudenten- oder Junior-Titel, nur Pflichtpraktikum, befristet auf "
        "wenige Monate, sehr hohe oder unrealistische Anforderungen, unbezahlt. Sonst leere Liste.\n\n"
        f"BEKANNTE BEGRIFFE:\n{liste}")


def ki_prompt(job: Job) -> str:
    return f"ANZEIGE: {job.title} bei {job.company}\n{job.description[:6000]}"


ECKDATEN = ("stunden", "verguetung", "remote", "start")


def eckdaten(roh, hinweise=None) -> dict:
    """Eckdaten aus der KI-Antwort säubern: nur kurze Texte, abschlussarbeit nur als True; dazu höchstens 2 Hinweise
    („Passt das wirklich?“, z. B. „verlangt Berufserfahrung“)."""
    out = {k: str(roh[k]).strip()[:30] for k in ECKDATEN
           if isinstance(roh, dict) and roh.get(k) not in (None, "", "null") and str(roh[k]).strip()}
    if isinstance(roh, dict) and roh.get("abschlussarbeit") is True:
        out["abschlussarbeit"] = True
    hin = [str(h).strip()[:80] for h in (hinweise if isinstance(hinweise, list) else []) if str(h).strip()][:2]
    if hin:
        out["hinweise"] = hin
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
    """Werte für die Eckdaten-Filter der Stellenliste: h = kleinste genannte Wochenstundenzahl, r = Remote (1/0),
    t = Abschlussarbeit (1), v = Vergütung bzw. Gehalt genannt (1), vz = Vollzeit (1/0), tz = Teilzeit möglich (1/0).
    Leer heißt „steht nicht in der Anzeige“ – solche Stellen bleiben bei Stunden, Remote, Voll- und Teilzeit
    sichtbar."""
    text = str(e.get("stunden") or "")
    m = STUNDEN.search(text)
    remote = str(e.get("remote") or "")
    h = int(m.group(1)) if m else None
    voll = "1" if re.search(r"vollzeit", text, re.I) or (h is not None and h >= 35) else ("0" if h is not None else "")
    teil = ("1" if re.search(r"teilzeit", text, re.I) or (h is not None and h < 35) else
            ("0" if voll == "1" and not re.search(r"teilzeit", text, re.I) else ""))
    return {"h": str(h) if h is not None else "", "r": ("0" if KEIN_REMOTE.search(remote) else "1") if remote else "",
            "t": "1" if e.get("abschlussarbeit") else "", "v": "1" if e.get("verguetung") else "",
            "vz": voll, "tz": teil}


def ki_anforderungen(job: Job, begriffe: dict, model: str, ask=None) -> tuple[dict[str, float], dict[str, float], dict] | None:
    """(bekannte Begriffe → Gewicht, weitere Anforderungen ohne Begriff → Gewicht, Eckdaten) oder None, wenn die KI
    nicht antwortet."""
    # Großzügiges Budget: Haiku denkt vor der Antwort (adaptive thinking), das zählt mit
    antwort = (ask or llm._ask)(model, ki_prompt(job), effort="low", max_tokens=8000, system=ki_system(begriffe))
    return ki_auswerten(antwort, begriffe, job.title)


def ki_auswerten(antwort: str | None, begriffe: dict, titel: str = "") -> tuple[dict, dict, dict] | None:
    """KI-Antwort (JSON) → (bekannte Begriffe, weitere Anforderungen, Eckdaten) – auch für Ergebnisse aus einem
    KI-Stapel (ki_batch.py)."""
    data = llm.json_aus(antwort)
    if not isinstance(data, dict) or not isinstance(data.get("anforderungen"), list):
        log.info("KI-Anforderungen für „%s“ nicht lesbar (%s)", titel[:60],
                 "keine Antwort" if not antwort else f"{len(antwort)} Zeichen ohne gültiges JSON")
        return None
    namen = {b.lower(): b for b in begriffe}
    bekannt: dict[str, float] = {}
    weitere: dict[str, float] = {}
    for a in data["anforderungen"]:
        if not isinstance(a, dict) or not str(a.get("begriff") or "").strip():
            continue
        name, gewicht = str(a["begriff"]).strip(), 1.0 if a.get("pflicht", True) is not False else 0.5
        if name.lower() in namen:
            b = namen[name.lower()]
            bekannt[b] = max(bekannt.get(b, 0.0), gewicht)
        elif len(name) <= 40 and len(weitere) < MAX_WEITERE:
            weitere[name] = max(weitere.get(name, 0.0), gewicht)
    return bekannt, weitere, eckdaten(data.get("eckdaten"), data.get("hinweise"))


MAX_WEITERE = 8      # Anforderungen außerhalb der Fit-Begriffe je Stelle (z. B. Java, React, SAP)
# Frühere Fit-Begriffe, die zu viel Falsches fanden („Richtlinien“ über „Dokumentation“); in gespeicherten Stellen
# zählen sie nicht mehr
ALT = {"Richtlinien", "Awareness"}


def ki_zusammenfuehren(regel: dict[str, float], bekannt: dict[str, float], weitere: dict[str, float]) -> dict:
    """Anforderungen aus Stichwortsuche und KI: Hat die KI die Anzeige gelesen, entscheidet sie – Stichwort-Treffer, die
    sie nicht nennt, fallen weg (z. B. „Hardware“, weil „Clients“ im Text steht). Dazu kommen Anforderungen, für die
    es keinen Fit-Begriff gibt; sie werden direkt gegen den Lebenslauf geprüft (cv_data.Abdeckung)."""
    if not bekannt and not weitere:
        return dict(regel)
    return {**bekannt, **{n: g for n, g in weitere.items() if n not in bekannt}}


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
        apply(job, ki_zusammenfuehren(job.fit_anforderungen, bekannt, weitere), covered, cfg)
        vorschlaege.update(list(weitere))
        if gelesen is not None:
            gelesen.add(job.short_id)
    if geprueft:
        log.info("KI-Anforderungen für %d Stelle(n) gelesen", geprueft)
    return vorschlaege
