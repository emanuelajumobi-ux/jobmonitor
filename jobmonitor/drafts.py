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

{vorstellung} {schwerpunkt} \
[Ein Satz zu deiner aktuellen Tätigkeit und einem konkreten Projekt.]

{ausblick}Über ein Gespräch freue ich mich sehr.

Mit freundlichen Grüßen
{name}

Anlagen: Lebenslauf, Zeugnisse
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
    fokus = ", ".join((entry.get("fokus") or [])[:3])
    orte = [s for s in entry.get("standorte") or [] if s != "Remote"]
    ort = f" am Standort {orte[0]}" if orte else ""
    themen = (f"verbindet {entry['name']} genau die Themen, die mich am meisten interessieren: {fokus}." if fokus
              else f"ist {entry['name']} für mich ein besonders interessanter Arbeitgeber.")
    return (f"als {branche}{ort} {themen} [Ein Satz, was dich konkret an {entry['name']} reizt – z. B. ein Projekt, "
            f"ein Produkt oder ein Blogartikel.]")


def vorstellung(profile: dict, cfg: dict) -> str:
    """Wer schreibt und was gesucht wird – aus profile.yaml (studium, zeitraum) und dem Suchprofil (absicht)."""
    absicht = cfg.get("absicht") or "[welche Stelle du suchst]"
    zeit = f" ab {profile['zeitraum']}" if profile.get("zeitraum") else ""
    if profile.get("studium"):
        return f"Ich studiere {profile['studium']} und suche{zeit} {absicht}."
    return f"[Ein Satz zu dir: Studium, Ausbildung oder aktuelle Tätigkeit.] Ich suche{zeit} {absicht}."


def schwerpunkt(cfg: dict, cv: dict | None) -> str:
    """Eigener Satz aus config.yaml → entwuerfe.schwerpunkt, sonst die ersten Kenntnisse aus dem Master-CV, sonst ein
    Platzhalter. (Früher stand hier fest ein IT-Schwerpunkt – falsch für alle anderen Fachrichtungen.)"""
    if str(cfg.get("schwerpunkt") or "").strip():
        return str(cfg["schwerpunkt"]).strip()
    namen = []
    for kat in (cv or {}).get("kenntnisse") or []:
        for e in (kat.get("eintraege") or []) if isinstance(kat, dict) else [kat]:
            name = e.get("name") if isinstance(e, dict) else e
            if name and str(name) not in namen:
                namen.append(str(name))
    if len(namen) >= 2:
        return f"Meine Schwerpunkte sind {', '.join(namen[:3][:-1])} und {namen[:3][-1]}."
    return "[Ein Satz zu deinen fachlichen Schwerpunkten.]"


def render(entry: dict, profile: dict, cfg: dict, today: date, cv: dict | None = None) -> str:
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
        "vorstellung": vorstellung(profile, cfg),
        "schwerpunkt": schwerpunkt(cfg, cv),
    }
    return TEMPLATE.format(**fields)


def write_drafts(entries: list[dict], root: Path, cfg: dict, today: date) -> list[Path]:
    profile = load_profile(root)
    try:
        from .cv_data import load_cv_master
        cv, _ = load_cv_master(root)
    except Exception:        # ohne lesbaren Lebenslauf: Platzhalter statt Schwerpunkten
        cv = None
    out_dir = root / "drafts"
    out_dir.mkdir(exist_ok=True)
    written = []
    for entry in entries:
        name = entry["name"].lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
        slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
        path = out_dir / f"{today.isoformat()}-{slug}.md"
        if path.exists():
            continue
        text = render(entry, profile, cfg, today, cv)
        if cfg.get("llm") and llm.verfuegbar():
            improved = llm.draft_letter(cfg.get("model", "claude-opus-5-5"), text)
            text = improved or text
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
