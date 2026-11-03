"""Ist der Master-CV noch aktuell? Findet Angaben, die mit der Zeit veralten – vor allem nach ein paar Monaten
Pause (Ruhemodus):

- „5. Semester“ im Profil oder bei der Ausbildung, obwohl laut Studienbeginn schon ein späteres läuft
  (Wintersemester ab September, Sommersemester ab März; mit Knopf zum Korrigieren)
- „voraussichtlich 02/2028“ als Ende, das schon vorbei ist
- Projekte, die seit über `IN_ARBEIT_MONATE` Monaten „in Arbeit“ sind
- Zertifikate „geplant“ oder „in Arbeit“ mit einem Datum in der Vergangenheit
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import date

SEMESTER = re.compile(r"\b(\d{1,2})\.\s*(Semester|Fachsemester)\b")
MONAT = re.compile(r"\b(0?[1-9]|1[0-2])/(\d{4})\b")
IN_ARBEIT_MONATE = 9


@dataclass
class Veraltet:
    text: str
    fix: str = ""          # "semester": per Knopf korrigierbar


def _monat(text) -> date | None:
    m = MONAT.search(str(text or ""))
    return date(int(m.group(2)), int(m.group(1)), 1) if m else None


def _monate(von: date, heute: date) -> int:
    return (heute.year - von.year) * 12 + heute.month - von.month


def semester_jetzt(cv: dict, heute: date) -> int | None:
    """Laufendes Semester aus dem Beginn der ersten Ausbildung mit Semesterangabe bzw. mit Beginn (MM/JJJJ)."""
    for a in cv.get("ausbildung") or []:
        beginn = _monat(a.get("von")) if isinstance(a, dict) else None
        if beginn and "abitur" not in str(a.get("abschluss", "")).lower() and beginn <= heute:
            return _monate(beginn, heute) // 6 + 1
    return None


def _texte(cv: dict):
    """(Ort, Text) aller Stellen, an denen ein Semester stehen kann."""
    yield "Profil", str(cv.get("profil") or "")
    for a in cv.get("ausbildung") or []:
        for p in (a.get("punkte") or []) if isinstance(a, dict) else []:
            yield "Ausbildung", str(p)


def pruefen(cv: dict, heute: date) -> list[Veraltet]:
    out = []
    jetzt = semester_jetzt(cv, heute)
    if jetzt:
        alt = sorted({int(m.group(1)) for _, t in _texte(cv) for m in SEMESTER.finditer(t)} - {jetzt})
        if alt:
            out.append(Veraltet(f"Im Master-CV steht „{alt[0]}. Semester“, laut Studienbeginn bist du jetzt im "
                                f"{jetzt}. Semester.", "semester"))
    for a in cv.get("ausbildung") or []:
        bis = str(a.get("bis") or "") if isinstance(a, dict) else ""
        ende = _monat(bis)
        if "voraussichtlich" in bis.lower() and ende and ende < date(heute.year, heute.month, 1):
            out.append(Veraltet(f"Ausbildung „{a.get('abschluss')}“: „{bis}“ ist vorbei – Abschluss oder neues "
                                f"voraussichtliches Ende eintragen."))
    for p in cv.get("projekte") or []:
        if not isinstance(p, dict) or p.get("status") != "in_arbeit":
            continue
        beginn = _monat(p.get("zeitraum") or p.get("von"))
        if beginn and _monate(beginn, heute) > IN_ARBEIT_MONATE:
            out.append(Veraltet(f"Projekt „{p.get('name')}“ ist seit über {IN_ARBEIT_MONATE} Monaten „in Arbeit“ – "
                                f"fertig? Dann Status „erreicht“ (zählt im Fit voll)."))
    for z in cv.get("zertifikate") or []:
        if not isinstance(z, dict) or z.get("status") not in ("geplant", "in_arbeit"):
            continue
        datum = _monat(z.get("datum"))
        if datum and datum < date(heute.year, heute.month, 1):
            out.append(Veraltet(f"Zertifikat „{z.get('name')}“ steht noch auf „{z.get('status')}“, das Datum "
                                f"{z.get('datum')} ist vorbei – bestanden? Dann Status „erreicht“."))
    return out


def semester_korrigieren(cv: dict, heute: date) -> dict:
    """Kopie mit dem laufenden Semester an allen Stellen (Profil, Ausbildungspunkte)."""
    jetzt = semester_jetzt(cv, heute)
    cv = copy.deepcopy(cv)
    if not jetzt:
        return cv
    ersetzen = lambda t: SEMESTER.sub(lambda m: f"{jetzt}. {m.group(2)}", t)  # noqa: E731
    if cv.get("profil"):
        cv["profil"] = ersetzen(str(cv["profil"]))
    for a in cv.get("ausbildung") or []:
        if isinstance(a, dict) and a.get("punkte"):
            a["punkte"] = [ersetzen(str(p)) for p in a["punkte"]]
    return cv
