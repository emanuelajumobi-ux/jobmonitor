"""Designs für Lebenslauf und Anschreiben – gleiche Inhalte (Master-CV), anderes Aussehen je Richtung.

„klassisch“ ist das bisherige Layout (deine LaTeX-Vorlage, wenn cv.format latex ist, sonst cv/template.html.j2). Die
übrigen Designs sind HTML-Vorlagen in cv/designs/ (PDF über pdf_html.py, also ohne LaTeX).

Welches Design gilt (erste Angabe gewinnt):
1. für eine einzelne Bewerbung: Auswahl auf der Bewerbungsseite (design.json im Bewerbungsordner)
2. für ein Suchprofil: profile.<name>.design in config.yaml, sonst passend zur Karrierestufe (STUFE_DESIGN)
3. sonst cv.design (Standard: klassisch)

`ats`: gut maschinenlesbar (einspaltig, ohne Grafik) – wichtig, wenn die Firma Bewerbungen über ein Bewerbungssystem
automatisch einliest. Die Prüfung vor dem Abschicken warnt bei anderen Designs auf solchen Portalen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DESIGNS: dict[str, dict] = {
    "klassisch": {"name": "Klassisch", "ats": True, "lebenslauf": "", "anschreiben": "",
                  "beschreibung": "Einspaltig und schlicht (Harvard-Stil).",
                  "passt": "IT, Ingenieurwesen, Beratung, Finanzen, öffentlicher Dienst"},
    "modern": {"name": "Modern", "ats": False, "lebenslauf": "cv/designs/modern.html.j2",
               "anschreiben": "cv/designs/modern_anschreiben.html.j2",
               "beschreibung": "Zwei Spalten: links Kontakt, Kenntnisse und Sprachen, rechts Stationen.",
               "passt": "IT, Startups, Marketing, Vertrieb"},
    "kreativ": {"name": "Kreativ", "ats": False, "lebenslauf": "cv/designs/kreativ.html.j2",
                "anschreiben": "cv/designs/kreativ_anschreiben.html.j2",
                "beschreibung": "Farbiger Kopf, großes Foto, Projekte im Vordergrund.",
                "passt": "Design, Medien, Kommunikation, Architektur"},
    "kompakt": {"name": "Kompakt", "ats": True, "lebenslauf": "cv/designs/kompakt.html.j2",
                "anschreiben": "cv/designs/kompakt_anschreiben.html.j2",
                "beschreibung": "Tabellarisch mit Zeitspalte und Foto, wie man es in Deutschland gewohnt ist.",
                "passt": "Ausbildung, Pflege, Handwerk, Verwaltung, Handel"},
    "akademisch": {"name": "Akademisch", "ats": True, "lebenslauf": "cv/designs/akademisch.html.j2",
                   "anschreiben": "cv/designs/akademisch_anschreiben.html.j2",
                   "beschreibung": "Studium, Abschlussarbeit und Projekte zuerst, nüchtern gesetzt.",
                   "passt": "Abschlussarbeiten, Forschung, Promotion"},
}
STUFE_DESIGN = {"ausbildung": "kompakt", "abschlussarbeit": "akademisch"}
DATEI = "design.json"
# Bewerbungssysteme, die Lebensläufe automatisch auslesen (Host der Anzeige)
ATS_HOSTS = re.compile(r"successfactors|myworkdayjobs|workday|greenhouse|lever\.co|smartrecruiters|personio|softgarden|"
                       r"rexx|dvinci|d-vinci|onlyfy|prescreen|umantis|taleo|icims|phenom|avature|jobs\.sap", re.I)
AKZENT = re.compile(r"^#[0-9a-fA-F]{6}$")


def gueltig(key: str | None) -> str | None:
    return key if key in DESIGNS else None


def fuer_profil(cfg: dict, profil_key: str | None) -> str:
    from . import suchprofil
    p = suchprofil.get(cfg, profil_key)
    raw = ((cfg.get("profile") or {}).get(p.key) or {})
    return (gueltig(raw.get("design")) or STUFE_DESIGN.get(p.stufe)
            or gueltig((cfg.get("cv") or {}).get("design")) or "klassisch")


def fuer_bewerbung(cfg: dict, folder: Path | None, stelle: dict | None) -> str:
    if folder is not None:
        try:
            gewaehlt = json.loads((folder / DATEI).read_text(encoding="utf-8")).get("design")
            if gueltig(gewaehlt):
                return gewaehlt
        except (OSError, ValueError, AttributeError):
            pass
    if stelle is not None and stelle.get("profil"):
        return fuer_profil(cfg, stelle.get("profil"))
    return gueltig((cfg.get("cv") or {}).get("design")) or "klassisch"


def waehlen(folder: Path, key: str) -> None:
    if not gueltig(key):
        raise ValueError("Unbekanntes Design.")
    (folder / DATEI).write_text(json.dumps({"design": key}), encoding="utf-8")


def akzent(cfg: dict) -> str:
    farbe = str((cfg.get("cv") or {}).get("akzentfarbe") or "")
    return farbe if AKZENT.match(farbe) else "#1F4E79"


def ats_warnung(key: str, url: str) -> str:
    """Hinweis, wenn ein gestaltetes Design auf ein Portal geht, das Lebensläufe automatisch einliest."""
    if DESIGNS.get(key, {}).get("ats", True) or not ATS_HOSTS.search(url or ""):
        return ""
    return (f"Design „{DESIGNS[key]['name']}“ ist gestaltet (Spalten/Farben); diese Firma nutzt ein Bewerbungssystem, "
            f"das Lebensläufe automatisch einliest – „Klassisch“, „Kompakt“ oder „Akademisch“ werden dort sicherer erkannt.")


# --- Oberfläche ---
def vorschau_html(root: Path, cfg: dict, key: str) -> str:
    """Lebenslauf im Design als HTML mit deinen Daten (für die Galerie; das Foto über /unterlagen/foto)."""
    from . import pdf_html
    from .cv_build import complete_cv, html_vorlage, load_profile
    from .cv_data import load_cv_master
    cv, _ = load_cv_master(root)
    profile = load_profile(root) or {}
    if profile.get("foto"):
        profile = {**profile, "foto": "/unterlagen/foto"}
    rel = DESIGNS[key]["lebenslauf"] or (cfg.get("cv") or {}).get("vorlage_html", "cv/template.html.j2")
    vorlage = html_vorlage(root, rel)
    return pdf_html.environment(vorlage.parent).get_template(vorlage.name).render(
        cv=complete_cv(cv or {}), profile=profile, stelle=None, akzent=akzent(cfg))


def auswahl_html(token: str, ziel: str, aktuell: str, esc, hinweis: str = "") -> str:
    """Kleines Formular „Design“ (Bewerbungsseite)."""
    optionen = "".join(f'<option value="{k}"{" selected" if k == aktuell else ""}>{esc(d["name"])} – {esc(d["passt"])}'
                       f'</option>' for k, d in DESIGNS.items())
    return (f'<div class="card"><h2>Design</h2><form method="post" action="{ziel}" class="row" style="gap:8px">'
            f'<input type="hidden" name="token" value="{token}"><select name="design" style="width:auto">{optionen}'
            f'</select><button name="aktion" value="design" class="ghost small">Übernehmen</button>'
            f'<a href="/master#designs" class="muted">alle Designs ansehen</a></form>'
            f'<p class="muted">{esc(DESIGNS[aktuell]["beschreibung"])} Gilt für Lebenslauf und Anschreiben dieser '
            f'Bewerbung; neu bauen, damit die PDFs es übernehmen.</p>{hinweis}</div>')


def galerie_html(esc) -> str:
    karten = "".join(
        f'<figure class="design"><div class="rahmen"><iframe src="/designs/vorschau/{k}" loading="lazy" tabindex="-1" '
        f'title="Vorschau {esc(d["name"])}"></iframe></div><figcaption><b>{esc(d["name"])}</b>'
        f'{" · gut maschinenlesbar" if d["ats"] else " · gestaltet"}<br><span class="muted">{esc(d["passt"])}</span>'
        f'</figcaption></figure>' for k, d in DESIGNS.items())
    return (f'<div class="card" id="designs"><h2>Designs für Lebenslauf und Anschreiben</h2><p class="muted">Gleicher '
            f'Inhalt, anderes Aussehen. Das Design wählst du je Suchprofil (Einstellungen) oder je Bewerbung. '
            f'„Gestaltete“ Designs (Spalten, Farbflächen) lesen Bewerbungssysteme großer Firmen teils schlechter – '
            f'die Prüfung vor dem Abschicken weist darauf hin.</p><div class="designs">{karten}</div></div>')


CSS = """
.designs { display:grid; grid-template-columns:repeat(auto-fill, minmax(190px, 1fr)); gap:14px; }
.design { margin:0; } .design figcaption { font-size:13px; margin-top:6px; line-height:1.35; }
.design .rahmen { width:100%; aspect-ratio:210/297; overflow:hidden; border-radius:8px; border:1px solid var(--line);
  background:#fff; position:relative; }
.design iframe { width:794px; height:1123px; border:0; transform-origin:0 0; transform:scale(.24); pointer-events:none;
  position:absolute; top:0; left:0; }
"""
