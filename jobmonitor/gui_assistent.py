"""Einrichtungs-Assistent (/einrichten): in fünf Schritten von null zur ersten Suche, ohne Dateien von Hand.

1. Persönliche Angaben → cv/profile.yaml (bleibt lokal, geht nie an eine KI)
2. KI-Schlüssel (optional) → Einstellungen → KI
3. Wohnort → Fahrzeiten von der KI (wohnort.py) oder nur der Ort
4. Was suchst du? → Suchprofil von der KI (ki.suchprofil_vorschlag) oder aus der Karrierestufen-Vorlage
5. Lebenslauf → PDF hochladen: Text wird lokal gelesen, persönliche Angaben aus Schritt 1 sowie E-Mail-Adressen,
   Telefonnummern, Links und Geburtsdaten werden VOR dem Senden entfernt; die KI macht daraus den Master-CV, der
   danach noch einmal auf persönliche Daten geprüft wird (cv_data.check_no_personal_data). Ohne KI: Master-CV von Hand.
Fortschritt lokal in .gui_eingerichtet.json.
"""
from __future__ import annotations

import io
import json
import re
from datetime import date
from html import escape
from pathlib import Path

from . import gui_master as gm
from . import gui_profil as gp
from . import gui_suchprofile as gsp
from . import gui_ki as gki
from . import hochschulboersen, ki, llm, mailzugang, suchprofil, wohnort
from .config import load_companies, load_config
from .cv_data import EMAIL_RE, FORBIDDEN_KEYS, PHONE_RE, CvDataError, check_no_personal_data

DATEI = ".gui_eingerichtet.json"
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
GEBURT_RE = re.compile(r"^.*\b(?:geb(?:oren|\.)|geburtsdatum|date of birth)\b.*$", re.I | re.M)
MAX_PDF = 10 * 1024 * 1024


class AssistentError(Exception):
    pass


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def laden(root: Path) -> dict:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def merken(root: Path, **werte) -> None:
    data = {**laden(root), **werte}
    (root / DATEI).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def schritte(root: Path, cfg: dict, ki_an: bool) -> dict[str, bool]:
    profil = gp.load(root) if (root / "cv" / "profile.yaml").exists() else {}
    return {"person": bool(gp.get(profil, "name")), "ki": ki_an,
            "wohnort": bool(laden(root).get("wohnort") or (cfg.get("ort") or {}).get("zentrum")),
            "suche": any(p.enabled for p in suchprofil.alle(cfg)),
            "lebenslauf": bool(gm.load(root)), "mail": bool(mailzugang.laden(root).get("benutzer"))}


# --- Lebenslauf-Import ---
def pdf_text(daten: bytes) -> str:
    from pypdf import PdfReader
    try:
        return "\n".join((s.extract_text() or "") for s in PdfReader(io.BytesIO(daten)).pages)[:30000]
    except Exception as exc:   # kaputte oder verschlüsselte PDFs
        raise AssistentError(f"Das PDF ließ sich nicht lesen ({exc.__class__.__name__}).") from None


def schwaerzen(text: str, profil: dict) -> str:
    """Persönliche Angaben entfernen, bevor der Text an die KI geht."""
    werte = [gp.get(profil, k) for k in ("name", "email", "telefon", "adresse.strasse", "adresse.plz",
                                         "links.linkedin", "links.github", "geburtsdatum")]
    teile = [str(w).strip() for w in werte if w and len(str(w).strip()) >= 3]
    name = str(gp.get(profil, "name") or "")
    teile += [t for t in name.split() if len(t) >= 3]                      # Vor- und Nachname auch einzeln
    for teil in sorted(set(teile), key=len, reverse=True):
        text = re.sub(re.escape(teil), "[entfernt]", text, flags=re.I)
    text = GEBURT_RE.sub("[entfernt]", text)
    for muster in (EMAIL_RE, URL_RE, PHONE_RE):
        text = muster.sub("[entfernt]", text)
    return text


def _ohne_persoenliches(wert):
    if isinstance(wert, dict):
        return {k: _ohne_persoenliches(v) for k, v in wert.items() if str(k).lower() not in FORBIDDEN_KEYS}
    if isinstance(wert, list):
        return [_ohne_persoenliches(v) for v in wert]
    return wert


