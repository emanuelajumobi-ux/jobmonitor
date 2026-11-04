"""Passende Firmen finden: die KI stellt eine Liste von Arbeitgebern zusammen, die zu Lebenslauf, Suchprofilen und
Wohnort passen – als Ergänzung zu „Vorschläge aus deinen Treffern“ (dort nur Firmen, die schon Stellen hatten).

Gesendet werden nur Wohnort, Suchprofile, ein optionaler Wunsch und der fachliche Teil des Lebenslaufs (keine
persönlichen Daten). Die App ruft dabei keine Webseiten ab; die Karriereseiten nennt die KI aus ihrem Wissen – sie
können veraltet sein, darum prüft man sie vor dem Hinzufügen (Link öffnen). Jobbörsen wie LinkedIn werden aussortiert.
Hinzugefügte Firmen liest die Pipeline wie jede andere, mit robots.txt-Prüfung.

Die letzte Liste liegt in .gui_ki.json → firmenfinder.
"""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

ANZAHL = (10, 20, 30)


def _ziele(cfg: dict) -> str:
    zeilen = []
    for p in (cfg.get("profile") or {}).values():
        if not isinstance(p, dict) or p.get("enabled") is False:
            continue
        rollen = ", ".join(list(p.get("rollen") or {})[:8])
        fach = ", ".join(list(p.get("fach") or {})[:10])
        zeilen.append(f"- {p.get('name') or ''}: {p.get('zielrolle') or ''}; Rollen-Wörter: {rollen}"
                      + (f"; Fach: {fach}" if fach else ""))
    return "\n".join(zeilen) or "(keine Suchprofile)"


def prompt(cfg: dict, cv_text: str, vorhandene: list[str], wunsch: str, anzahl: int) -> str:
    from .gui_firmen import KATEGORIEN
    ort = cfg.get("ort") or {}
    from .location import zentrum as wohnort
    zentrum = wohnort(ort) or "(noch nicht festgelegt – nenne Firmen mit Remote-Möglichkeit in Deutschland)"
    return (
        "Du hilfst bei der Jobsuche: Stelle eine Liste von Arbeitgebern zusammen, deren Karriereseiten man beobachten "
        "sollte, weil dort regelmäßig passende Stellen ausgeschrieben werden könnten.\n\n"
        f"WOHNORT: {zentrum}; erreichbar sind Standorte bis etwa {ort.get('max_fahrzeit_min', 60)} Minuten mit Bahn/ÖPNV "
        "sowie Remote-Stellen in Deutschland.\n"
        f"SUCHPROFILE:\n{_ziele(cfg)}\n"
        + (f"WUNSCH: {wunsch}\n" if wunsch else "")
        + f"\nLEBENSLAUF (fachlich, ohne persönliche Angaben):\n{cv_text[:5000]}\n\n"
        f"SCHON IN DER LISTE (nicht noch einmal nennen): {', '.join(vorhandene[:300]) or '(keine)'}\n\n"
        f"Antworte nur mit JSON: {{\"firmen\": [{{\"name\": \"...\", \"kategorie\": \"...\", \"branche\": \"...\", "
        "\"standorte\": [\"...\"], \"fokus\": [\"...\"], \"karriereseite_url\": \"https://...\", \"warum\": \"...\"}]}\n"
        f"- Genau {anzahl} reale, existierende Arbeitgeber mit Standort im erreichbaren Umkreis (oder Remote in "
        "Deutschland). Mische Konzerne, Mittelstand und kleinere Firmen; keine Personalvermittler und Zeitarbeit.\n"
        f"- kategorie: eine von {', '.join(KATEGORIEN)}.\n"
        "- karriereseite_url: die offizielle Karriere- oder Jobseite der Firma (eigene Domain oder ihr "
        "Bewerbungssystem), nie LinkedIn, StepStone, Indeed oder eine andere Jobbörse. Wenn du sie nicht sicher weißt, "
        "die Startseite der Firma.\n"
        "- fokus: 2 bis 4 Themen, die zu den Suchprofilen passen.\n"
        "- warum: ein kurzer Satz, warum die Firma passt (Bezug zu Lebenslauf oder Suchprofil).")


def _gueltig(f: dict) -> bool:
    from .gui_firmen import BOARD_HOSTS
    from .eigene_stelle import BLOCKED_HOSTS
    url = str(f.get("karriereseite_url") or "")
    host = urlsplit(url).netloc.lower()
    return (bool(str(f.get("name") or "").strip()) and url.startswith(("https://", "http://")) and bool(host)
            and not any(b in host for b in (*BLOCKED_HOSTS, *BOARD_HOSTS)))


