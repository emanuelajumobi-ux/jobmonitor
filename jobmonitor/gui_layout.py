"""Aussehen der Oberfläche: Design (CSS), Seitenleiste mit Navigation, Symbole und kleine Bausteine.

Die bisherigen Klassen (card, row, btn, ghost, chip, status, muted, ok, err …) bleiben gültig und werden hier
gestaltet, damit alle Seiten einheitlich aussehen. Farben: Akzent wie im Lebenslauf (#1F4E79), hell und dunkel.
"""
from __future__ import annotations

from html import escape

ICONS = {
    "stellen": '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
    "traum": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 '
             '8.91 8.26 12 2"/>',
    "bewerbungen": '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 '
                   '2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "eigene": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>',
    "firmen": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M12 6h.01M16 6h.01M8 10h.01'
              'M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
    "rueckblick": '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
    "luecken": '<line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" '
               'y2="16"/>',
    "bericht": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>'
               '<line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "master": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "profil": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "unterlagen": '<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 '
                  '1-2.83-2.83l8.49-8.48"/>',
    "sync": '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36'
            'L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    "power": '<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "einstellungen": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 '
                     '2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 '
                     '0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 '
                     '.33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-'
                     '1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 '
                     '0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06'
                     '.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "hilfe": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "bookmark": '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "file": '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>',
}

# (Schlüssel, Titel, Link, Abschnitt)
# Kleines App-Icon: Radar mit einem Treffer auf tiefem Türkis (gleiche Formen wie AppIcon.icon, Raster 1024)
LOGO = ('<svg class="logo" viewBox="100 100 824 824" aria-hidden="true">'
        '<rect x="100" y="100" width="824" height="824" rx="185" fill="#0E3B36"/>'
        '<circle cx="512" cy="512" r="300" fill="none" stroke="#fff" stroke-opacity=".3" stroke-width="34"/>'
        '<circle cx="512" cy="512" r="190" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="34"/>'
        '<circle cx="512" cy="512" r="62" fill="#fff"/><circle cx="694" cy="334" r="72" fill="#5EEAD4"/></svg>')

NAV = [
    ("stellen", "Stellen", "/", "Übersicht"), ("traum", "Cloud Security", "/?traum=1", "Übersicht"),
    ("bewerbungen", "Bewerbungen", "/bewerbungen", "Übersicht"), ("eigene", "Eigene Stelle", "/eigene", "Übersicht"),
    ("rueckblick", "Rückblick", "/rueckblick", "Übersicht"),
    ("firmen", "Firmen", "/firmen", "Recherche"), ("luecken", "Lücken-Auswertung", "/luecken", "Recherche"),
    ("bericht", "Letzter Bericht", "/bericht", "Recherche"),
    ("master", "Master-CV", "/master", "Mein Profil"), ("profil", "Profil", "/profil", "Mein Profil"),
    ("unterlagen", "Unterlagen", "/unterlagen", "Mein Profil"),
    ("einstellungen", "Einstellungen", "/einstellungen", "System"),
    ("hilfe", "Anleitung", "/hilfe", "System"),
]


def icon(name: str, size: int = 18) -> str:
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


