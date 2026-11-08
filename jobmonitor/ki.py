"""KI-Hilfen auf Knopfdruck (Claude-API, nur lokal in der Oberfläche): Anschreiben-Entwurf je Stelle und
Gesprächsvorbereitung.

Was an die API geht: Titel und Firma der Stelle, der öffentliche Anzeigentext (sofern lesbar) und die Inhalte aus
cv_master.yaml (per Definition ohne persönliche Daten, siehe cv_data). Nie Name, Adresse, Telefon, Foto oder der
Zeitraum aus profile.yaml – den setzt die App erst lokal für den Platzhalter [Zeitraum] ein. Die KI schickt nichts ab;
sie liefert nur Entwürfe.

Der API-Schlüssel kommt aus ANTHROPIC_API_KEY (.env) oder dem macOS-Schlüsselbund (Einstellungen → KI). Aufrufe und
Tokens je Monat stehen in .gui_ki.json (gitignored); ki.max_aufrufe_monat begrenzt die Aufrufe.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from ruamel.yaml import YAML

from . import llm
from .suchprofil import STUFEN

log = logging.getLogger(__name__)
DATEI = ".gui_ki.json"
DIENST = "job-monitor-anthropic"          # Eintrag im Schlüsselbund
DEFAULTS = {"model": "claude-opus-5-5", "max_aufrufe_monat": 60, "pipeline_warnung_monat": 3_000_000,
            "pipeline_warnung_lauf": 400_000}
ZEITRAUM = "[Zeitraum]"


class KiError(Exception):
    pass


def settings(cfg: dict) -> dict:
    return {**DEFAULTS, **(cfg.get("ki") or {})}


# --- Schlüssel (je KI-Anbieter, siehe ki_anbieter.py; aktiver Anbieter: llm.ANBIETER) ---
def _dienst() -> str:
    from . import llm
    return DIENST if llm.ANBIETER == "claude" else f"job-monitor-{llm.ANBIETER}"


def _env() -> str:
    from . import llm
    return "ANTHROPIC_API_KEY" if llm.ANBIETER == "claude" else "KI_API_KEY"


def schluessel(run=subprocess.run) -> str | None:
    from . import ki_anbieter, llm
    if os.environ.get(_env()):
        return os.environ[_env()]
    if ki_anbieter.ANBIETER[llm.ANBIETER].get("ohne_schluessel"):
        return "lokal"                       # Ollama braucht keinen Schlüssel
    if sys.platform != "darwin":
        tresor = _keyring()        # Windows: Anmeldeinformationsverwaltung
        try:
            return (tresor.get_password(_dienst(), "job-monitor") or None) if tresor else None
        except Exception:
            return None
    try:
        proc = run(["security", "find-generic-password", "-s", _dienst(), "-w"], capture_output=True, text=True,
                   timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _keyring():
    """Schlüsselspeicher des Systems außerhalb von macOS (Paket keyring, in der Windows-App enthalten)."""
    try:
        import keyring
        return keyring
    except ImportError:
        return None


def herkunft(run=subprocess.run) -> str:
    if os.environ.get(_env()):
        return ".env"
    return "Schlüsselbund" if schluessel(run) else ""


def schluessel_speichern(wert: str, run=subprocess.run) -> None:
    from . import llm
    wert = wert.strip()
    if llm.ANBIETER == "claude" and not re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", wert):
        raise KiError("Das sieht nicht nach einem Claude-API-Schlüssel aus (beginnt mit „sk-ant-“).")
    if not re.fullmatch(r"[A-Za-z0-9_\-.:]{16,300}", wert):
        raise KiError("Das sieht nicht nach einem API-Schlüssel aus – bitte vollständig und ohne Leerzeichen kopieren.")
    if sys.platform != "darwin":
        tresor = _keyring()
        if tresor is None:
            raise KiError(f"Kein Schlüsselspeicher auf diesem System – bitte {_env()} in die Datei .env.")
        tresor.set_password(_dienst(), "job-monitor", wert)
        return
    proc = run(["security", "add-generic-password", "-U", "-s", _dienst(), "-a", "job-monitor", "-w", wert],
               capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        raise KiError("Schlüssel nicht im Schlüsselbund gespeichert.")


def schluessel_loeschen(run=subprocess.run) -> None:
    if sys.platform != "darwin":
        tresor = _keyring()
        try:
            tresor and tresor.delete_password(_dienst(), "job-monitor")
        except Exception:
            pass
        return
    run(["security", "delete-generic-password", "-s", _dienst()], capture_output=True, text=True, timeout=10)


# --- lokaler Speicher: Nutzung, Anzeigentexte, Vorbereitungen ---
def laden(root: Path) -> dict:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _speichern(root: Path, data: dict) -> None:
    (root / DATEI).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def nutzung(root: Path, heute: date | None = None) -> dict:
    monat = (heute or date.today()).strftime("%Y-%m")
    return {"aufrufe": 0, "eingabe": 0, "ausgabe": 0, **(laden(root).get("nutzung") or {}).get(monat, {})}


def vorbereitungen(root: Path) -> dict[str, str]:
    return laden(root).get("vorbereitung") or {}


def anzeige(root: Path, link: str, fetcher, cache: Path | None = None) -> str:
    """Öffentlicher Anzeigentext (robots.txt, ehrlicher User-Agent; nie LinkedIn & Co.). Zwischengespeichert in
    `cache` (Bewerbungsordner) oder .gui_ki.json. Leer, wenn die Seite nicht lesbar ist."""
    if cache is not None and cache.is_file():
        return cache.read_text(encoding="utf-8")
    data = laden(root)
    if link in (data.get("anzeigen") or {}):
        return data["anzeigen"][link]
    from .eigene_stelle import from_url
    try:
        text = from_url(link, fetcher).description.strip()[:12000] if link.startswith("http") else ""
    except Exception:   # Anzeige weg, robots.txt-Verbot, LinkedIn & Co., Netz: dann ohne Anzeigentext
        text = ""
    if cache is not None:
        cache.write_text(text, encoding="utf-8")
    else:
        data.setdefault("anzeigen", {})[link] = text
        _speichern(root, data)
    return text


def cv_text(cv: dict) -> str:
    """cv_master.yaml als kompakter YAML-Text (enthält keine persönlichen Daten)."""
    import io
    out = io.StringIO()
    y = YAML()
    y.width = 4096
    y.dump(cv or {}, out)
    return out.getvalue()[:15000]


# --- Aufruf mit Limit und Zähler ---
def fragen(root: Path, cfg: dict, prompt: str, effort: str = "medium", max_tokens: int = 6000, ask=None,
           heute: date | None = None, model: str | None = None, system: str | None = None) -> str:
    s = settings(cfg)
    llm.einstellen(cfg)
    key = schluessel()
    if not key:
        raise KiError("Kein API-Schlüssel hinterlegt (Einstellungen → KI).")
    if key == "lokal":
        key = None
    monat = (heute or date.today()).strftime("%Y-%m")
    if nutzung(root, heute)["aufrufe"] >= int(s["max_aufrufe_monat"]):
        raise KiError(f"Monatslimit von {s['max_aufrufe_monat']} KI-Aufrufen erreicht (config.yaml → "
                      "ki.max_aufrufe_monat).")
    usage: list = []
    extra = {"system": system} if system else {}
    antwort = (ask or llm._ask)(model or s["model"], prompt, effort=effort, max_tokens=max_tokens, api_key=key,
                                usage=usage, **extra)
    data = laden(root)
    m = data.setdefault("nutzung", {}).setdefault(monat, {"aufrufe": 0, "eingabe": 0, "ausgabe": 0})
    m["aufrufe"] += 1
    for ein, aus in usage:
        m["eingabe"] += ein
        m["ausgabe"] += aus
    _speichern(root, data)
    if not antwort:
        from . import ki_anbieter
        grund = ki_anbieter.grund(llm.ANBIETER) if llm.ANBIETER != "claude" and not ask else ""
        raise KiError(grund or "Die KI hat nicht geantwortet (Netz, Schlüssel oder Guthaben prüfen; Details im "
                               "Protokoll).")
    return antwort.strip()


def frage_funktion(root: Path, cfg: dict, ask=None):
    """Aufruf wie llm._ask für die Anforderungs-Erkennung (fit.ki_anforderungen) aus der Oberfläche: mit dem
    Schlüssel aus dem Schlüsselbund, Monatslimit und Zählung wie alle KI-Knöpfe. Fehler → None (dann bleibt die
    Stichwortsuche)."""
    def frage(model: str, prompt: str, effort: str = "low", max_tokens: int = 4000, system: str | None = None,
              **_):
        try:
            return fragen(root, cfg, prompt, effort, max_tokens, ask=ask, model=model, system=system)
        except KiError as exc:
            log.info("KI-Anforderungen nicht gelesen: %s", exc)
            return None
    return frage


# --- Anschreiben ---
def _kopf(stelle: dict, anzeige_text: str, cv: dict) -> str:
    anforderungen = ", ".join(stelle.get("anforderungen") or {}) or "nicht erkannt"
    return (f"STELLE: {stelle.get('title')} bei {stelle.get('company')}\n"
            f"ERKANNTE ANFORDERUNGEN: {anforderungen}\n\n"
            f"ANZEIGENTEXT:\n{anzeige_text[:8000] if anzeige_text else '(nicht verfügbar – nur Titel und Anforderungen)'}"
            f"\n\nLEBENSLAUF (einzige Quelle für Fakten über die Person):\n{cv_text(cv)}")


def anschreiben_prompt(stelle: dict, anzeige_text: str, cv: dict, ziel, grenzen: dict, englisch: bool = False) -> str:
    sprache = ("- Schreibe auf Englisch (professionelles, natürliches Business-Englisch, wie in englischen Cover Letters "
               "üblich), konkret statt Floskeln wie „I am writing to express my interest“. Platzhalter ebenfalls auf "
               "Englisch.\n" if englisch else
               "- Sachlich und konkret, Deutsch, Sie-Form gegenüber der Firma. Keine Floskeln wie „hiermit bewerbe ich "
               "mich“ oder „mit großem Interesse“.\n")
    return (
        "Du hilfst jemandem, ein Anschreiben für eine Bewerbung zu entwerfen. Die Person liest und überarbeitet den "
        "Entwurf selbst, bevor er ihn verschickt.\n\n"
        f"{_kopf(stelle, anzeige_text, cv)}\n\n"
        f"ZIEL: {ziel.zielrolle or stelle.get('title')}; gesucht wird {ziel.absicht or 'diese Stelle'}. "
        f"{ziel.ausblick}\n\n"
        "REGELN:\n"
        "- Nur Fakten aus dem Lebenslauf. Nichts erfinden: keine Projekte, Noten, Jahreszahlen oder Kenntnisse, die "
        "dort nicht stehen. Fehlt etwas, schreibe einen Platzhalter in [eckigen Klammern].\n"
        "- Gehe auf 2 bis 3 konkrete Anforderungen der Anzeige ein und belege sie mit Stationen oder Projekten aus "
        "dem Lebenslauf. Passt etwas nicht, lass es weg statt es schönzureden.\n"
        f"- Schreibe für Verfügbarkeit (ab wann, Stunden pro Woche) genau den Platzhalter {ZEITRAUM}.\n"
        f"- {grenzen['min_woerter']} bis {min(grenzen['max_woerter'], 320)} Wörter, 3 bis 4 Absätze, getrennt durch "
        f"eine Leerzeile. Höchstens {grenzen['max_ich_saetze']} Sätze beginnen mit „Ich“ bzw. „I“.\n"
        f"{sprache}"
        "- Ohne Anrede, ohne Grußformel, ohne Namen, Adresse oder Datum – die ergänzt das Programm.\n"
        "- Gib nur den Text des Anschreibens aus, ohne Überschrift und ohne Erklärung.")


GRUSS = re.compile(r"^(sehr geehrte|liebe|hallo|guten tag|mit freundlichen|viele grüße|beste grüße|freundliche "
                   r"grüße|dear\b|kind regards|best regards|yours sincerely|yours faithfully|sincerely)", re.I)


def aufraeumen(text: str) -> str:
    """Anrede- und Grußzeilen entfernen, falls die KI sie doch schreibt; Absätze normalisieren."""
    zeilen = [z for z in text.replace("\r\n", "\n").split("\n") if not GRUSS.match(z.strip())]
    while zeilen and not zeilen[-1].strip():
        zeilen.pop()
    if zeilen and len(zeilen[-1].split()) <= 3 and not zeilen[-1].strip().endswith("."):
        zeilen.pop()                                   # nachgestellter Name o. Ä.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(zeilen)).strip()


def anschreiben(root: Path, cfg: dict, stelle: dict, anzeige_text: str, cv: dict, ziel, zeitraum: str | None,
                ask=None, englisch: bool = False) -> str:
    from .anschreiben_check import limits
    text = aufraeumen(fragen(root, cfg, anschreiben_prompt(stelle, anzeige_text, cv, ziel, limits(cfg), englisch),
                             ask=ask))
    if englisch:
        return text.replace(ZEITRAUM, "[when you can start and how many hours per week]")
    return text.replace(ZEITRAUM, zeitraum) if zeitraum else text


# --- Gesprächsvorbereitung ---
def vorbereitung_prompt(stelle: dict, anzeige_text: str, cv: dict) -> str:
    return (
        "Du hilfst jemandem, sich auf ein Vorstellungsgespräch vorzubereiten.\n\n"
        f"{_kopf(stelle, anzeige_text, cv)}\n\n"
        "Schreibe auf Deutsch, knapp und konkret, genau in diesem Format (Überschriften mit „## “, Punkte mit „- “):\n"
        "## Wahrscheinliche Fragen\n5 bis 7 Fragen, die zu dieser Stelle gestellt werden dürften, je mit einem kurzen "
        "Hinweis, welches Beispiel aus dem Lebenslauf passt.\n"
        "## Deine Beispiele\n3 Beispiele aus Stationen oder Projekten des Lebenslaufs, je in einem Satz nach dem "
        "Muster Situation – Aufgabe – Vorgehen – Ergebnis. Nur, was im Lebenslauf steht.\n"
        "## Ehrlich einordnen\nAnforderungen der Anzeige, die der Lebenslauf nicht belegt, und wie man offen damit "
        "umgeht (was man kennt, wie man es lernt).\n"
        "## Fragen an die Firma\n4 gute Fragen zu Team, Aufgaben in den ersten Wochen und Entwicklung.\n"
        "Nichts erfinden. Keine Einleitung, kein Schlusswort.")


def vorbereitung(root: Path, cfg: dict, link: str, stelle: dict, anzeige_text: str, cv: dict,
                 ask=None, notizen: str = "") -> str:
    """`notizen`: eigene Notizen aus früheren Gesprächen bei derselben Firma (gui_gespraech.frueher_notizen)."""
    prompt = vorbereitung_prompt(stelle, anzeige_text, cv)
    if notizen:
        prompt += ("\n\nEIGENE NOTIZEN AUS FRÜHEREN GESPRÄCHEN BEI DIESER FIRMA (berücksichtige, was damals gefragt "
                   f"wurde oder offen blieb):\n{notizen[:3000]}")
    text = fragen(root, cfg, prompt, ask=ask)
    data = laden(root)
    data.setdefault("vorbereitung", {})[link] = text
    _speichern(root, data)
    return text


def als_html(text: str, esc) -> str:
    """„## Überschrift“ und „- Punkt“ als kleines HTML; alles andere als Absatz."""
    out, liste = [], False
    for zeile in text.splitlines():
        z = zeile.strip()
        if z.startswith(("- ", "* ")) or re.match(r"^\d+[.)] ", z):
            if not liste:
                out.append("<ul>")
                liste = True
            out.append(f"<li>{esc(re.sub(r'^(?:[-*]|\d+[.)]) ', '', z).replace('**', ''))}</li>")
            continue
        if liste:
            out.append("</ul>")
            liste = False
        if z.startswith("#"):
            out.append(f"<h3>{esc(z.lstrip('#').strip())}</h3>")
        elif z:
            out.append(f"<p>{esc(z.replace('**', ''))}</p>")
    if liste:
        out.append("</ul>")
    return "".join(out)


