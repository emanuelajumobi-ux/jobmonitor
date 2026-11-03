"""Regelbasierter Filter und Score (0–100) für Stellen."""
from __future__ import annotations

import re
from dataclasses import replace
from functools import lru_cache

from .location import location_points
from . import suchprofil
from .models import Job

_LETTER = "a-z0-9äöüß"
# IT-Bezug im Titel. Fehlt er, müssen mindestens zwei starke Fach-Stichwörter in der Beschreibung stehen,
# sonst rutschen z. B. Chemie-Praktika durch, deren Text zufällig "Sicherheit" oder "Automatisierung" enthält.
IT_TITLE = ["it", "informatik", "software", "data", "daten", "netzwerk", "network", "system",
            "cyber", "tech", "entwickl", "develop", "engineer", "infrastru", "cloud", "ki", "ai"]
STRONG = 8


@lru_cache(maxsize=None)
def _kw_re(keyword: str) -> re.Pattern:
    """Stichwort muss am Wortanfang stehen; kurze Stichwörter (<=4 Zeichen) als ganzes Wort."""
    tail = rf"(?![{_LETTER}])" if len(keyword) <= 4 else ""
    return re.compile(rf"(?<![{_LETTER}]){re.escape(keyword.lower())}{tail}")


def has(text: str, keyword: str) -> bool:
    return bool(_kw_re(keyword).search(text))


def matches(text: str, keywords) -> list[str]:
    text = text.lower()
    return [k for k in keywords if has(text, k)]


def ausschluesse(f: dict, eigen: bool = False, stufe: str = "") -> list[str]:
    """Titel-Ausschlüsse eines Profils: eigene Liste immer, Stufen-Wörter (senior, lead …) außer für berufserfahrene
    Profile, Fach-Wörter (marketing, vertrieb …) nur beim gemeinsamen IT-Fachgebiet."""
    out = list(f.get("ausschluss_titel") or [])
    if stufe != "berufserfahren":
        out += f.get("ausschluss_stufe_titel") or []
    if not eigen:
        out += f.get("ausschluss_fach_titel") or []
    return out


def evaluate(job: Job, cfg: dict, rollen: dict[str, int] | None = None, ausschluss: list[str] = (),
             fach: dict[str, int] | None = None, fach_max: int | None = None, stufe: str = "") -> Job | None:
    """Setzt score/reason und gibt den Job zurück, oder None wenn er rausfällt.
    rollen/ausschluss: Rollen-Stichwörter und zusätzliche Titel-Ausschlüsse eines Suchprofils
    (Standard: erstes Profil in config.yaml). fach: eigenes Fachgebiet des Profils statt filter.fach; dann
    entfallen die IT-spezifischen Prüfungen (IT-Bezug im Titel, reine ISMS-Stelle)."""
    f = cfg["filter"]
    eigen = bool(fach)
    fach = fach if eigen else f["fach"]
    fach_max = fach_max or f["fach_max"]
    rollen = rollen if rollen is not None else suchprofil.alle(cfg)[0].rollen
    title = job.title.lower()
    desc = job.description.lower()
    role_text = f"{title} {job.kind.lower()}"

    if matches(job.company, f["ausschluss_firmen"]):
        return None
    if matches(title, ausschluesse(f, eigen, stufe)) or matches(title, ausschluss):
        return None

    roles = matches(role_text, rollen)
    if not roles:
        return None
    role_pts = max(rollen[r] for r in roles)

    fach_title = matches(title, fach)
    fach_desc = [k for k in matches(desc, fach) if k not in fach_title]
    if not fach_title and not fach_desc:
        return None
    if not fach_title and (eigen or not matches(title, IT_TITLE)):
        if len([k for k in fach_desc if fach[k] >= STRONG]) < 2:
            return None
    if not eigen and matches(title, f["isms_titel"]) and not [k for k in fach_title if fach[k] >= 8]:
        return None  # reine ISMS/Datenschutz-Stelle
    fach_pts = min(fach_max, sum(2 * fach[k] for k in fach_title) + sum(fach[k] for k in fach_desc))

    loc = location_points(job.location, job.remote, cfg["ort"], job.distance_km)
    if loc is None:
        return None
    loc_pts, loc_text = loc

    bonus = 0
    full = f"{title} {desc}"
    if has(full, "bachelorarbeit") or has(full, "abschlussarbeit") or has(full, "thesis"):
        if roles and not any(r in ("bachelorarbeit", "abschlussarbeit", "thesis") for r in roles):
            bonus += f["bonus"]["bachelorarbeit_moeglich"]
            job.flags.append("Abschlussarbeit möglich")
    if re.search(r"übernahme|festanstellung|langfristig", full):
        bonus += f["bonus"]["uebernahme"]
        job.flags.append("Übernahmechance erwähnt")

    job.score = max(0, min(100, role_pts + fach_pts + loc_pts + bonus))
    themen = list(dict.fromkeys(fach_title + fach_desc))[:4]
    job.reason = f"{roles[0].capitalize()} mit Bezug zu {', '.join(themen)}; Ort: {loc_text}."
    return job if job.score >= f["min_score"] else None


def evaluate_profiles(job: Job, cfg: dict, profile: list[suchprofil.Profil]) -> Job | None:
    """Bewertet die Stelle für jedes Profil und behält das mit dem höchsten Score (Gleichstand: erstes Profil).
    Setzt job.profil; gibt None zurück, wenn kein Profil passt."""
    best = None
    for p in profile:
        candidate = evaluate(replace(job, flags=list(job.flags)), cfg, p.rollen, p.ausschluss_titel, p.fach or None,
                             p.fach_max, p.stufe)
        if candidate is not None and (best is None or candidate.score > best.score):
            candidate.profil = p.key
            best = candidate
    return best
