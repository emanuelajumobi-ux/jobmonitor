"""Suchprofile in der App anlegen, bearbeiten und löschen (Einstellungen → Suchprofile).

Gespeichert wird nur der Block des einen Profils unter `profile:` in config.yaml; der Rest der Datei bleibt Zeichen
für Zeichen erhalten. Innerhalb des Profils bleiben Kommentare und Felder, die das Formular nicht kennt
(slug_begriffe, ausschluss_titel, ats_suchbegriffe), erhalten. Grenzen für sparsame Abfragen: suchprofil.MAX_AKTIV
aktive Profile, suchprofil.MAX_BEGRIFFE Suchbegriffe je Quelle.
"""
from __future__ import annotations

import io
import json
import re
from html import escape
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from . import suchprofil
from .gui_wartung import speichern as datei_speichern

ART = {"studium": (34, "Werkstudent, Praktikum, Abschlussarbeit"),
       "ausbildung": (4, "Ausbildung"),
       "arbeit": (1, "Feste Stelle (Berufseinstieg)"),
       "alle": (None, "Alle Angebotsarten")}
ROLLE_STANDARD = 25
FACH_STANDARD = 8
MIN_FACH = 3


class SuchprofilError(Exception):
    pass


def esc(value) -> str:
    return escape(str(value if value is not None else ""))


# --- Formular lesen ---
def _zeilen(text: str) -> list[str]:
    return list(dict.fromkeys(z.strip() for z in (text or "").splitlines() if z.strip()))


def _gewichte(text: str, standard: int, was: str) -> dict[str, int]:
    """Zeilen „wort: punkte“ oder nur „wort“ (Standardpunkte)."""
    out: dict[str, int] = {}
    for zeile in _zeilen(text):
        wort, _, punkte = zeile.rpartition(":") if ":" in zeile else (zeile, "", "")
        wort = wort.strip().lower()
        try:
            wert = int(punkte.strip()) if punkte.strip() else standard
        except ValueError:
            raise SuchprofilError(f"{was}: „{zeile}“ – nach dem Doppelpunkt bitte eine Zahl.") from None
        if not wort or not 1 <= wert <= 40:
            raise SuchprofilError(f"{was}: „{zeile}“ – Punkte zwischen 1 und 40.")
        out[wort] = wert
    return out


def _synonyme(text: str) -> dict[str, list[str]]:
    """Zeilen „Begriff: Synonym, Synonym“."""
    out: dict[str, list[str]] = {}
    for zeile in _zeilen(text):
        begriff, _, rest = zeile.partition(":")
        if begriff.strip():
            out[begriff.strip()] = [s.strip().lower() for s in rest.split(",") if s.strip()]
    return out


def schluessel(name: str, vorhanden) -> str:
    key = name.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")[:30] or "profil"
    basis, i = key, 2
    while key in vorhanden:
        key, i = f"{basis}_{i}", i + 1
    return key