# --- Lebenslauf auf die Stelle zuschneiden ---
def _sichtbare_projekte(cv: dict) -> list[dict]:
    return [p for p in cv.get("projekte") or [] if isinstance(p, dict) and p.get("im_cv") is not False]


def lebenslauf_prompt(stelle: dict, anzeige_text: str, cv: dict, max_projekte: int) -> str:
    stationen = "\n".join(
        f"Station {i}: {s.get('rolle')} bei {s.get('organisation')}\n"
        + "\n".join(f"  Aufgabe {j}: {a}" for j, a in enumerate(s.get("aufgaben") or []))
        for i, s in enumerate(cv.get("stationen") or []) if isinstance(s, dict))
    projekte = "\n".join(f"Projekt {i}: {p.get('name')} – {p.get('beschreibung', '')} "
                         f"({', '.join(p.get('technologien') or [])})" for i, p in enumerate(_sichtbare_projekte(cv)))
    return (
        "Du schneidest einen Lebenslauf auf eine Stelle zu. Du darfst nur auswählen, ordnen und den Profiltext "
        "umformulieren – nichts hinzuerfinden.\n\n"
        f"{_kopf(stelle, anzeige_text, cv)}\n\n"
        f"AUFGABEN JE STATION (mit Nummern):\n{stationen or '(keine)'}\n\nPROJEKTE (mit Nummern):\n{projekte or '(keine)'}"
        "\n\nAntworte nur mit JSON:\n"
        '{"profil": "...", "aufgaben": {"0": [2, 0, 1]}, "projekte": [1, 0]}\n'
        "- profil: 2 bis 3 Sätze (höchstens 450 Zeichen) in der dritten Person ohne Namen, in der Sprache des "
        "Lebenslaufs, wie der bisherige Profiltext. Betone, was zur Stelle passt. Nenne nur Kenntnisse, Stationen und Ziele, die im Lebenslauf "
        "stehen.\n"
        "- aufgaben: je Station die Nummern ihrer Aufgaben, wichtigste für diese Stelle zuerst; unpassende darfst "
        "du weglassen, aber behalte mindestens 3 (oder alle, wenn es weniger sind).\n"
        f"- projekte: Nummern der Projekte, passendste zuerst, höchstens {max_projekte}.")


