"""KI-Anbieter: Claude (Standard, eigene Anbindung in llm.py) und Anbieter mit OpenAI-kompatibler Schnittstelle –
OpenAI, Google Gemini, Mistral und Ollama (läuft lokal und kostenlos, nichts verlässt den Rechner).

Auswahl in config.yaml → ki.anbieter und ki.modelle.<anbieter>: {schnell, gut}. „schnell“ nutzt die tägliche Suche
(viele kurze Aufrufe), „gut“ die Oberfläche (Anschreiben, Vorbereitung, Lebenslauf). Modellnamen ändern sich bei allen
Anbietern oft – darum lädt die App die Liste beim Einrichten vom Anbieter (`modelle`) und schlägt passende vor, statt
Namen fest einzubauen. Schlüssel liegen je Anbieter im Schlüsselbund bzw. in der Windows-Anmeldeinformationsverwaltung
(ki.py), in der Pipeline in der Umgebungsvariablen KI_API_KEY.
"""
from __future__ import annotations

import re

import requests

# Schlüssel → Name, Basis-Adresse (OpenAI-kompatibel), Seite für den Schlüssel, Hinweis
ANBIETER: dict[str, dict] = {
    "claude": {"name": "Claude (Anthropic)", "basis": "", "schluessel_url": "https://console.anthropic.com/settings/keys",
               "hinweis": "Empfohlen – die App ist auf Claude abgestimmt (Prompt-Caching, Ersatzmodell bei Ablehnung)."},
    "openai": {"name": "OpenAI (ChatGPT)", "basis": "https://api.openai.com/v1",
               "schluessel_url": "https://platform.openai.com/api-keys", "hinweis": "Abrechnung über dein OpenAI-Konto."},
    "gemini": {"name": "Google Gemini", "basis": "https://generativelanguage.googleapis.com/v1beta/openai",
               "schluessel_url": "https://aistudio.google.com/apikey",
               "hinweis": "Kostenloses Kontingent über Google AI Studio (Grenzen je Modell, „Pro“ meist nur bezahlt); "
                          "darüber hinaus Abrechnung über dein Google-Konto."},
    "mistral": {"name": "Mistral (EU)", "basis": "https://api.mistral.ai/v1",
                "schluessel_url": "https://console.mistral.ai/api-keys", "hinweis": "Anbieter mit Sitz in Frankreich."},
    "ollama": {"name": "Ollama (lokal, kostenlos)", "basis": "http://localhost:11434/v1", "ohne_schluessel": True,
               "schluessel_url": "https://ollama.com/download",
               "hinweis": "Läuft auf deinem Rechner, nichts verlässt ihn. Braucht einen kräftigen Rechner; Ergebnisse "
                          "sind meist schwächer als bei den großen Anbietern."},
}
SCHNELL = re.compile(r"mini|flash|small|haiku|lite|nano|8b|3b|instant", re.I)
GUT = re.compile(r"pro|large|opus|sonnet|\bgpt-\d(?:\.\d)?$|70b|medium", re.I)
OHNE = re.compile(r"embed|audio|tts|whisper|image|vision-preview|moderation|realtime|transcribe|search|dall|guard",
                  re.I)


class AnbieterError(Exception):
    pass


def gueltig(key: str | None) -> str:
    return key if key in ANBIETER else "claude"


def aus_config(cfg: dict) -> tuple[str, dict]:
    """(Anbieter, {schnell, gut}) aus config.yaml → ki."""
    k = cfg.get("ki") or {}
    anbieter = gueltig(k.get("anbieter"))
    return anbieter, dict(((k.get("modelle") or {}).get(anbieter) or {}))