def aus_formular(form: dict, cfg: dict) -> tuple[str, dict]:
    """(Schlüssel, Felder) aus dem Formular; SuchprofilError mit allen Fehlern auf einmal."""
    profile = cfg.get("profile") or {}
    key = form.get("key", "")
    if key and key not in profile:
        raise SuchprofilError("Unbekanntes Suchprofil.")
    fehler = []
    name = (form.get("name") or "").strip()
    if not name:
        fehler.append("Bitte einen Namen angeben.")
    elif any((v or {}).get("name", k).lower() == name.lower() for k, v in profile.items() if k != key):
        fehler.append(f"Ein Suchprofil „{name}“ gibt es schon.")
    daten: dict = {"name": name, "enabled": bool(form.get("enabled")),
                   "zielrolle": (form.get("zielrolle") or "").strip(), "absicht": (form.get("absicht") or "").strip(),
                   "ausblick": (form.get("ausblick") or "").strip(),
                   "angebotsart": ART.get(form.get("art"), ART["alle"])[0],
                   "stufe": form.get("stufe") if form.get("stufe") in suchprofil.STUFEN else ""}
    try:
        daten["rollen"] = _gewichte(form.get("rollen", ""), ROLLE_STANDARD, "Rollen-Wörter")
        if not daten["rollen"]:
            fehler.append("Mindestens ein Rollen-Wort (z. B. werkstudent, junior, trainee).")
    except SuchprofilError as exc:
        fehler.append(str(exc))
    such = {q: _zeilen(form.get(f"such_{q}", "")) for q in ("bundesagentur", "stellenwerk")}
    for q, begriffe in such.items():
        if len(begriffe) > suchprofil.MAX_BEGRIFFE:
            fehler.append(f"Höchstens {suchprofil.MAX_BEGRIFFE} Suchbegriffe für {q.capitalize()} "
                          f"(jetzt {len(begriffe)}), damit die Seite nicht unnötig oft abgefragt wird.")
    if not any(such.values()):
        fehler.append("Mindestens einen Suchbegriff für die Bundesagentur oder Stellenwerk.")
    daten["suchbegriffe"] = such
    daten["fach"] = {}
    if form.get("fachgebiet") == "eigen":
        try:
            daten["fach"] = _gewichte(form.get("fach", ""), FACH_STANDARD, "Fach-Stichwörter")
            if len(daten["fach"]) < MIN_FACH:
                fehler.append(f"Für ein eigenes Fachgebiet mindestens {MIN_FACH} Fach-Stichwörter.")
        except SuchprofilError as exc:
            fehler.append(str(exc))
    daten["fit_begriffe"] = _synonyme(form.get("fit_begriffe", ""))
    andere_aktiv = sum(1 for k, v in profile.items() if k != key and (v or {}).get("enabled", True) is not False)
    if daten["enabled"] and andere_aktiv >= suchprofil.MAX_AKTIV:
        fehler.append(f"Höchstens {suchprofil.MAX_AKTIV} Suchprofile gleichzeitig aktiv. Schalte erst ein anderes ab "
                      "oder speichere dieses ausgeschaltet.")
    if fehler:
        raise SuchprofilError("\n".join(fehler))
    return key or schluessel(name, profile), daten


# --- config.yaml ändern (nur den Block des Profils) ---
def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096       # wie config.save: nichts neu umbrechen
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def _abschnitt(text: str) -> tuple[int, int]:
    """Anfang (nach „profile:“) und Ende des Abschnitts profile (ohne Kommentare, die schon zum nächsten gehören)."""
    m = re.search(r"^profile:[ \t]*(#.*)?\n", text, re.MULTILINE)
    if not m:
        raise SuchprofilError("Abschnitt „profile:“ nicht in config.yaml gefunden.")
    nxt = re.compile(r"^[^\s#]", re.MULTILINE).search(text, m.end())
    ende = nxt.start() if nxt else len(text)
    zeilen = text[m.end():ende].splitlines(keepends=True)
    while zeilen and (not zeilen[-1].strip() or zeilen[-1].startswith("#")):
        ende -= len(zeilen.pop())
    return m.end(), ende


def _block(text: str, key: str) -> tuple[int, int] | None:
    start, ende = _abschnitt(text)
    m = re.compile(rf"^  {re.escape(key)}:[ \t]*(#.*)?\n", re.MULTILINE).search(text, start, ende)
    if not m:
        return None
    nxt = re.compile(r"^ {0,2}\S", re.MULTILINE).search(text, m.end(), ende)
    return m.start(), nxt.start() if nxt else ende


def _setzen(ziel: CommentedMap, feld: str, wert) -> None:
    """Leere Werte entfernen, Unverändertes nicht anfassen (dann bleiben Kommentare darin erhalten)."""
    if wert in (None, "", [], {}):
        ziel.pop(feld, None)
    elif feld not in ziel or _plain(ziel[feld]) != wert:
        ziel[feld] = wert


def _plain(wert):
    return json.loads(json.dumps(wert))


FLOW = re.compile(r"^(\s*[^\s#][^:\n]*: \[)([^\]\n]*)\](.*)$")
BREITE = 120


def _umbrechen(block: str) -> str:
    """Listen in eckigen Klammern wie in der Datei üblich umbrechen (Folgezeilen unter dem ersten Eintrag)."""
    out = []
    for zeile in block.splitlines(keepends=True):
        m = FLOW.match(zeile.rstrip("\n"))
        if not m or len(zeile) <= BREITE:
            out.append(zeile)
            continue
        kopf, eintraege, rest = m.group(1), m.group(2).split(", "), m.group(3)
        zeilen, aktuell = [], kopf
        for i, eintrag in enumerate(eintraege):
            teil = eintrag + ("," if i < len(eintraege) - 1 else "]")
            if aktuell.strip() and aktuell != kopf and len(aktuell) + 1 + len(teil) > BREITE:
                zeilen.append(aktuell)
                aktuell = " " * len(kopf) + teil
            else:
                aktuell += ("" if aktuell == kopf else " ") + teil
        out.append("\n".join(zeilen + [aktuell + rest]) + "\n")
    return "".join(out)


