"""Übungsgespräch: Die KI spielt das Vorstellungsgespräch für eine konkrete Stelle durch – sie stellt eine Frage, du
antwortest, sie gibt kurz Rückmeldung (was gut war, was fehlte, ein passendes Beispiel aus deinem Lebenslauf) und
stellt die nächste Frage. Nach FRAGEN Fragen gibt es eine Zusammenfassung.

Gesendet werden Anzeige, Anforderungen, der fachliche Teil des Lebenslaufs und deine Antworten – keine persönlichen
Daten aus profile.yaml. Der Verlauf liegt lokal in .gui_ki.json → uebung (je Bewerbung, Schlüssel: Link der Anzeige).
"""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from . import ki, llm

FRAGEN = 5
BEREICH = "uebung"


def laden(root: Path, link: str) -> dict | None:
    return (ki.laden(root).get(BEREICH) or {}).get(link)


def _speichern(root: Path, link: str, sitzung: dict | None) -> None:
    data = ki.laden(root)
    if sitzung is None:
        (data.get(BEREICH) or {}).pop(link, None)
    else:
        data.setdefault(BEREICH, {})[link] = sitzung
    ki._speichern(root, data)


def _rolle(sitzung: dict) -> str:
    s = sitzung["stelle"]
    sprache = ("Führe das Gespräch auf Englisch (Fragen und Rückmeldung)." if sitzung.get("englisch") else
               "Führe das Gespräch auf Deutsch, in der Sie-Form wie in einem echten Gespräch.")
    return (f"Du führst ein Übungs-Vorstellungsgespräch für die Stelle „{s.get('title')}“ bei {s.get('company')}. "
            f"Du bist freundlich, aber realistisch – wie eine Personalerin oder ein Fachbereichsleiter. {sprache} "
            f"Insgesamt {FRAGEN} Fragen, gemischt: Motivation, Fachfragen zu den Anforderungen der Anzeige, eine "
            "Verhaltensfrage („Erzählen Sie von einer Situation …“) und eine Frage zu einer Lücke im Lebenslauf. Stelle "
            "jeweils genau eine Frage. Erfinde nichts über die Person; beziehe dich nur auf den Lebenslauf.")


def _kontext(sitzung: dict, anzeige: str, cv: dict) -> str:
    return ki._kopf(sitzung["stelle"], anzeige, cv)


def starten(root: Path, cfg: dict, link: str, stelle: dict, anzeige: str, cv: dict, englisch: bool = False,
            ask=None) -> dict:
    sitzung = {"stelle": {k: stelle.get(k) for k in ("title", "company", "anforderungen")}, "englisch": englisch,
               "datum": date.today().isoformat(), "verlauf": [], "abschluss": ""}
    frage = ki.fragen(root, cfg, f"{_rolle(sitzung)}\n\n{_kontext(sitzung, anzeige, cv)}\n\nBeginne mit einer kurzen "
                                 "Begrüßung (ein Satz) und der ersten Frage. Gib nur das aus, was du sagst.",
                      effort="low", max_tokens=2000, ask=ask)
    sitzung["verlauf"].append({"frage": frage.strip(), "antwort": "", "feedback": ""})
    _speichern(root, link, sitzung)
    return sitzung


def antworten(root: Path, cfg: dict, link: str, antwort: str, anzeige: str, cv: dict, ask=None) -> dict:
    sitzung = laden(root, link)
    if not sitzung or not sitzung["verlauf"] or sitzung["verlauf"][-1]["antwort"]:
        raise ki.KiError("Kein offenes Übungsgespräch – bitte neu beginnen.")
    sitzung["verlauf"][-1]["antwort"] = antwort.strip()[:4000]
    letzte = len(sitzung["verlauf"]) >= FRAGEN
    bisher = "\n\n".join(f"FRAGE {i + 1}: {r['frage']}\nANTWORT: {r['antwort']}"
                         for i, r in enumerate(sitzung["verlauf"]))
    auftrag = ('Antworte nur mit JSON: {"feedback": "...", "abschluss": "..."}\n- feedback: 2 bis 4 Sätze zur '
               "letzten Antwort.\n- abschluss: Zusammenfassung des Gesprächs mit „## Stärken“ und „## Daran arbeiten“ "
               "(je 2 bis 3 Punkte „- “) und einem Satz, wie das Gespräch wohl gewirkt hätte." if letzte else
               'Antworte nur mit JSON: {"feedback": "...", "naechste_frage": "..."}\n- feedback: 2 bis 4 Sätze zur '
               "letzten Antwort: was gut war, was fehlte (z. B. ein konkretes Beispiel, ein Ergebnis) und – falls "
               "passend – welches Beispiel aus dem Lebenslauf sich angeboten hätte.\n- naechste_frage: die nächste "
               "Frage, wie du sie im Gespräch sagen würdest.")
    data = llm.json_aus(ki.fragen(root, cfg, f"{_rolle(sitzung)}\n\n{_kontext(sitzung, anzeige, cv)}\n\nBISHERIGES "
                                             f"GESPRÄCH:\n{bisher}\n\n{auftrag}", effort="low", max_tokens=4000,
                                  ask=ask))
    if not isinstance(data, dict) or not data.get("feedback"):
        sitzung["verlauf"][-1]["antwort"] = ""            # Antwort nicht verlieren: erneut senden möglich
        raise ki.KiError("Die KI hat nicht lesbar geantwortet – bitte die Antwort noch einmal senden.")
    sitzung["verlauf"][-1]["feedback"] = str(data["feedback"]).strip()
    if letzte:
        sitzung["abschluss"] = str(data.get("abschluss") or "").strip()
    elif data.get("naechste_frage"):
        sitzung["verlauf"].append({"frage": str(data["naechste_frage"]).strip(), "antwort": "", "feedback": ""})
    _speichern(root, link, sitzung)
    return sitzung


