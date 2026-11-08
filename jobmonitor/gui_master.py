"""Master-CV (cv/cv_master.yaml) in der Oberfläche bearbeiten: Formular je Abschnitt, Prüfung, Speichern.

Das Formular wird im Browser aus SCHEMA aufgebaut und als JSON zurückgeschickt. Unbekannte Felder eines
Eintrags bleiben erhalten. Kommentare innerhalb der Datei gehen beim Speichern verloren, der Kommentarblock am
Dateianfang bleibt. Vor jedem Überschreiben wird der alte Stand nach cv/cv_master.yaml.bak kopiert (gitignored).
"""
from __future__ import annotations

import io
import json
import re
import shutil
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from .cv_data import CvDataError, check_no_personal_data, covered_terms, find_cv_master

LEVELS = ["Grundkenntnisse", "gut", "sehr gut"]
STATUS = ["erreicht", "in_arbeit", "geplant"]

# Abschnitt → Felder. Typen: text, area (mehrzeilig), lines (Liste, eine Zeile je Eintrag), csv (Liste, mit
# Komma getrennt), select, bool, list (verschachtelte Liste mit eigenen Feldern).
SCHEMA = [
    {"key": "profil", "title": "Profil", "type": "area"},
    {"key": "stationen", "title": "Berufserfahrung", "type": "list", "label": "rolle", "fields": [
        {"key": "rolle", "title": "Rolle", "type": "text"},
        {"key": "organisation", "title": "Organisation", "type": "text"},
        {"key": "von", "title": "von (MM/JJJJ)", "type": "text", "half": True},
        {"key": "bis", "title": "bis (leer = seit)", "type": "text", "half": True},
        {"key": "aufgaben", "title": "Aufgaben (eine je Zeile)", "type": "lines"},
        {"key": "technologien", "title": "Technologien und Werkzeuge (optional, mit Komma getrennt)", "type": "csv"}]},
    {"key": "ausbildung", "title": "Ausbildung", "type": "list", "label": "abschluss", "fields": [
        {"key": "abschluss", "title": "Abschluss", "type": "text"},
        {"key": "institution", "title": "Institution", "type": "text"},
        {"key": "von", "title": "von", "type": "text", "half": True},
        {"key": "bis", "title": "bis", "type": "text", "half": True},
        {"key": "punkte", "title": "Punkte (einer je Zeile)", "type": "lines"}]},
    {"key": "kenntnisse", "title": "Kenntnisse", "type": "list", "label": "kategorie", "fields": [
        {"key": "kategorie", "title": "Kategorie", "type": "text"},
        {"key": "eintraege", "title": "Einträge", "type": "list", "label": "name", "compact": True, "fields": [
            {"key": "name", "title": "Name", "type": "text"},
            {"key": "level", "title": "Level", "type": "select", "options": LEVELS, "default": "gut"}]}]},
    {"key": "zertifikate", "title": "Zertifikate und Weiterbildung", "type": "list", "label": "name", "fields": [
        {"key": "name", "title": "Name", "type": "text"},
        {"key": "zusatz", "title": "Zusatz", "type": "text"},
        {"key": "datum", "title": "Datum", "type": "text", "half": True},
        {"key": "status", "title": "Status", "type": "select", "options": STATUS, "default": "erreicht", "half": True},
        {"key": "im_cv", "title": "im Lebenslauf zeigen", "type": "bool"},
        {"key": "nachweis", "title": "Nachweis (PDF, landet in Unterlagen → Zeugnisse und Zertifikate)",
         "type": "nachweis"}]},
    {"key": "projekte", "title": "Projekte", "type": "list", "label": "name", "fields": [
        {"key": "name", "title": "Name", "type": "text"},
        {"key": "zeitraum", "title": "Zeitraum", "type": "text", "half": True},
        {"key": "status", "title": "Status", "type": "select", "options": STATUS, "default": "erreicht", "half": True},
        {"key": "beschreibung", "title": "Beschreibung", "type": "area"},
        {"key": "technologien", "title": "Technologien und Werkzeuge (optional, mit Komma getrennt)", "type": "csv"},
        {"key": "im_cv", "title": "im Lebenslauf zeigen", "type": "bool"}]},
    {"key": "sprachen", "title": "Sprachen", "type": "list", "label": "sprache", "compact": True, "fields": [
        {"key": "sprache", "title": "Sprache", "type": "text"},
        {"key": "niveau", "title": "Niveau (z. B. B2, C1, Muttersprache)", "type": "text"}]},
    {"key": "interessen", "title": "Interessen (mit Komma getrennt)", "type": "csv"},
]