def import_prompt(text: str) -> str:
    return ("Übertrage diesen Lebenslauf in das JSON-Format unten. Nur Inhalte aus dem Text, nichts erfinden, nichts "
            "beschönigen. Keine persönlichen Daten (Name, Adresse, Telefon, E-Mail, Geburtsdatum, Foto) – mit "
            "[entfernt] markierte Stellen weglassen. Daten als MM/JJJJ, wenn erkennbar.\n\n"
            '{"profil": "2–3 Sätze aus dem Kurzprofil, falls vorhanden, sonst leer",\n'
            ' "stationen": [{"rolle": "", "organisation": "", "von": "MM/JJJJ", "bis": "MM/JJJJ oder leer", '
            '"aufgaben": [""]}],\n'
            ' "ausbildung": [{"abschluss": "", "institution": "", "von": "", "bis": "", "punkte": [""]}],\n'
            ' "projekte": [{"name": "", "zeitraum": "", "status": "erreicht", "beschreibung": "", '
            '"technologien": [""]}],\n'
            ' "zertifikate": [{"name": "", "zusatz": "", "datum": "", "status": "erreicht"}],\n'
            ' "kenntnisse": [{"kategorie": "", "eintraege": [{"name": "", "level": "Grundkenntnisse|gut|sehr gut"}]}],\n'
            ' "sprachen": [{"sprache": "", "niveau": "z. B. C1 oder Muttersprache"}],\n'
            ' "interessen": [""]}\n\n'
            "Antworte nur mit dem JSON.\n\nLEBENSLAUF:\n" + text)


def lebenslauf_import(root: Path, cfg: dict, pdf: bytes, ask=None) -> dict:
    if len(pdf) > MAX_PDF:
        raise AssistentError("Das PDF ist größer als 10 MB.")
    text = pdf_text(pdf)
    if len(text.strip()) < 200:
        raise AssistentError("Im PDF steht kaum lesbarer Text (eingescannt?). Bitte den Master-CV von Hand ausfüllen.")
    profil = gp.load(root) if (root / "cv" / "profile.yaml").exists() else {}
    data = llm.json_aus(ki.fragen(root, cfg, import_prompt(schwaerzen(text, profil)), effort="medium",
                                  max_tokens=16000, ask=ask))
    if not isinstance(data, dict):
        raise ki.KiError("Die KI hat keinen lesbaren Lebenslauf geliefert.")
    data = _ohne_persoenliches({k: v for k, v in data.items() if k in {f["key"] for f in gm.SCHEMA}})
    try:
        check_no_personal_data(data)
    except CvDataError as exc:
        raise AssistentError(f"Im Ergebnis stehen noch persönliche Daten – nicht gespeichert ({exc}).") from None
    gm.save(root, data)
    return data


# --- Suchprofil ---
def suchprofil_anlegen(root: Path, cfg: dict, wunsch: str, stufe: str, ki_an: bool, ask=None) -> str:
    wunsch = (wunsch or "").strip()
    if not wunsch:
        raise AssistentError("Bitte kurz beschreiben, was du suchst.")
    vorlage = suchprofil.STUFEN.get(stufe) or suchprofil.STUFEN["werkstudent"]
    if ki_an:
        cv = gm.load(root)
        v = ki.suchprofil_vorschlag(root, cfg, "", f"{wunsch} ({vorlage['name']})", cv,
                                    suchprofil.MAX_BEGRIFFE, ask=ask)
        form = {**v, "enabled": "1", "stufe": stufe or v.get("stufe", "")}
        if form["stufe"] == "minijob":            # Minijob-Suche bei der Bundesagentur (arbeitszeit=mj)
            form["art"] = "minijob"
    else:
        woerter = [w.strip() for w in re.split(r"[,\n]", wunsch) if w.strip()]
        if len(woerter) < 3:
            raise AssistentError("Ohne KI bitte mindestens drei Stichwörter zu deinem Fach, mit Komma getrennt "
                                 "(z. B. Pflege, Gesundheit, Klinik).")
        form = {"name": woerter[0][:40], "enabled": "1", "art": vorlage["art"], "stufe": stufe,
                "rollen": "\n".join(f"{k}: {p}" for k, p in vorlage["rollen"].items()),
                "such_bundesagentur": "\n".join(f"{vorlage['name'].split(' /')[0]} {w}".strip()
                                                for w in re.split(r"[,\n]", wunsch) if w.strip())[:2000],
                "such_stellenwerk": "\n".join(woerter[:suchprofil.MAX_BEGRIFFE]), "fachgebiet": "eigen",
                "fach": "\n".join(f"{w.strip().lower()}: 10" for w in re.split(r"[,\n]", wunsch) if w.strip()),
                "fit_begriffe": "", "zielrolle": "", "absicht": "", "ausblick": ""}
    try:
        key, daten = gsp.aus_formular(form, cfg)
    except gsp.SuchprofilError as exc:
        raise AssistentError(str(exc)) from None
    gsp.speichern(root, key, daten)
    return daten["name"]