def modelle(anbieter: str, schluessel: str | None, get=requests.get) -> list[str]:
    """Modell-IDs des Anbieters (GET …/models), ohne offensichtliche Nicht-Text-Modelle."""
    a = ANBIETER[gueltig(anbieter)]
    if not a["basis"]:
        raise AnbieterError("Für Claude wählt die App die Modelle selbst.")
    headers = {"Authorization": f"Bearer {schluessel}"} if schluessel else {}
    try:
        resp = get(f"{a['basis']}/models", headers=headers, timeout=15)
    except requests.RequestException as exc:
        if anbieter == "ollama":
            raise AnbieterError("Ollama ist nicht erreichbar – läuft es auf diesem Rechner? (ollama.com)") from None
        raise AnbieterError(f"{a['name']} nicht erreichbar ({exc.__class__.__name__}).") from None
    if resp.status_code in (401, 403):
        raise AnbieterError("Der Schlüssel wurde abgelehnt – bitte prüfen (ganz kopiert, beim richtigen Anbieter?).")
    if resp.status_code != 200 and anbieter == "gemini":
        return _gemini_nativ(schluessel, get)     # die OpenAI-kompatible Liste antwortet bei Google teils mit 501
    if resp.status_code != 200:
        raise AnbieterError(f"{a['name']} antwortet mit Fehler {resp.status_code}.")
    return _filtern([m.get("id") for m in (resp.json().get("data") or [])])


def _gemini_nativ(schluessel: str | None, get) -> list[str]:
    """Modellliste über Googles eigene Schnittstelle (nur Modelle, die Text erzeugen können)."""
    try:
        resp = get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", timeout=15,
                   headers={"x-goog-api-key": schluessel or ""})
    except requests.RequestException as exc:
        raise AnbieterError(f"Google Gemini nicht erreichbar ({exc.__class__.__name__}).") from None
    if resp.status_code in (400, 401, 403):
        raise AnbieterError("Der Schlüssel wurde abgelehnt – bitte prüfen (ganz kopiert, beim richtigen Anbieter?).")
    if resp.status_code != 200:
        raise AnbieterError(f"Google Gemini antwortet mit Fehler {resp.status_code}.")
    return _filtern([m.get("name") for m in resp.json().get("models") or []
                     if "generateContent" in (m.get("supportedGenerationMethods") or ["generateContent"])])


def _filtern(roh: list) -> list[str]:
    ids = []
    for mid in roh:
        mid = str(mid or "").removeprefix("models/")
        if mid and not OHNE.search(mid) and mid not in ids:
            ids.append(mid)
    if not ids:
        raise AnbieterError("Der Anbieter hat keine passenden Modelle gemeldet.")
    return sorted(ids)


def vorschlag(ids: list[str], anbieter: str = "") -> dict[str, str]:
    """Vorschlag für schnell/gut aus der Modell-Liste (neueste Namen zuerst durch umgekehrte Sortierung).
    Gemini: beide aus der Flash-Reihe – Pro-Modelle sind im kostenlosen Kontingent oft nicht enthalten."""
    neu = sorted(ids, reverse=True)
    if GEPRUEFT.get(anbieter) and all(m in ids for m in GEPRUEFT[anbieter].values()):
        return dict(GEPRUEFT[anbieter])
    if anbieter == "gemini":
        flash = [m for m in neu if "flash" in m and "image" not in m and "live" not in m and "tts" not in m]
        stabil = [m for m in flash if "preview" not in m and "exp" not in m] or flash
        lite = [m for m in stabil if "lite" in m]
        voll = [m for m in stabil if "lite" not in m]
        if voll or lite:
            return {"schnell": (lite or voll)[0], "gut": (voll or lite)[0]}
    schnell = next((m for m in neu if SCHNELL.search(m)), neu[0])
    gut = next((m for m in neu if GUT.search(m) and not SCHNELL.search(m)), next((m for m in neu if m != schnell), schnell))
    return {"schnell": schnell, "gut": gut}