CSS = """
/* Design: tasteskill (App-Stil „true-black flat“, Farbe nur auf Daten) und apple-design (Rückmeldung beim Drücken,
   Materialien, Bedienungshilfen); wo sie sich widersprechen, die Mitte: durchscheinend sind nur die Seitenleiste
   im App-Fenster und eine schwebende Leiste je Seite, Tiefe entsteht über Helligkeitsstufen statt Schatten.
   Eine Datenfarbe: das Türkis aus dem Suchstrahl des App-Icons. */
:root {
  --bg:#f6f7f8; --surface:#ffffff; --surface-2:#f0f1f3; --line:#eceef0; --control:#d1d5db; --field:#ffffff;
  --field-line:#d9dce1;
  --text:#111111; --muted:#5f6368; --faint:#6b6b6b;
  --accent:#0b8476; --accent-2:#086b60; --accent-soft:#e3f5f2; --on-accent:#ffffff;
  --primary:#1d1f20; --primary-ink:#ffffff;
  --ok:#0b8476; --ok-soft:#e3f5f2; --warn:#92400e; --warn-soft:#fff6e0; --err:#b42318; --err-soft:#fdecea;
  --side:#f6f7f8; --side-2:#eceef0; --side-3:#e3e5e8; --side-text:#1f2937; --side-muted:#6b6b6b; --side-strong:#111111;
  --side-line:rgba(0,0,0,.07); --side-solid:#eceef0;
  --shadow:none; --shadow-lg:0 12px 32px rgba(0,0,0,.18); --radius:20px; --radius-sm:12px;
  --press:cubic-bezier(.2,0,0,1);
}
@media (prefers-color-scheme: dark) { :root {
  --bg:#0c0d0f; --surface:#15171a; --surface-2:#23262b; --line:#1f2226; --control:#45484e; --field:#0e1013;
  --field-line:#33363c;
  --text:#ffffff; --muted:#b4b4b4; --faint:#949494;
  --accent:#5eead4; --accent-2:#99f6e4; --accent-soft:#12302c; --on-accent:#000000;
  --primary:#ffffff; --primary-ink:#000000;
  --ok:#5eead4; --ok-soft:#12302c; --warn:#e5a93b; --warn-soft:#2b2414; --err:#f28b82; --err-soft:#2c1a20;
  --side:#0c0d0f; --side-2:#1b1d21; --side-3:#23262b; --side-text:#d6d8dc; --side-muted:#949494; --side-strong:#ffffff;
  --side-line:rgba(255,255,255,.07); --side-solid:#15171a;
  --shadow-lg:0 12px 32px rgba(0,0,0,.5);
} }
* { box-sizing:border-box; }
html, body { margin:0; }
body { font:14px/20px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg);
       color:var(--text); -webkit-font-smoothing:antialiased; font-optical-sizing:auto; }
a { color:var(--text); text-decoration:underline; text-decoration-color:var(--control); text-underline-offset:3px; }
a:hover { text-decoration-color:currentColor; }
.ic { flex:none; vertical-align:-3px; }
.num { font-variant-numeric:tabular-nums; }

/* Seitenleiste: im Browser auf dem Seitengrund, im App-Fenster durchscheinend (siehe html.native) */
.side { position:fixed; inset:0 auto 0 0; width:236px; background:var(--side); color:var(--side-text);
        border-right:1px solid var(--side-line); display:flex; flex-direction:column; padding:18px 12px; overflow-y:auto; }
.brand { display:flex; align-items:center; gap:10px; padding:4px 10px 14px; color:var(--side-strong); font-weight:600;
         font-size:15px; letter-spacing:-.01em; }
.brand .logo { width:28px; height:28px; flex:none; display:block; }   /* wie das App-Icon (assets/AppIcon.icon) */
.nav-sec { font-size:12px; font-weight:500; color:var(--side-muted); padding:18px 10px 6px; }
.nav a { display:flex; align-items:center; gap:10px; height:32px; padding:0 10px; margin:1px 0; border-radius:8px;
         color:var(--side-text); font-size:14px; text-decoration:none; transition:background .12s, transform 100ms var(--press); }
.nav a .ic { color:var(--side-muted); }
.nav a:hover { background:var(--side-2); color:var(--side-strong); }
.nav a:active { background:var(--side-3); transform:scale(.98); }
.nav a.active { background:var(--side-2); color:var(--side-strong); font-weight:500; }
.nav a.active .ic { color:var(--side-strong); }
.nav .badge { margin-left:auto; font-size:12px; font-weight:500; min-width:20px; text-align:center; padding:0 6px;
              border-radius:999px; background:var(--side-3); color:var(--side-strong); font-variant-numeric:tabular-nums; }
.nav .badge.warn { background:var(--warn-soft); color:var(--warn); }
.side-foot { margin-top:auto; padding:12px 0 0; border-top:1px solid var(--side-line); display:grid; gap:2px; }
.side-foot form { margin:0; }
.side-foot button { width:100%; height:32px; display:flex; align-items:center; gap:10px; justify-content:flex-start;
                    background:transparent; color:var(--side-text); border:0; border-radius:8px; padding:0 10px;
                    font-weight:400; font-size:14px; }
.side-foot button .ic { color:var(--side-muted); }
.side-foot button:hover { background:var(--side-2); color:var(--side-strong); }
.side-foot button:active { background:var(--side-3); }
.side-foot .hint { font-size:12px; color:var(--side-muted); padding:0 10px 6px; }

/* Leinwand: mittig rechts der Seitenleiste, höchstens 1156px breit */
main { margin-left:236px; padding:28px max(24px, calc((100vw - 236px - 1156px) / 2)) 72px; }
h1 { font-size:22px; line-height:28px; font-weight:600; margin:0; letter-spacing:-.018em; }
h2 { font-size:16px; line-height:22px; font-weight:600; margin:0 0 12px; letter-spacing:-.005em; }
h3 { font-size:14px; line-height:20px; font-weight:500; margin:0; }
.sub { color:var(--muted); font-size:15px; line-height:22px; margin:4px 0 20px; max-width:68ch; }
.sub b { color:var(--text); font-weight:500; }
.page-head { display:flex; align-items:flex-start; justify-content:space-between; gap:24px; margin-bottom:20px; }
.page-head .sub { margin-bottom:0; }
.page-head > .row { flex:none; }
.card { background:var(--surface); border-radius:var(--radius); padding:20px 22px; margin-bottom:14px; }
.card.info, .card.ok-card, .card:has(> p.ok:first-child), .card.err, .card:has(> p.err:first-child) {
  border-radius:var(--radius-sm); padding:12px 16px; }
.card.info { background:var(--surface-2); }
.card.info p, .card:has(> p.ok:first-child) p, .card:has(> p.err:first-child) p { margin:0; }
.card.ok-card, .card:has(> p.ok:first-child) { background:var(--ok-soft); }
.card.ok-card p.ok, .card:has(> p.ok:first-child) p.ok { color:var(--text); }
.card.err, .card:has(> p.err:first-child) { background:var(--err-soft); color:var(--err); }
.row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:0 14px; }
.muted { color:var(--muted); font-size:13px; } .ok { color:var(--ok); } .err { color:var(--err); white-space:pre-wrap; }
pre { white-space:pre-wrap; font-size:12.5px; background:var(--surface-2); padding:12px; border-radius:10px; }
ul { padding-left:20px; } li { margin:3px 0; }
.checks { list-style:none; padding:0; margin:0; display:grid; gap:6px; }
.checks li { padding:9px 12px; border-radius:10px; background:var(--surface-2); }
.checks li.warnung { background:var(--warn-soft); color:var(--warn); }
.follow { list-style:none; padding:0; margin:0; display:grid; gap:0; }
.follow > li { padding:14px 0; border-top:1px solid var(--line); }
.follow > li:first-child { border-top:0; padding-top:4px; }
/* Antworten von Firmen (Bewerbungen): Art als Chip, Aktionen rechts */
.antwort { display:flex; justify-content:space-between; align-items:center; gap:16px; }
.antwort b { font-weight:500; margin-right:8px; } .antwort p { margin:2px 0 0; } .antwort .row { flex:none; gap:6px; }
.chip.absage { background:var(--err-soft); color:var(--err); }
.chip.einladung, .chip.zusage { background:var(--ok-soft); color:var(--ok); }
.chip.eingang, .chip.nachricht { background:var(--surface-2); color:var(--muted); }
.chip.eck { background:transparent; border:1px solid var(--line); color:var(--muted); }
.gespraech details { margin-top:8px; } .gespraech summary { cursor:pointer; font-size:13px; color:var(--muted); }
.gespraech details ul { margin:6px 0 0; padding-left:18px; font-size:13px; } .gespraech details li { margin:3px 0; }
.ki-text { font-size:13px; line-height:1.5; margin-top:6px; } .ki-text h3 { font-size:13px; font-weight:600; margin:12px 0 4px; }
.ki-text h3:first-child { margin-top:4px; } .ki-text p { margin:4px 0; }
.follow details { margin-top:8px; } .follow summary { cursor:pointer; font-weight:500; }
.follow .row { margin-top:8px; }
.lern { list-style:none; padding:0; margin:6px 0 16px; display:grid; gap:8px; }
.lern li { line-height:20px; }
pre.out { max-height:320px; overflow:auto; font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; }
textarea.code { font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12.5px; min-height:520px;
                white-space:pre; tab-size:2; }

/* Knöpfe: primär invertiert (Weiß auf Schwarz bzw. umgekehrt), sonst Umriss; Rückmeldung sofort beim Drücken */
button, .btn { font:inherit; font-weight:500; font-size:14px; height:36px; border:1px solid var(--primary);
               background:var(--primary); color:var(--primary-ink); border-radius:999px; padding:0 16px; cursor:pointer;
               text-decoration:none; display:inline-flex; align-items:center; justify-content:center; gap:6px;
               white-space:nowrap; transition:background .12s, border-color .12s, opacity .12s, transform 100ms var(--press);
               -webkit-user-select:none; user-select:none; }
button:hover, .btn:hover { opacity:.88; text-decoration:none; }
button.ghost, .btn.ghost { background:transparent; color:var(--text); border-color:var(--control); }
button.ghost:hover, .btn.ghost:hover { opacity:1; background:var(--surface-2); }
button.small, .btn.small { height:30px; padding:0 13px; font-size:13px; }
button.danger, .btn.danger { color:var(--err); border-color:var(--control); background:transparent; }
button.danger:hover { background:var(--err-soft); opacity:1; }
button.icon { padding:0; width:32px; height:32px; }
button:active, .btn:active, .tabs a:active, .filters a:active { transform:scale(.97); }
button:focus-visible, .btn:focus-visible, a:focus-visible, summary:focus-visible {
  outline:none; box-shadow:0 0 0 3px color-mix(in srgb, var(--text) 30%, transparent); border-radius:8px; }
button[aria-busy=true] { opacity:.7; pointer-events:none; }
button[aria-busy=true]::after { content:""; width:12px; height:12px; border-radius:50%; border:2px solid currentColor;
                                border-right-color:transparent; animation:spin .7s linear infinite; }
/* Eingabefelder: eigene Fläche mit feinem Rand, damit man sie auf jeder Fläche sofort erkennt (tasteskill §8.1) */
input, textarea, select { font:inherit; width:100%; min-height:38px; padding:8px 12px; border:1px solid var(--field-line);
                          border-radius:10px; background:var(--field); color:var(--text);
                          transition:border-color .12s, box-shadow .12s; }
input::placeholder, textarea::placeholder { color:var(--faint); }
input:hover, textarea:hover, select:hover { border-color:var(--control); }
input:focus, textarea:focus, select:focus { outline:none; border-color:var(--text);
  box-shadow:0 0 0 3px color-mix(in srgb, var(--text) 12%, transparent); }
input[type=checkbox], input[type=radio] { min-height:0; width:auto; accent-color:var(--text); }
input[type=file] { padding:6px; }
textarea { min-height:150px; line-height:21px; }
label { display:block; font-size:13px; font-weight:500; color:var(--muted); margin:14px 0 6px; }
label.check { display:flex; align-items:center; gap:8px; color:var(--text); font-size:14px; font-weight:400; margin:6px 0; }
label.check input { width:auto; }
/* Schalter mit Text (an = gefüllt, aus = Umriss), z. B. „im Lebenslauf zeigen“ */
.switch { display:inline-flex; align-items:center; gap:10px; margin:0; min-height:38px; color:var(--text);
          font-size:14px; font-weight:500; cursor:pointer; -webkit-user-select:none; user-select:none; }
.switch input { position:absolute; opacity:0; width:1px; height:1px; }
.switch .track { width:40px; height:24px; border-radius:999px; background:transparent; position:relative; flex:none;
                 box-shadow:inset 0 0 0 1.5px var(--control); transition:background .15s; }
.switch .track::after { content:""; position:absolute; top:4px; left:4px; width:16px; height:16px; border-radius:50%;
                        background:var(--faint); transition:transform .18s cubic-bezier(.2,0,0,1), background .15s; }
.switch input:checked + .track { background:var(--text); box-shadow:none; }
.switch input:checked + .track::after { transform:translateX(16px); background:var(--bg); }
.switch input:not(:checked) ~ .state { color:var(--faint); font-weight:400; }
.switch input:focus-visible + .track { box-shadow:0 0 0 3px color-mix(in srgb, var(--text) 30%, transparent); }
.switch .state .on, .switch input:not(:checked) ~ .state .off { display:inline; }
.switch .state .off, .switch input:not(:checked) ~ .state .on { display:none; }
.switches { display:grid; gap:2px; }
.modi { display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:10px; margin-top:12px; }
.modus { display:grid; grid-template-columns:auto 1fr; gap:4px 10px; align-items:start; margin:0; padding:12px 14px;
  border-radius:10px; border:1px solid var(--line); cursor:pointer; color:var(--text); }
.modus input { margin-top:3px; grid-row:span 2; } .modus span { font-size:12.5px; line-height:1.45; }
.modus.an { border-color:var(--accent); background:var(--accent-soft); }
.modus:has(input:focus-visible) { box-shadow:0 0 0 3px color-mix(in srgb, var(--accent) 30%, transparent); }
@media (max-width:860px) { .modi { grid-template-columns:1fr; } }
.switch .state { white-space:nowrap; }
@media (prefers-reduced-motion: reduce) { .switch .track, .switch .track::after { transition:none; } }
/* Die eine schwebende Leiste einer Formularseite: Speichern bleibt erreichbar */
.sticky { position:sticky; bottom:0; background:var(--bg); border-top:1px solid var(--line); padding:12px 0;
          margin-top:8px; z-index:2; }
.card .sticky { background:var(--surface); }

/* Tabellen: Linien und Ausrichtung, Kopf grau in Satzschreibung */
table { width:100%; border-collapse:collapse; }
th { text-align:left; font-size:12px; font-weight:400; color:var(--faint); padding:6px 8px; }
td { padding:12px 8px; border-top:1px solid var(--line); vertical-align:top; }
tr:first-child td { border-top:0; }
td.fit { white-space:nowrap; font-weight:500; width:70px; font-variant-numeric:tabular-nums; } td.act { width:1%; white-space:nowrap; }
.apps textarea { min-height:0; }

/* Etiketten: blasse Paare, nie gequetscht */
.chip, .status { display:inline-flex; align-items:center; gap:4px; flex:none; font-size:12px; font-weight:500;
                 line-height:16px; padding:2px 8px; border-radius:999px; background:var(--surface-2); color:var(--muted);
                 white-space:nowrap; }
.status.traum, .chip.traum, .status.new, .chip.new { background:var(--accent-soft); color:var(--accent); }
.status.frist, .chip.frist { background:var(--warn-soft); color:var(--warn); }
.chip.abgelaufen { background:var(--err-soft); color:var(--err); }

/* Reiter: Unterstrich auf einer durchgehenden Linie (Stellen-Seite schwebend, siehe .filters) */
.toolbar { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin:0 0 14px; }
.eckfilter { display:flex; flex-wrap:wrap; gap:8px 18px; align-items:center; margin:10px 0 4px; font-size:13px; }
.eckfilter label { display:inline-flex; gap:6px; align-items:center; cursor:pointer; color:var(--muted); }
.eckfilter input { width:auto; min-height:0; margin:0; } .eckfilter .muted { font-size:12px; }
.search { position:relative; flex:1; min-width:200px; max-width:280px; }
.search .ic { position:absolute; left:11px; top:10px; color:var(--faint); }
.search input { padding-left:34px; border-radius:999px; height:36px; min-height:0; }
.tabs, .filters { display:flex; gap:24px; align-items:flex-end; border-bottom:1px solid var(--line); }
.tabs a, .filters a { white-space:nowrap; color:var(--muted); font-weight:500; padding:8px 0 10px; margin-bottom:-1px;
                      border-bottom:2px solid transparent; text-decoration:none;
                      transition:color .12s, transform 100ms var(--press); }
.tabs a:hover, .filters a:hover { color:var(--text); }
.tabs a.active, .tabs a[aria-current=page], .filters a.active { color:var(--text); border-bottom-color:var(--text); }
.filters a span, .tabs a span { color:var(--faint); margin-left:4px; font-variant-numeric:tabular-nums; }
/* Stellen-Seite: die eine schwebende Leiste, als Material (Mitte aus apple-design und tasteskill) */
.filters { position:sticky; top:0; z-index:3; padding-top:6px; margin:0 0 14px; gap:24px;
           background:color-mix(in srgb, var(--bg) 82%, transparent);
           -webkit-backdrop-filter:blur(20px) saturate(180%); backdrop-filter:blur(20px) saturate(180%); } /* taste-skill-ignore */
.filters .search { margin:0 0 6px auto; flex:none; width:240px; }
.filters .search input { height:32px; font-size:13.5px; background:var(--surface-2); border-color:transparent; }
.filters .search .ic { top:8px; }

/* Stellenliste: eine Fläche, Zeilen mit Haarlinien, rechts Belege */
.board { display:grid; grid-template-columns:minmax(0,1fr) 288px; gap:14px; align-items:start; }
.board > section { background:var(--surface); border-radius:var(--radius); padding:6px 0; }
.group { display:flex; justify-content:space-between; color:var(--faint); font-size:12px; padding:14px 22px 6px;
         -webkit-user-select:none; user-select:none; }
.job { display:grid; grid-template-columns:minmax(0,1fr) 118px 56px auto; gap:16px; align-items:center;
       min-height:72px; padding:10px 22px; position:relative; }
.job + .job::before { content:""; position:absolute; top:0; left:22px; right:22px; border-top:1px solid var(--line); }
@media (hover:hover) and (pointer:fine) {
  .job:hover { outline:1px solid var(--control); outline-offset:-1px; border-radius:12px; }
  .job:hover::before, .job:hover + .job::before { border-color:transparent; }
}
.job.expired { opacity:.6; }
.job h3 { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.job h3 a { color:var(--text); text-decoration:none; }
.job h3 a:hover { color:var(--accent); }
.job .meta { color:var(--muted); font-size:13px; margin-top:2px; display:flex; gap:6px; align-items:center; min-width:0; }
.job .meta > span:first-child { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
.job .mark { color:var(--accent); font-weight:500; }
.req { display:flex; flex-direction:column; gap:5px; }
.units { display:flex; flex-wrap:wrap; gap:2px; max-width:118px; }
.units i { width:10px; height:10px; border-radius:2.5px; background:var(--accent); }
.units i.miss { background:transparent; box-shadow:inset 0 0 0 1.5px var(--control); }
.req small { color:var(--faint); font-size:12px; line-height:14px; }
.fitnum { text-align:right; font-size:20px; font-weight:500; font-variant-numeric:tabular-nums; }
.fitnum small { color:var(--faint); font-size:12px; font-weight:400; margin-left:1px; }
.fitnum.hi { color:var(--accent); }
.fitnum.none { color:var(--faint); }
.job .actions { display:flex; align-items:center; justify-content:flex-end; gap:2px; }
.job .actions form { margin:0; display:inline; }
.job .actions .btn { margin-right:6px; }
.job .actions button.icon { width:30px; height:30px; border:0; background:transparent; color:var(--faint); }
.job .actions button.icon:hover { background:var(--surface-2); color:var(--text); }
.rail { display:grid; gap:14px; position:sticky; top:68px; }   /* unter der schwebenden Filterzeile */
.rail .card { margin:0; }
.rail .head { display:flex; justify-content:space-between; align-items:baseline; margin:0 0 12px; }
.rail .head h2 { margin:0; }
.rail .head a { font-size:13px; font-weight:500; color:var(--muted); text-decoration:none; }
.rail .head a:hover { color:var(--text); }
.gap-item { display:grid; grid-template-columns:1fr auto; gap:3px 12px; padding:7px 0; }
.gap-item b { font-weight:500; }
.gap-item span { color:var(--faint); font-size:12px; text-align:right; font-variant-numeric:tabular-nums; }
.gap-item i { grid-column:1 / -1; height:2px; border-radius:1px; background:var(--control); width:calc(var(--p) * 1%); }
.gap-item:first-of-type i { background:var(--text); }
.traum-item a { font-weight:500; text-decoration:none; }
.traum-item p { color:var(--muted); font-size:13px; margin:2px 0 8px; }
.empty { color:var(--muted); padding:24px 22px; }
/* Firmen → Quellen beobachten: Warnung links, Aktionen rechts */
.watch { display:grid; gap:8px; }
.watch-item { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:10px 14px;
              border-radius:12px; background:var(--warn-soft); }
.watch-item b { font-weight:500; color:var(--warn); } .watch-item p { margin:2px 0 0; font-size:13px; color:var(--muted); }
.watch-item .row { flex:none; gap:6px; }
.watch-item .chip { margin-top:8px; display:inline-block; }
.watch-item.pruefung { background:var(--surface-2); } .watch-item.pruefung b { color:var(--text); }
.chip.pruefung { background:var(--surface); color:var(--text); box-shadow:inset 0 0 0 1px var(--control); }
.chip.offen { background:var(--err-soft); color:var(--err); }
.watch-item.done { background:var(--ok-soft); } .watch-item.done b { color:var(--ok); }
@media (max-width:860px) { .watch-item { flex-direction:column; align-items:flex-start; } }

.report h1 { font-size:20px; } .report h2 { font-size:16px; margin-top:22px; } .report h3 { font-size:14.5px; margin:14px 0 2px; }
.splash { display:grid; place-items:center; min-height:70vh; text-align:center; }

/* Nur bei längeren Aktionen (erscheint verzögert, siehe JS); kurze Klicks behalten nur das Feedback am Knopf */
#busy { display:none; position:fixed; inset:0; background:rgba(0,0,0,.25); align-items:center;
        justify-content:center; z-index:10; animation:fade .2s ease-out; }
#busy div { background:var(--surface); color:var(--text); padding:14px 20px; border-radius:14px;
            box-shadow:var(--shadow-lg); display:flex; gap:12px; align-items:center; font-weight:500;
            animation:materialize .25s var(--press); }
#busy div::before { content:""; width:16px; height:16px; border-radius:50%; border:2px solid var(--control);
                    border-top-color:var(--text); animation:spin .8s linear infinite; }
#busy span { display:grid; gap:4px; } #busy small { display:none; font-weight:400; font-size:12.5px; color:var(--muted);
  font-variant-numeric:tabular-nums; }
#busy.ki small { display:block; } #busy.ki div { max-width:min(440px, 90vw); padding:16px 20px; }
@keyframes spin { to { transform:rotate(360deg); } }
@keyframes fade { from { opacity:0; } }
@keyframes materialize { from { opacity:0; transform:scale(.96); } }

/* Bedienungshilfen: sanftere Bewegung, weniger Transparenz, mehr Kontrast */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration:0s !important; }
  button:active, .btn:active, .tabs a:active, .filters a:active, .nav a:active { transform:none; }
  #busy, #busy div { animation:fade .15s ease-out; }
  #busy div::before, button[aria-busy=true]::after { animation:pulse 1.2s ease-in-out infinite; }
}
@keyframes pulse { 50% { opacity:.35; } }
@media (prefers-reduced-transparency: reduce) {
  .filters { background:var(--bg); -webkit-backdrop-filter:none; backdrop-filter:none; }
  html.native body { background:var(--bg); }
  html.native .side { background:var(--side-solid); }
}
@media (prefers-contrast: more) {
  :root { --line:#98a2b3; --faint:var(--muted); }
  .card, .board > section { box-shadow:inset 0 0 0 1px var(--control); } /* taste-skill-ignore: nur bei „Kontrast erhöhen“ */
  .units i.miss { box-shadow:inset 0 0 0 2px var(--muted); }
}

/* App-Fenster (pywebview mit Vibrancy): Seitenleiste durchscheinend wie Finder/Mail, Inhalt deckend */
html.native body { background:transparent; }
html.native main { background:var(--bg); min-height:100vh; }
html.native { --side:rgba(255,255,255,.28); --side-2:rgba(0,0,0,.06); --side-3:rgba(0,0,0,.1); --side-text:#1f2937;
              --side-muted:#6b6b6b; --side-strong:#0b1220; --side-line:rgba(0,0,0,.08); }
html.native .side { border-right:1px solid rgba(0,0,0,.08); }
html.native button, html.native .btn, html.native .tabs a, html.native .filters a { cursor:default; }
html.native .side, html.native .filters, html.native .tabs, html.native .job .actions { -webkit-user-select:none; user-select:none; }
/* Vom Suchfeld ausgefilterte Zeilen: hidden schlägt display:grid/flex der Bauteile */
[hidden] { display:none !important; }
/* Eingabefelder bleiben bedienbar, auch in Leisten ohne Textauswahl (sonst nimmt WebKit keine Eingabe an) */
input, textarea, select, [contenteditable] { -webkit-user-select:text; user-select:text; }
@media (prefers-color-scheme: dark) {
  html.native { --side:rgba(0,0,0,.18); --side-2:rgba(255,255,255,.08); --side-3:rgba(255,255,255,.13);
                --side-text:#e6e9ef; --side-muted:#98a2b3; --side-strong:#fff; --side-line:rgba(255,255,255,.08); }
  html.native .side { border-right-color:rgba(255,255,255,.06); }
}

@media (max-width:1180px) { .board { grid-template-columns:1fr; } .rail { position:static; grid-template-columns:1fr 1fr; } }
@media (max-width:860px) {
  .side { position:static; width:auto; flex-direction:row; flex-wrap:wrap; gap:4px; padding:10px; }
  .brand, .nav-sec, .side-foot .hint { display:none; }
  .nav { display:contents; } .side-foot { margin:0; border:0; padding:0; display:flex; }
  main { margin-left:0; padding:20px 16px 60px; }
  .page-head { flex-direction:column; }
  .grid2 { grid-template-columns:1fr; } .rail { grid-template-columns:1fr; }
  .filters { overflow-x:auto; } .filters .search { display:none; }
  .job { grid-template-columns:minmax(0,1fr) 56px; padding:12px 16px; }
  .job + .job::before { left:16px; right:16px; }
  .req { grid-row:2; grid-column:1; flex-direction:row; align-items:center; gap:8px; }
  .fitnum { grid-row:1; grid-column:2; } .job .actions { grid-row:2; grid-column:2; }
  .job .actions .btn { display:none; }
}
"""

