"""Gesprächsvorbereitung (ki.vorbereitung) als Karteikarten nach Anki schicken – lokal über AnkiConnect
(http://127.0.0.1:8765, deshalb nutzt die Oberfläche einen anderen Port).

Karten landen im Stapel „Job-Monitor::<Firma>“ mit eigenem Notiztyp „Job-Monitor Frage“ (Felder Frage/Antwort, so
unabhängig von der Sprache der Anki-Standardtypen). Schon vorhandene Karten werden übersprungen. Gelöscht oder geändert
wird in Anki nie etwas.
"""
from __future__ import annotations

import re

import requests

URL = "http://127.0.0.1:8765"
MODELL = "Job-Monitor Frage"
STAPEL = "Job-Monitor"
VORLAGE = [{"Name": "Karte 1", "Front": "{{Frage}}", "Back": "{{FrontSide}}<hr id=answer>{{Antwort}}"}]


class AnkiError(Exception):
    pass


def rufen(action: str, post=requests.post, **params):
    try:
        resp = post(URL, json={"action": action, "version": 6, "params": params}, timeout=10)
        data = resp.json()
    except (requests.RequestException, ValueError):
        raise AnkiError("Anki ist nicht erreichbar. Öffne Anki (mit dem Add-on AnkiConnect) und versuch es noch einmal.") \
            from None
    if data.get("error"):
        raise AnkiError(f"AnkiConnect: {data['error']}")
    return data.get("result")


def _abschnitte(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    aktuell = ""
    for zeile in text.splitlines():
        z = zeile.strip()
        if z.startswith("#"):
            aktuell = z.lstrip("#").strip().lower()
        elif re.match(r"^([-*]|\d+[.)])\s", z) and aktuell:
            out.setdefault(aktuell, []).append(re.sub(r"^([-*]|\d+[.)])\s+", "", z).replace("**", ""))
    return out


def karten(text: str, firma: str) -> list[tuple[str, str]]:
    """(Frage, Antwort) aus der Gesprächsvorbereitung: wahrscheinliche Fragen mit Hinweis, ehrlich einzuordnende
    Lücken und eine Karte mit deinen Fragen an die Firma."""
    teile = _abschnitte(text)
    out = []
    for punkt in next((v for k, v in teile.items() if "frage" in k and "firma" not in k), []):
        frage, zeichen, hinweis = punkt.partition("?")
        if zeichen:
            out.append((frage.strip() + "?", hinweis.strip(" –-:()") or "Mit einem Beispiel aus deinem Lebenslauf "
                                                                         "antworten."))
    for punkt in next((v for k, v in teile.items() if "einordnen" in k), []):
        thema = re.split(r"\s[–-]\s|:|\(", punkt, maxsplit=1)[0].strip()
        out.append((f"Wie gehst du ehrlich mit der Lücke „{thema}“ um?", punkt))
    fragen = next((v for k, v in teile.items() if "firma" in k), [])
    if fragen:
        out.append((f"Welche Fragen stellst du {firma}?", "<br>".join(f"• {f}" for f in fragen)))
    return out


def _stapelname(firma: str) -> str:
    return f"{STAPEL}::{re.sub(r'[:\"]+', ' ', firma).strip() or 'Firma'}"


def senden(firma: str, karten_liste: list[tuple[str, str]], post=requests.post) -> tuple[int, int, str]:
    """(neu angelegt, schon vorhanden, Stapelname)."""
    if not karten_liste:
        raise AnkiError("In der Vorbereitung stehen keine Fragen, aus denen Karten werden könnten.")
    if MODELL not in (rufen("modelNames", post) or []):
        rufen("createModel", post, modelName=MODELL, inOrderFields=["Frage", "Antwort"], cardTemplates=VORLAGE)
    stapel = _stapelname(firma)
    rufen("createDeck", post, deck=stapel)
    notizen = [{"deckName": stapel, "modelName": MODELL, "fields": {"Frage": f, "Antwort": a},
                "tags": ["job-monitor", "vorstellungsgespraech"], "options": {"allowDuplicate": False}}
               for f, a in karten_liste]
    moeglich = rufen("canAddNotes", post, notes=notizen) or [False] * len(notizen)
    neu = [n for n, ok in zip(notizen, moeglich) if ok]
    if neu:
        rufen("addNotes", post, notes=neu)
    return len(neu), len(notizen) - len(neu), stapel