def master_path(root: Path) -> Path:
    return find_cv_master(root) or root / "cv" / "cv_master.yaml"


def load(root: Path) -> dict:
    path = master_path(root)
    if not path.exists():
        return {}
    return YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}


def _header(text: str) -> str:
    """Kommentarblock am Dateianfang (bleibt beim Speichern erhalten)."""
    lines = []
    for line in text.splitlines():
        if line.startswith("#") or (not line.strip() and lines):
            lines.append(line)
        else:
            break
    return "\n".join(lines).rstrip() + "\n\n" if lines else ""


def _clean(value):
    """Leere Listeneinträge entfernen, Text trimmen. Leere Strings bleiben (die Vorlage erwartet z. B. 'bis')."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        items = [_clean(v) for v in value]
        return [v for v in items if v not in ("", None, {})]
    return value.strip() if isinstance(value, str) else value


def parse(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise CvDataError("Formulardaten unlesbar. Seite neu laden.") from None
    if not isinstance(data, dict):
        raise CvDataError("Formulardaten unlesbar. Seite neu laden.")
    data = _clean(data)
    for k in data.get("kenntnisse") or []:          # Untereinträge ohne Namen still weglassen
        if isinstance(k, dict):
            k["eintraege"] = [e for e in k.get("eintraege") or [] if isinstance(e, dict) and e.get("name")]
    data["sprachen"] = [s for s in data.get("sprachen") or [] if isinstance(s, dict) and s.get("sprache")]
    for section in ("stationen", "ausbildung", "kenntnisse", "projekte", "zertifikate"):
        for i, entry in enumerate(data.get(section) or [], 1):
            label = next(f for f in SCHEMA if f["key"] == section)["label"]
            if not isinstance(entry, dict) or not str(entry.get(label, "")).strip():
                raise CvDataError(f"{section}, Eintrag {i}: Feld „{label}“ fehlt.")
    check_no_personal_data(data, "Master-CV")
    return data


def _ordered(value, fields: list[dict] | None):
    """Schlüssel in der Reihenfolge des Formulars (unbekannte danach). Kompakte Listen (Kenntnis-Einträge,
    Sprachen) als einzeilige { name: …, level: … } wie in der Originaldatei."""
    if isinstance(value, list):
        return [_ordered(v, fields) for v in value]
    if not isinstance(value, dict) or fields is None:
        return value
    out = CommentedMap()
    for f in fields:
        if f["key"] in value:
            out[f["key"]] = _ordered(value[f["key"]], f.get("fields"))
    for k, v in value.items():
        if k not in out:
            out[k] = v
    return out


def _compact(seq, fields):
    for f in fields:
        if f["type"] != "list":
            continue
        for item in seq:
            if isinstance(item, CommentedMap) and f["key"] in item:
                if f.get("compact"):
                    for sub in item[f["key"]]:
                        sub.fa.set_flow_style()
                else:
                    _compact(item[f["key"]], f["fields"])


def dump(data: dict, header: str = "") -> str:
    doc = CommentedMap()
    for section in SCHEMA:
        if section["key"] in data:
            doc[section["key"]] = _ordered(data[section["key"]], section.get("fields"))
            if section["type"] == "list":
                if section.get("compact"):
                    for item in doc[section["key"]]:
                        if isinstance(item, CommentedMap):
                            item.fa.set_flow_style()
                else:
                    _compact(doc[section["key"]], section["fields"])
    for k, v in data.items():
        if k not in doc:
            doc[k] = v
    data = doc
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    buf = io.StringIO()
    yaml.dump(data, buf)
    return header + buf.getvalue()


def save(root: Path, data: dict) -> Path:
    """Schreibt cv_master.yaml (Kopfkommentar bleibt, alter Stand → .bak). Wirft CvDataError bei Problemen."""
    path = master_path(root)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    text = dump(data, _header(old))
    YAML(typ="safe").load(text)   # gültiges YAML?
    if old:
        shutil.copy(path, path.with_name(path.name + ".bak"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def coverage(data: dict, begriffe: dict) -> list[tuple[str, float | None]]:
    covered = covered_terms(data, begriffe)
    return [(term, covered.get(term)) for term in begriffe]


EDITOR_JS = r"""
const SCHEMA = JSON.parse(document.getElementById('schema').textContent);
let DATA = JSON.parse(document.getElementById('data').textContent);
const root = document.getElementById('editor');

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v; else if (k.startsWith('on')) e[k] = v; else e.setAttribute(k, v);
  }
  kids.flat().forEach(k => e.append(k));
  return e;
}

