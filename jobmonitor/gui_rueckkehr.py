"""Checkliste „Zurück aus dem Ruhemodus“ auf der Startseite.

Schaltest du unter Einstellungen → Suche von Ruhemodus oder Angehalten zurück auf Aktiv, merkt sich die App das in
.gui_rueckkehr.json (lokal). Bis du die Liste abhakst, zeigt die Startseite, was nach der Pause zu prüfen ist –
mit dem, was sich automatisch feststellen lässt (veraltete Angaben im Master-CV, Quellen ohne Ergebnis, Mitteilungen
aus).
"""
from __future__ import annotations

import json
from datetime import date
from html import escape
from pathlib import Path

DATEI = ".gui_rueckkehr.json"


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def laden(root: Path) -> dict:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def starten(root: Path, heute: date) -> None:
    (root / DATEI).write_text(json.dumps({"seit": heute.isoformat(), "erledigt": []}), encoding="utf-8")


def abhaken(root: Path, punkt: str) -> None:
    data = laden(root)
    if not data:
        return
    if punkt == "alle":
        (root / DATEI).unlink(missing_ok=True)
        return
    data["erledigt"] = sorted(set(data.get("erledigt") or []) | {punkt})
    (root / DATEI).write_text(json.dumps(data), encoding="utf-8")


def punkte(veraltet: int, quellen: int, mitteilung_an: bool) -> list[tuple[str, str, str, str]]:
    """(Schlüssel, Titel, Stand, Link)."""
    return [
        ("cv", "Master-CV auf den neuesten Stand bringen",
         f"{veraltet} veraltete Angabe(n) erkannt (z. B. Semester)" if veraltet else
         "keine veralteten Angaben erkannt – neue Projekte, Zertifikate oder Stationen nachtragen", "/master"),
        ("unterlagen", "Neue Zeugnisse und Zertifikate hochladen", "z. B. Notenspiegel, Arbeitszeugnis, Zertifikate",
         "/unterlagen"),
        ("profile", "Suchprofile prüfen", "Passen Rollen und Suchbegriffe noch? (z. B. Junior statt Werkstudent)",
         "/einstellungen"),
        ("quellen", "Quellen beobachten",
         f"{quellen} Quelle(n) liefern seit einer Weile nichts – Karriereseiten prüfen" if quellen else
         "alle Quellen liefern", "/firmen"),
        ("mitteilung", "Tägliche Mitteilung einschalten",
         "ist an" if mitteilung_an else "ist aus – unter Einstellungen einschalten", "/einstellungen"),
    ]


def render(token: str, data: dict, eintraege: list[tuple[str, str, str, str]]) -> str:
    if not data:
        return ""
    erledigt = set(data.get("erledigt") or [])
    offen = [e for e in eintraege if e[0] not in erledigt]
    if not offen:
        return ""
    seit = data.get("seit", "")
    form = lambda punkt, label, cls: (f'<form method="post" action="/rueckkehr" style="display:inline">'  # noqa: E731
                                      f'<input type="hidden" name="token" value="{token}"><input type="hidden" '
                                      f'name="punkt" value="{punkt}"><button class="{cls}">{label}</button></form>')
    zeilen = "".join(
        f'<li><div><a href="{link}"><b>{esc(titel)}</b></a><p class="muted">{esc(stand)}</p></div>'
        f'{form(key, "Erledigt", "ghost small")}</li>' for key, titel, stand, link in offen)
    return (f'<div class="card heute"><div class="head"><h2>Willkommen zurück</h2><span class="muted">Suche wieder '
            f'aktiv seit {esc(seit[8:10])}.{esc(seit[5:7])}. · {len(offen)} Punkt(e) offen</span></div>'
            f'<ul>{zeilen}</ul><div class="row" style="margin-top:8px">{form("alle", "Alles erledigt", "small")}'
            f'</div></div>')