VORUEBERGEHEND = {500, 502, 503, 504}     # überlastet oder kurz gestört: noch einmal versuchen
WARTEN = (0, 3, 8)                         # Sekunden vor dem 1., 2. und 3. Versuch
LETZTER_FEHLER: dict = {}                  # Status des letzten Fehlschlags (für das Ausweichmodell in llm._ask)
GEPRUEFT: dict[str, dict] = {}             # Anbieter → beim Einrichten geprüfter Modellvorschlag


def fragen(anbieter: str, schluessel: str | None, modell: str, prompt: str, system: str | None = None,
           max_tokens: int = 4000, usage: list | None = None, post=requests.post, warten=None) -> str | None:
    """Eine Frage über die OpenAI-kompatible Schnittstelle (chat/completions). None bei Fehlern (wird geloggt).
    Überlastung (503 & Co.) und Zeitüberschreitung werden bis zu zweimal mit kurzer Pause wiederholt."""
    import logging
    import time
    log = logging.getLogger("jobmonitor.llm")
    a = ANBIETER[gueltig(anbieter)]
    nachrichten = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": modell, "messages": nachrichten}
    body["max_completion_tokens" if anbieter == "openai" else "max_tokens"] = max_tokens
    headers = {"Authorization": f"Bearer {schluessel}"} if schluessel else {}
    LETZTER_FEHLER.clear()
    resp = None
    for i, pause in enumerate(WARTEN):
        if pause:
            (warten or time.sleep)(pause)
        try:
            resp = post(f"{a['basis']}/chat/completions", json=body, headers=headers, timeout=120)
        except requests.RequestException as exc:
            log.warning("%s nicht erreichbar (%s)%s", a["name"], exc.__class__.__name__,
                        " – neuer Versuch" if i < len(WARTEN) - 1 else "")
            LETZTER_FEHLER["status"] = "netz"
            continue
        if resp.status_code == 429 and anbieter == "gemini" and i == 0:
            # kostenloses Gemini-Kontingent zählt pro Minute: einmal kurz warten (beim Einrichten kommen mehrere
            # Anfragen direkt hintereinander), danach erst aufgeben
            log.info("%s: Minutenkontingent erreicht – neuer Versuch in 15 s", a["name"])
            (warten or time.sleep)(15)
            try:
                resp = post(f"{a['basis']}/chat/completions", json=body, headers=headers, timeout=120)
            except requests.RequestException:
                LETZTER_FEHLER["status"] = "netz"
                return None
        if resp.status_code in VORUEBERGEHEND:
            log.warning("%s: %s ist gerade überlastet (%s)%s", a["name"], modell, resp.status_code,
                        " – neuer Versuch" if i < len(WARTEN) - 1 else "")
            LETZTER_FEHLER["status"] = resp.status_code
            continue
        break
    else:
        return None
    if resp is None:
        return None
    if resp.status_code == 429:
        log.warning("%s: Kontingent erschöpft (zu viele Anfragen pro Minute oder Tag) – später erneut versuchen",
                    a["name"])
        LETZTER_FEHLER["status"] = 429
        return None
    if resp.status_code != 200:
        log.warning("%s-Fehler %s: %s", a["name"], resp.status_code, resp.text[:200])
        LETZTER_FEHLER["status"] = resp.status_code
        LETZTER_FEHLER["text"] = resp.text[:300]
        return None
    data = resp.json()
    u = data.get("usage") or {}
    if usage is not None:
        usage.append((int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)))
    wahl = (data.get("choices") or [{}])[0]
    if wahl.get("finish_reason") == "length":
        log.warning("%s: Antwort abgeschnitten (max_tokens zu klein)", a["name"])
        return None
    return str((wahl.get("message") or {}).get("content") or "").strip() or None


