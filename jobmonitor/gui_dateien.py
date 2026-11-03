"""Einstellungen → Dateien bearbeiten: verständliche Übersicht und ein Editor, der beim Bearbeiten hilft.

Übersicht: je Datei, wofür sie da ist und welche Formulare dasselbe bequemer können (die meisten Nutzer brauchen den
Editor nie). Editor: Inhaltsverzeichnis der Abschnitte mit Sprung zur Zeile, Zeilennummern, Suche im Text, Tab rückt
mit zwei Leerzeichen ein, Warnung bei ungespeicherten Änderungen, YAML-Kurzhilfe, bei Fehlern Sprung zur Zeile und
„Vorherige Fassung wiederherstellen“ (.bak, die beim Speichern entsteht). Gespeichert wird weiter über
gui_wartung.speichern – mit Prüfung.
"""
from __future__ import annotations

import re
from html import escape

# Datei → (Titel, wofür, [(Formular, Link)])
INFOS = {
    "config.yaml": ("Einstellungen der Suche", "Quellen, Filter, Ausschlüsse, Fit-Begriffe, Ort, KI, Lebenslauf und "
                    "Designs – alles, was die tägliche Suche steuert.",
                    [("Suchprofile", "/einstellungen#suchprofile"), ("Wohnort", "/einstellungen#wohnort"),
                     ("KI", "/einstellungen#ki"), ("Suche aktiv/Ruhe/aus", "/einstellungen")]),
    "companies.yaml": ("Firmen und Hochschulbörsen", "Welche Karriereseiten die Suche liest, Initiativ-Möglichkeiten "
                       "und Warnhinweise je Firma.", [("Firmen", "/firmen")]),
    "lernpfade.yaml": ("Lernvorschläge", "Zertifikate, Kurse und kleine Projekte, die die Lücken-Auswertung je "
                       "fehlender Kenntnis vorschlägt.", [("Lücken-Auswertung", "/luecken")]),
    "cv/anschreiben_vorlage.txt": ("Anschreiben-Vorlage", "Textbausteine für neue Anschreiben-Entwürfe. Platzhalter in "
                                   "{geschweiften Klammern} füllt die App aus; Text in [eckigen Klammern] schreibst du "
                                   "je Bewerbung selbst.", [("Entwurf mit KI (je Bewerbung)", "/bewerbungen")]),
    "cv/nachfassen_vorlage.txt": ("Nachfrage-Vorlage", "Vorlage für die Nachfrage, wenn eine Firma nicht antwortet. Die "
                                  "erste Zeile ist der Betreff.", [("Mit KI formulieren (Bewerbungen)", "/bewerbungen")]),
}

