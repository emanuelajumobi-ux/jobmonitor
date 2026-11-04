"""Optionale KI-Funktionen über die Claude-API (Standard: aus).

Anmeldung: lokal mit API-Schlüssel (ANTHROPIC_API_KEY oder Schlüsselbund, siehe ki.py); in GitHub Actions über
Workload Identity Federation (WIF) ohne gespeicherten Schlüssel: Die Pipeline holt sich ein kurzlebiges OIDC-Token
von GitHub und tauscht es bei Anthropic gegen ein Zugriffstoken (Umgebungsvariablen ANTHROPIC_FEDERATION_RULE_ID,
ANTHROPIC_ORGANIZATION_ID, ANTHROPIC_SERVICE_ACCOUNT_ID aus den Repo-Variablen, siehe monitor.yml).

Fallbacks sind aktiviert: lehnt das Modell eine Anfrage ab, beantwortet sie automatisch ein Ersatzmodell.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path

log = logging.getLogger(__name__)
FALLBACK_BETA = "server-side-fallback-2026-07-01"
AUDIENCE = "https://api.anthropic.com"
TOKEN_ALTER = 240          # GitHub-OIDC-Tokens gelten ~5 Minuten; vorher neu holen


# Aktiver KI-Anbieter (ki_anbieter.py) und seine Modelle {schnell, gut}; gesetzt von einstellen(cfg)
ANBIETER = "claude"
MODELLE: dict[str, str] = {}


def einstellen(cfg: dict) -> None:
    """Anbieter und Modelle aus config.yaml → ki übernehmen (Pipeline-Lauf und Oberfläche)."""
    global ANBIETER, MODELLE
    from . import ki_anbieter
    ANBIETER, MODELLE = ki_anbieter.aus_config(cfg)


def foederation() -> bool:
    """WIF in GitHub Actions eingerichtet (Regel und Organisation gesetzt, OIDC-Token anforderbar)?"""
    return bool(os.environ.get("ANTHROPIC_FEDERATION_RULE_ID") and os.environ.get("ANTHROPIC_ORGANIZATION_ID")
                and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"))


def verfuegbar() -> bool:
    """Kann die Pipeline die KI nutzen (API-Schlüssel oder WIF; bei anderen Anbietern KI_API_KEY bzw. Ollama)?"""
    if ANBIETER != "claude":
        from . import ki_anbieter
        return bool(MODELLE.get("schnell") and (os.environ.get("KI_API_KEY")
                                               or ki_anbieter.ANBIETER[ANBIETER].get("ohne_schluessel")))
    return bool(os.environ.get("ANTHROPIC_API_KEY")) or foederation()


def _github_token_auffrischen(get=None) -> None:
    """OIDC-Token von GitHub in ANTHROPIC_IDENTITY_TOKEN_FILE schreiben, wenn es fehlt oder älter als TOKEN_ALTER
    Sekunden ist. Das SDK liest die Datei bei jedem Austausch neu."""
    if not foederation():
        return
    pfad = Path(os.environ.get("ANTHROPIC_IDENTITY_TOKEN_FILE") or Path(tempfile.gettempdir()) / "gha-oidc.jwt")
    os.environ["ANTHROPIC_IDENTITY_TOKEN_FILE"] = str(pfad)
    if pfad.is_file() and time.time() - pfad.stat().st_mtime < TOKEN_ALTER:
        return
    if get is None:
        import requests
        get = requests.get
    resp = get(os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"], params={"audience": AUDIENCE}, timeout=20,
               headers={"Authorization": f"Bearer {os.environ.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN', '')}"})
    resp.raise_for_status()
    pfad.write_text(resp.json()["value"], encoding="utf-8")
    pfad.chmod(0o600)


MERKMALE = ("sub", "aud", "event_name", "ref", "repository", "repository_owner", "repository_owner_id", "iss")


def token_merkmale() -> dict:
    """Ausgewählte Claims des GitHub-OIDC-Tokens zur Fehlersuche (nie das Token oder die Signatur selbst)."""
    import base64
    try:
        teil = Path(os.environ["ANTHROPIC_IDENTITY_TOKEN_FILE"]).read_text(encoding="utf-8").split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(teil + "=" * (-len(teil) % 4)))
    except (KeyError, OSError, IndexError, ValueError):
        return {}
    return {k: claims.get(k) for k in MERKMALE}


_CLIENT = None


def _client(api_key: str | None):
    import anthropic  # nur laden, wenn KI wirklich aktiv ist
    global _CLIENT
    if api_key:
        return anthropic.Anthropic(api_key=api_key)
    _github_token_auffrischen()
    if _CLIENT is None:              # ein Client je Lauf: das Zugriffstoken wird zwischengespeichert und erneuert
        _CLIENT = anthropic.Anthropic()
    return _CLIENT


def json_aus(text: str | None):
    """Erstes JSON-Objekt aus einer Antwort (auch in ```json-Blöcken); None, wenn keins lesbar ist."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except ValueError:
        return None


# Nutzung in diesem Prozess (für die Pipeline: runner schreibt sie je Monat nach state/seen.sqlite)
NUTZUNG = {"aufrufe": 0, "eingabe": 0, "ausgabe": 0, "cache_lesen": 0, "cache_schreiben": 0}


def _zaehlen(u) -> None:
    NUTZUNG["aufrufe"] += 1
    for feld, attr in (("eingabe", "input_tokens"), ("ausgabe", "output_tokens"),
                       ("cache_lesen", "cache_read_input_tokens"), ("cache_schreiben", "cache_creation_input_tokens")):
        NUTZUNG[feld] += int(getattr(u, attr, 0) or 0)


def _ask(model: str, prompt: str, effort: str = "low", max_tokens: int = 4000, api_key: str | None = None,
         usage: list | None = None, system: str | None = None) -> str | None:
    """Eine Frage, eine Antwort. api_key: sonst ANTHROPIC_API_KEY. usage: bekommt (Eingabe-, Ausgabe-Tokens).
    system: gleichbleibender Teil (Anweisungen, Begriffsliste), wird zwischengespeichert (Prompt-Caching) –
    weitere Aufrufe im selben Lauf zahlen dafür nur einen Bruchteil."""
    if ANBIETER != "claude":            # OpenAI, Gemini, Mistral, Ollama: OpenAI-kompatible Schnittstelle
        from . import ki_anbieter
        modell = MODELLE.get("schnell" if "haiku" in model else "gut") or MODELLE.get("gut") or MODELLE.get("schnell")
        if not modell:
            log.warning("KI: für %s sind noch keine Modelle gewählt (Einstellungen → KI)", ANBIETER)
            return None
        schluessel = api_key or os.environ.get("KI_API_KEY")
        nutzung: list = []
        antwort = ki_anbieter.fragen(ANBIETER, schluessel, modell, prompt, system, max_tokens, nutzung)
        anderes = next((m for m in (MODELLE.get("gut"), MODELLE.get("schnell")) if m and m != modell), None)
        if antwort is None and anderes and ki_anbieter.LETZTER_FEHLER.get("status") in (500, 502, 503, 504, "netz"):
            log.info("KI: %s überlastet – weiche auf %s aus", modell, anderes)
            antwort = ki_anbieter.fragen(ANBIETER, schluessel, anderes, prompt, system, max_tokens, nutzung)
        for ein, aus in nutzung:
            NUTZUNG["aufrufe"] += 1
            NUTZUNG["eingabe"] += ein
            NUTZUNG["ausgabe"] += aus
        if usage is not None:
            usage += nutzung
        return antwort
    import anthropic  # nur laden, wenn KI wirklich aktiv ist

    try:
        client = _client(api_key)
    except Exception as exc:   # z. B. GitHub-OIDC-Token nicht abrufbar: dann ohne KI weiter
        log.warning("Claude-API: Anmeldung nicht möglich (%s)", type(exc).__name__)
        return None
    try:
        # Haiku hat keinen serverseitigen Fallback (der Parameter wäre ein Fehler 400)
        extra = {} if "haiku" in model else {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        if system:
            extra["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        response = client.beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": prompt}],
            **extra,
        )
    except anthropic.APIStatusError as exc:
        log.warning("Claude-API-Fehler %s: %s", exc.status_code, exc.message)
        return None
    except anthropic.APIConnectionError:
        log.warning("Claude-API nicht erreichbar")
        return None
    except anthropic.AnthropicError as exc:   # z. B. WIF-Tokentausch abgelehnt: ohne KI weiter, Lauf bricht nicht ab
        log.warning("Claude-API: Anmeldung fehlgeschlagen (%s)", str(exc).split(" Ensure ")[0][:200])
        return None
    if getattr(response, "usage", None) is not None:
        _zaehlen(response.usage)
        if usage is not None:
            u = response.usage
            usage.append((u.input_tokens + int(getattr(u, "cache_read_input_tokens", 0) or 0)
                          + int(getattr(u, "cache_creation_input_tokens", 0) or 0), u.output_tokens))
    if response.stop_reason in ("refusal", "max_tokens"):
        log.warning("Claude-API: Antwort %s", "abgelehnt" if response.stop_reason == "refusal" else
                    "abgeschnitten (max_tokens zu klein)")
        return None
    return "".join(b.text for b in response.content if b.type == "text").strip()


def score_job(model: str, profil: str, title: str, company: str, description: str) -> int | None:
    """KI-Einschätzung 0–100, wie gut die Stelle zum Profil passt."""
    prompt = (
        f"Profil: {profil}\n\nStelle: {title} bei {company}\n\nBeschreibung (gekürzt):\n{description[:4000]}\n\n"
        "Wie gut passt die Stelle zum Profil? Antworte nur mit einer ganzen Zahl von 0 bis 100."
    )
    answer = _ask(model, prompt)
    m = re.search(r"\d{1,3}", answer or "")
    return min(100, int(m.group())) if m else None


def draft_letter(model: str, context: str) -> str | None:
    """Kurzer Anschreiben-Entwurf auf Deutsch aus den übergebenen Fakten."""
    prompt = (
        "Schreibe einen kurzen, sachlichen Entwurf für eine Initiativbewerbung auf Deutsch (max. 200 Wörter, "
        "Markdown, ohne Floskeln). Nutze nur die folgenden Fakten und lasse Platzhalter in [eckigen Klammern] "
        f"stehen, wo Angaben fehlen:\n\n{context}"
    )
    return _ask(model, prompt, effort="medium", max_tokens=8000)