JS = """
// Sofort: der gedrückte Knopf zeigt „arbeitet“ (und verhindert Doppelklicks). Das Overlay kommt erst, wenn es
// länger als 400 ms dauert – kurze Aktionen wie Merken oder Ausblenden bleiben so ohne Flackern.
// KI-Knöpfe (data-ki="Was gerade passiert"): Overlay sofort, mit Sekundenzähler – KI-Aufrufe dauern 10–60 s.
let kiTakt;
document.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => {
  if (e.defaultPrevented) return;   // z. B. Rückfrage abgelehnt
  const b = e.submitter || f.querySelector('button');
  if (b) b.setAttribute('aria-busy', 'true');
  const busy = document.getElementById('busy');
  if (b && b.dataset.ki) {
    busy.classList.add('ki');
    busy.querySelector('b').textContent = b.dataset.ki;
    const zeit = busy.querySelector('small'), start = Date.now();
    const zeigen = () => { const s = Math.round((Date.now() - start) / 1000);
      zeit.textContent = `${s} s · die KI arbeitet, meist 10 bis 40 Sekunden. Fenster bitte offen lassen.`; };
    zeigen(); kiTakt = setInterval(zeigen, 1000);
    busy.style.display = 'flex';
    return;
  }
  setTimeout(() => { busy.style.display = 'flex'; }, 400);
}));
window.addEventListener('pageshow', () => {   // zurück-Navigation: Zustand zurücksetzen
  const busy = document.getElementById('busy');
  busy.style.display = 'none'; busy.classList.remove('ki'); clearInterval(kiTakt);
  document.querySelectorAll('[aria-busy]').forEach(b => b.removeAttribute('aria-busy'));
});
// Stellen filtern: Suchfeld plus Eckdaten (bis 20 h, Remote, Abschlussarbeit); die Auswahl merkt sich der Browser
const q = document.getElementById('filter'), ecks = [...document.querySelectorAll('[data-eck]')];
function filtern() {
  const v = q ? q.value.toLowerCase() : '', an = Object.fromEntries(ecks.map(c => [c.dataset.eck, c.checked]));
  document.querySelectorAll('[data-s]').forEach(el => {
    const d = el.dataset;
    el.hidden = !d.s.includes(v) || (an.h && d.h !== undefined && d.h !== '' && +d.h > 20)
      || (an.r && d.r === '0') || (an.t && d.t !== '1');
  });
}
if (q) q.addEventListener('input', filtern);
ecks.forEach(c => {
  try { c.checked = localStorage.getItem('eck-' + c.dataset.eck) === '1'; } catch (e) {}
  c.addEventListener('change', () => { try { localStorage.setItem('eck-' + c.dataset.eck, c.checked ? '1' : '0'); } catch (e) {} filtern(); });
});
if (ecks.some(c => c.checked)) filtern();
// Entwürfe in die Zwischenablage kopieren; Fallback für Fenster ohne Clipboard-API
document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () => {
  const el = document.getElementById(b.dataset.copy), old = b.textContent;
  const done = () => { b.textContent = 'Kopiert'; setTimeout(() => b.textContent = old, 1500); };
  if (navigator.clipboard) navigator.clipboard.writeText(el.value).then(done, () => { el.select(); document.execCommand('copy'); done(); });
  else { el.select(); document.execCommand('copy'); done(); }
}));
// PDFs in Vorschau öffnen statt im Fenster
document.addEventListener('click', e => {
  const a = e.target.closest('a[data-open]');
  if (!a) return;
  e.preventDefault();
  fetch('/oeffnen', {method: 'POST', body: new URLSearchParams({token: document.body.dataset.token,
                                                               pfad: a.getAttribute('href')})});
});
"""


