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


def fragen(anbieter: str, schluessel: str | None, modell: str, prompt: str, system: str | None = None,
           max_tokens: int = 4000, usage: list | None = None, post=requests.post) -> str | None:
    """Eine Frage über die OpenAI-kompatible Schnittstelle (chat/completions). None bei Fehlern (wird geloggt)."""
    import logging
    log = logging.getLogger("jobmonitor.llm")
    a = ANBIETER[gueltig(anbieter)]
    nachrichten = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": modell, "messages": nachrichten}
    body["max_completion_tokens" if anbieter == "openai" else "max_tokens"] = max_tokens
    headers = {"Authorization": f"Bearer {schluessel}"} if schluessel else {}
    try:
        resp = post(f"{a['basis']}/chat/completions", json=body, headers=headers, timeout=180)
    except requests.RequestException as exc:
        log.warning("%s nicht erreichbar (%s)", a["name"], exc.__class__.__name__)
        return None
    if resp.status_code == 429:
        log.warning("%s: Kontingent erschöpft (zu viele Anfragen pro Minute oder Tag) – später erneut versuchen",
                    a["name"])
        return None
    if resp.status_code != 200:
        log.warning("%s-Fehler %s: %s", a["name"], resp.status_code, resp.text[:200])
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
