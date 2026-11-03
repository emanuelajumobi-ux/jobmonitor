"""Seite „Rückblick“: Wie läuft die Bewerbungsphase? Zahlen aus applications.csv, den erkannten Antworten
(state/antworten.json) und den gefundenen Stellen (state/seen.sqlite). Nichts wird gespeichert oder verschickt.

- Bewerbungen je Woche (letzte 8 Wochen, nach Bewerbungsdatum)
- Weg von „gefunden“ bis „Zusage“
- Rücklauf: Anteil mit Antwort, Ø Tage bis zur Antwort, Ergebnisse
- Herkunft: Wo die passenden Stellen und deine Bewerbungen herkommen
- Was zum Gespräch führt: Antwort- und Gesprächsquote nach Fit-Bereich, Art (Stelle/Initiativ) und Quelle
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from html import escape
from urllib.parse import urlsplit

BEWORBEN = ("beworben", "nachgefasst", "Antwort", "Absage", "Zusage")
ANTWORT = ("Antwort", "Absage", "Zusage")
HERKUNFT = [("arbeitsagentur.", "Bundesagentur"), ("arbeitnow.", "Arbeitnow"), ("adzuna.", "Adzuna"),
            ("stellenwerk.", "Stellenwerk"), ("hs-niederrhein.", "Hochschule"),
            ("linkedin.", "Job-Alerts"), ("stepstone.", "Job-Alerts"), ("indeed.", "Job-Alerts"), ("xing.", "Job-Alerts")]


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def herkunft(url: str) -> str:
    host = urlsplit(url or "").netloc.lower()
    return next((name for key, name in HERKUNFT if key in host), "Firmenseiten" if host else "ohne Link")


def _datum(text: str) -> date | None:
    try:
        return date.fromisoformat((text or "")[:10])
    except ValueError:
        return None


FIT_BEREICHE = (("Fit ab 75 %", 75, 101), ("Fit 50–74 %", 50, 75), ("Fit unter 50 %", -1, 50))


def fit_bereich(fit) -> str:
    if fit is None:
        return "ohne Fit"
    return next(name for name, von, bis in FIT_BEREICHE if von <= fit < bis)


def erfolg(beworben: list[dict], mit_antwort: list[dict], fit_von: dict[str, int | None]) -> dict[str, list]:
    """Je Merkmal: [(Gruppe, Bewerbungen, mit Antwort, mit Gespräch)], größte Gruppe zuerst."""
    antwort = {id(r) for r in mit_antwort}
    merkmale = {"Fit": lambda r: fit_bereich(fit_von.get(r.get("link"))),
                "Art": lambda r: r.get("typ") or "Stelle",
                "Quelle": lambda r: herkunft(r.get("link"))}
    out = {}
    for name, schluessel in merkmale.items():
        gruppen: dict[str, list[int]] = {}
        for r in beworben:
            g = gruppen.setdefault(schluessel(r), [0, 0, 0])
            g[0] += 1
            g[1] += id(r) in antwort
            g[2] += bool(r.get("termin")) or r.get("status") == "Zusage"
        reihenfolge = [n for n, _, _ in FIT_BEREICHE] + ["ohne Fit"] if name == "Fit" else None
        out[name] = sorted(((g, *v) for g, v in gruppen.items()),
                           key=lambda t: reihenfolge.index(t[0]) if reihenfolge else -t[1])
    return out


def zahlen(rows: list[dict], antworten: list, stellen: list[dict], heute: date) -> dict:
    beworben = [r for r in rows if r.get("status") in BEWORBEN]
    beantwortet_links = {a.link for a in antworten if a.status}
    mit_antwort = [r for r in beworben if r.get("status") in ANTWORT or r.get("link") in beantwortet_links]
    # Ø Tage bis zur Antwort: erste echte Antwort aus dem Postfach minus Bewerbungsdatum
    erste: dict[str, date] = {}
    for a in antworten:
        d = _datum(a.datum)
        if a.status and d and (a.link not in erste or d < erste[a.link]):
            erste[a.link] = d
    dauer = [(erste[r["link"]] - d).days for r in beworben
             if r.get("link") in erste and (d := _datum(r.get("datum"))) and erste[r["link"]] >= d]
    montag = heute - timedelta(days=heute.weekday())
    wochen = []
    for i in range(7, -1, -1):
        start = montag - timedelta(weeks=i)
        n = sum(1 for r in beworben if (d := _datum(r.get("datum"))) and start <= d < start + timedelta(days=7))
        wochen.append((start, n))
    grenze = (heute - timedelta(days=56)).isoformat()
    neu = [s for s in stellen if (s.get("first_seen") or "") >= grenze]
    return {
        "wochen": wochen,
        "weg": [("Passende Stellen gefunden (8 Wochen)", len(neu)),
                ("In deine Liste übernommen", sum(1 for r in rows if r.get("typ") == "Stelle")),
                ("Beworben", len(beworben)), ("Antwort bekommen", len(mit_antwort)),
                ("Gespräch", sum(1 for r in rows if r.get("termin"))),
                ("Zusage", sum(1 for r in rows if r.get("status") == "Zusage"))],
        "quote": round(100 * len(mit_antwort) / len(beworben)) if beworben else None,
        "dauer": round(sum(dauer) / len(dauer)) if dauer else None,
        "ergebnis": Counter(r.get("status") for r in beworben),
        "herkunft_stellen": Counter(herkunft(s.get("url")) for s in neu).most_common(),
        "herkunft_bewerbungen": Counter(herkunft(r.get("link")) for r in beworben).most_common(),
        "beworben": len(beworben),
        "erfolg": erfolg(beworben, mit_antwort, {s.get("url"): s.get("fit") for s in stellen if s.get("url")}),
    }


def _balken(items: list[tuple[str, int]], leer: str) -> str:
    gesamt = max((n for _, n in items), default=0)
    if not gesamt:
        return f'<p class="muted">{esc(leer)}</p>'
    return "".join(f'<div class="gap-item"><b>{esc(name)}</b><span>{n}</span>'
                   f'<i style="--p:{round(100 * n / gesamt)}"></i></div>' for name, n in items)


def _erfolg_html(erfolg: dict[str, list]) -> str:
    if not any(erfolg.values()):
        return ""
    pct = lambda n, g: f"{round(100 * n / g)} %" if g else "–"  # noqa: E731
    teile = []
    for name, zeilen in erfolg.items():
        body = "".join(f'<tr><td>{esc(g)}</td><td class="num">{n}</td><td class="num">{pct(a, n)}</td>'
                       f'<td class="num">{pct(t, n)}</td></tr>' for g, n, a, t in zeilen)
        teile.append(f'<table class="erfolg"><thead><tr><th>{esc(name)}</th><th>Bewerbungen</th><th>mit Antwort</th>'
                     f'<th>Gespräch</th></tr></thead><tbody>{body}</tbody></table>')
    wenig = sum(z[1] for z in next(iter(erfolg.values()))) < 10
    return (f'<div class="card"><h2>Was zum Gespräch führt</h2><p class="muted">Antwort- und Gesprächsquote je '
            f'Gruppe{" – bei weniger als 10 Bewerbungen noch kaum aussagekräftig" if wenig else ""}.</p>'
            f'<div class="erfolg-grid">{"".join(teile)}</div></div>')


def render(z: dict) -> str:
    kacheln = [("Bewerbungen", z["beworben"], "seit Beginn"),
               ("Rücklauf", f'{z["quote"]} %' if z["quote"] is not None else "–", "mit Antwort der Firma"),
               ("Ø bis zur Antwort", f'{z["dauer"]} Tage' if z["dauer"] is not None else "–", "laut Postfach"),
               ("Gespräche", dict(z["weg"])["Gespräch"], "mit Termin")]
    kopf = "".join(f'<div class="kpi"><span>{esc(t)}</span><b>{esc(v)}</b><small>{esc(u)}</small></div>'
                   for t, v, u in kacheln)
    wochen = _balken([(f"ab {d:%d.%m.}", n) for d, n in z["wochen"]],
                     "Noch keine Bewerbungen mit Datum. Setz den Status auf „beworben“, dann zählt sie hier.")
    weg = "".join(f'<div class="step"><b>{n}</b><span>{esc(name)}</span></div>' for name, n in z["weg"])
    ergebnis = _balken([(s, z["ergebnis"].get(s, 0)) for s in BEWORBEN if z["ergebnis"].get(s)], "Noch nichts.")
    return f"""<div class="page-head"><div><h1>Rückblick</h1><p class="sub">Wie deine Bewerbungsphase läuft – aus