function input(field, value, set, ctx) {
  const id = 'f' + Math.random().toString(36).slice(2);
  let ctl;
  if (field.type === 'area' || field.type === 'lines') {
    const text = field.type === 'lines' ? (value || []).join('\n') : (value || '');
    ctl = el('textarea', {id, rows: field.type === 'lines' ? Math.max(3, (value || []).length + 1) : 3});
    ctl.value = text;
    ctl.oninput = () => set(field.type === 'lines' ? ctl.value.split('\n') : ctl.value);
  } else if (field.type === 'csv') {
    ctl = el('input', {id}); ctl.value = (value || []).join(', ');
    ctl.oninput = () => set(ctl.value.split(',').map(s => s.trim()));
  } else if (field.type === 'select') {
    ctl = el('select', {id});
    const opts = field.options.includes(value) || !value ? field.options : [value, ...field.options];
    opts.forEach(o => ctl.append(el('option', {value: o}, o)));
    ctl.value = value || field.default || field.options[0];
    if (!value) set(ctl.value);
    ctl.onchange = () => set(ctl.value);
  } else if (field.type === 'bool') {
    // Schalter statt Häkchen: An/Aus muss man sofort sehen (Text, Füllung und Position unterscheiden sich)
    ctl = el('input', {id, type: 'checkbox', role: 'switch'}); ctl.checked = value !== false;
    if (value === undefined) set(true);
    const state = el('span', {class: 'state'});
    const show = () => {
      state.textContent = ctl.checked ? 'wird angezeigt' : 'ausgeblendet';
      if (ctx && ctx.onVisible && field.key === 'im_cv') ctx.onVisible(ctl.checked);
    };
    ctl.onchange = () => { set(ctl.checked); show(); };
    show();
    return el('div', {class: 'half toggle-field'}, el('label', {for: id}, field.title),
              el('label', {class: 'switch', for: id}, ctl, el('span', {class: 'track'}), state));
  } else if (field.type === 'nachweis') {
    return nachweis(field, value, set, ctx);
  } else {
    ctl = el('input', {id}); ctl.value = value ?? '';
    ctl.oninput = () => { set(ctl.value); if (ctx && ctx.onLabel && field.key === ctx.labelKey) ctx.onLabel(ctl.value); };
  }
  return el('div', {class: field.half ? 'half' : 'full'}, el('label', {for: id}, field.title), ctl);
}

