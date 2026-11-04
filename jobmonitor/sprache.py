"""Bewerbung auf Englisch: Sprache je Bewerbung, englischer Master-CV und englische Beschriftungen in den PDFs.

- Sprache je Bewerbung in sprache.json im Bewerbungsordner („de“ oder „en“). Ist die Anzeige auf Englisch, schlägt die
  Bewerbungsseite Englisch vor (`erkennen`).
- Inhalte: cv/cv_master.en.yaml – einmal von der KI aus dem deutschen Master-CV übersetzt (`uebersetzen`), danach
  frei bearbeitbar. Übersetzt werden nur Texte; Struktur, Level, Status und Zeiträume bleiben unverändert, damit
  Fit-Rating und Vorlagen weiter stimmen.
- Beschriftungen: Die Vorlagen (auch eigene) bleiben deutsch; `beschriften` ersetzt im fertigen HTML/LaTeX die festen
  Überschriften und Wörter („Berufserfahrung“, „seit“, „Mit freundlichen Grüßen“ …) durch die englischen.
- Englische Lebensläufe kommen ohne Foto und Geburtsdatum aus (international üblich); `profil_en` blendet beides aus.
"""
from __future__ import annotations

import copy
import io
import json
import re
from datetime import date
from pathlib import Path

DATEI = "sprache.json"
SPRACHEN = {"de": "Deutsch", "en": "Englisch"}
CV_EN = "cv_master.en.yaml"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
ANREDE_EN = "Dear Hiring Team,"

# Feste Wörter der Vorlagen → Englisch (längere zuerst, damit „Zertifikate und Weiterbildung“ vor „Zertifikate“ greift)
WOERTER = {
    "Zertifikate und Weiterbildung": "Certifications and Training", "Sprachen und Interessen": "Languages and Interests",
    "Kenntnisse und Sprachen": "Skills and Languages", "Studium und Ausbildung": "Education",
    "Schule und Ausbildung": "Education", "Projekte und Forschung": "Projects and Research",
    "Berufserfahrung": "Work Experience", "Ausbildung": "Education", "Kenntnisse": "Skills", "Sprachen": "Languages",
    "Projekte": "Projects", "Zertifikate": "Certifications", "Interessen": "Interests", "Profil": "Profile",
    "Kontakt": "Contact", "Lebenslauf": "Curriculum Vitae", "Mit freundlichen Grüßen": "Kind regards",
    "Anlagen": "Enclosures", "Grundkenntnisse in": "basic knowledge of", "in Arbeit": "in progress",
    "geplant": "planned", "Bewerbung als": "Application for", "geboren am": "born",
}
# nur ganze Wörter und nur außerhalb von Wörtern wie „Projektelement“
_WORT_RE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(w) for w in sorted(WOERTER, key=len, reverse=True))
                      + r")(?![\w-])")
_SEIT_RE = re.compile(r"(?<![\w-])seit(?=\s|\\,|~)")
_VORAUS_RE = re.compile(r"(?<![\w-])voraussichtlich(?=\s)")


class SpracheError(Exception):
    pass


def fuer_bewerbung(folder: Path | None) -> str:
    if folder is not None:
        try:
            wert = json.loads((folder / DATEI).read_text(encoding="utf-8")).get("sprache")
            if wert in SPRACHEN:
                return wert
        except (OSError, ValueError, AttributeError):
            pass
    return "de"


def waehlen(folder: Path, code: str) -> None:
    if code not in SPRACHEN:
        raise SpracheError("Unbekannte Sprache.")
    (folder / DATEI).write_text(json.dumps({"sprache": code}), encoding="utf-8")


DE = {"und", "der", "die", "das", "wir", "sie", "mit", "für", "ihre", "deine", "bei", "eine", "auf", "sind", "werden"}
EN = {"and", "the", "you", "we", "with", "for", "our", "your", "are", "will", "of", "to", "in", "is", "team"}