def grund(anbieter: str) -> str:
    """Verständlicher Grund für den letzten Fehlschlag von fragen() – statt nur „hat nicht geantwortet“."""
    name = ANBIETER[gueltig(anbieter)]["name"]
    status = LETZTER_FEHLER.get("status")
    text = str(LETZTER_FEHLER.get("text") or "").lower()
    if status == "keine_modelle":
        return (f"Für {name} sind noch keine Modelle gewählt. Unter Einstellungen → KI auf „Modelle vom Anbieter "
                "laden“ klicken.")
    if status == "netz":
        if anbieter == "ollama":
            return "Ollama ist nicht erreichbar – läuft es auf diesem Rechner? (ollama.com)"
        return f"{name} ist nicht erreichbar. Bitte die Internetverbindung prüfen und es noch einmal versuchen."
    if status == 429:
        return (f"{name}: Kontingent erschöpft. Der kostenlose Zugang erlaubt nur wenige Anfragen pro Minute und pro "
                "Tag – eine Minute warten und noch einmal versuchen.")
    if status in (400, 401, 403) and ("key" in text or "api_key" in text or "permission" in text or status != 400):
        return (f"{name} lehnt den Schlüssel ab. Bitte unter Einstellungen → KI prüfen, ob er ganz kopiert ist. "
                "Ein gerade erstellter Schlüssel braucht manchmal ein, zwei Minuten, bis er funktioniert.")
    if status == 404:
        return (f"Das gewählte Modell gibt es bei {name} nicht (mehr). Unter Einstellungen → KI auf „Modelle vom "
                "Anbieter laden“ klicken.")
    if status in VORUEBERGEHEND:
        return f"{name} ist gerade überlastet. In ein paar Minuten noch einmal versuchen."
    if status:
        return f"{name} meldet Fehler {status}. Details stehen im Protokoll."
    return ""


def _version(mid: str) -> tuple:
    import re as _re
    m = _re.search(r"gemini-(\d+)(?:\.(\d+))?", mid)
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)


def gemini_pruefen(schluessel: str | None, ids: list[str], post=requests.post) -> dict[str, str]:
    """Beim Einrichten: welche Flash-Modelle antworten im Kontingent dieses Schlüssels wirklich? Neue Modelle sind oft
    überlastet, ältere für neue Nutzer abgeschaltet und „Pro“ ist nicht kostenlos – darum je eine kurze Probe (wenige
    Token). Gibt {schnell, gut} zurück (leer, wenn nichts antwortet) und merkt es für vorschlag()."""
    voll = sorted((m for m in ids if re.fullmatch(r"gemini-\d+(\.\d+)?-flash", m)), key=_version, reverse=True)
    lite = sorted((m for m in ids if re.fullmatch(r"gemini-\d+(\.\d+)?-flash-lite", m)), key=_version, reverse=True)
    voll += [m for m in ("gemini-flash-latest",) if m in ids]
    lite += [m for m in ("gemini-flash-lite-latest",) if m in ids]

    def antwortet(m: str) -> bool:
        try:
            r = post(f"{ANBIETER['gemini']['basis']}/chat/completions", timeout=25,
                     headers={"Authorization": f"Bearer {schluessel}"},
                     json={"model": m, "messages": [{"role": "user", "content": "Antworte nur mit: ok"}],
                           "max_tokens": 300})
            return r.status_code == 200
        except requests.RequestException:
            return False
    # alle Proben gleichzeitig statt nacheinander: dauert so lange wie die langsamste, nicht wie alle zusammen
    from concurrent.futures import ThreadPoolExecutor
    kandidaten = voll[:5] + lite[:4]
    with ThreadPoolExecutor(max_workers=max(1, len(kandidaten))) as pool:
        ok = dict(zip(kandidaten, pool.map(antwortet, kandidaten)))
    gut = next((m for m in voll[:5] if ok.get(m)), "")
    schnell = next((m for m in lite[:4] if ok.get(m)), "") or gut
    out = {"schnell": schnell, "gut": gut or schnell} if (gut or schnell) else {}
    if out:
        GEPRUEFT["gemini"] = out
    return out
