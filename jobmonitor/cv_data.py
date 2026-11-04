"""cv_master.yaml laden (nicht-persönliche Lebenslauf-Daten) und vor persönlichen Daten schützen.

Quelle: Umgebungsvariable CV_MASTER_YAML (YAML-Text, z. B. GitHub Secret) hat Vorrang, sonst die Datei
cv_master.yaml in der Repo-Wurzel oder in cv/. Persönliche Kontaktdaten gehören nur in profile.yaml.
"""
from __future__ import annotations

import io
import os
import re
from pathlib import Path

from ruamel.yaml import YAML

from .scoring import has

FORBIDDEN_KEYS = {"adresse", "anschrift", "strasse", "straße", "plz", "telefon", "tel", "mobil", "handy", "email",
                  "e-mail", "mail", "geburtsdatum", "geburtsort", "geboren", "foto", "bild", "photo"}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+49|0049|\b0)\s?\d{2,5}[\s/()-]*\d[\d\s/()-]{4,}")
LEVELS = {"grundkenntnisse": 0.6, "basis": 0.6, "gut": 0.85, "fortgeschritten": 0.85, "sehr gut": 1.0,
          "experte": 1.0}
DEFAULT_LEVEL = 0.85
# Sprachniveau (niveau) → Gewicht; bei "B2/C1" zählt die erste Angabe
CEFR = {"a1": 0.3, "a2": 0.45, "b1": 0.6, "b2": 0.85, "c1": 1.0, "c2": 1.0, "muttersprache": 1.0,
        "verhandlungssicher": 1.0, "fließend": 1.0}


class CvDataError(Exception):
    """cv_master.yaml ist ungültig oder enthält vermutlich persönliche Daten (Meldung ohne die Werte)."""


def find_cv_master(root: Path) -> Path | None:
    for path in (root / "cv_master.yaml", root / "cv" / "cv_master.yaml"):
        if path.exists():
            return path
    return None


def load_cv_master(root: Path) -> tuple[dict | None, str]:
    """(Daten, Herkunft). Daten ist None, wenn weder Secret noch Datei vorhanden sind."""
    text = os.environ.get("CV_MASTER_YAML") or ""
    origin = "Secret CV_MASTER_YAML"
    if not text.strip():
        path = find_cv_master(root)
        if path is None:
            return None, "keine cv_master.yaml"
        text = path.read_text(encoding="utf-8")
        origin = str(path.relative_to(root))
    try:
        data = YAML(typ="safe").load(io.StringIO(text)) or {}
    except Exception as exc:
        raise CvDataError(f"{origin} ist kein gültiges YAML ({type(exc).__name__})") from None
    if not isinstance(data, dict):
        raise CvDataError(f"{origin} muss eine YAML-Zuordnung sein")
    check_no_personal_data(data, origin)
    return data, origin


def check_no_personal_data(data, origin: str = "cv_master.yaml") -> None:
    """Bricht ab, wenn Schlüssel oder Werte nach persönlichen Kontaktdaten aussehen. Nennt nie den Wert."""
    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).strip().lower() in FORBIDDEN_KEYS:
                    raise CvDataError(f"{origin}: Schlüssel '{key}' gehört in profile.yaml, nicht hierher")
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")
        elif isinstance(node, str):
            if EMAIL_RE.search(node):
                raise CvDataError(f"{origin}: E-Mail-Adresse in '{path}' gefunden – gehört in profile.yaml")
            if PHONE_RE.search(node):
                raise CvDataError(f"{origin}: Telefonnummer in '{path}' gefunden – gehört in profile.yaml")
    walk(data, "")


def _entries(value) -> list[dict]:
    """Listen aus Strings oder Dicts einheitlich als Dicts mit 'name'."""
    out = []
    for item in value or []:
        out.append({"name": item} if isinstance(item, str) else dict(item))
    return out


def kenntnisse(cv: dict) -> list[dict]:
    """Alle Kenntnisse flach. Kategorien (kategorie + eintraege) werden aufgelöst, flache Listen gehen auch."""
    out = []
    for entry in _entries(cv.get("kenntnisse")):
        out.extend(_entries(entry["eintraege"]) if "eintraege" in entry else [entry])
    return out


def counts(entry: dict) -> bool:
    """Einträge mit status: geplant zählen nicht als Kenntnis."""
    return str(entry.get("status") or "").strip().lower() != "geplant"