# Abschnitte von config.yaml → (verständlicher Name, kurze Erklärung)
CONFIG_ABSCHNITTE = {
    "run": ("Suche: Rhythmus und Modus", "aktiv / Ruhemodus / angehalten, Abstand zwischen den Läufen"),
    "http": ("Abfragen", "Kennung der App und Pausen zwischen Abfragen derselben Seite"),
    "sources": ("Quellen", "Bundesagentur, Hochschulbörsen, Arbeitnow, Firmenseiten, Job-Alert-Mails ein- und ausschalten"),
    "antworten": ("Antworten von Firmen", "Erkennen von Eingangsbestätigung, Einladung, Absage im Postfach"),
    "anzeigen_check": ("Anzeige noch online?", "wie oft die Links deiner Bewerbungen geprüft werden"),
    "benachrichtigung": ("Mitteilungen", "ab welchem Fit eine eigene Mitteilung kommt"),
    "profile": ("Suchprofile", "lieber im Formular unter Einstellungen bearbeiten"),
    "ats_freigabe": ("Freigaben", "inoffizielle Schnittstellen – nur ändern, wenn du weißt, was du tust"),
    "filter": ("Filter und Ausschlüsse", "Mindest-Score, Fach-Wörter, Titel und Firmen, die rausfliegen"),
    "ort": ("Wohnort und Fahrzeit", "maximale Fahrzeit, Punkte je Entfernung, Remote"),
    "initiativ": ("Initiativ-Bewerbungen", "Vorschläge für Firmen ohne passende Stelle"),
    "tracking": ("Bewerbungsliste", "nach wie vielen Tagen Nachfassen vorgeschlagen wird"),
    "fit": ("Fit-Bewertung", "Fit-Begriffe mit Synonymen und Gewichte der Kenntnis-Level"),
    "entwuerfe": ("Initiativ-Entwürfe", "automatische Anschreiben-Entwürfe für Initiativ-Vorschläge"),
    "ki": ("KI", "Modell und Monatslimit für Aufrufe aus der Oberfläche"),
    "cv": ("Lebenslauf und Designs", "Vorlagen, Design, Akzentfarbe, Prüfungen von Lebenslauf und Anschreiben"),
    "quellen_verlauf": ("Quellen beobachten", "ab wann eine stumme Quelle gemeldet wird"),
    "erinnerungen": ("Erinnerungen", "Vorlauf und Uhrzeit für Fristen"),
    "traumprofil": ("Traumprofil", "optionaler Reiter für besonders passende Stellen"),
    "updates": ("Updates", "Suche nach neuen Versionen der App"),
    "gui": ("Oberfläche", "kleine Einstellungen der App"),
    "mail": ("Bericht per Mail", "Versand aus der GitHub-Pipeline"),
}
TOP = re.compile(r"^([A-Za-z_][\w-]*):", re.M)
EINTRAG = re.compile(r"^  - name: *(.+)$", re.M)


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def gliederung(name: str, text: str) -> list[tuple[int, str, str]]:
    """[(Zeile, Titel, Erklärung)] für das Inhaltsverzeichnis des Editors."""
    zeile = lambda pos: text.count("\n", 0, pos) + 1  # noqa: E731
    if name == "config.yaml":
        return [(zeile(m.start()), *CONFIG_ABSCHNITTE.get(m.group(1), (m.group(1), ""))) for m in TOP.finditer(text)]
    if name == "companies.yaml":
        out = []
        for m in TOP.finditer(text):
            out.append((zeile(m.start()), {"firmen": "Firmen", "hochschulen": "Hochschulbörsen"}.get(m.group(1),
                                                                                                    m.group(1)), ""))
        out += [(zeile(m.start()), "  " + m.group(1).strip().strip("'\""), "") for m in EINTRAG.finditer(text)]
        return sorted(out)
    if name.endswith(".yaml"):
        return [(zeile(m.start()), m.group(1), "") for m in TOP.finditer(text)]
    return []


def fehler_zeile(meldung: str) -> int | None:
    m = re.search(r"Zeile (\d+)", meldung or "")
    return int(m.group(1)) if m else None


def fehler_html(meldung: str) -> str:
    tipp = ""
    if "YAML" in meldung:
        tipp = ("<p class=\"muted\">Meist ist die <b>Einrückung</b> verrutscht: nur Leerzeichen (keine Tabs), Einträge "
                "derselben Ebene gleich weit eingerückt, nach dem Doppelpunkt ein Leerzeichen. Der Editor springt zur "
                "gemeldeten Zeile – der Fehler steckt oft in der Zeile davor.</p>")
    return f'<div class="card err"><p>Nicht gespeichert: {esc(meldung)}</p>{tipp}</div>'


def uebersicht_html() -> str:
    karten = ""
    for datei, (titel, wofuer, formulare) in INFOS.items():
        links = " · ".join(f'<a href="{href}">{esc(label)}</a>' for label, href in formulare)
        karten += (f'<li><div><a href="/einstellungen/datei?name={esc(datei)}"><b>{esc(titel)}</b></a> '
                   f'<code>{esc(datei)}</code><p class="muted">{esc(wofuer)}</p>'
                   + (f'<p class="muted">Bequemer: {links}</p>' if links else "") + '</div>'
                   f'<a class="btn ghost small" href="/einstellungen/datei?name={esc(datei)}">Bearbeiten</a></li>')
    return (f'<div class="card" id="dateien"><h2>Dateien bearbeiten</h2><p class="muted">Für Fortgeschrittene: alles, '
            f'was es nicht als eigenes Formular gibt. Vor dem Speichern prüft die App die Datei; der alte Stand bleibt '
            f'als Sicherung und lässt sich mit einem Klick zurückholen.</p><ul class="dateiliste">{karten}</ul></div>')


YAML_HILFE = """<details class="yaml-hilfe"><summary>Kurzhilfe zum Format</summary><ul>
<li><code>name: Wert</code> – ein Eintrag. Nach dem Doppelpunkt ein Leerzeichen.</li>
<li><b>Einrückung</b> mit Leerzeichen zeigt, was wozu gehört (die Tab-Taste fügt hier zwei Leerzeichen ein).</li>
<li><code>- Wert</code> – ein Listenpunkt; oder kurz <code>[a, b, c]</code>.</li>
<li><code># …</code> – Kommentar, wird ignoriert. Gut, um zu notieren, warum du etwas geändert hast.</li>
<li>Text mit Doppelpunkt oder # in Anführungszeichen setzen: <code>titel: "Teil: Zwei"</code>.</li>
</ul></details>"""

