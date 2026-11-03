"""Seite „Letzter Bericht“ im Stil der App statt als Mail-Markdown.

Die Pipeline schreibt reports/<Datum>.md (report.py). Diese Seite liest die bekannten Abschnitte daraus und zeigt sie
mit den Bauteilen der Stellen-Seite: Stellen als Zeilen mit Fit, Quellen mit Statuspunkt statt Emoji, Manuelles
zum Aufklappen. Unbekanntes Format (sehr alte oder fremde Berichte): Markdown wie bisher.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
URL = re.compile(r"https?://\S+")
EMOJI = re.compile(r"[☀-➿\U0001F300-\U0001FAFF️]+\s*")


def esc(value) -> str:
    return escape(str(value or ""), quote=True)


def inline(text: str) -> str:
    """Kleines Markdown (Links, fett, Code) als HTML, ohne Emojis."""
    text = EMOJI.sub("", text or "")
    out, pos = [], 0
    for m in LINK.finditer(text):
        out.append(esc(text[pos:m.start()]))
        out.append(f'<a href="{esc(m.group(2))}" target="_blank" rel="noopener">{esc(m.group(1))}</a>')
        pos = m.end()
    html = "".join(out) + esc(text[pos:])
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    return re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"\1", html)


@dataclass
class Quelle:
    name: str
    status: str            # ok, warn, err
    treffer: str
    notiz: str = ""
    fehler: list[str] = field(default_factory=list)
    teilfehler: list[str] = field(default_factory=list)     # einzelne Firma nicht erreichbar (Quelle läuft)


@dataclass
class Stelle:
    titel: str
    url: str
    score: str
    firma: str = ""
    meta: str = ""
    grund: str = ""
    fit: int | None = None
    passt: str = ""
    fehlt: str = ""
    sid: str = ""
    frist: str = ""
    traum: bool = False
    eckdaten: list[str] = field(default_factory=list)


@dataclass
class Gruppe:
    titel: str
    stellen: list[Stelle] = field(default_factory=list)
    leer: str = ""
    zeilen: list[str] = field(default_factory=list)     # Listenpunkte (Initiativ, Nachfassen, Traumprofil)


@dataclass
class Bericht:
    datum: str = ""
    quellen: list[Quelle] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    beobachten: list[str] = field(default_factory=list)
    manuell: list[str] = field(default_factory=list)
    gruppen: list[Gruppe] = field(default_factory=list)
    fuss: str = ""

    @property
    def neue(self) -> int:
        return sum(len(g.stellen) for g in self.gruppen if g.titel.startswith("Neue Stellen"))


QUELLE = re.compile(r"^- (✅|⚠️|❌)\s*\*\*(.+?)\*\*: (\d+) Rohtreffer(?: \((.*)\))?$")
FIT = re.compile(r"Fit (\d+) %")


def _stelle(kopf: str, zeilen: list[str]) -> Stelle | None:
    m = re.match(r"^### (\d+) · (?:(⭐+)\s*)?\[(.+)\]\((\S+)\)\s*$", kopf)
    if not m:
        return None
    s = Stelle(titel=m.group(3), url=m.group(4), score=m.group(1), traum=bool(m.group(2)))
    zeilen = [z.rstrip() for z in zeilen if z.strip()]
    if zeilen:
        teile = zeilen[0].split(" · ")
        s.firma = BOLD.sub(r"\1", teile[0])
        s.meta = " · ".join(teile[1:])
    if len(zeilen) > 1:
        s.grund = zeilen[1]
    for z in zeilen[2:]:
        if z.startswith("Eckdaten: "):
            s.eckdaten = [e.strip() for e in z[len("Eckdaten: "):].split(" · ") if e.strip()]
            continue
        if (f := FIT.search(z)):
            s.fit = int(f.group(1))
        for teil in z.split(" · "):
            if teil.startswith("passt: "):
                s.passt = teil[7:]
            elif teil.startswith("fehlt: "):
                s.fehlt = teil[7:]
            elif (i := re.match(r"ID `(\w+)`", teil)):
                s.sid = i.group(1)
            elif (b := re.fullmatch(r"\*\*(.+)\*\*", teil.strip())):
                s.frist = b.group(1)
    return s


def parse(text: str) -> Bericht | None:
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# Job-Monitor"):
        return None
    b = Bericht(datum=lines[0].partition("–")[2].strip())
    abschnitt, gruppe, unter = "", None, ""
    i = 0
    while i < len(lines):
        z = lines[i]
        if z.startswith("## "):
            titel = EMOJI.sub("", z[3:]).strip()
            abschnitt, unter = ("status", "") if titel == "Status der Quellen" else ("gruppe", "")
            gruppe = None
            if abschnitt == "gruppe":
                gruppe = Gruppe(titel)
                b.gruppen.append(gruppe)
        elif z.startswith("### ") and gruppe is not None:
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].startswith("#"):
                j += 1
            if (s := _stelle(z, lines[i + 1:j])):
                gruppe.stellen.append(s)
            i = j
            continue
        elif z.startswith("**Quellen beobachten**"):
            unter = "beobachten"
        elif z.startswith("**Manuell prüfen:**"):
            unter = "manuell"
        elif z.startswith("---"):
            abschnitt, gruppe = "fuss", None
        elif abschnitt == "fuss" and z.strip():
            b.fuss = z.strip("_ ")
        elif abschnitt == "status" and z.startswith("- "):
            if unter == "beobachten":
                b.beobachten.append(z[2:])
            elif unter == "manuell":
                b.manuell.append(z[2:])
            elif (m := QUELLE.match(z)):
                b.quellen.append(Quelle(m.group(2), {"✅": "ok", "⚠️": "warn", "❌": "err"}[m.group(1)], m.group(3),
                                        m.group(4) or ""))
            else:
                b.hinweise.append(z[2:])
        elif abschnitt == "status" and z.startswith("  - Nicht erreichbar: ") and b.quellen:
            b.quellen[-1].teilfehler.append(z[len("  - Nicht erreichbar: "):])
        elif abschnitt == "status" and z.startswith("  - ") and b.quellen:
            b.quellen[-1].fehler.append(z[4:].removeprefix("Fehler: "))
        elif gruppe is not None and z.startswith("- "):
            gruppe.zeilen.append(z[2:])
        elif gruppe is not None and z.strip() and not gruppe.stellen:
            gruppe.leer = z.strip()
        i += 1
    return b if (b.quellen or b.gruppen) else None


# --- Darstellung ---
def _stelle_html(s: Stelle) -> str:
    fit = (f'<div class="fitnum{" hi" if s.fit >= 75 else ""}" title="Fit {s.fit} %">{s.fit}<small>%</small></div>'
           if s.fit is not None else '<div class="fitnum none" title="Zu wenig Angaben in der Anzeige">–</div>')
    belege = []
    if s.passt:
        belege.append(f'<span><b>passt</b> {esc(s.passt)}</span>')
    if s.fehlt:
        belege.append(f'<span><b>fehlt</b> {esc(s.fehlt)}</span>')
    chips = (f'<span class="chip frist">{esc(s.frist)}</span>' if s.frist else "") + \
            ('<span class="mark">Traumprofil</span>' if s.traum else "") + \
            "".join(f'<span class="chip eck">{esc(e)}</span>' for e in s.eckdaten)
    return (f'<article class="job rep" title="Score {esc(s.score)}{" · ID " + esc(s.sid) if s.sid else ""}">'
            f'<div style="min-width:0"><h3><a href="{esc(s.url)}" target="_blank" rel="noopener">{esc(s.titel)}</a>'
            f'</h3><div class="meta"><span>{esc(s.firma)}{" · " + inline(s.meta) if s.meta else ""}</span>{chips}'
            f'</div>{f"<div class=belege>{''.join(belege)}</div>" if belege else ""}</div>{fit}</article>')


def _zeile_html(text: str) -> str:
    m = re.match(r"^\*\*(.+?)\*\*(.*?): (.*)$", EMOJI.sub("", text))
    if m:   # Initiativ: **Firma**: [Initiativbewerbung](url) – Begründung
        return (f'<div class="rep-line"><b>{esc(m.group(1))}{"" if not m.group(2).strip() else " " + esc(m.group(2))}'
                f'</b><p>{inline(m.group(3))}</p></div>')
    return f'<div class="rep-line"><p>{inline(URL.sub(lambda u: f"[Link]({u.group(0)})", text))}</p></div>'


def _gruppe_html(g: Gruppe) -> str:
    m = re.match(r"^(.*?)\s*\((\d+)\)$", g.titel)
    titel, anzahl = (m.group(1), m.group(2)) if m else (g.titel, "")
    rows = "".join(_stelle_html(s) for s in g.stellen) + "".join(_zeile_html(z) for z in g.zeilen)
    if not rows:
        rows = f'<p class="empty">{esc(g.leer or "Nichts Neues.")}</p>'
    return f'<section><div class="group"><span>{esc(titel)}</span><span>{esc(anzahl)}</span></div>{rows}</section>'


def _manuell_html(text: str) -> str:
    name, _, rest = text.partition(": ")
    url = URL.search(rest)
    grund = URL.sub("", rest).rstrip(" –")
    kopf = (f'<a href="{esc(url.group(0))}" target="_blank" rel="noopener">{esc(name)}</a>' if url else esc(name))
    return f'<li>{kopf}<span>{inline(grund)}</span></li>'


def render(b: Bericht, aeltere: list[str], aktuell: str) -> str:
    fehler = sum(q.status != "ok" for q in b.quellen)
    teile = [f"{b.neue} neue Stelle{'' if b.neue == 1 else 'n'}",
             f"{len(b.quellen)} Quellen" + (f", {fehler} mit Problemen" if fehler else ", alle ohne Fehler")]
    if b.manuell:
        teile.append(f"{len(b.manuell)} Seiten zum selbst Ansehen")
    tage = "".join(f'<a href="/bericht/{esc(t)}"{" class=active" if t == aktuell else ""}>{esc(_kurz(t))}</a>'
                   for t in aeltere)
    kopf = (f'<div class="page-head"><div><h1>Bericht vom {esc(b.datum)}</h1><p class="sub">{esc(" · ".join(teile))}'
            f'</p></div></div>' + (f'<nav class="tabs rep-tabs" aria-label="Berichte">{tage}</nav>' if tage else ""))

    quellen = "".join(
        f'<div class="src"><i class="dot {q.status}"></i><b title="{esc(q.notiz)}">{esc(q.name)}</b>'
        f'<span>{esc(q.treffer)}</span>'
        + (f'<p>{esc(q.notiz)}</p>' if q.notiz else "")
        + "".join(f'<p class="err">{esc(f)}</p>' for f in q.fehler)
        + (f'<p>Nicht erreichbar: {esc(", ".join(t.split(":")[0] for t in q.teilfehler))} · '
           f'<a href="/firmen">bei Firmen ansehen</a></p>' if q.teilfehler else "") + '</div>' for q in b.quellen)
    hinweise = "".join(f'<p class="muted">{inline(h)}</p>' for h in b.hinweise)
    rail = [f'<div class="card"><div class="head"><h2>Quellen</h2><span class="muted">Rohtreffer</span></div>'
            f'{quellen}{hinweise}</div>']
    if b.beobachten:
        rail.append('<div class="card"><div class="head"><h2>Quellen beobachten</h2></div>'
                    + "".join(f'<p class="muted">{inline(w)}</p>' for w in b.beobachten) + '</div>')
    if b.manuell:
        rail.append(f'<div class="card"><details><summary><h2>Selbst ansehen</h2><span>{len(b.manuell)}</span>'
                    f'</summary><p class="muted">Diese Seiten lassen sich nicht automatisch lesen.</p>'
                    f'<ul class="manual">{"".join(_manuell_html(m) for m in b.manuell)}</ul></details></div>')

    main = "".join(_gruppe_html(g) for g in b.gruppen) or '<section><p class="empty">Keine Abschnitte.</p></section>'
    fuss = f'<p class="muted rep-foot">{esc(b.fuss)}</p>' if b.fuss else ""
    return f'{kopf}<div class="board rep-board"><div class="rep-main">{main}{fuss}</div>' \
           f'<aside class="rail">{"".join(rail)}</aside></div>'


def _kurz(stem: str) -> str:
    j, m, t = stem.split("-")
    return f"{t}.{m}."


def seite(root: Path, stem: str | None = None) -> str | None:
    """HTML für den neuesten Bericht oder den vom Tag `stem` (YYYY-MM-DD); None, wenn es ihn nicht gibt."""
    import markdown

    reports = sorted((root / "reports").glob("*.md"))
    if not reports:
        return '<h1>Bericht</h1><p class="muted">Noch kein Bericht.</p>'
    if stem is None:
        path = reports[-1]
    else:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stem) or not (root / "reports" / f"{stem}.md").is_file():
            return None
        path = root / "reports" / f"{stem}.md"
    text = path.read_text(encoding="utf-8")
    aeltere = [p.stem for p in reversed(reports[-8:])]
    b = parse(text)
    if b is None:   # unbekanntes Format: wie bisher
        nav = " · ".join(f'<a href="/bericht/{esc(t)}">{esc(t)}</a>' for t in aeltere if t != path.stem)
        return (f'<p class="sub">{"Weitere: " + nav if nav else ""}</p>'
                f'<div class="card report">{markdown.markdown(text)}</div>')
    return render(b, aeltere, path.stem)


CSS = """
.rep-tabs { margin:-8px 0 16px; }
.rep-main { display:grid; gap:14px; align-content:start; }
.rep-main > section { background:var(--surface); border-radius:var(--radius); padding:6px 0; }
.rep-board .rail { top:20px; }
.job.rep { grid-template-columns:minmax(0,1fr) 56px; min-height:64px; }
.job .belege { display:flex; flex-wrap:wrap; gap:4px 14px; margin-top:4px; font-size:12.5px; color:var(--faint); }
.job .belege b { font-weight:500; color:var(--muted); margin-right:4px; }
.rep-line { padding:10px 22px; position:relative; }
.rep-line + .rep-line::before { content:""; position:absolute; top:0; left:22px; right:22px; border-top:1px solid var(--line); }
.rep-line b { font-weight:500; } .rep-line p { margin:2px 0 0; color:var(--muted); font-size:13px; }
.src { display:grid; grid-template-columns:8px minmax(0,1fr) auto; gap:2px 10px; align-items:center; padding:7px 0; }
.src + .src { border-top:1px solid var(--line); }
.src b { font-weight:500; overflow-wrap:anywhere; }
.src > span { color:var(--faint); font-size:12px; font-variant-numeric:tabular-nums; }
.src p { grid-column:2 / -1; margin:0; font-size:12px; color:var(--faint); display:-webkit-box; -webkit-line-clamp:2;
         -webkit-box-orient:vertical; overflow:hidden; }
.src p.err { color:var(--err); white-space:normal; }
.dot { width:8px; height:8px; border-radius:50%; background:var(--ok); }
.dot.warn { background:var(--warn); } .dot.err { background:var(--err); }
.rail details summary { display:flex; justify-content:space-between; align-items:baseline; cursor:pointer; list-style:none; }
.rail details summary::-webkit-details-marker { display:none; }
.rail details summary h2 { margin:0; } .rail details summary span { color:var(--faint); font-size:12px; }
.rail details[open] summary { margin-bottom:6px; }
.manual { list-style:none; padding:0; margin:8px 0 0; display:grid; gap:8px; }
.manual li { display:grid; gap:1px; font-size:13px; } .manual a { font-weight:500; text-decoration:none; }
.manual span { color:var(--faint); font-size:12px; }
.rep-foot { padding:0 4px; }
"""