def lebenslauf(root: Path, cfg: dict, stelle: dict, anzeige_text: str, cv: dict, max_projekte: int,
               ask=None) -> dict:
    """KI-Zuschnitt {profil, aufgaben, projekte} (noch ungeprüft, siehe cv_build.ki_anwenden). Zwischengespeichert
    je Stelle und Lebenslauf-Stand, damit „Mappe bauen“ nach „Nur Lebenslauf“ nicht noch einmal fragt."""
    import hashlib
    schl = hashlib.sha256(json.dumps([cv, stelle.get("id"), stelle.get("anforderungen"), anzeige_text[:500]],
                                     sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:24]
    data = laden(root)
    if schl in (data.get("zuschnitt") or {}):
        return data["zuschnitt"][schl]
    antwort = llm.json_aus(fragen(root, cfg, lebenslauf_prompt(stelle, anzeige_text, cv, max_projekte), ask=ask))
    if not isinstance(antwort, dict):
        raise KiError("Die KI hat keinen lesbaren Zuschnitt geliefert; der Lebenslauf ist ohne KI zugeschnitten.")
    data = laden(root)
    data.setdefault("zuschnitt", {})[schl] = antwort
    _speichern(root, data)
    return antwort


def unbelegt(text: str, cv: dict, begriffe: dict) -> list[str]:
    """Fit-Begriffe, die `text` nennt, der Lebenslauf aber nicht belegt (Schutz gegen erfundene Kenntnisse)."""
    from .cv_data import covered_terms
    from .scoring import has
    belegt = covered_terms(cv, begriffe)
    return [b for b, syn in begriffe.items() if b not in belegt and any(has(text.lower(), s) for s in [b, *(syn or [])])]


# --- Mit KI ausfüllen: Profiltext im Master-CV ---
def profiltext(root: Path, cfg: dict, cv: dict, ziel: str = "", ask=None) -> str:
    text = fragen(root, cfg, (
        "Schreibe den Profiltext (Kurzprofil oben im Lebenslauf) für diesen Lebenslauf: 2 bis 3 Sätze, höchstens "
        "450 Zeichen, dritte Person ohne Namen und ohne „Ich“, sachlich. Nenne Studium, praktische Erfahrung und die "
        "stärksten Kenntnisse – nur, was im Lebenslauf steht – und zum Schluss das berufliche Ziel"
        + (f" ({ziel})" if ziel else "") + ".\n\nLEBENSLAUF:\n" + cv_text({**cv, "profil": ""})
        + "\n\nGib nur den Profiltext aus."), effort="low", max_tokens=4000, ask=ask)
    text = text.strip().strip('"„“').strip()
    fremd = unbelegt(text, cv, cfg["fit"]["begriffe"])
    if fremd:
        raise KiError(f"Der KI-Vorschlag nannte {', '.join(fremd[:3])}, das dein Master-CV nicht belegt – verworfen.")
    return text


# --- Mit KI ausfüllen: Nachfrage-Mail ---
def nachfassen(root: Path, cfg: dict, row: dict, titel: str, tage: int, name: str, ask=None) -> tuple[str, str]:
    """(Betreff, Text) einer kurzen, höflichen Nachfrage. Der Name kommt erst lokal hinein (Platzhalter [Name])."""
    antwort = llm.json_aus(fragen(root, cfg, (
        "Schreibe eine kurze, höfliche Nachfrage zum Stand einer Bewerbung auf Deutsch (Sie-Form, 60 bis 110 Wörter, "
        "ohne Floskeln und ohne Druck). Unterschreibe mit genau [Name].\n\n"
        f"FIRMA: {row.get('firma')}\nSTELLE: {titel}\nBEWORBEN AM: {row.get('datum')} (vor {tage} Tagen)\n\n"
        'Antworte nur mit JSON: {"betreff": "...", "text": "..."}'), effort="low", max_tokens=4000, ask=ask))
    if not isinstance(antwort, dict) or not antwort.get("betreff") or not antwort.get("text"):
        raise KiError("Die KI hat keinen lesbaren Entwurf geliefert.")
    text = str(antwort["text"]).replace("[Name]", name or "[Name]")
    data = laden(root)
    data.setdefault("nachfassen", {})[row.get("link", "")] = [str(antwort["betreff"]), text]
    _speichern(root, data)
    return str(antwort["betreff"]), text


def nachfass_entwuerfe(root: Path) -> dict[str, tuple[str, str]]:
    return {k: tuple(v) for k, v in (laden(root).get("nachfassen") or {}).items()}


# --- Mit KI ausfüllen: Suchprofil ---
def zentrum(ort):
    from .location import zentrum as wohnort
    return wohnort(ort)


def suchprofil_vorschlag(root: Path, cfg: dict, name: str, wunsch: str, cv: dict, max_begriffe: int,
                         ask=None) -> dict:
    """Formularfelder für ein Suchprofil (gui_suchprofile) aus einer kurzen Beschreibung des Wunsches."""
    fach = ", ".join(list((cfg.get("filter") or {}).get("fach") or {})[:30])
    beispiel = next(iter((cfg.get("profile") or {}).values()), {})
    antwort = llm.json_aus(fragen(root, cfg, (
        "Lege ein Suchprofil für einen Job-Monitor an, der deutsche Stellenbörsen (Bundesagentur für Arbeit, "
        f"Stellenwerk) durchsucht. Gesucht wird im Raum {zentrum(cfg.get('ort')) or 'Deutschland'}.\n\n"
        f"NAME DES PROFILS: {name or '(frei)'}\nWAS GESUCHT WIRD: {wunsch}\n\n"
        f"GEMEINSAMES FACHGEBIET DER ANDEREN PROFILE (Stichwörter): {fach}\n"
        f"BEISPIEL EINES BESTEHENDEN PROFILS (Rollen-Wörter): {json.dumps(beispiel.get('rollen') or {}, ensure_ascii=False)}\n\n"
        "LEBENSLAUF (nur zur Einordnung von Zielrolle und Absicht):\n" + cv_text(cv)[:5000] + "\n\n"
        "Antworte nur mit JSON:\n"
        '{"name": "...", "stufe": "ausbildung|praktikum|werkstudent|abschlussarbeit|einstieg|minijob|berufserfahren", '
        '"art": "studium|ausbildung|arbeit|minijob|alle", "zielrolle": "...", "absicht": "...", "ausblick": "...", '
        '"rollen": {"werkstudent": 30}, "such_bundesagentur": ["..."], "such_stellenwerk": ["..."], '
        '"fachgebiet": "gemeinsam|eigen", "fach": {"stichwort": 10}, "fit_begriffe": {"Begriff": ["synonym"]}}\n'
        "- stufe: die Karrierestufe der gesuchten Stellen.\n"
        "- art: studium = Werkstudent/Praktikum/Abschlussarbeit, ausbildung = Ausbildung/duales Studium, "
        "arbeit = feste Stelle (Einstieg oder mit Erfahrung), minijob = Minijob, Aushilfe oder Nebenjob auf "
        "geringfügiger Basis.\n"
        "- rollen: Wörter, die im Stellentitel stehen (klein geschrieben), Punkte 15 bis 30.\n"
        f"- such_bundesagentur und such_stellenwerk: je höchstens {max_begriffe} kurze Suchbegriffe, wie man sie in "
        "eine Jobsuche tippt (z. B. „Werkstudent Data Engineering“).\n"
        "- fachgebiet: gemeinsam nur, wenn das gemeinsame Fachgebiet passt; für jedes andere Fach (z. B. BWL, Pflege, "
        "Maschinenbau, Marketing) eigen mit 6 bis 15 Fach-Stichwörtern "
        "(klein, so wie sie in Anzeigentiteln stehen, Punkte 4 bis 14).\n"
        "- zielrolle, absicht, ausblick: für Anschreiben („… und suche {absicht}.“), sachlich.\n"
        "- fit_begriffe: nur Kenntnisse, die in solchen Anzeigen oft verlangt werden und im gemeinsamen Fachgebiet "
        "fehlen; sonst leer."), effort="medium", max_tokens=8000, ask=ask))
    if not isinstance(antwort, dict):
        raise KiError("Die KI hat keinen lesbaren Vorschlag geliefert.")

    def zeilen(d) -> str:
        return "\n".join(f"{k}: {v}" for k, v in (d or {}).items() if isinstance(v, (int, float))) \
            if isinstance(d, dict) else ""
    out = {
        "name": str(antwort.get("name") or name), "art": antwort.get("art") if antwort.get("art") in
        ("studium", "ausbildung", "arbeit", "minijob", "alle") else "studium", "zielrolle": str(antwort.get("zielrolle") or ""),
        "stufe": antwort.get("stufe") if antwort.get("stufe") in STUFEN else "",
        "absicht": str(antwort.get("absicht") or ""), "ausblick": str(antwort.get("ausblick") or ""),
        "rollen": zeilen(antwort.get("rollen")),
        "such_bundesagentur": "\n".join(map(str, (antwort.get("such_bundesagentur") or [])[:max_begriffe])),
        "such_stellenwerk": "\n".join(map(str, (antwort.get("such_stellenwerk") or [])[:max_begriffe])),
        "fachgebiet": "eigen" if antwort.get("fachgebiet") == "eigen" and antwort.get("fach") else "gemeinsam",
        "fach": zeilen(antwort.get("fach")),
        "fit_begriffe": "\n".join(f"{k}: {', '.join(map(str, v or []))}"
                                  for k, v in (antwort.get("fit_begriffe") or {}).items()
                                  if isinstance(v, list)) if isinstance(antwort.get("fit_begriffe"), dict) else "",
    }
    return out


# --- Lücken → Lernplan ---
def lernplan(root: Path, cfg: dict, zeilen: list[dict], cv: dict, pfade: dict, heute: date | None = None,
             ask=None) -> str:
    """Lernplan für die teuersten Lücken (Zeilen aus gui_luecken.analyse) – gespeichert in .gui_ki.json."""
    luecken = [z for z in zeilen if z["gewinn"]][:8]
    if not luecken:
        raise KiError("Keine Lücken mit Fit-Gewinn – dein Lebenslauf deckt die gefundenen Stellen schon gut ab.")
    liste = "\n".join(
        f"- {z['term']}: in {z['gefordert']} Anzeigen gefordert, {z['optional']} gewünscht; Fit-Gewinn bis zu "
        f"{max(z['gewinn'].values()):.0f} Punkte; dein Stand: {'fehlt' if z['stand'] is None else z['stand']}"
        + (f"; bekannte Vorschläge: {', '.join(v['name'] for v in pfade.get(z['term'], [])[:3])}"
           if pfade.get(z['term']) else "") for z in luecken)
    text = fragen(root, cfg, (
        f"Erstelle einen realistischen Lernplan für eine Person auf Jobsuche (heute: {(heute or date.today()):%d.%m.%Y}). "
        "Er studiert und arbeitet nebenbei als Werkstudent, hat also etwa 4 bis 6 Stunden pro Woche.\n\n"
        f"LÜCKEN (aus den Anforderungen gefundener Stellen, wichtigste zuerst):\n{liste}\n\n"
        f"LEBENSLAUF:\n{cv_text(cv)[:6000]}\n\n"
        "Schreibe auf Deutsch, knapp, genau in diesem Format (Überschriften mit „## “, Punkte mit „- “):\n"
        "## Reihenfolge\n3 bis 5 Schritte, je mit Zeitraum (z. B. „Woche 1–4“), was genau (Zertifikat oder kleines "
        "Projekt) und warum zuerst. Baue auf dem auf, was er schon kann.\n"
        "## Projekt für den Lebenslauf\nEin konkretes Projekt, das mehrere Lücken auf einmal schließt, mit 3 bis 5 "
        "Teilschritten.\n"
        "## Hinweise\nWas sich zuerst im Fit bemerkbar macht; Prüfungsnamen und Preise vor dem Buchen beim Anbieter "
        "prüfen.\nNichts über die Person erfinden. Keine Einleitung."), effort="medium", max_tokens=8000, ask=ask)
    data = laden(root)
    data["lernplan"] = {"text": text, "datum": (heute or date.today()).isoformat()}
    _speichern(root, data)
    return text


def gespeicherter_lernplan(root: Path) -> dict | None:
    return laden(root).get("lernplan")


# --- Firmen-Kurzprofil fürs Gespräch ---
def firmen_text(urls: list[str], fetcher) -> str:
    """Haupttext der genannten Seiten (Startseite, Karriereseite) – robots.txt, nie LinkedIn & Co."""
    from urllib.parse import urlsplit

    from .eigene_stelle import BLOCKED_HOSTS, _main_text
    teile, gesehen = [], set()
    for url in urls:
        if not url or not url.startswith("http") or url in gesehen:
            continue
        gesehen.add(url)
        if any(b in urlsplit(url).netloc.lower() for b in BLOCKED_HOSTS):
            continue
        try:
            teile.append(_main_text(fetcher.get(url).text)[:5000])
        except Exception:   # Seite nicht lesbar: dann ohne
            continue
    return "\n\n---\n\n".join(t for t in teile if t.strip())


def firmenprofil(root: Path, cfg: dict, firma: str, seiten: str, stellen: list[dict], heute: date | None = None,
                 ask=None) -> str:
    """Kurzprofil aus Webseiten-Text und den gespeicherten Stellen der Firma – gespeichert in .gui_ki.json."""
    from collections import Counter
    begriffe = Counter(b for s in stellen for b in (s.get("anforderungen") or {}))
    stellen_text = "\n".join(f"- {s.get('title')}" for s in stellen[:12]) or "(keine gespeichert)"
    technik = ", ".join(f"{b} ({n}×)" for b, n in begriffe.most_common(12)) or "(unbekannt)"
    text = fragen(root, cfg, (
        f"Erstelle ein kurzes Firmenprofil von „{firma}“ zur Vorbereitung auf ein Vorstellungsgespräch.\n\n"
        f"TEXT VON DER WEBSEITE DER FIRMA:\n{seiten[:9000] or '(nicht lesbar)'}\n\n"
        f"STELLEN DIESER FIRMA, DIE DER JOB-MONITOR GEFUNDEN HAT:\n{stellen_text}\n"
        f"HÄUFIGE ANFORDERUNGEN IN DIESEN STELLEN: {technik}\n\n"
        "Schreibe auf Deutsch, knapp, genau in diesem Format (Überschriften mit „## “, Punkte mit „- “):\n"
        "## Was die Firma macht\n2 bis 4 Punkte: Geschäft, Kunden, Größe/Standorte – nur, was im Text steht.\n"
        "## Technik und Themen\nWas in ihren Stellen immer wieder verlangt wird und was das über die Arbeit verrät.\n"
        "## Gute Gesprächsthemen\n3 Punkte, mit denen man zeigt, dass man sich vorbereitet hat.\n"
        "## Noch herausfinden\nWas der Text nicht verrät und man im Gespräch fragen kann.\n"
        "Nichts erfinden: Steht etwas nicht im Text, schreib „laut Webseite nicht ersichtlich“. Keine Einleitung."),
        effort="medium", max_tokens=6000, ask=ask)
    data = laden(root)
    data.setdefault("firmenprofil", {})[firma.lower()] = {"text": text, "datum": (heute or date.today()).isoformat()}
    _speichern(root, data)
    return text


def firmenprofile(root: Path) -> dict[str, dict]:
    return laden(root).get("firmenprofil") or {}