def speichern(root: Path, key: str, daten: dict) -> None:
    path = root / "config.yaml"
    text = path.read_text(encoding="utf-8")
    doc = _yaml().load(text)
    alt = (doc.get("profile") or {}).get(key)
    profil = alt if isinstance(alt, CommentedMap) else CommentedMap()
    for feld in ("enabled", "name", "stufe", "zielrolle", "absicht", "ausblick", "angebotsart", "rollen"):
        _setzen(profil, feld, daten[feld] if feld != "enabled" else bool(daten[feld]))
    such = profil.get("suchbegriffe") if isinstance(profil.get("suchbegriffe"), CommentedMap) else CommentedMap()
    for q, begriffe in daten["suchbegriffe"].items():
        _setzen(such, q, begriffe)
    _setzen(profil, "suchbegriffe", such if such else None)
    _setzen(profil, "fach", daten["fach"])
    _setzen(profil, "fit_begriffe", daten["fit_begriffe"])
    if not isinstance(alt, CommentedMap):
        doc["profile"][key] = profil
    out = io.StringIO()
    _yaml().dump(doc, out)          # ganze Datei ausgeben, damit Kommentare in ihrer Spalte bleiben …
    ausgabe = out.getvalue()
    neu_block = _block(ausgabe, key)
    neu = _umbrechen(ausgabe[neu_block[0]:neu_block[1]])
    block = _block(text, key)       # … aber nur den Block dieses Profils übernehmen
    if block:
        text = text[:block[0]] + neu + text[block[1]:]
    else:
        _, ende = _abschnitt(text)
        text = text[:ende] + neu + text[ende:]
    datei_speichern(root, "config.yaml", text)


def loeschen(root: Path, key: str, cfg: dict) -> str:
    profile = cfg.get("profile") or {}
    if key == suchprofil.DEFAULT_KEY or len(profile) <= 1:
        raise SuchprofilError("Das Grundprofil Werkstudent bleibt; du kannst es aber ausschalten.")
    path = root / "config.yaml"
    text = path.read_text(encoding="utf-8")
    block = _block(text, key)
    if not block:
        raise SuchprofilError("Unbekanntes Suchprofil.")
    datei_speichern(root, "config.yaml", text[:block[0]] + text[block[1]:])
    return (profile.get(key) or {}).get("name", key)


# --- Darstellung ---
def portale(companies_doc) -> int:
    return sum(1 for h in (companies_doc or {}).get("hochschulen") or []
               if h.get("quelle") == "stellenwerk" and h.get("aktiv"))


def _abrufe(n: dict) -> str:
    return f"bis zu {n['bundesagentur']} Abrufe bei der Bundesagentur und {n['stellenwerk']} bei Stellenwerk"


def render_liste(token: str, cfg: dict, n_portale: int) -> str:
    profile = suchprofil.alle(cfg)
    aktiv = sum(1 for p in profile if p.enabled)
    zeilen = []
    for p in profile:
        art = next((label for wert, label in ART.values() if wert == p.angebotsart), ART["alle"][1])
        fach = "eigenes Fachgebiet" if p.fach else "gemeinsames Fachgebiet"
        schalter = (f'<form method="post" action="/einstellungen" style="display:inline"><input type="hidden" '
                    f'name="token" value="{token}"><input type="hidden" name="aktion" value="profil"><input '
                    f'type="hidden" name="key" value="{esc(p.key)}"><input type="hidden" name="an" '
                    f'value="{"" if p.enabled else "1"}"><button class="ghost small">'
                    f'{"ausschalten" if p.enabled else "einschalten"}</button></form>')
        zeilen.append(
            f'<tr><td><b>{esc(p.name)}</b><br><span class="muted">{esc(p.zielrolle)}</span></td>'
            f'<td class="muted">{esc(art)} · {fach}</td>'
            f'<td>{"<span class=ok>an</span>" if p.enabled else "<span class=muted>aus</span>"}</td>'
            f'<td class="act"><a class="btn ghost small" href="/einstellungen/suchprofil?key={esc(p.key)}">'
            f'Bearbeiten</a> {schalter}</td></tr>')
    return f"""<div class="card"><div class="row" style="justify-content:space-between;align-items:center">
<h2 style="margin:0">Suchprofile</h2><a class="btn small" href="/einstellungen/suchprofil">Neues Suchprofil</a></div>
<p class="muted">Gilt ab dem nächsten Lauf der Pipeline. Aktiv: {aktiv} von höchstens {suchprofil.MAX_AKTIV}.
Pro Lauf {_abrufe(suchprofil.anfragen(cfg, n_portale))} (Suchen plus nachgeladene Anzeigentexte).</p>
<table>{"".join(zeilen)}</table></div>"""