// Nachweis zu einem Zertifikat: PDF hochladen (landet bei den Unterlagen) und hier verknüpfen.
// Der Upload wird sofort gespeichert; die Verknüpfung im Master-CV erst mit „Speichern“.
function nachweis(field, value, set, ctx) {
  const box = el('div', {class: 'full'}, el('label', {}, field.title));
  const row = el('div', {class: 'nachweis'});
  const draw = (v) => {
    row.replaceChildren();
    if (v) {
      const name = v.split('/').pop();
      row.append(el('span', {class: 'linked'}, el('span', {class: 'chip new'}, 'verknüpft'),
        el('a', {href: '/master/nachweis?pfad=' + encodeURIComponent(v), 'data-open': ''}, name)),
        el('button', {type: 'button', class: 'ghost small', onclick: () => { set(''); draw(''); }}, 'Verknüpfung lösen'));
    }
    const file = el('input', {type: 'file', accept: 'application/pdf'});
    const status = el('span', {class: 'muted'});
    const up = el('button', {type: 'button', class: 'ghost small', onclick: async () => {
      if (!file.files.length) { status.textContent = 'Erst eine PDF-Datei auswählen.'; return; }
      const fd = new FormData();
      fd.append('token', document.body.dataset.token);
      fd.append('name', (ctx && ctx.item && ctx.item.name) || 'zertifikat');
      fd.append('datei', file.files[0]);
      up.setAttribute('aria-busy', 'true');
      try {
        const res = await (await fetch('/master/nachweis', {method: 'POST', body: fd})).json();
        if (res.fehler) { status.textContent = res.fehler; return; }
        set(res.pfad); draw(res.pfad);
        row.append(el('span', {class: 'muted'}, 'Hochgeladen. Mit „Speichern“ wird die Verknüpfung übernommen.'));
      } catch (e) { status.textContent = 'Hochladen fehlgeschlagen.'; }
      finally { up.removeAttribute('aria-busy'); }
    }}, v ? 'Ersetzen' : 'Hochladen');
    row.append(file, up, status);
  };
  draw(value || '');
  box.append(row);
  return box;
}

function listEditor(field, items, setItems) {
  items = items || [];
  const box = el('div', {class: field.compact ? 'list compact' : 'list'});
  const redraw = () => { box.replaceWith(listEditor(field, items, setItems)); };
  items.forEach((item, i) => {
    if (typeof item !== 'object' || item === null) item = items[i] = {[field.label]: String(item)};
    const tools = el('div', {class: 'tools'},
      el('button', {type: 'button', class: 'ghost small', title: 'nach oben', 'aria-label': 'nach oben',
        onclick: () => { if (i > 0) { [items[i - 1], items[i]] = [items[i], items[i - 1]]; setItems(items); redraw(); } }}, '↑'),
      el('button', {type: 'button', class: 'ghost small', title: 'nach unten', 'aria-label': 'nach unten',
        onclick: () => { if (i < items.length - 1) { [items[i + 1], items[i]] = [items[i], items[i + 1]]; setItems(items); redraw(); } }}, '↓'),
      el('button', {type: 'button', class: 'ghost small danger', title: 'löschen', 'aria-label': 'löschen',
        onclick: () => { if (confirm('Eintrag „' + (item[field.label] || 'neu') + '“ löschen?')) { items.splice(i, 1); setItems(items); redraw(); } }}, '×'));
    const title = el('b', {class: item[field.label] ? '' : 'leer'}, item[field.label] || 'Neuer Eintrag');
    const hiddenChip = el('span', {class: 'chip off'}, 'nicht im Lebenslauf');
    const card = el('div', {class: 'item'});
    const ctx = {item, labelKey: field.label,
                 onLabel: v => { title.textContent = v || 'Neuer Eintrag'; title.className = v ? '' : 'leer'; },
                 onVisible: on => { card.classList.toggle('cv-off', !on); hiddenChip.hidden = on; }};
    const fields = el('div', {class: 'fields'});
    field.fields.forEach(f => {
      if (f.type === 'list') fields.append(el('div', {class: 'full'}, el('label', {}, f.title),
        listEditor(f, item[f.key], v => { item[f.key] = v; })));
      else fields.append(input(f, item[f.key], v => { item[f.key] = v; }, ctx));
    });
    hiddenChip.hidden = item.im_cv !== false;
    card.classList.toggle('cv-off', item.im_cv === false);
    card.append(el('div', {class: 'item-head'}, title, hiddenChip, tools), fields);
    box.append(card);
  });
  box.append(el('button', {type: 'button', class: 'ghost small add', onclick: () => {
    const blank = {}; field.fields.forEach(f => { if (f.type === 'list') blank[f.key] = []; });
    items.push(blank); setItems(items); redraw();
  }}, '+ ' + (field.compact ? 'Eintrag' : field.title.split(' ')[0] + ' hinzufügen')));
  return box;
}