def beenden(root: Path, link: str) -> None:
    _speichern(root, link, None)


def render(link: str, titel: str, firma: str, sitzung: dict | None, token: str, ki_an: bool, esc=escape,
           englisch_vorschlag: bool = False) -> str:
    kopf = (f'<h1>Übungsgespräch</h1><p class="sub">{esc(titel)} · {esc(firma)} · <a href="/bewerbungen">zurück zu '
            f'den Bewerbungen</a></p>')
    hidden = f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="link" value="{esc(link)}">'
    if not ki_an:
        return kopf + ('<div class="card"><p>Das Übungsgespräch braucht die KI. <a href="/einstellungen#ki">KI '
                       'einrichten</a></p></div>')
    if not sitzung:
        return kopf + (
            f'<div class="card"><h2>So funktioniert es</h2><p>Die KI stellt dir {FRAGEN} Fragen, wie sie in einem '
            f'Gespräch für genau diese Stelle kommen könnten – Motivation, Fachliches aus der Anzeige, eine Situation '
            f'aus deiner Praxis und eine Lücke. Nach jeder Antwort bekommst du kurz Rückmeldung, am Ende eine '
            f'Zusammenfassung.</p><p class="muted">Tipp: Antworte so, wie du es sagen würdest – ruhig in ganzen Sätzen. '
            f'Gesendet werden Anzeige, Lebenslauf (ohne persönliche Daten) und deine Antworten.</p>'
            f'<form method="post" action="/uebung" class="row" style="gap:12px;margin-top:10px">{hidden}'
            f'<label class="check"><input type="checkbox" name="englisch" value="1"'
            f'{" checked" if englisch_vorschlag else ""}> auf Englisch üben</label>'
            f'<button name="aktion" value="start" data-ki="KI bereitet das Gespräch vor …">Gespräch beginnen</button>'
            f'</form></div>')
    teile = []
    for i, r in enumerate(sitzung["verlauf"]):
        teile.append(f'<div class="ue-frage"><span class="muted">Frage {i + 1} von {FRAGEN}</span>'
                     f'{ki.als_html(r["frage"], esc)}</div>')
        if r["antwort"]:
            teile.append(f'<div class="ue-antwort">{ki.als_html(r["antwort"], esc)}</div>')
        if r["feedback"]:
            teile.append(f'<div class="ue-feedback"><b>Rückmeldung</b>{ki.als_html(r["feedback"], esc)}</div>')
    offen = sitzung["verlauf"] and not sitzung["verlauf"][-1]["antwort"]
    eingabe = (f'<form method="post" action="/uebung" class="ue-eingabe">{hidden}<label for="ue-text">Deine '
               f'Antwort</label><textarea id="ue-text" name="antwort" rows="6" required autofocus></textarea>'
               f'<div class="row"><button name="aktion" value="antwort" data-ki="KI hört zu …">Antwort senden</button>'
               f'</div></form>' if offen else "")
    abschluss = (f'<div class="card ue-abschluss"><h2>Zusammenfassung</h2>{ki.als_html(sitzung["abschluss"], esc)}'
                 f'</div>' if sitzung.get("abschluss") else "")
    neu = (f'<form method="post" action="/uebung" style="margin-top:12px" onsubmit="return confirm(\'Gespräch '
           f'verwerfen und neu beginnen?\')">{hidden}<button name="aktion" value="neu" class="ghost small">'
           f'{"Neues Gespräch" if sitzung.get("abschluss") else "Abbrechen und neu beginnen"}</button></form>')
    return kopf + f'<div class="card ue">{"".join(teile)}{eingabe}</div>{abschluss}{neu}'


CSS = """
.ue { display:grid; gap:12px; }
.ue-frage { padding:12px 14px; border-radius:12px; background:var(--surface-2); max-width:85%; }
.ue-frage .muted { font-size:12px; display:block; margin-bottom:4px; }
.ue-antwort { padding:12px 14px; border-radius:12px; background:var(--accent-soft); margin-left:auto; max-width:85%; }
.ue-feedback { padding:10px 14px; border-left:3px solid var(--accent); color:var(--text); font-size:14px; }
.ue-frage p, .ue-antwort p, .ue-feedback p { margin:4px 0; }
.ue-eingabe textarea { min-height:120px; }
"""