def level_weight(level) -> float:
    return LEVELS.get(str(level or "").strip().lower(), DEFAULT_LEVEL)


def language_weight(entry: dict) -> float:
    niveau = str(entry.get("niveau") or "").strip().lower()
    first = re.split(r"[/\s,]+", niveau)[0] if niveau else ""
    return CEFR.get(first, CEFR.get(niveau, level_weight(entry.get("level"))))


def cv_texts(cv: dict) -> list[tuple[str, float, bool]]:
    """(Text, Gewicht, explizit) aller Stellen im Lebenslauf, an denen Kenntnisse belegt sind.

    Explizit = Kenntnisse/Sprachen mit deinem eigenen Level. Zertifikate, Projekte und Stationen belegen
    einen Begriff nur, wenn er dort nicht schon mit Level steht (dein Level hat Vorrang). Einträge mit
    status: geplant zählen nicht, sonst wird der Fit zu gut. Die Ausbildung (Abschluss, Punkte) belegt einen
    Begriff mit Grundkenntnissen.
    """
    out = []
    for k in kenntnisse(cv):
        out.append((" ".join([str(k.get("name", ""))] + [str(s) for s in k.get("synonyme") or []]),
                    level_weight(k.get("level")), True))
    for s in _entries(cv.get("sprachen")):
        out.append((str(s.get("sprache") or s.get("name") or ""), language_weight(s), True))
    for z in _entries(cv.get("zertifikate")):
        if counts(z):
            out.append((f"{z.get('name', '')} {z.get('zusatz') or ''}", DEFAULT_LEVEL, False))
    for a in _entries(cv.get("ausbildung")):   # Studium belegt Grundlagen (schwächer als Praxis)
        belege = [str(a.get("abschluss") or "")] + [str(p) for p in a.get("punkte") or []]
        out.append((" | ".join(belege), LEVELS["grundkenntnisse"], False))
    for block in ("projekte", "stationen"):
        for p in _entries(cv.get(block)):
            if not counts(p):
                continue
            belege = [str(t) for t in p.get("technologien") or []] + [str(t) for t in p.get("aufgaben") or []]
            belege.append(str(p.get("beschreibung") or ""))
            out.append((" | ".join(belege), DEFAULT_LEVEL, False))
    return [entry for entry in out if entry[0].strip()]


def _gewicht(texts: list, variants: list[str]) -> float | None:
    hits = [(w, explicit) for text, w, explicit in texts if any(has(text, v) for v in variants)]
    explicit = [w for w, e in hits if e]
    if explicit:
        return max(explicit)
    return max(w for w, _ in hits) if hits else None


class Abdeckung(dict):
    """Begriff → belegtes Kenntnis-Gewicht. Verhält sich wie ein dict der Fit-Begriffe, prüft aber auch Begriffe
    außerhalb der Liste bei Bedarf gegen den Lebenslauf (z. B. „Java“, das die KI in einer Anzeige fand) – so zählen
    alle Anforderungen, nicht nur die vorher festgelegten."""

    def __init__(self, texts: list, begriffe: dict):
        super().__init__()
        self._texts, self._begriffe, self._geprueft = texts, begriffe, set()
        for term, synonyms in begriffe.items():
            w = _gewicht(texts, [term.lower()] + [s.lower() for s in synonyms or []])
            if w is not None:
                self[term] = w
        self._geprueft.update(begriffe)

    def _pruefen(self, term) -> None:
        if not isinstance(term, str) or term in self._geprueft:
            return
        self._geprueft.add(term)
        w = _gewicht(self._texts, [term.lower()]) if term.strip() else None
        if w is not None:
            dict.__setitem__(self, term, w)

    def __contains__(self, term) -> bool:
        self._pruefen(term)
        return dict.__contains__(self, term)

    def __getitem__(self, term):
        self._pruefen(term)
        return dict.__getitem__(self, term)

    def get(self, term, default=None):
        self._pruefen(term)
        return dict.get(self, term, default)


def covered_terms(cv: dict, begriffe: dict) -> Abdeckung:
    """Kanonischer Begriff → belegtes Kenntnis-Gewicht (0–1); weitere Begriffe auf Nachfrage (Abdeckung)."""
    return Abdeckung([(t.lower(), w, explicit) for t, w, explicit in cv_texts(cv)], begriffe)