deiner Liste, den erkannten Antworten und den gefundenen Stellen.</p></div></div>
<div class="kpis">{kopf}</div>
<div class="card"><h2>Vom Fund zur Zusage</h2><div class="steps">{weg}</div></div>
{_erfolg_html(z.get("erfolg") or {})}
<div class="grid2 rueck">
<div class="card"><h2>Bewerbungen je Woche</h2>{wochen}</div>
<div class="card"><h2>Stand deiner Bewerbungen</h2>{ergebnis}</div>
<div class="card"><h2>Woher passende Stellen kommen</h2><p class="muted">Letzte 8 Wochen</p>
{_balken(z["herkunft_stellen"], "Noch keine Stellen.")}</div>
<div class="card"><h2>Woher deine Bewerbungen kommen</h2>
{_balken(z["herkunft_bewerbungen"], "Noch keine Bewerbungen.")}</div>
</div>"""


CSS = """
.kpis { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:14px; margin-bottom:14px; }
.kpi { background:var(--surface); border-radius:var(--radius); padding:16px 18px; display:grid; gap:2px; }
.kpi span { color:var(--muted); font-size:13px; } .kpi b { font-size:26px; font-weight:500; font-variant-numeric:tabular-nums; }
.kpi small { color:var(--faint); font-size:12px; }
.steps { display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); gap:8px; }
.step { display:grid; gap:2px; padding:10px 12px; border-radius:10px; background:var(--surface-2); }
.step b { font-size:20px; font-weight:500; font-variant-numeric:tabular-nums; } .step span { font-size:12px; color:var(--muted); }
.erfolg-grid { display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:18px; }
.erfolg { width:100%; border-collapse:collapse; font-size:13px; }
.erfolg th { text-align:left; color:var(--muted); font-weight:500; padding:4px 6px 6px 0; }
.erfolg td { padding:5px 6px 5px 0; border-top:1px solid var(--line); } .erfolg .num, .erfolg th + th { text-align:right; }
.rueck { gap:14px; } .rueck .card { margin:0; }
@media (max-width:980px) { .kpis { grid-template-columns:repeat(2, minmax(0,1fr)); }
  .steps { grid-template-columns:repeat(3, minmax(0,1fr)); } .erfolg-grid { grid-template-columns:1fr; } }
"""