def finden(root: Path, cfg: dict, cv: dict, wunsch: str = "", anzahl: int = 20, ask=None,
           heute: date | None = None) -> list[dict]:
    """Neue Liste von der KI holen, aufräumen und speichern. Gibt die Firmen zurück."""
    from . import ki, llm
    from .gui_firmen import KATEGORIEN, _key, firmen
    anzahl = anzahl if anzahl in ANZAHL else 20
    vorhanden = [str(f.get("name") or "") for f in firmen(root)]
    antwort = llm.json_aus(ki.fragen(root, cfg, prompt(cfg, ki.cv_text(cv or {}), vorhanden, wunsch.strip()[:500],
                                                          anzahl), effort="medium", max_tokens=9000, ask=ask))
    liste = (antwort or {}).get("firmen") if isinstance(antwort, dict) else None
    if not isinstance(liste, list) or not liste:
        raise ki.KiError("Die KI hat keine lesbare Firmenliste geliefert – bitte noch einmal versuchen.")
    schon = {_key(n) for n in vorhanden}
    out, gesehen = [], set()
    for f in liste:
        if not isinstance(f, dict) or not _gueltig(f):
            continue
        key = _key(f["name"])
        if key in schon or key in gesehen:
            continue
        gesehen.add(key)
        out.append({"name": str(f["name"]).strip()[:120],
                    "kategorie": f.get("kategorie") if f.get("kategorie") in KATEGORIEN else "sonstige",
                    "branche": str(f.get("branche") or "")[:80],
                    "standorte": [str(s)[:60] for s in (f.get("standorte") or []) if s][:5],
                    "fokus": [str(s)[:40] for s in (f.get("fokus") or []) if s][:5],
                    "karriereseite_url": str(f["karriereseite_url"]).strip()[:300],
                    "warum": str(f.get("warum") or "")[:300]})
    data = ki.laden(root)
    data["firmenfinder"] = {"datum": (heute or date.today()).isoformat(), "wunsch": wunsch.strip()[:500],
                            "firmen": out}
    ki._speichern(root, data)
    return out


def gespeichert(root: Path) -> dict:
    from . import ki
    return ki.laden(root).get("firmenfinder") or {}


def karte(root: Path, token: str, ki_an: bool) -> str:
    """Karte „Passende Firmen finden“ auf der Seite Firmen."""
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    from .gui_firmen import _ignored, _key, firmen
    esc = lambda v: escape(str(v if v is not None else ""))  # noqa: E731
    letzte = gespeichert(root)
    vorhanden = {_key(str(f.get("name") or "")) for f in firmen(root)} | set(_ignored(root))
    offen = [f for f in letzte.get("firmen") or [] if _key(f["name"]) not in vorhanden]
    zeilen = []
    for f in offen:
        orte = ", ".join(f.get("standorte") or [])
        verborgen = "".join(f'<input type="hidden" name="{k}" value="{esc(v)}">' for k, v in (
            ("name", f["name"]), ("kategorie", f["kategorie"]), ("branche", f["branche"]), ("standorte", orte),
            ("fokus", ", ".join(f.get("fokus") or [])), ("notizen", f"Vorschlag der KI: {f['warum']}")))
        zeilen.append(
            f'<tr><td><b>{esc(f["name"])}</b><br><span class="muted">{esc(f["kategorie"])}'
            f'{" · " + esc(f["branche"]) if f["branche"] else ""}{" · " + esc(orte) if orte else ""}</span>'
            f'{"<br>" + esc(f["warum"]) if f["warum"] else ""}</td>'
            f'<td><form method="post" action="/firmen/neu" class="row"><input type="hidden" name="token" '
            f'value="{token}">{verborgen}<input name="karriereseite_url" value="{esc(f["karriereseite_url"])}" '
            f'required style="flex:1;min-width:180px"><a class="btn ghost small" href="{esc(f["karriereseite_url"])}" '
            f'target="_blank" rel="noopener">Prüfen</a><button class="small">Hinzufügen</button></form></td>'
            f'<td class="act"><form method="post" action="/firmen/ignorieren"><input type="hidden" name="token" '
            f'value="{token}"><input type="hidden" name="name" value="{esc(f["name"])}"><button class="ghost small">'
            f'Ignorieren</button></form></td></tr>')
    if ki_an:
        optionen = "".join(f'<option value="{n}"{" selected" if n == 20 else ""}>{n} Firmen</option>' for n in ANZAHL)
        formular = (f'<form method="post" action="/firmen/finden" class="row" style="gap:8px;margin:10px 0">'
                    f'<input type="hidden" name="token" value="{token}"><input name="wunsch" '
                    f'value="{esc(letzte.get("wunsch") or "")}" placeholder="Optional: z. B. eher Mittelstand, '
                    f'Energie und Versicherungen, kein Konzern" style="flex:1;min-width:240px"><select name="anzahl" '
                    f'style="width:auto">{optionen}</select><button class="small" data-ki="KI sucht passende Firmen …">'
                    f'{"Neue Liste erstellen" if letzte else "Liste erstellen"}</button></form>')
    else:
        formular = ('<p><a class="btn ghost small" href="/einstellungen#ki">KI einrichten</a> <span class="muted">'
                    '– ohne KI helfen die „Vorschläge aus deinen Treffern“.</span></p>')
    stand = (f'<p class="muted">Liste vom {date.fromisoformat(letzte["datum"]):%d.%m.%Y}: {len(offen)} noch offen '
             f'(hinzugefügte und ignorierte sind ausgeblendet).</p>' if letzte else "")
    tabelle = f'<table>{"".join(zeilen)}</table>' if zeilen else ""
    return (f'<div class="card" id="finden"><h2>Passende Firmen finden</h2><p class="muted">Die KI stellt Arbeitgeber in '
            f'deiner Nähe zusammen, die zu Lebenslauf und Suchprofilen passen – auch solche, die noch keine Stelle '
            f'ausgeschrieben haben. Gesendet werden Wohnort, Suchprofile und dein Master-CV ohne persönliche Angaben. '
            f'Die Karriereseiten kennt die KI nur aus ihrem Wissen: vor dem Hinzufügen mit „Prüfen“ öffnen und die '
            f'Adresse bei Bedarf korrigieren.</p>{formular}{stand}{tabelle}</div>')
