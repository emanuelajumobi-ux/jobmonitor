"""Suchprofile (z. B. Werkstudent und Junior) aus config.yaml.

Jedes Profil bringt eigene Rollen-Stichwörter, Suchbegriffe für die Quellen und die Zielrolle für Anschreiben mit.
Fach-Stichwörter gelten gemeinsam (filter.fach), außer ein Profil hat ein eigenes Fachgebiet (`fach`). Zusätzliche
Fit-Begriffe eines Profils (`fit_begriffe`) ergänzen fit.begriffe (siehe config.load_config). Ausschlüsse, Ort und
Traumprofil gelten für alle Profile.

Damit die Quellen sparsam abgefragt werden: höchstens MAX_AKTIV aktive Profile und MAX_BEGRIFFE Suchbegriffe je
Quelle und Profil (geprüft beim Speichern in der App und beim Laden in der Pipeline).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_KEY = "werkstudent"
MAX_AKTIV = 4
MAX_BEGRIFFE = 15
# Vorlagen je Karrierestufe für neue Suchprofile: Rollen-Wörter im Titel und Stellenart der Bundesagentur
# (34 = Praktikum/Trainee/Werkstudent, 4 = Ausbildung, 1 = Arbeit). Gilt für jedes Fachgebiet.
STUFEN: dict[str, dict] = {
    "ausbildung": {"name": "Ausbildung / duales Studium", "art": "ausbildung",
                   "rollen": {"ausbildung": 30, "azubi": 28, "auszubildende": 28, "duales studium": 28,
                              "dualer student": 26, "duale studentin": 26}},
    "praktikum": {"name": "Praktikum", "art": "studium",
                  "rollen": {"praktikum": 30, "praktikant": 28, "praktikantin": 28, "pflichtpraktikum": 28,
                             "praxissemester": 26, "praxisphase": 24, "internship": 26, "intern": 22}},
    "werkstudent": {"name": "Werkstudent / Nebenjob im Studium", "art": "studium",
                    "rollen": {"werkstudent": 30, "werkstudentin": 30, "working student": 30,
                               "studentische hilfskraft": 22, "studentische aushilfe": 20}},
    "abschlussarbeit": {"name": "Abschlussarbeit", "art": "studium",
                        "rollen": {"bachelorarbeit": 32, "masterarbeit": 32, "abschlussarbeit": 32, "thesis": 30}},
    "einstieg": {"name": "Berufseinstieg / Junior", "art": "arbeit",
                 "rollen": {"junior": 30, "berufseinsteiger": 30, "berufseinstieg": 28, "trainee": 28,
                            "graduate": 26, "absolvent": 26, "entry level": 28}},
    "minijob": {"name": "Minijob / Aushilfe", "art": "minijob",
                "rollen": {"minijob": 30, "aushilfe": 28, "aushilfskraft": 28, "geringfügig": 26,
                           "geringfügige beschäftigung": 26, "nebenjob": 24, "mini-job": 28}},
    "berufserfahren": {"name": "Berufserfahren", "art": "arbeit",
                       "rollen": {"referent": 22, "referentin": 22, "spezialist": 22, "specialist": 22,
                                  "sachbearbeiter": 20, "berater": 20, "beraterin": 20, "consultant": 20,
                                  "manager": 20, "engineer": 20, "ingenieur": 22, "fachkraft": 20,
                                  "senior": 24, "lead": 22}},
}


def stufe_von(p) -> str:
    """Karrierestufe eines Profils; ältere Profile ohne Angabe nach ihrem Namen (werkstudent, junior …)."""
    if p.stufe in STUFEN:
        return p.stufe
    key = f"{p.key} {p.name}".lower()
    if "junior" in key or "einstieg" in key or "trainee" in key:
        return "einstieg"
    return next((s for s in STUFEN if s in key), "")


@dataclass
class Profil:
    key: str
    name: str
    rollen: dict[str, int]
    zielrolle: str = ""
    absicht: str = ""                 # Anschreiben: „Ich studiere … und suche {absicht}.“
    ausblick: str = ""                # Anschreiben: Schlusssatz vor dem Gruß
    suchbegriffe: dict[str, list[str]] = field(default_factory=dict)   # je Quelle
    angebotsart: int | None = None    # Bundesagentur: 1 = Arbeit, 34 = Praktikum/Trainee/Werkstudent
    arbeitszeit: str = ""             # Bundesagentur: „mj“ = Minijob (sonst alle Arbeitszeiten)
    ats_suchbegriffe: list[str] = field(default_factory=list)
    ausschluss_titel: list[str] = field(default_factory=list)   # zusätzlich zu filter.ausschluss_titel
    slug_begriffe: list[str] = field(default_factory=list)      # für Links auf Karriereseiten (Standard: rollen)
    fach: dict[str, int] = field(default_factory=dict)          # eigenes Fachgebiet; leer = filter.fach
    fach_max: int | None = None
    fit_begriffe: dict[str, list[str]] = field(default_factory=dict)
    enabled: bool = True
    stufe: str = ""                   # Karrierestufe (STUFEN); „berufserfahren“ hebt filter.ausschluss_stufe_titel auf

    def begriffe(self, quelle: str) -> list[str]:
        return list(self.suchbegriffe.get(quelle) or [])

    def slug_re(self) -> re.Pattern:
        """Slug- bzw. Rollen-Stichwörter als Muster für URL-Slugs und Titel (Leerzeichen dürfen Bindestriche sein)."""
        terms = sorted((re.escape(r).replace(r"\ ", "[- ]") for r in self.slug_begriffe or self.rollen),
                       key=len, reverse=True)
        return re.compile("|".join(terms) or r"(?!)", re.IGNORECASE)


def _from_dict(key: str, raw: dict) -> Profil:
    return Profil(
        key=key, name=raw.get("name") or key.capitalize(), rollen=dict(raw.get("rollen") or {}),
        zielrolle=raw.get("zielrolle") or "", absicht=raw.get("absicht") or "", ausblick=raw.get("ausblick") or "",
        suchbegriffe={q: list(v or []) for q, v in (raw.get("suchbegriffe") or {}).items()},
        angebotsart=raw.get("angebotsart"), arbeitszeit=str(raw.get("arbeitszeit") or ""),
        ats_suchbegriffe=list(raw.get("ats_suchbegriffe") or []),
        ausschluss_titel=list(raw.get("ausschluss_titel") or []), slug_begriffe=list(raw.get("slug_begriffe") or []),
        fach={str(k): int(v) for k, v in (raw.get("fach") or {}).items()}, fach_max=raw.get("fach_max"),
        fit_begriffe={str(k): list(v or []) for k, v in (raw.get("fit_begriffe") or {}).items()},
        enabled=raw.get("enabled", True) is not False, stufe=str(raw.get("stufe") or ""))


def _legacy(cfg: dict) -> Profil:
    """Ältere config.yaml ohne Block `profile:`: ein Werkstudent-Profil aus filter.rollen & Co."""
    src = cfg.get("sources") or {}
    return Profil(
        key=DEFAULT_KEY, name="Werkstudent", rollen=dict((cfg.get("filter") or {}).get("rollen") or {}),
        zielrolle=(cfg.get("entwuerfe") or {}).get("zielrolle", ""),
        suchbegriffe={q: list(v.get("suchbegriffe") or []) for q, v in src.items()
                      if isinstance(v, dict) and v.get("suchbegriffe")})


def alle(cfg: dict) -> list[Profil]:
    """Alle Profile in der Reihenfolge der config.yaml (auch abgeschaltete)."""
    raw = cfg.get("profile")
    if not raw:
        return [_legacy(cfg)]
    return [_from_dict(key, value or {}) for key, value in raw.items()]


def aktive(cfg: dict) -> list[Profil]:
    """Aktive Profile, höchstens MAX_AKTIV und je Quelle höchstens MAX_BEGRIFFE Suchbegriffe (Rest wird ignoriert,
    falls jemand config.yaml von Hand über die Grenze bringt)."""
    out = [p for p in alle(cfg) if p.enabled][:MAX_AKTIV]
    for p in out:
        p.suchbegriffe = {q: v[:MAX_BEGRIFFE] for q, v in p.suchbegriffe.items()}
    return out


def alle_fach(cfg: dict) -> dict[str, int]:
    """Gemeinsame Fach-Stichwörter plus die eigenen Fachgebiete aktiver Profile (für Vorfilter wie HSNR)."""
    fach = dict((cfg.get("filter") or {}).get("fach") or {})
    for p in aktive(cfg):
        for k, v in p.fach.items():
            fach.setdefault(k, v)
    return fach


def anfragen(cfg: dict, portale: int, profile: list[Profil] | None = None) -> dict[str, int]:
    """Ungefähre Höchstzahl an Abrufen je Lauf, die von den Suchprofilen abhängen (Suchen plus nachgeladene
    Anzeigentexte). Firmen-Karriereseiten, Hochschule und Mail-Alerts kommen unabhängig davon dazu."""
    src = cfg.get("sources") or {}
    ba, sw = src.get("bundesagentur") or {}, src.get("stellenwerk") or {}
    profile = aktive(cfg) if profile is None else profile
    out = {"bundesagentur": 0, "stellenwerk": 0}
    for p in profile:
        if ba.get("enabled", True) and p.begriffe("bundesagentur"):
            out["bundesagentur"] += (len(p.begriffe("bundesagentur")) * (2 if ba.get("bundesweit_remote") else 1)
                                     + int(ba.get("max_details", 0)))
        if sw.get("enabled", True) and p.begriffe("stellenwerk") and portale:
            out["stellenwerk"] += portale * (len(p.begriffe("stellenwerk")) + int(sw.get("max_detail_pages", 0)))
    return out


def get(cfg: dict, key: str | None) -> Profil:
    """Profil nach Schlüssel; unbekannt oder leer (ältere Stellen) → erstes Profil."""
    profile = alle(cfg)
    return next((p for p in profile if p.key == key), profile[0])


def name(cfg: dict, key: str | None) -> str:
    return get(cfg, key).name