def erkennen(text: str) -> str | None:
    """„en“ oder „de“, wenn die Anzeige eindeutig in einer Sprache ist; sonst None."""
    woerter = re.findall(r"[a-zäöüß]+", (text or "").lower())[:1500]
    if len(woerter) < 30:
        return None
    de, en = sum(w in DE for w in woerter), sum(w in EN for w in woerter)
    if en > 2 * de and en >= 10:
        return "en"
    if de > 2 * en and de >= 10:
        return "de"
    return None


def beschriften(text: str) -> str:
    """Feste deutsche Wörter einer gerenderten Vorlage (HTML oder LaTeX) ins Englische."""
    text = _WORT_RE.sub(lambda m: WOERTER[m.group(1)], text)
    text = _SEIT_RE.sub("since", text)
    text = _VORAUS_RE.sub("expected", text)
    text = text.replace('lang="de"', 'lang="en"').replace("[ngerman]{babel}", "[english]{babel}")
    return text.replace("{ngerman}", "{english}")


def profil_en(profile: dict) -> dict:
    """Englischer Lebenslauf: ohne Foto und Geburtsdatum (international üblich, vermeidet Ablehnungen wegen Fotos)."""
    anzeigen = {**(profile.get("anzeigen") or {}), "foto": False, "geburtsdatum": False}
    return {**profile, "anzeigen": anzeigen}


def datum(tag: date) -> str:
    return f"{tag.day} {MONTHS[tag.month - 1]} {tag.year}"


# --- Englischer Master-CV ---
def pfad_en(root: Path) -> Path:
    from .cv_data import find_cv_master
    de = find_cv_master(root)
    return (de.parent if de is not None else root / "cv") / CV_EN


def cv_en(root: Path) -> dict | None:
    """cv_master.en.yaml (mit demselben Schutz vor persönlichen Daten wie der deutsche) oder None."""
    from ruamel.yaml import YAML

    from .cv_data import CvDataError, check_no_personal_data
    path = pfad_en(root)
    if not path.is_file():
        return None
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise CvDataError(f"{CV_EN} ist kein gültiges YAML ({type(exc).__name__})") from None
    if not isinstance(data, dict):
        raise CvDataError(f"{CV_EN} muss eine YAML-Zuordnung sein")
    check_no_personal_data(data, CV_EN)
    return data


FEST = {"level", "status", "im_cv", "von", "nachweis", "url", "link", "datum"}


def _texte(node, pfad=()) -> list[tuple[tuple, str]]:
    """Alle übersetzbaren Texte mit Pfad (ohne Level, Status, Zeiträume und Links)."""
    if isinstance(node, dict):
        return [t for k, v in node.items() if k not in FEST for t in _texte(v, pfad + (k,))]
    if isinstance(node, list):
        return [t for i, v in enumerate(node) for t in _texte(v, pfad + (i,))]
    if isinstance(node, str) and re.search(r"[A-Za-zÄÖÜäöü]{2}", node):
        return [(pfad, node)]
    return []


def _setzen(node, pfad: tuple, wert: str) -> None:
    for teil in pfad[:-1]:
        node = node[teil]
    node[pfad[-1]] = wert