TEXT_HILFE = """<details class="yaml-hilfe"><summary>Platzhalter</summary><p class="muted">Zeilen mit # am Anfang werden
ignoriert. Welche Platzhalter es gibt, steht in den Kommentarzeilen oben in der Datei.</p></details>"""


def editor_html(token: str, name: str, text: str, message: str = "", suche: str = "", von: str = "",
                bak: bool = False, fehler: int | None = None) -> str:
    titel, wofuer, formulare = INFOS.get(name, (name, "", []))
    zurueck = "/firmen" if name == "companies.yaml" or von else "/einstellungen#dateien"
    teile = gliederung(name, text)
    inhalt = "".join(f'<button type="button" class="sprung{" eintrag" if t.startswith("  ") else ""}" '
                     f'data-zeile="{z}" title="{esc(e)}">{esc(t.strip())}</button>' for z, t, e in teile)
    bequemer = " · ".join(f'<a href="{href}">{esc(label)}</a>' for label, href in formulare)
    wiederherstellen = (f'<form method="post" action="/einstellungen/datei" style="display:inline" '
                        f'onsubmit="return confirm(\'Den Stand vor dem letzten Speichern zurückholen? Deine jetzige '
                        f'Fassung wird dabei zur Sicherung.\')"><input type="hidden" name="token" value="{token}">'
                        f'<input type="hidden" name="name" value="{esc(name)}"><input type="hidden" name="aktion" '
                        f'value="wiederherstellen"><button class="ghost small">Vorherige Fassung wiederherstellen'
                        f'</button></form>' if bak else "")
    return f"""<div class="page-head"><div><h1>{esc(titel)}</h1><p class="sub"><code>{esc(name)}</code> ·
{esc(wofuer)}{f" Bequemer: {bequemer}." if bequemer else ""}</p></div>
<div class="row"><a class="btn ghost small" href="{zurueck}">Zurück</a>{wiederherstellen}</div></div>
{message}
<form method="post" action="/einstellungen/datei" id="dateiform"><input type="hidden" name="token" value="{token}">
<input type="hidden" name="name" value="{esc(name)}"><input type="hidden" name="von" value="{esc(von)}">
<div class="editor-raster">
<aside class="card editor-inhalt">{f'<h3>Inhalt</h3>{inhalt}' if inhalt else ''}{YAML_HILFE if name.endswith('.yaml') else TEXT_HILFE}</aside>
<div class="card editor-karte">
<div class="row editor-leiste"><label class="search"><input id="such" type="search" placeholder="Im Text suchen"
value="{esc(suche)}" aria-label="Im Text suchen"></label><button type="button" class="ghost small" id="weiter">Weiter</button>
<span class="muted" id="such-info"></span><span class="chip" id="geaendert" hidden>ungespeichert</span>
<span class="muted" id="position"></span></div>
<div class="editor"><pre class="zeilen" id="zeilen" aria-hidden="true"></pre><textarea id="datei" name="text"
spellcheck="false" class="code" wrap="off" data-fehler="{fehler or ''}">{esc(text)}</textarea></div>
</div></div>
<div class="sticky row"><button>Prüfen und speichern</button><a class="btn ghost" href="{zurueck}">Abbrechen</a></div>
</form>{EDITOR_JS}"""


