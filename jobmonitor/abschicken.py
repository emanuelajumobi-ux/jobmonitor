"""„Vor dem Abschicken“: Checkliste auf der Bewerbungsseite, bevor du die Mappe selbst verschickst.

Geprüft wird nur Messbares und Lokales (keine KI, kein Netz):
- keine Platzhalter in [eckigen Klammern] mehr
- Firma, Stelle und Anrede laut Anschreiben-Prüfer (anschreiben_check.py) ohne Warnung
- Mappe gebaut und neuer als die letzte Änderung am Anschreiben
- Mappe höchstens `max_mb` MB (viele Bewerbungsportale nehmen nicht mehr), Dateiname ohne Leer- und Sonderzeichen
- alle Anlagen vorhanden, Frist nicht abgelaufen, Anzeige laut Pipeline noch online

Dazu optional die KI-Durchsicht des Anschreibens (Rechtschreibung, Floskeln, Länge, Bezug zur Stelle): gesendet
werden nur Anschreiben-Text und Anzeige, nie profile.yaml. Grenzwerte: config.yaml → bewerbung.abschicken.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

from . import anschreiben_check
from . import bewerbung as bw
from . import fristen, ki, llm

DEFAULTS = {"max_mb": 5}
DATEINAME = re.compile(r"^[A-Za-z0-9._-]{1,80}\.pdf$")


@dataclass
class Punkt:
    ok: bool
    text: str


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def mappe(folder: Path) -> Path | None:
    pdfs = sorted(folder.glob("bewerbungsmappe-*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pdfs[0] if pdfs else None


def pruefen(folder: Path, data: dict, stelle: dict, cfg: dict, anlagen: list[dict], andere: list[str],
            offline: bool = False, heute: date | None = None) -> list[Punkt]:
    grenzen = {**DEFAULTS, **((cfg.get("bewerbung") or {}).get("abschicken") or {})}
    out: list[Punkt] = []
    offen = bw.placeholders(data.get("text") or "")
    out.append(Punkt(not offen, "Keine Platzhalter mehr im Anschreiben" if not offen else
                     f"Noch {len(offen)} Platzhalter: {', '.join(offen[:3])}"))
    warnungen = [h.text for h in anschreiben_check.check_text(data, stelle, cfg, andere) if h.stufe == "warnung"]
    out += ([Punkt(False, w) for w in warnungen] if warnungen else
            [Punkt(True, "Firma, Stelle und Anrede im Anschreiben passen zur Anzeige")])
    pdf = mappe(folder)
    if pdf is None:
        out.append(Punkt(False, "Noch keine Mappe gebaut („Speichern und Mappe bauen“)"))
    else:
        brief = folder / "anschreiben.json"
        aktuell = not brief.is_file() or pdf.stat().st_mtime >= brief.stat().st_mtime - 1
        out.append(Punkt(aktuell, "Mappe ist auf dem Stand des Anschreibens" if aktuell else
                         "Anschreiben nach dem Bauen geändert – Mappe neu bauen"))
        mb = pdf.stat().st_size / 1_000_000
        out.append(Punkt(mb <= grenzen["max_mb"], f"Mappe {mb:.1f} MB" + ("" if mb <= grenzen["max_mb"] else
                         f" – über {grenzen['max_mb']} MB, viele Portale nehmen das nicht (Anlagen verkleinern)")))
        sauber = bool(DATEINAME.match(pdf.name))
        out.append(Punkt(sauber, f"Dateiname „{pdf.name}“" + ("" if sauber else
                         " enthält Leer- oder Sonderzeichen – vor dem Hochladen umbenennen")))
    fehlend = [a["name"] for a in anlagen if not a["pdfs"]]
    out.append(Punkt(not fehlend, "Alle Anlagen vorhanden" if not fehlend else
                     f"Anlage fehlt: {', '.join(fehlend)} (Unterlagen hochladen)"))
    frist = fristen.label(stelle.get("frist"), heute or date.today())
    if frist and "abgelaufen" not in frist:      # abgelaufene Frist meldet schon der Anschreiben-Prüfer
        out.append(Punkt(True, f"Frist: {frist}"))
    if offline:
        out.append(Punkt(False, "Die Anzeige ist laut letzter Prüfung nicht mehr online – vielleicht schon besetzt"))
    return out


def render(punkte: list[Punkt], token: str, slug_url: str, ki_an: bool) -> str:
    offen = sum(not p.ok for p in punkte)
    items = "".join(f'<li class="{"" if p.ok else "warnung"}"><b>{"✓" if p.ok else "✗"}</b> {esc(p.text)}</li>'
                    for p in punkte)
    knopf = (f'<form method="post" action="{slug_url}" style="margin-top:10px"><input type="hidden" name="token" '
             f'value="{token}"><button name="aktion" value="ki_pruefen" class="ghost small" data-ki="KI liest dein '
             f'Anschreiben …" onclick="return confirm(\'Anschreiben von der KI durchsehen lassen? Gesendet werden der '
             f'Anschreiben-Text und die Anzeige, keine persönlichen Daten aus profile.yaml.\')">Anschreiben mit KI '
             f'prüfen</button> <span class="muted">Rechtschreibung, Floskeln, Länge, Bezug zur Stelle</span></form>'
             if ki_an else "")
    stand = ("Alles erledigt – abschicken tust du selbst." if not offen else f"{offen} Punkt(e) offen.")
    return (f'<div class="card"><div class="head"><h2>Vor dem Abschicken</h2><span class="muted">{stand}</span>'
            f'</div><ul class="checks">{items}</ul>{knopf}</div>')


# --- KI-Durchsicht ---
def ki_prompt(text: str, stelle: dict, anzeige: str) -> str:
    return ("Lies dieses Bewerbungsanschreiben (Werkstudent/Junior, Deutsch) wie ein sorgfältiger Korrektor und "
            "gib konkrete Hinweise zu: Rechtschreibung und Grammatik, Floskeln und Füllsätzen, Länge, Bezug zur "
            "Stelle (greift es die Aufgaben der Anzeige auf?). Erfinde nichts dazu, schreibe den Text nicht neu. "
            "Höchstens 8 Hinweise, die wichtigsten zuerst; keine Hinweise, wo nichts zu verbessern ist.\n\n"
            f"STELLE: {stelle.get('title')} bei {stelle.get('company')}\n\n"
            f"ANZEIGE:\n{anzeige[:6000] if anzeige else '(nicht verfügbar)'}\n\nANSCHREIBEN:\n{text[:6000]}\n\n"
            'Antworte nur mit JSON: {"fazit": "ein Satz", "hinweise": [{"art": "Rechtschreibung|Floskel|Länge|'
            'Bezug", "zitat": "betroffene Stelle, kurz", "vorschlag": "was besser wäre"}]}')


def ki_pruefen(root: Path, cfg: dict, text: str, stelle: dict, anzeige: str, ask=None) -> dict:
    if not (text or "").strip():
        raise ki.KiError("Das Anschreiben ist leer.")
    data = llm.json_aus(ki.fragen(root, cfg, ki_prompt(text, stelle, anzeige), effort="low", max_tokens=6000,
                                  ask=ask))
    if not isinstance(data, dict) or not isinstance(data.get("hinweise"), list):
        raise ki.KiError("Die KI hat keine lesbare Durchsicht geliefert.")
    hinweise = [h for h in data["hinweise"] if isinstance(h, dict) and h.get("vorschlag")][:8]
    return {"fazit": str(data.get("fazit") or ""), "hinweise": hinweise}


def ki_html(ergebnis: dict) -> str:
    items = "".join(f'<li><b>{esc(h.get("art") or "Hinweis")}:</b> '
                    + (f'„{esc(h.get("zitat"))}“ – ' if h.get("zitat") else "") + f'{esc(h.get("vorschlag"))}</li>'
                    for h in ergebnis["hinweise"])
    return (f'<div class="card"><h2>KI-Durchsicht des Anschreibens</h2><p>{esc(ergebnis["fazit"])}</p>'
            + (f'<ul class="checks">{items}</ul>' if items else '<p class="ok">Keine Verbesserungsvorschläge.</p>')
            + '<p class="muted">Vorschläge, keine Pflicht – den Text änderst du selbst.</p></div>')