def _profil_formdaten(raw: dict) -> dict:
    such = raw.get("suchbegriffe") or {}
    art = next((k for k, (wert, _) in ART.items() if wert == raw.get("angebotsart")), "alle")
    return {"name": raw.get("name", ""), "enabled": raw.get("enabled", True) is not False,
            "zielrolle": raw.get("zielrolle", ""), "absicht": raw.get("absicht", ""),
            "ausblick": raw.get("ausblick", ""), "art": art, "stufe": raw.get("stufe") or "",
            "rollen": "\n".join(f"{k}: {v}" for k, v in (raw.get("rollen") or {}).items()),
            "such_bundesagentur": "\n".join(such.get("bundesagentur") or []),
            "such_stellenwerk": "\n".join(such.get("stellenwerk") or []),
            "fachgebiet": "eigen" if raw.get("fach") else "gemeinsam",
            "fach": "\n".join(f"{k}: {v}" for k, v in (raw.get("fach") or {}).items()),
            "fit_begriffe": "\n".join(f"{k}: {', '.join(v or [])}" for k, v in (raw.get("fit_begriffe") or {}).items())}


NEU = {"name": "", "enabled": True, "zielrolle": "", "absicht": "", "ausblick": "", "art": "studium", "stufe": "",
       "rollen": "werkstudent: 30\nworking student: 30\npraktikum: 18", "such_bundesagentur": "",
       "such_stellenwerk": "", "fachgebiet": "gemeinsam", "fach": "", "fit_begriffe": ""}