EDITOR_JS = """<script>
(() => {
  const ta = document.getElementById('datei'), nr = document.getElementById('zeilen');
  const such = document.getElementById('such'), info = document.getElementById('such-info');
  const pos = document.getElementById('position'), geaendert = document.getElementById('geaendert');
  const start = ta.value;
  let dirty = false;
  const zeilenHoehe = () => parseFloat(getComputedStyle(ta).lineHeight) || 19;
  const nummern = () => { nr.textContent = ta.value.split('\\n').map((_, i) => i + 1).join('\\n'); };
  const syncScroll = () => { nr.scrollTop = ta.scrollTop; };
  const zeigePos = () => { const vor = ta.value.slice(0, ta.selectionStart).split('\\n');
    pos.textContent = 'Zeile ' + vor.length + ', Spalte ' + (vor[vor.length - 1].length + 1); };
  const springe = (zeile, laenge) => {
    const zeilen = ta.value.split('\\n'); let i = 0;
    for (let k = 0; k < zeile - 1 && k < zeilen.length; k++) i += zeilen[k].length + 1;
    ta.focus({preventScroll: true});
    ta.setSelectionRange(i, i + (laenge ?? (zeilen[zeile - 1] || '').length));
    ta.scrollTop = Math.max(0, (zeile - 4) * zeilenHoehe()); syncScroll(); zeigePos();
  };
  const finden = (vonVorn) => {
    const q = such.value; if (!q) { info.textContent = ''; return; }
    const text = ta.value.toLowerCase(), w = q.toLowerCase();
    let i = text.indexOf(w, vonVorn ? 0 : ta.selectionEnd);
    if (i < 0) i = text.indexOf(w);
    const anzahl = text.split(w).length - 1;
    info.textContent = anzahl ? anzahl + ' Treffer' : 'nicht gefunden';
    if (i < 0) return;
    springe(ta.value.slice(0, i).split('\\n').length, 0);
    ta.setSelectionRange(i, i + q.length);
  };
  nummern();
  ta.addEventListener('scroll', syncScroll);
  ta.addEventListener('input', () => { nummern(); dirty = ta.value !== start; geaendert.hidden = !dirty; });
  ['click', 'keyup'].forEach(e => ta.addEventListener(e, zeigePos));
  ta.addEventListener('keydown', e => {          // Tab rückt mit zwei Leerzeichen ein statt das Feld zu verlassen
    if (e.key !== 'Tab' || e.shiftKey) return;
    e.preventDefault();
    ta.setRangeText('  ', ta.selectionStart, ta.selectionEnd, 'end');
    ta.dispatchEvent(new Event('input'));
  });
  document.querySelectorAll('.sprung').forEach(b => b.addEventListener('click', () => springe(+b.dataset.zeile)));
  such.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); finden(false); } });
  such.addEventListener('input', () => finden(true));
  document.getElementById('weiter').addEventListener('click', () => finden(false));
  document.getElementById('dateiform').addEventListener('submit', () => { dirty = false; });
  window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
  if (ta.dataset.fehler) springe(+ta.dataset.fehler);
  else if (such.value) finden(true);
})();
</script>"""

CSS = """
.dateiliste { list-style:none; padding:0; margin:0; display:grid; gap:2px; }
.dateiliste li { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; padding:12px 0;
  border-top:1px solid var(--line); } .dateiliste li:first-child { border-top:0; }
.dateiliste p { margin:3px 0 0; max-width:70ch; } .dateiliste code { font-size:12px; margin-left:6px; }
.editor-raster { display:grid; grid-template-columns:230px minmax(0,1fr); gap:14px; align-items:start; }
.editor-inhalt { position:sticky; top:16px; max-height:calc(100vh - 140px); overflow:auto; margin:0; }
.editor-inhalt h3 { margin:0 0 8px; font-size:14px; }
.sprung { display:block; width:100%; text-align:left; background:none; border:0; color:var(--text); padding:5px 8px;
  border-radius:7px; font-size:13px; cursor:pointer; min-height:0; }
.sprung:hover { background:var(--surface-2); } .sprung.eintrag { color:var(--muted); padding-left:18px; font-size:12.5px; }
.yaml-hilfe { margin-top:12px; font-size:13px; } .yaml-hilfe ul { padding-left:18px; } .yaml-hilfe li { margin:4px 0; }
.editor-karte { margin:0; } .editor-leiste { gap:10px; margin-bottom:10px; flex-wrap:wrap; }
.editor-leiste .search { max-width:260px; }
.editor { display:grid; grid-template-columns:auto minmax(0,1fr); border:1px solid var(--line); border-radius:10px;
  overflow:hidden; height:calc(100vh - 260px); min-height:420px; }
.editor .zeilen { margin:0; padding:10px 8px 10px 12px; text-align:right; color:var(--faint); background:var(--surface-2);
  font:12.5px/19px ui-monospace, SFMono-Regular, Menlo, monospace; overflow:hidden; user-select:none; }
.editor textarea.code { border:0; border-radius:0; height:100%; min-height:0; resize:none; padding:10px 12px;
  font:12.5px/19px ui-monospace, SFMono-Regular, Menlo, monospace; white-space:pre; overflow:auto; tab-size:2; }
@media (max-width:900px) { .editor-raster { grid-template-columns:1fr; } .editor-inhalt { position:static; max-height:none; } }
"""