def _boersen_html(root: Path, cfg: dict, hidden: str) -> str:
    """Stellenwerk-Portale in Reichweite zum Ankreuzen (nichts vorausgewählt, siehe hochschulboersen.py)."""
    ort = cfg.get("ort") or {}
    try:
        da = {str(h.get("karriereseite_url", "")).rstrip("/").rsplit("/", 1)[-1]
              for h in (load_companies(root / "companies.yaml").get("hochschulen") or [])}
    except OSError:
        da = set()
    liste = [(k, n) for k, n in hochschulboersen.vorschlaege(ort.get("zentrum", ""), ort.get("fahrzeiten"),
                                                             ort.get("max_fahrzeit_min", 60)) if k not in da]
    if not liste:
        return ""
    boxen = "".join(f'<label class="check"><input type="checkbox" name="portal_{k}" value="1"> Stellenwerk {esc(n)}'
                    f'</label>' for k, n in liste)
    return (f'<form method="post" action="/einrichten" style="margin-top:12px">{hidden}<input type="hidden" '
            f'name="aktion" value="hochschulen"><p><b>Jobbörsen von Hochschulen in deiner Nähe</b> (Werkstudenten-, '
            f'Praktikums- und Einstiegsstellen):</p><div class="row" style="gap:6px 16px;flex-wrap:wrap">{boxen}</div>'
            f'<p class="muted">Hinweis: stellenwerk.de beantwortet die Abfrage seiner Regeln für Programme (robots.txt) '
            f'mit einer Sperrmeldung statt mit Regeln. Die Seiten sind öffentlich; die App fragt sparsam ab. Ob du sie '
            f'nutzt, entscheidest du – deshalb ist nichts vorausgewählt.</p><button class="ghost small">Ausgewählte '
            f'einschalten</button></form>')