def nav(active: str, badges: dict[str, tuple[int, str]], token: str, hint: str = "",
        traum_name: str | None = "Cloud Security") -> str:
    """`traum_name`: Name des Traumprofils (config.yaml → traumprofil.name); None blendet den Eintrag aus."""
    parts, section = [], None
    for key, title, href, sec in NAV:
        if key == "traum":
            if traum_name is None:
                continue
            title = traum_name
        if sec != section:
            parts.append(f'<div class="nav-sec">{escape(sec)}</div>')
            section = sec
        count, kind = badges.get(key, (0, ""))
        badge = f'<span class="badge {kind}">{count}</span>' if count else ""
        cls = ' class="active"' if key == active else ""
        parts.append(f'<a href="{href}"{cls}>{icon(key)}<span>{escape(title)}</span>{badge}</a>')
    hint_html = f'<div class="hint">{escape(hint)}</div>' if hint else ""
    return f"""<aside class="side"><div class="brand">{LOGO}Job-Monitor</div>
<nav class="nav">{"".join(parts)}</nav>
<div class="side-foot">{hint_html}
<form method="post" action="/sync"><input type="hidden" name="token" value="{token}"><button>{icon("sync", 16)}
Synchronisieren</button></form>
<form method="post" action="/quit"><input type="hidden" name="token" value="{token}"><button>{icon("power", 16)}
Beenden</button></form></div></aside>"""


def document(title: str, body: str, side: str = "", extra_css: str = "", token: str = "",
             native: bool = False) -> bytes:
    """`native`: im App-Fenster mit durchscheinender Seitenleiste (nur zusammen mit `side`)."""
    main_style = "" if side else ' style="margin:0 auto;max-width:1180px"'
    html_cls = ' class="native"' if native and side else ""
    return f"""<!doctype html><html lang="de"{html_cls}><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} · Job-Monitor</title>
<style>{CSS}{extra_css}</style></head><body data-token="{token}">{side}<main{main_style}>{body}</main>
<div id="busy" role="status" aria-live="polite"><div><span><b>Bitte warten …</b><small></small></span></div></div><script>{JS}</script></body></html>""".encode()


def head(title: str, sub: str = "", actions: str = "") -> str:
    sub_html = f'<p class="sub">{sub}</p>' if sub else ""
    return f'<div class="page-head"><div><h1>{escape(title)}</h1>{sub_html}</div><div class="row">{actions}</div></div>'