def render_formular(token: str, cfg: dict, key: str, n_portale: int, fehler: str = "",
                    eingabe: dict | None = None, ki_an: bool = False, hinweis: str = "") -> str:
    raw = (cfg.get("profile") or {}).get(key) or {}
    f = {**(_profil_formdaten(raw) if key else NEU), **(eingabe or {})}
    if eingabe is not None:
        f["enabled"] = bool(eingabe.get("enabled"))
    andere = [p for p in suchprofil.aktive(cfg) if p.key != key]
    basis = suchprofil.anfragen(cfg, n_portale, andere)
    src = cfg.get("sources") or {}
    ba, sw = src.get("bundesagentur") or {}, src.get("stellenwerk") or {}
    rechnung = {"basis": basis, "portale": n_portale, "faktor": 2 if ba.get("bundesweit_remote") else 1,
                "details": int(ba.get("max_details", 0)), "sw_details": int(sw.get("max_detail_pages", 0)),
                "max": suchprofil.MAX_BEGRIFFE}
    art = "".join(f'<option value="{k}"{" selected" if f["art"] == k else ""}>{esc(label)}</option>'
                  for k, (_, label) in ART.items())
    stufen = "".join(f'<option value="{k}"{" selected" if f.get("stufe") == k else ""}>{esc(v["name"])}</option>'
                     for k, v in suchprofil.STUFEN.items())
    fehler_html = ("".join(f"<p>{esc(z)}</p>" for z in fehler.splitlines()) if fehler else "")
    loeschen = ("" if not key or key == suchprofil.DEFAULT_KEY else
                f'<button class="ghost" name="aktion" value="loeschen" formnovalidate '
                f'onclick="return confirm(\'Suchprofil „{esc(f["name"])}“ löschen? Gefundene Stellen bleiben.\')">'
                f'Löschen</button>')
    eigen = f["fachgebiet"] == "eigen"
    ki_knopf = ('<button name="aktion" value="ki" class="ghost" formnovalidate data-ki="KI legt das Suchprofil an …">'
                'Felder mit KI ausfüllen</button><span class="muted">Gesendet: deine Beschreibung und dein Master-CV. '
                'Du prüfst alles, gespeichert wird erst mit „Speichern“.</span>' if ki_an else
                '<a href="/einstellungen#ki">API-Schlüssel in den Einstellungen hinterlegen</a>')
    return f"""<h1>{esc(f["name"]) if key else "Neues Suchprofil"}</h1>
<p class="sub">Suchprofil · <a href="/einstellungen">zurück zu den Einstellungen</a></p>
{f'<div class="card err">{fehler_html}</div>' if fehler_html else ""}
{f'<div class="card"><p class="ok">{esc(hinweis)}</p></div>' if hinweis else ""}
<form method="post" action="/einstellungen/suchprofil" id="sp"><input type="hidden" name="token" value="{token}">
<input type="hidden" name="key" value="{esc(key)}">
<div class="card info"><h2>Mit KI ausfüllen</h2>
<label for="wunsch">Was suchst du? In ein, zwei Sätzen</label>
<textarea id="wunsch" name="wunsch" rows="2" style="min-height:0"
placeholder="z. B. Werkstudentenjob im Bereich Data Engineering oder KI, gern mit Python, in Köln oder remote">{esc(f.get("wunsch", ""))}</textarea>
<div class="row" style="margin-top:10px">{ki_knopf}</div></div>
<div class="card"><h2>Grunddaten</h2>
<div class="grid2"><div><label for="name">Name</label><input id="name" name="name" value="{esc(f["name"])}" required
placeholder="z. B. Praktikum Security"></div>
<div><label for="art">Stellenart (Bundesagentur)</label><select id="art" name="art">{art}</select></div></div>
<label for="stufe">Karrierestufe (Vorlage für Rollen-Wörter und Stellenart; passt zu jedem Fachgebiet)</label>
<select id="stufe" name="stufe" data-vorlagen="{esc(json.dumps({k: {"art": v["art"], "rollen": v["rollen"]} for k, v in suchprofil.STUFEN.items()}))}">
<option value="">– keine Vorlage –</option>{stufen}</select>
<p class="muted">„Berufserfahren“ schließt Stellen mit senior, lead oder leiter im Titel nicht mehr aus.</p>
<label class="switch" style="margin-top:12px"><input type="checkbox" role="switch" name="enabled" value="1"
{" checked" if f["enabled"] else ""}><span class="track"></span><span>Aktiv (wird bei jedem Lauf abgefragt)</span></label>
<label for="zielrolle">Zielrolle für Anschreiben</label><input id="zielrolle" name="zielrolle" value="{esc(f["zielrolle"])}"
placeholder="z. B. Werkstudent IT-Security">
<div class="grid2"><div><label for="absicht">Absicht („… und suche …“)</label><input id="absicht" name="absicht"
value="{esc(f["absicht"])}" placeholder="eine Werkstudententätigkeit im Bereich …"></div>
<div><label for="ausblick">Ausblick (Schlusssatz)</label><input id="ausblick" name="ausblick" value="{esc(f["ausblick"])}"
placeholder="Langfristig möchte ich …"></div></div></div>

<div class="card"><h2>Was gesucht wird</h2>
<label for="rollen">Rollen-Wörter im Titel, je Zeile „wort: punkte“ (ohne Punkte: {ROLLE_STANDARD})</label>
<textarea id="rollen" name="rollen" rows="5" spellcheck="false">{esc(f["rollen"])}</textarea>
<p class="muted">Eine Stelle zählt nur, wenn eines davon im Titel steht. Mehr Punkte = weiter oben im Bericht.</p>
<div class="grid2"><div><label for="such_bundesagentur">Suchbegriffe Bundesagentur, einer je Zeile
<span class="zaehler" data-fuer="such_bundesagentur"></span></label>
<textarea id="such_bundesagentur" name="such_bundesagentur" rows="8">{esc(f["such_bundesagentur"])}</textarea></div>
<div><label for="such_stellenwerk">Suchbegriffe Stellenwerk, einer je Zeile
<span class="zaehler" data-fuer="such_stellenwerk"></span></label>
<textarea id="such_stellenwerk" name="such_stellenwerk" rows="8">{esc(f["such_stellenwerk"])}</textarea></div></div>
<p class="muted" id="abrufe"></p></div>

<div class="card"><h2>Fachgebiet</h2>
<p class="muted">Bestimmt, welche Stellen inhaltlich passen und wie hoch ihr Score ist.</p>
<label class="modus{"" if eigen else " an"}" style="margin-bottom:8px"><input type="radio" name="fachgebiet"
value="gemeinsam"{"" if eigen else " checked"}><b>Gemeinsam mit den anderen Profilen</b><span class="muted">Cloud,
Azure, IAM, DevOps, IT-Security … aus config.yaml (filter.fach). Richtig für Profile im selben Bereich.</span></label>
<label class="modus{" an" if eigen else ""}"><input type="radio" name="fachgebiet" value="eigen"{" checked" if eigen else ""}>
<b>Eigenes Fachgebiet</b><span class="muted">Für ein anderes Feld, z. B. Data Science oder Netzwerktechnik. Dann
zählen nur diese Stichwörter, die IT-Prüfungen des gemeinsamen Fachgebiets entfallen.</span></label>
<div id="fachfeld"{"" if eigen else " hidden"}><label for="fach">Fach-Stichwörter, je Zeile „wort: punkte“
(ohne Punkte: {FACH_STANDARD}; Titel zählt doppelt)</label>
<textarea id="fach" name="fach" rows="7" spellcheck="false"
placeholder="data engineering: 12&#10;künstliche intelligenz: 12&#10;ki: 10&#10;business intelligence: 10">{esc(f["fach"])}</textarea>
<p class="muted">Tipp: Wörter so, wie sie in Anzeigentiteln stehen (eher „KI“ und „Data Engineering“ als „Machine
Learning“). Bei der Bundesagentur kennt der Filter oft nur den Titel; mit einem Fach-Wort im Titel kommt eine Stelle
sicher durch, sonst braucht es zwei starke Stichwörter (ab 8 Punkten) in der Beschreibung.</p></div>
<label for="fit_begriffe">Zusätzliche Fit-Begriffe (optional), je Zeile „Begriff: Synonym, Synonym“</label>
<textarea id="fit_begriffe" name="fit_begriffe" rows="4" spellcheck="false"
placeholder="Pandas: pandas dataframe&#10;Machine Learning: ml, scikit-learn">{esc(f["fit_begriffe"])}</textarea>
<p class="muted">Damit der Fit erkennt, was solche Anzeigen verlangen. Ob du es kannst, kommt weiter aus deinem
Master-CV. Die Begriffe gelten für alle Stellen, sie machen den Fit nur genauer.</p></div>

<div class="sticky row"><button name="aktion" value="speichern">Speichern</button>
<a class="btn ghost" href="/einstellungen">Abbrechen</a>{loeschen}</div></form>
<script>
(() => {{
  const r = {json.dumps(rechnung)}, form = document.getElementById('sp');
  const zeilen = id => document.getElementById(id).value.split('\\n').filter(z => z.trim()).length;
  const update = () => {{
    const ba = zeilen('such_bundesagentur'), sw = zeilen('such_stellenwerk');
    document.querySelectorAll('.zaehler').forEach(el => {{
      const n = zeilen(el.dataset.fuer);
      el.textContent = `(${{n}}/${{r.max}})`; el.className = 'zaehler' + (n > r.max ? ' err' : ' muted');
    }});
    const aktiv = form.enabled.checked;
    const gesBa = r.basis.bundesagentur + (aktiv && ba ? ba * r.faktor + r.details : 0);
    const gesSw = r.basis.stellenwerk + (aktiv && sw && r.portale ? r.portale * (sw + r.sw_details) : 0);
    document.getElementById('abrufe').textContent = `Mit diesem Profil fragt ein Lauf bis zu ${{gesBa}} Seiten bei der `
      + `Bundesagentur und ${{gesSw}} bei Stellenwerk ab (alle aktiven Profile zusammen, Suchen plus Anzeigentexte).`;
    const eigen = form.fachgebiet.value === 'eigen';
    document.getElementById('fachfeld').hidden = !eigen;
    form.querySelectorAll('input[name=fachgebiet]').forEach(i => i.closest('.modus').classList.toggle('an', i.checked));
  }};
  // Karrierestufe gewählt: Rollen-Wörter und Stellenart aus der Vorlage (vorhandene Rollen nur nach Rückfrage ersetzen)
  const stufe = document.getElementById('stufe');
  stufe.addEventListener('change', () => {{
    const v = JSON.parse(stufe.dataset.vorlagen)[stufe.value];
    if (!v) return;
    const rollen = document.getElementById('rollen');
    if (rollen.value.trim() && !confirm('Rollen-Wörter durch die Vorlage ersetzen?')) return;
    rollen.value = Object.entries(v.rollen).map(([w, p]) => `${{w}}: ${{p}}`).join('\n');
    document.getElementById('art').value = v.art;
  }});
  form.addEventListener('input', update); form.addEventListener('change', update); update();
}})();
</script>"""