def uebersetzen(root: Path, cfg: dict, cv: dict, ask=None) -> Path:
    """Master-CV mit KI ins Englische; schreibt cv_master.en.yaml (eine vorhandene Fassung bleibt als .bak)."""
    from ruamel.yaml import YAML

    from . import ki, llm
    from .cv_data import check_no_personal_data
    texte = _texte(cv)
    if not texte:
        raise SpracheError("Der Master-CV enthält keine Texte zum Übersetzen.")
    antwort = ki.fragen(root, cfg, (
        "Übersetze diese Texte aus einem deutschen Lebenslauf ins Englische (britisches oder internationales "
        "Business-Englisch, wie in englischen CVs üblich). Regeln: sinngemäß und knapp, nichts hinzufügen oder "
        "weglassen; Eigennamen von Firmen, Hochschulen, Produkten und Technologien unverändert; Abschlüsse gängig "
        "übersetzen (z. B. „Abitur“ → „Abitur (German university entrance qualification)“); Datumsangaben wie "
        "„07/2026“ unverändert, „voraussichtlich“ → „expected“.\n\nAntworte nur mit JSON: {\"texte\": [...]} mit "
        f"genau {len(texte)} Strings in derselben Reihenfolge.\n\nTEXTE:\n"
        + json.dumps([t for _, t in texte], ensure_ascii=False)), effort="low", max_tokens=12000, ask=ask)
    liste = (llm.json_aus(antwort) or {}).get("texte")
    if not isinstance(liste, list) or len(liste) != len(texte) or not all(isinstance(x, str) for x in liste):
        raise SpracheError("Die KI hat keine vollständige Übersetzung geliefert – bitte noch einmal versuchen.")
    neu = copy.deepcopy(cv)
    for (pfad, _), wert in zip(texte, liste):
        _setzen(neu, pfad, wert.strip())
    check_no_personal_data(neu, CV_EN)
    path = pfad_en(root)
    if path.is_file():
        path.with_name(CV_EN + ".bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.width = 4096
    buf = io.StringIO()
    buf.write("# Englische Fassung deines Master-CV (von der KI übersetzt – bitte prüfen und anpassen).\n"
              "# Wird für Bewerbungen auf Englisch genutzt. Level, Status und Zeiträume wie im deutschen Master-CV.\n")
    yaml.dump(neu, buf)
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


def auswahl_html(token: str, ziel: str, aktuell: str, vorschlag: str | None, hat_en: bool, ki_an: bool, esc) -> str:
    """Karte „Sprache der Bewerbung“ auf der Bewerbungsseite."""
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    optionen = "".join(f'<option value="{k}"{" selected" if k == aktuell else ""}>{v}</option>'
                       for k, v in SPRACHEN.items())
    hinweis = ""
    if vorschlag == "en" and aktuell == "de":
        hinweis = ('<p class="muted" style="margin-top:8px"><b>Die Anzeige ist auf Englisch.</b> Internationale Firmen erwarten dann meist '
                   'auch Lebenslauf und Anschreiben auf Englisch.</p>')
    fehlt = ""
    if aktuell == "en" and not hat_en:
        knopf = ('<button name="aktion" value="cv_uebersetzen" class="small" data-ki="KI übersetzt deinen '
                 'Lebenslauf …">Master-CV mit KI übersetzen</button>' if ki_an else
                 '<a class="btn small ghost" href="/einstellungen#ki">KI einrichten</a>')
        fehlt = (f'<p class="err">Für Englisch fehlt noch die englische Fassung deines Master-CV '
                 f'(cv/{CV_EN}). Die KI übersetzt ihn einmal, danach kannst du ihn unter Dateien anpassen. Ohne '
                 f'Übersetzung nutzt der Lebenslauf die deutschen Inhalte.</p>{knopf}')
    elif aktuell == "en":
        fehlt = (f'<p class="muted">Inhalte aus cv/{CV_EN} · <a href="/dateien">unter Dateien anpassen</a>. Englische '
                 'Lebensläufe ohne Foto und Geburtsdatum.</p>')
    return (f'<div class="card"><h2>Sprache der Bewerbung</h2><form method="post" action="{ziel}" class="row" '
            f'style="gap:8px"><input type="hidden" name="token" value="{token}"><select name="sprache" '
            f'style="width:auto">{optionen}</select><button name="aktion" value="sprache" class="ghost small">'
            f'Übernehmen</button></form>{hinweis}<form method="post" action="{ziel}" style="margin-top:8px">'
            f'<input type="hidden" name="token" value="{token}">{fehlt}</form></div>')
