"""Firmen aus companies.yaml in der Oberfläche: Liste, neue Firma hinzufügen, aktiv/inaktiv, und Erinnerung an
Karriereseiten, die das Tool nicht lesen kann („manuell prüfen“, laut neuestem Bericht).

Wann du eine Seite zuletzt selbst besucht hast, steht lokal in .gui_manuell.json (gitignored).
Dazu „Quellen beobachten“: was laut Pipeline-Verlauf (state/seen.sqlite) dauerhaft nichts mehr liefert. Wer einen
Eintrag von dort aus bearbeitet, bekommt einen Vermerk (.gui_beobachten.json, lokal): „wird überprüft“ bis zum nächsten
Lauf, danach „läuft wieder“ oder „weiterhin ein Problem“.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlsplit

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from . import erinnerungen, quellen_verlauf
from .config import load_companies, save_companies
from .eigene_stelle import BLOCKED_HOSTS
from .models import normalize
from .state import State

KATEGORIEN = ["msp", "systemhaus", "beratung", "energie", "bank", "versicherung", "konzern", "pruefung", "medien",
              "sonstige"]
VISITS = ".gui_manuell.json"
IGNORED = ".gui_ignoriert.json"
GEAENDERT = ".gui_beobachten.json"     # "firma:Zurich" → Datum der Änderung (ISO)
VERMERK_RE = re.compile(r"^(firma|quelle):.{1,120}$")
RECHTSFORM = re.compile(r"\b(gmbh|mbh|ag|se|kg|kgaa|co|ohg|ug|e v|ev|gbr|inc|ltd|llc|group|gruppe|holding|"
                        r"deutschland|germany)\b")
# Börsen und Hochschulseiten: deren Adresse ist keine Karriereseite der Firma
BOARD_HOSTS = ("arbeitsagentur.", "stellenwerk.", "hs-niederrhein.", "jobexport.", "empfehlungsbund.",
               "jobanzeiger.", "stepstone.", "linkedin.", "indeed.", "xing.", "glassdoor.", "monster.", "jobware.",
               "arbeitnow.", "adzuna.")
URL_RE = re.compile(r"https?://\S+")


class FirmaError(Exception):
    pass


# --- Firmen ---
def firmen(root: Path) -> list:
    path = root / "companies.yaml"
    return list((load_companies(path) or {}).get("firmen") or []) if path.exists() else []


def _liste(text: str) -> CommentedSeq:
    seq = CommentedSeq([t.strip() for t in (text or "").split(",") if t.strip()])
    seq.fa.set_flow_style()
    return seq


def add(root: Path, form: dict) -> str:
    name = (form.get("name") or "").strip()
    url = (form.get("karriereseite_url") or "").strip()
    if not name:
        raise FirmaError("Name fehlt.")
    if not url.startswith(("http://", "https://")):
        raise FirmaError("Die Karriereseite muss mit http:// oder https:// beginnen.")
    host = urlsplit(url).netloc.lower()
    if any(b in host for b in BLOCKED_HOSTS):
        raise FirmaError("Bitte die Karriereseite der Firma selbst angeben, keine Jobbörse wie LinkedIn oder StepStone.")
    path = root / "companies.yaml"
    doc = load_companies(path)
    if any(normalize(f.get("name", "")) == normalize(name) for f in doc.get("firmen") or []):
        raise FirmaError(f"„{name}“ steht schon in der Liste.")
    entry = CommentedMap()
    entry["name"] = name
    entry["kategorie"] = (form.get("kategorie") or "sonstige").strip()
    entry["branche"] = (form.get("branche") or "").strip() or None
    entry["karriereseite_url"] = url
    entry["ats"] = None
    entry["ats_id"] = None
    entry["standorte"] = _liste(form.get("standorte"))
    entry["fokus"] = _liste(form.get("fokus"))
    initiativ = CommentedMap([("moeglich", "unbekannt"), ("url", None), ("zuletzt_geprueft", None)])
    entry["initiativ"] = initiativ   # Blockstil: Flow-Maps mit leeren Werten hatten früher Parser-Probleme
    if (form.get("notizen") or "").strip():
        entry["notizen"] = form["notizen"].strip()
    doc["firmen"].append(entry)
    save_companies(doc, path)
    return name


def set_active(root: Path, name: str, aktiv: bool) -> bool:
    path = root / "companies.yaml"
    doc = load_companies(path)
    entry = next((f for f in doc.get("firmen") or [] if f.get("name") == name), None)
    if entry is None:
        return False
    if aktiv:
        entry.pop("aktiv", None)          # Standard ist aktiv
    else:
        entry["aktiv"] = False
    save_companies(doc, path)
    return True


# --- Vorschläge aus gefundenen Stellen ---
def _key(name: str) -> str:
    return re.sub(r"\s+", " ", RECHTSFORM.sub(" ", normalize(name))).strip()


def _ignored(root: Path) -> list[str]:
    try:
        return json.loads((root / IGNORED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def ignore(root: Path, name: str) -> None:
    data = _ignored(root)
    if _key(name) not in data:
        data.append(_key(name))
    (root / IGNORED).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def suggestions(root: Path, details: list[dict], ausschluss: list[str], limit: int = 10) -> list[dict]:
    """Firmen aus gefundenen Stellen, die noch nicht in companies.yaml stehen (nach Trefferzahl)."""
    known = set()
    for f in firmen(root):
        known.add(_key(f.get("name", "")))
        known.update(_key(n) for n in f.get("match_namen") or [])
    blocked = {_key(a) for a in ausschluss} | set(_ignored(root))
    groups: dict[str, dict] = {}
    for d in details:
        company = (d.get("company") or "").strip()
        key = _key(company)
        if not key or company.startswith("(") or len(key) < 2:
            continue
        if any(k and (k in key or key in k) for k in known | blocked):
            continue
        g = groups.setdefault(key, {"name": company, "anzahl": 0, "titel": [], "url": ""})
        g["anzahl"] += 1
        if len(g["titel"]) < 3:
            g["titel"].append(d.get("title") or "")
        host = urlsplit(d.get("url") or "").netloc.lower()
        if not g["url"] and host and not any(b in host for b in BOARD_HOSTS):
            g["url"] = f"https://{host}/"
    return sorted(groups.values(), key=lambda g: (-g["anzahl"], g["name"].lower()))[:limit]


# --- Manuell prüfen ---
def manual_entries(root: Path) -> list[dict]:
    """Einträge unter „Manuell prüfen“ im neuesten Bericht: [{name, grund, url}]."""
    reports = sorted((root / "reports").glob("*.md"))
    if not reports:
        return []
    lines, active = [], False
    for line in reports[-1].read_text(encoding="utf-8").splitlines():
        if line.strip() == "**Manuell prüfen:**":
            active = True
            continue
        if active:
            if line.startswith("- "):
                lines.append(line[2:].strip())
            elif line.strip() and not line.startswith("- "):
                break
    urls = {f.get("name"): f.get("karriereseite_url") for f in firmen(root)}
    out = []
    for text in lines:
        name, _, rest = text.partition(": ")
        match = URL_RE.search(rest)
        url = match.group(0) if match else urls.get(name, "")
        grund = URL_RE.sub("", rest).strip(" –-")
        out.append({"name": name, "grund": grund, "url": url})
    return out


def visits(root: Path) -> dict[str, str]:
    try:
        return json.loads((root / VISITS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def mark_visited(root: Path, name: str, today: date) -> None:
    data = visits(root)
    data[name] = today.isoformat()
    (root / VISITS).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def next_visit(root: Path, name: str, today: date, days: int) -> date:
    """Wann die Seite wieder dran ist: letzter Besuch + `days`, frühestens heute."""
    last = visits(root).get(name)
    return max(today, date.fromisoformat(last) + timedelta(days=days)) if last else today


def due(root: Path, today: date, days: int) -> list[dict]:
    """Manuell zu prüfende Seiten, die du schon besucht hast und die seit mindestens `days` Tagen wieder dran sind.
    Noch nie besuchte Seiten zählen nicht als Warnung (stehen ruhig in der Firmen-Liste), sonst gewöhnt man sich an
    einen Dauerhinweis und übersieht ihn."""
    seen = visits(root)
    out = []
    for e in manual_entries(root):
        last = seen.get(e["name"])
        age = (today - date.fromisoformat(last)).days if last else None
        if age is not None and age >= days:
            out.append({**e, "zuletzt": last, "tage": age})
    return out


# --- Darstellung ---
def initiativ_karte(kandidaten: list, bewerbungen: dict[str, str]) -> str:
    """Karte „Initiativ bewerben“: dieselbe Auswahl wie im Bericht (initiativ_liste), vollständig.
    `bewerbungen`: Firmenname (klein) → Status einer Initiativbewerbung aus applications.csv."""
    if not kandidaten:
        return ""
    esc = lambda v: escape(str(v if v is not None else ""))  # noqa: E731
    zeilen = []
    for tip, hat_stellen in kandidaten:
        status = bewerbungen.get(tip.firma.lower())
        chips = (('<span class="status frist">hat gerade passende Stellen – lieber direkt bewerben</span> '
                  if hat_stellen else "")
                 + (f'<span class="status">{esc(status)}</span>' if status else ""))
        zeilen.append(f'<tr><td><b>{esc(tip.firma)}</b> {chips}<br><span class="muted">{esc(tip.warum)}</span></td>'
                      f'<td class="act"><a class="btn ghost small" href="{esc(tip.url)}" target="_blank" '
                      f'rel="noopener">Initiativ-Seite</a></td></tr>')
    return (f'<div class="card"><h2>Initiativ bewerben ({len(kandidaten)})</h2><p class="muted">Firmen in Reichweite, '
            f'die Initiativbewerbungen annehmen (companies.yaml: initiativ.moeglich ja). Der Bericht nennt nur neu '
            f'dazugekommene. Wichtige Kategorien zuerst, Firmen mit passenden Stellen am Ende.</p>'
            f'<table>{"".join(zeilen)}</table></div>')


def render(root: Path, token: str, today: date, days: int, message: str = "",
           vorschlaege: list[dict] | None = None, beobachten: list | None = None, cfg: dict | None = None,
           status: dict | None = None, behoben: list | None = None, initiativ_namen: set | None = None) -> str:
    esc = lambda v: escape(str(v if v is not None else ""))  # noqa: E731
    beobachten = beobachten or []
    by_firma = {w.name: w for w in beobachten if w.art == "firma"}
    urls = {f.get("name"): f.get("karriereseite_url") for f in firmen(root)}
    status, behoben = status or {}, behoben or []
    warn_rows = "".join(_warn_row(w, urls, esc, status.get(f"{w.art}:{w.name}")) for w in beobachten) + "".join(
        f'<div class="watch-item done"><div><b>{esc(name)}</b><p>{esc(text)}</p></div></div>' for name, text in behoben)
    warn_html = (f'<div class="card"><h2>Quellen beobachten</h2><p class="muted">Liefern seit mehreren Läufen der '
                 f'Pipeline nichts mehr oder nur Fehler. Meist ist die Karriereseite umgezogen.</p>'
                 f'<div class="watch">{warn_rows}</div></div>' if beobachten or behoben else "")
    vor_rows = []
    for v in vorschlaege or []:
        titel = "; ".join(v["titel"])
        vor_rows.append(
            f'<tr><td><b>{esc(v["name"])}</b> <span class="muted">({v["anzahl"]} Stelle(n))</span><br>'
            f'<span class="muted">{esc(titel)}</span></td><td>'
            f'<form method="post" action="/firmen/neu" class="row"><input type="hidden" name="token" value="{token}">'
            f'<input type="hidden" name="name" value="{esc(v["name"])}">'
            f'<input name="karriereseite_url" value="{esc(v["url"])}" placeholder="Karriereseite eintragen" required '
            f'style="flex:1;min-width:180px"><button class="small">Hinzufügen</button></form></td>'
            f'<td class="act"><form method="post" action="/firmen/ignorieren"><input type="hidden" name="token" '
            f'value="{token}"><input type="hidden" name="name" value="{esc(v["name"])}">'
            f'<button class="ghost small">Ignorieren</button></form></td></tr>')
    vor_html = (f'<div class="card"><h2>Vorschläge aus deinen Treffern</h2><p class="muted">Firmen, die in gefundenen '
                f'Stellen vorkommen, aber noch nicht in deiner Liste stehen. Prüf die Karriereseite, bevor du '
                f'hinzufügst.</p><table>{"".join(vor_rows)}</table></div>' if vor_rows else "")
    seen = visits(root)
    erinnert = erinnerungen.eingetragen(root)
    manual = manual_entries(root)
    manual_names = {m["name"] for m in manual}
    rows = []
    for m in manual:
        last = seen.get(m["name"])
        age = (today - date.fromisoformat(last)).days if last else None
        state = ('<span class="muted">noch nicht besucht</span>' if age is None else
                 f'<span class="err">vor {age} Tagen</span>' if age >= days else
                 f'<span class="muted">{"heute" if age == 0 else "gestern" if age == 1 else f"vor {age} Tagen"}</span>')
        link = (f'<a href="{esc(m["url"])}" target="_blank" rel="noopener">Seite öffnen</a>' if m["url"] else "")
        erinnern = ""
        if cfg is not None and erinnerungen.verfuegbar():
            e = erinnerungen.fuer_besuch(m["name"], m["url"], next_visit(root, m["name"], today, days), cfg)
            erinnern = ('<span class="muted">in Erinnerungen</span> ' if e.schluessel in erinnert else
                        f'<form method="post" action="/erinnern" style="display:inline"><input type="hidden" '
                        f'name="token" value="{token}"><input type="hidden" name="art" value="besuch">'
                        f'<input type="hidden" name="name" value="{esc(m["name"])}"><button class="ghost small" '
                        f'title="Erinnerung für den nächsten Besuch ({e.faellig:%d.%m.})">Erinnern</button></form> ')
        rows.append(f'<tr><td><b>{esc(m["name"])}</b><br><span class="muted">{esc(m["grund"])}</span></td>'
                    f'<td>{state}</td><td class="act">{link} {erinnern}'
                    f'<form method="post" action="/firmen/besucht" style="display:inline">'
                    f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="name" '
                    f'value="{esc(m["name"])}"><button class="ghost small">Besucht</button></form></td></tr>')
    manual_html = (f'<table>{"".join(rows)}</table>' if rows else
                   '<p class="muted">Im neuesten Bericht gibt es keine Seiten zum manuellen Prüfen.</p>')

    firm_rows = []
    for f in firmen(root):
        aktiv = f.get("aktiv", True) is not False
        ini = (f.get("initiativ") or {}).get("moeglich") or "unbekannt"
        if ini == "ja" and initiativ_namen is not None and aktiv and f.get("name") not in initiativ_namen:
            ini = "ja (Standort außerhalb der Reichweite oder ohne Link – nicht unter „Initiativ bewerben“)"
        badges = "".join([
            '' if aktiv else ' <span class="status">inaktiv</span>',
            ' <span class="status">manuell prüfen</span>' if f.get("name") in manual_names else '',
            ' <span class="status frist">beobachten</span>' if f.get("name") in by_firma else '',
            ' <span class="status">nur Initiativ</span>' if f.get("abruf") == "nur_initiativ" else ''])
        orte = ", ".join(f.get("standorte") or [])
        search = f"{f.get('name')} {f.get('kategorie')} {f.get('branche')} {orte}".lower()
        toggle = (f'<form method="post" action="/firmen/aktiv" style="display:inline">'
                  f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="name" '
                  f'value="{esc(f.get("name"))}"><input type="hidden" name="aktiv" value="{"" if aktiv else "1"}">'
                  f'<button class="ghost small">{"deaktivieren" if aktiv else "aktivieren"}</button></form>')
        firm_rows.append(
            f'<tr data-s="{esc(search)}"><td><a href="{esc(f.get("karriereseite_url"))}" target="_blank" '
            f'rel="noopener"><b>{esc(f.get("name"))}</b></a>{badges}<br><span class="muted">'
            f'{esc(f.get("kategorie"))}{" · " + esc(f.get("branche")) if f.get("branche") else ""}'
            f'{" · " + esc(orte) if orte else ""}</span>'
            f'{"<br><span class=muted>" + esc(f.get("notizen")) + "</span>" if f.get("notizen") else ""}</td>'
            f'<td class="muted">Initiativ: {esc(ini)}<br>Quelle: {esc(f.get("ats") or "wird erkannt")}</td>'
            f'<td class="act">{toggle}</td></tr>')
    options = "".join(f'<option{" selected" if k == "sonstige" else ""}>{k}</option>' for k in KATEGORIEN)
    return f"""