SCHEMA.forEach(section => {
  const card = el('div', {class: 'card'}, el('h2', {}, section.title));
  if (section.type === 'list') card.append(listEditor(section, DATA[section.key], v => { DATA[section.key] = v; }));
  else card.append(input({...section, title: ''}, DATA[section.key], v => { DATA[section.key] = v; }));
  root.append(card);
});

// Durchgestrichenen Fit-Begriff anklicken → im Feld „Kann ich schon“ auswählen
document.querySelectorAll('.cov span[data-term]').forEach(s => s.addEventListener('click', () => {
  const sel = document.getElementById('kenntnis-term');
  if (sel) { sel.value = s.dataset.term; sel.focus(); }
}));
document.getElementById('masterform').addEventListener('submit', () => {
  document.getElementById('payload').value = JSON.stringify(DATA);
});
"""

EDITOR_CSS = """
/* Jeder Eintrag ist eine umrandete Gruppe; seine Felder haben eine eigene Fläche (siehe input in gui_layout.CSS) */
.list { display:flex; flex-direction:column; gap:12px; }
.item { border:1px solid var(--line); border-radius:14px; padding:14px 16px 16px; display:flex; flex-direction:column;
        gap:4px; }
.item-head { display:flex; align-items:center; gap:8px; }
.item-head b { flex:1; font-weight:600; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.item-head b.leer { color:var(--faint); font-weight:400; }
.compact .item { padding:8px 10px; flex-direction:row; align-items:flex-end; gap:10px; }
.compact .item-head { order:2; } .compact .item-head b { display:none; }
.compact .fields label { display:none; }
.fields { flex:1; display:flex; flex-wrap:wrap; gap:0 14px; } .fields .full { flex:1 1 100%; }
.fields .half { flex:1 1 200px; } .compact .fields > div { flex:1 1 180px; }
.tools { display:flex; gap:2px; }
.tools button { width:30px; height:30px; padding:0; border:0; background:transparent; color:var(--faint); }
.tools button:hover { background:var(--surface-2); color:var(--text); opacity:1; }
.tools button.danger:hover { color:var(--err); background:var(--err-soft); }
.add { align-self:flex-start; }
/* „im Lebenslauf zeigen“: Schalter mit Text; ausgeblendete Einträge sind blass und tragen einen Hinweis */
.toggle-field { display:flex; flex-direction:column; }
.item.cv-off { border-style:dashed; }
.item.cv-off .fields > :not(.toggle-field), .item.cv-off .item-head b { opacity:.55; }
.chip.off { background:transparent; box-shadow:inset 0 0 0 1px var(--control); color:var(--muted); }
.chip.off[hidden] { display:none; }
.nachweis { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:6px; }
.nachweis input[type=file] { flex:1 1 220px; min-height:0; }
.nachweis .linked { display:inline-flex; gap:6px; align-items:center; }
.cov span[data-term] { cursor:pointer; } .cov span[data-term]:hover { border-color:var(--text); }
.cov span { display:inline-block; margin:2px 4px 2px 0; padding:1px 8px; border-radius:999px; font-size:13px;
            background:var(--surface-2); } .cov .no { opacity:.5; text-decoration:line-through; }
"""


# --- Kenntnis per Klick eintragen (Lücken-Auswertung, Fit-Begriffe oben im Master-CV) ---
LEVEL_WAHL = ("Grundkenntnisse", "gut", "sehr gut")
SONSTIGE = "Weitere Kenntnisse"


def _woerter(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9äöüß+#]+", text.lower()) if len(w) >= 3}


# Welche Art Begriff passt zu welcher Art Kategorie (Wörter im Kategorienamen)
ARTEN = [
    (r"office|excel|word|powerpoint|microsoft|365|intune|exchange|sharepoint|teams|windows", r"microsoft|office|betrieb"),
    (r"kubernetes|k8s|docker|container|terraform|bicep|ansible|ci/cd|gitlab|github|jenkins|devops|aws|azure|gcp|cloud",
     r"cloud|devops|automatisierung|infrastruktur"),
    (r"python|powershell|bash|skript|script|java|go\b|c#|sql|programm|entwicklung", r"programm|automatisierung|skript|entwickl"),
    (r"netzwerk|network|firewall|vpn|dns|dhcp|tcp|routing|switch|wlan|cisco", r"netzwerk|network"),
    (r"security|sicherheit|siem|soc|iso 27001|bsi|isms|forensik|pentest|hacking|grundschutz|datenschutz|risiko",
     r"security|sicherheit|isms"),
    (r"linux|unix|server|proxmox|vmware|virtualisierung|backup", r"system|server|betrieb"),
]
SPRACHEN = {"deutsch", "englisch", "französisch", "spanisch", "italienisch", "niederländisch", "türkisch", "polnisch",
            "russisch", "arabisch", "chinesisch", "japanisch"}
NIVEAU = {"Grundkenntnisse": "Grundkenntnisse (A2)", "gut": "gut (B2)", "sehr gut": "sehr gut (C1)"}


def kategorie_fuer(data: dict, term: str, synonyme: list[str]) -> str:
    """Kategorie, in der schon etwas Ähnliches steht (gemeinsames Wort mit Begriff oder Synonymen, oder dieselbe Art
    von Kenntnis laut ARTEN), sonst „Weitere Kenntnisse“."""
    suche = _woerter(" ".join([term, *synonyme]))
    text = " ".join([term, *synonyme]).lower()
    arten = [kat for muster, kat in ARTEN if re.search(muster, text)]
    beste, treffer = SONSTIGE, 0
    for k in data.get("kenntnisse") or []:
        if not isinstance(k, dict) or "eintraege" not in k:
            continue
        n = sum(len(suche & _woerter(str(e.get("name", "")))) for e in k.get("eintraege") or [] if isinstance(e, dict))
        n += len(suche & _woerter(str(k.get("kategorie", ""))))
        n += sum(2 for kat in arten if re.search(kat, str(k.get("kategorie", "")).lower()))
        if n > treffer:
            beste, treffer = str(k.get("kategorie")), n
    return beste


def kenntnis_eintragen(data: dict, term: str, level: str, synonyme: list[str]) -> tuple[str, bool]:
    """Begriff als Kenntnis in `data` eintragen (oder Level eines gleichnamigen Eintrags ändern).
    Gibt (Kategorie, neu angelegt) zurück."""
    if level not in LEVEL_WAHL:
        raise CvDataError("Unbekanntes Level.")
    if term.lower() in SPRACHEN:                       # Sprachen gehören in den Abschnitt Sprachen
        data.setdefault("sprachen", [])
        for s in data["sprachen"]:
            if isinstance(s, dict) and str(s.get("sprache", "")).lower() == term.lower():
                return "Sprachen", False
        data["sprachen"].append({"sprache": term, "niveau": NIVEAU[level]})
        return "Sprachen", True
    data.setdefault("kenntnisse", [])
    for k in data["kenntnisse"]:
        for e in (k.get("eintraege") or []) if isinstance(k, dict) else []:
            if isinstance(e, dict) and str(e.get("name", "")).lower() == term.lower():
                e["level"] = level
                return str(k.get("kategorie")), False
    kategorie = kategorie_fuer(data, term, synonyme)
    ziel = next((k for k in data["kenntnisse"] if isinstance(k, dict) and k.get("kategorie") == kategorie), None)
    if ziel is None:
        ziel = {"kategorie": kategorie, "eintraege": []}
        data["kenntnisse"].append(ziel)
    ziel.setdefault("eintraege", []).append({"name": term, "level": level})
    return kategorie, True


def kenntnis_speichern(root: Path, term: str, level: str, synonyme: list[str]) -> str:
    """Wie kenntnis_eintragen, direkt in cv_master.yaml (alter Stand → .bak). Gibt eine Meldung zurück."""
    data = load(root)
    kategorie, neu = kenntnis_eintragen(data, term, level, synonyme)
    save(root, parse(json.dumps(data, ensure_ascii=False)))
    if not neu and kategorie == "Sprachen":
        return f"„{term}“ steht schon unter Sprachen – Niveau bei Bedarf im Master-CV anpassen."
    return (f"„{term}“ ({level}) unter „{kategorie}“ in deinen Master-CV eingetragen." if neu else
            f"„{term}“ steht schon unter „{kategorie}“ – Level auf „{level}“ gesetzt.")