# --- Seite ---
def render(root: Path, token: str, ki_an: bool, message: str = "") -> str:
    cfg = load_config(root / "config.yaml")
    st = schritte(root, cfg, ki_an)
    profil = gp.load(root) if (root / "cv" / "profile.yaml").exists() else {}
    hidden = f'<input type="hidden" name="token" value="{token}">'

    def karte(nr: int, key: str, titel: str, inhalt: str) -> str:
        fertig = st[key]
        return (f'<div class="card schritt{" fertig" if fertig else ""}"><div class="head"><h2>{nr}. {esc(titel)}</h2>'
                f'<span class="{"ok" if fertig else "muted"}">{"✓ erledigt" if fertig else "offen"}</span></div>'
                f'{inhalt}</div>')

    felder = "".join(f'<div><label for="{k}">{esc(t)}</label><input id="{k}" name="{k}" '
                     f'value="{esc(gp.get(profil, k) or "")}"{" required" if k == "name" else ""}></div>'
                     for k, t in (("name", "Name"), ("email", "E-Mail"), ("telefon", "Telefon"),
                                  ("adresse.strasse", "Straße und Hausnummer"), ("adresse.plz", "PLZ"),
                                  ("adresse.ort", "Ort")))
    person = (f'<form method="post" action="/einrichten">{hidden}<input type="hidden" name="aktion" value="person">'
              f'<div class="grid2">{felder}</div><p class="muted">Steht nur im Kopf deiner PDFs. Bleibt auf diesem '
              f'Rechner, geht nie an eine KI.</p><button class="small">Speichern</button></form>')
    kschritt = ('<p class="ok">KI ist eingerichtet: Suchprofil und Lebenslauf füllt sie für dich aus.</p>' if ki_an else
                '<p><b>Empfohlen:</b> Mit KI holst du das meiste aus der App heraus – genauerer Fit, Suchprofil und '
                'Lebenslauf werden für dich ausgefüllt, Anschreiben und Gesprächsvorbereitung entworfen. Ohne geht alles '
                'auch, nur mit mehr Tipparbeit.</p>' + gki.wahl_html("einrichten") +
                '<p class="muted">Die KI nutzt <b>deinen eigenen</b> Zugang beim Anbieter – die App hat keinen '
                'eigenen, und deine Daten gehen direkt dorthin, nie an den Entwickler. Möglich sind auch OpenAI, '
                'Mistral oder Ollama (kostenlos auf deinem Rechner, unter Einstellungen → KI).</p>'
                '<a class="btn ghost small" href="/einstellungen#ki">Schlüssel hinterlegen</a>')
    zentrum = (cfg.get("ort") or {}).get("zentrum") or ""
    ort = (f'<form method="post" action="/einrichten" class="row" style="gap:8px;flex-wrap:wrap">{hidden}'
           f'<input type="hidden" name="aktion" value="wohnort"><input name="stadt" required maxlength="40" '
           f'value="{esc(zentrum or gp.get(profil, "adresse.ort") or "")}" placeholder="z. B. Leipzig" style="width:220px">'
           f'<button class="small"{" data-ki=\"KI schätzt die Fahrzeiten …\"" if ki_an else ""}>Übernehmen</button></form>'
           f'<p class="muted">{"Die KI schätzt die Fahrzeiten in die Umgebung (nur der Städtename wird gesendet)." if ki_an else "Ohne KI zählen Stellen in diesem Ort und remote; Umgebungsorte kannst du später ergänzen."}</p>')
    ort += _boersen_html(root, cfg, hidden) if zentrum else ""
    stufen = "".join(f'<option value="{k}">{esc(v["name"])}</option>' for k, v in suchprofil.STUFEN.items())
    suche = (f'<form method="post" action="/einrichten">{hidden}<input type="hidden" name="aktion" value="suche">'
             f'<label for="wunsch">Was suchst du? In ein, zwei Sätzen</label><textarea id="wunsch" name="wunsch" '
             f'rows="2" required placeholder="{"z. B. Werkstudent im Controlling oder Finanzbereich, gern mit Excel und SAP" if ki_an else "Ohne KI: mindestens drei Stichwörter mit Komma, z. B. Controlling, Finanzen, Reporting"}"></textarea><label for="stufe">Karrierestufe</label><select id="stufe" name="stufe">{stufen}'
             f'</select><div class="row" style="margin-top:10px"><button class="small"'
             f'{" data-ki=\"KI legt dein Suchprofil an …\"" if ki_an else ""}>Suchprofil anlegen</button>'
             f'<a href="/einstellungen" class="muted">später in den Einstellungen anpassen</a></div></form>')
    cv = (f'<form method="post" action="/einrichten" enctype="multipart/form-data">{hidden}'
          f'<input type="hidden" name="aktion" value="lebenslauf"><input type="file" name="pdf" accept="application/pdf" '
          f'required><div class="row" style="margin-top:10px"><button class="small" data-ki="KI liest deinen '
          f'Lebenslauf …">Lebenslauf übernehmen</button></div></form><p class="muted">Vor dem Senden entfernt die App '
          f'Name, Adresse, Telefon, E-Mail, Links und Geburtsdatum aus dem Text. Danach prüfst du alles im '
          f'<a href="/master">Master-CV</a>.</p>' if ki_an else
          '<p>Trag deine Stationen, Ausbildung und Kenntnisse im Master-CV ein – daraus entstehen alle Lebensläufe.</p>'
          '<a class="btn small" href="/master">Master-CV ausfüllen</a>')
    fertig = (f'<form method="post" action="/einrichten">{hidden}<input type="hidden" name="aktion" value="fertig">'
              f'<label class="check"><input type="checkbox" name="zeitplan" value="1" checked> Täglich automatisch '
              f'suchen (auf diesem Rechner)</label><div class="row" style="margin-top:10px"><button>Fertig – zur '
              f'Stellenliste</button></div></form>')
    offen = sum(1 for k, v in st.items() if not v and k not in ("ki", "mail"))
    return (f'<h1>Willkommen bei Job-Monitor</h1><p class="sub">In fünf Schritten zur ersten Suche, dazu optional KI und Postfach. '
            f'{"Alles Wichtige erledigt." if not offen else f"Noch {offen} Schritt(e) offen."}</p>{message}'
            + karte(1, "person", "Deine Angaben", person) + karte(2, "ki", "KI (optional)", kschritt)
            + karte(3, "wohnort", "Wohnort", ort) + karte(4, "suche", "Was suchst du?", suche)
            + karte(5, "lebenslauf", "Lebenslauf", cv)
            + karte(6, "mail", "Postfach (optional)", mailzugang.formular(root, token, esc))
            + f'<div class="card"><h2>Los geht’s</h2>{fertig}</div>')


