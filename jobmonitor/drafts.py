"""Anschreiben-Entwürfe für Initiativ-Vorschläge. Schreibt nur lokale Markdown-Dateien in drafts/ (gitignored).

Persönliche Daten kommen ausschließlich aus profile.yaml. Es wird nie etwas verschickt.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from ruamel.yaml import YAML

from . import llm

TEMPLATE = """\
<!-- Entwurf – bitte prüfen, anpassen und selbst verschicken. -->
{name}
{adresse}
{email} · {telefon}

**{firma}**
z. Hd. {ansprechperson}

{ort_datum}

**Initiativbewerbung als {zielrolle}**

{anrede}

{bezug}

Ich studiere {studium} und suche ab {zeitraum} {absicht}. Mein Schwerpunkt liegt auf Cloud (Azure), \
Identity & Access Management mit Entra ID sowie DevSecOps und Infrastructure as Code. \
[Ein Satz zu deiner aktuellen Tätigkeit und einem konkreten Projekt.]

{ausblick}Über ein Gespräch freue ich mich sehr.

Mit freundlichen Grüßen
{name}

Anlagen: Lebenslauf, Notenübersicht
"""


def load_profile(root: Path) -> dict:
    """profile.yaml in der Repo-Wurzel, sonst cv/profile.yaml (gleiche Datei wie für make cv)."""
    path = next((p for p in (root / "profile.yaml", root / "cv" / "profile.yaml") if p.exists()), None)
    if path is None:
        return {}
    with open(path, encoding="utf-8") as fh:
        profile = YAML(typ="safe").load(fh) or {}
    adresse = profile.get("adresse")
    if isinstance(adresse, dict):   # Schema aus cv/profile.example.yaml
        strasse, ort = adresse.get("strasse") or "", " ".join(filter(None, [adresse.get("plz"), adresse.get("ort")]))
        profile["adresse"] = ", ".join(filter(None, [strasse, ort])) or None
        profile["ort"] = adresse.get("ort") or None     # für „Ort, Datum“ im Anschreiben
    return {key: value for key, value in profile.items() if value not in (None, "")}


def bezug_saetze(entry: dict) -> str:
    """Zwei Sätze Bezug zur Firma aus companies.yaml (keine externen Quellen)."""
    branche = entry.get("branche") or "Ihr Unternehmen"
    fokus = ", ".join((entry.get("fokus") or [])[:3]) or "Cloud und IT-Sicherheit"
    orte = [s for s in entry.get("standorte") or [] if s != "Remote"]
    ort = f" am Standort {orte[0]}" if orte else ""
    return (f"als {branche}{ort} verbindet {entry['name']} genau die Themen, die mich im Studium am meisten "
            f"interessieren: {fokus}. [Ein Satz, was dich konkret an {entry['name']} reizt – z. B. ein Projekt, "
            f"ein Produkt oder ein Blogartikel.]")


def render(entry: dict, profile: dict, cfg: dict, today: date) -> str:
    ap = (entry.get("ansprechperson") or "").strip()
    bezug = bezug_saetze(entry)
    fields = {
        "name": profile.get("name", "[Dein Name]"),
        "adresse": profile.get("adresse", "[Deine Adresse]"),
        "email": profile.get("email", "[E-Mail]"),
        "telefon": profile.get("telefon", "[Telefon]"),
        "firma": entry["name"],
        "ansprechperson": ap or "[Ansprechperson laut Karriereseite]",
        "ort_datum": f"{ort}, {today:%d.%m.%Y}" if (ort := profile.get("ort")) else f"{today:%d.%m.%Y}",
        # Zielrolle, Absicht und Ausblick kommen aus dem Suchprofil (config.yaml → profile, entwuerfe.profil)
        "zielrolle": cfg.get("zielrolle") or "[Zielrolle]",
        "absicht": cfg.get("absicht") or "[welche Stelle du suchst]",
        "ausblick": f"{cfg['ausblick']} " if cfg.get("ausblick") else "",
        "anrede": f"Sehr geehrte/r {ap}," if ap else "Sehr geehrte Damen und Herren,",
        "bezug": bezug[0].upper() + bezug[1:],
        "studium": profile.get("studium", "[Studiengang, Hochschule, Semester]"),
        "zeitraum": profile.get("zeitraum", "[Zeitraum]"),
    }
    return TEMPLATE.format(**fields)


def write_drafts(entries: list[dict], root: Path, cfg: dict, today: date) -> list[Path]:
    profile = load_profile(root)
    out_dir = root / "drafts"
    out_dir.mkdir(exist_ok=True)
    written = []
    for entry in entries:
        name = entry["name"].lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
        slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
        path = out_dir / f"{today.isoformat()}-{slug}.md"
        if path.exists():
            continue
        text = render(entry, profile, cfg, today)
        if cfg.get("llm") and llm.verfuegbar():
            improved = llm.draft_letter(cfg.get("model", "claude-opus-5-5"), text)
            text = improved or text
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