<h1>Firmen</h1><p class="sub">companies.yaml · Änderungen werden beim Beenden hochgeladen und gelten ab dem nächsten
Lauf der Pipeline.</p>
{message}
{warn_html}
<div class="card"><h2>Manuell prüfen</h2>
<p class="muted">Diese Karriereseiten kann das Tool nicht automatisch lesen. Schau etwa alle {days} Tage selbst vorbei
und klick danach auf „Besucht“.</p>{manual_html}</div>
{vor_html}
<div class="card"><h2>Neue Firma</h2>
<form method="post" action="/firmen/neu"><input type="hidden" name="token" value="{token}">
<div class="grid2">
<div><label>Name (Pflicht)</label><input name="name" required></div>
<div><label>Karriereseite (Pflicht, am besten die Seite mit der Stellenliste)</label>
<input name="karriereseite_url" placeholder="https://firma.de/karriere/jobs" required></div>
<div><label>Kategorie</label><select name="kategorie">{options}</select></div>
<div><label>Branche (optional)</label><input name="branche" placeholder="z. B. IT-Beratung"></div>
<div><label>Standorte (mit Komma getrennt)</label><input name="standorte" placeholder="Köln, Remote"></div>
<div><label>Fokus (mit Komma getrennt)</label><input name="fokus" placeholder="Cloud, IAM, Security"></div>
</div>
<label>Notizen (optional)</label><input name="notizen">
<p class="muted">Stellenquelle (ATS) und Initiativ-Seite erkennt die Pipeline beim nächsten Lauf selbst – mit
robots.txt-Prüfung. Ansprechpersonen nur eintragen, wenn die Firma sie selbst für Bewerbungen nennt.</p>
<p><button>Firma hinzufügen</button></p></form></div>
<div class="card"><div class="row" style="justify-content:space-between;align-items:baseline">
<h2>Alle Firmen ({len(firm_rows)})</h2><a href="/einstellungen/datei?name=companies.yaml">Als Datei bearbeiten</a></div>
<p class="muted">Ändern oder löschen (z. B. neue Karriereseite, Warnhinweis, Initiativ-Status): als Datei bearbeiten.
Vor dem Speichern wird geprüft; der alte Stand bleibt als .bak daneben.</p>
<input id="filter" placeholder="Filtern nach Name, Kategorie, Branche oder Ort" style="margin-bottom:8px">
<table>{"".join(firm_rows)}</table></div>"""


# Quellen im Bericht → Abschnitt in config.yaml (sources.<key>), damit „bearbeiten“ an die richtige Stelle springt
QUELLE_ABSCHNITT = {"Bundesagentur": "bundesagentur:", "Hochschule Niederrhein": "hsnr:", "Stellenwerk": "stellenwerk:",
                    "Firmen-Karriereseiten": "companies:", "Job-Alert-Mails": "mail_alerts:"}


def _warn_row(w, urls: dict, esc, stand: tuple[str, str] | None = None) -> str:
    """Eine Warnung mit Aktionen: Firma → Karriereseite öffnen und Eintrag in companies.yaml bearbeiten;
    Quelle → ihren Abschnitt in config.yaml bearbeiten. `stand`: Vermerk nach einer Änderung (siehe beobachten)."""
    von = "&amp;von=" + quote(f"{w.art}:{w.name}")
    aktionen = []
    if w.art == "firma":
        if urls.get(w.name):
            aktionen.append(f'<a class="btn ghost small" href="{esc(urls[w.name])}" target="_blank" '
                            f'rel="noopener">Karriereseite öffnen</a>')
        aktionen.append(f'<a class="btn ghost small" href="/einstellungen/datei?name=companies.yaml&amp;suche='
                        f'{quote("name: " + w.name)}{von}">Eintrag bearbeiten</a>')
    else:
        abschnitt = next((v for k, v in QUELLE_ABSCHNITT.items() if w.name.startswith(k)), "")
        aktionen.append(f'<a class="btn ghost small" href="/einstellungen/datei?name=config.yaml'
                        f'{"&amp;suche=" + quote(abschnitt) if abschnitt else ""}{von}">In config.yaml bearbeiten</a>')
    vermerk = f'<span class="chip {stand[0]}">{esc(stand[1])}</span>' if stand else ""
    return (f'<div class="watch-item{" " + stand[0] if stand else ""}"><div><b>{"Firma" if w.art == "firma" else "Quelle"} '
            f'{esc(w.name)}</b><p>{esc(w.text)}</p>{vermerk}</div><div class="row">{"".join(aktionen)}</div></div>')


def _verlauf(root: Path, cfg: dict) -> dict:
    state = State(root / "state" / "seen.sqlite", readonly=True)
    history = state.source_history(quellen_verlauf.limits(cfg)["verlauf"])
    state.close()
    return history


def warnungen(root: Path, cfg: dict, history: dict | None = None) -> list:
    """Warnungen aus dem Verlauf: aktive Firmen und Quellen, die im letzten Lauf dabei waren."""
    history = _verlauf(root, cfg) if history is None else history
    if not history:
        return []
    letzter = max(entries[0][0] for entries in history.values())
    aktiv = {("firma", f.get("name")) for f in firmen(root) if f.get("aktiv", True) is not False}
    aktiv |= {key for key, entries in history.items() if key[0] == "quelle" and entries[0][0] == letzter}
    return quellen_verlauf.warnungen(history, cfg, aktiv)


# --- Vermerk „geändert“ bei Quellen beobachten ---
def vermerke(root: Path) -> dict[str, str]:
    try:
        data = json.loads((root / GEAENDERT).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def vermerken(root: Path, schluessel: str, heute: date) -> None:
    """Eintrag „firma:Name“ oder „quelle:Name“ als geändert merken; Vermerke älter als 30 Tage fallen weg."""
    if not VERMERK_RE.match(schluessel or ""):
        return
    grenze = (heute - timedelta(days=30)).isoformat()
    data = {k: v for k, v in vermerke(root).items() if v >= grenze}
    data[schluessel] = heute.isoformat()
    (root / GEAENDERT).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def beobachten(root: Path, cfg: dict) -> tuple[list, dict[str, tuple[str, str]], list[tuple[str, str]]]:
    """(Warnungen, Status je „art:name“, behoben). Status: ("pruefung", Text) bis zum nächsten Lauf nach der
    Änderung, danach ("offen", Text), solange die Warnung bleibt. Behoben: nach der Änderung keine Warnung mehr."""
    history = _verlauf(root, cfg)
    liste = warnungen(root, cfg, history)
    marks = vermerke(root)
    status, aktiv = {}, set()
    for w in liste:
        key = f"{w.art}:{w.name}"
        aktiv.add(key)
        if key not in marks:
            continue
        datum = _kurzdatum(marks[key])
        zuletzt = (history.get((w.art, w.name)) or [("", 0, "")])[0][0]
        status[key] = (("pruefung", f"Geändert am {datum} · wird beim nächsten Lauf überprüft") if zuletzt <= marks[key]
                       else ("offen", f"Nach deiner Änderung am {datum} weiterhin ein Problem – bitte noch einmal ansehen"))
    behoben = []
    for key, tag in marks.items():
        art, _, name = key.partition(":")
        zuletzt = (history.get((art, name)) or [("", 0, "")])[0][0]
        if key not in aktiv and zuletzt > tag:
            behoben.append((name, f"läuft wieder (geprüft beim Lauf am {_kurzdatum(zuletzt)})"))
    return liste, status, behoben


def _kurzdatum(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}." if len(iso) >= 10 else iso


def due_link(n: int) -> str:
    return (f'<div class="card info"><p>{n} Karriereseite(n) solltest du mal wieder selbst ansehen – '
            f'<a href="/firmen">zu den Firmen</a>.</p></div>' if n else "")