CSS = ".schritt.fertig h2 { color: var(--muted); } .schritt .head .ok { font-weight: 500; }" + gki.WAHL_CSS


def ausfuehren(root: Path, form: dict, uploads: dict, ki_an: bool, ask=None) -> str:
    """Einen Schritt ausführen; gibt die Erfolgsmeldung zurück (AssistentError/KiError bei Problemen)."""
    aktion = form.get("aktion", "")
    cfg = load_config(root / "config.yaml")
    if aktion == "person":
        if not (form.get("name") or "").strip():
            raise AssistentError("Bitte deinen Namen angeben.")
        email = (form.get("email") or "").strip()
        if email and not gp.EMAIL.match(email):
            raise AssistentError("Die E-Mail-Adresse sieht nicht gültig aus.")
        profil = gp.load(root)
        for k in ("name", "email", "telefon", "adresse.strasse", "adresse.plz", "adresse.ort"):
            if k in form:
                gp.set_value(profil, k, str(form[k]).strip())
        gp.save(root, profil)
        return "Angaben gespeichert."
    if aktion == "wohnort":
        stadt = form.get("stadt", "")
        tabelle = wohnort.ki_fahrzeiten(root, cfg, stadt, ask=ask) if ki_an else {stadt.strip().lower(): 0}
        wohnort.speichern(root, stadt, tabelle)
        merken(root, wohnort=stadt.strip())
        return f"Wohnort {stadt.strip()} übernommen ({len(tabelle)} Orte)."
    if aktion == "suche":
        name = suchprofil_anlegen(root, cfg, form.get("wunsch", ""), form.get("stufe", ""), ki_an, ask=ask)
        return f"Suchprofil „{name}“ angelegt und eingeschaltet."
    if aktion == "lebenslauf":
        dateien = uploads.get("pdf") or []
        if not dateien:
            raise AssistentError("Bitte ein PDF auswählen.")
        data = lebenslauf_import(root, cfg, dateien[0][1], ask=ask)
        n = sum(len(data.get(k) or []) for k in ("stationen", "ausbildung", "projekte", "zertifikate"))
        return f"Lebenslauf übernommen ({n} Einträge). Bitte im Master-CV prüfen."
    if aktion == "mail":
        try:
            return mailzugang.verbinden(root, form.get("anbieter", ""), form.get("benutzer", ""),
                                        form.get("passwort", ""), form.get("host", ""))
        except mailzugang.MailError as exc:
            raise AssistentError(str(exc)) from None
    if aktion == "hochschulen":
        neu = hochschulboersen.eintragen(root, [k[len("portal_"):] for k, v in form.items()
                                                if k.startswith("portal_") and v])
        if not neu:
            raise AssistentError("Bitte mindestens ein Portal ankreuzen.")
        return f"Eingeschaltet: Stellenwerk {', '.join(neu)}. Gesucht wird mit den Stellenwerk-Begriffen deines Suchprofils."
    if aktion in ("mail_bericht_an", "mail_bericht_aus"):
        try:
            return mailzugang.bericht_schalten(root, aktion == "mail_bericht_an")
        except mailzugang.MailError as exc:
            raise AssistentError(str(exc)) from None
    if aktion == "mail_trennen":
        mailzugang.trennen(root)
        return "Postfach getrennt."
    if aktion == "fertig":
        merken(root, fertig=date.today().isoformat())
        return "fertig"
    raise AssistentError("Unbekannter Schritt.")
