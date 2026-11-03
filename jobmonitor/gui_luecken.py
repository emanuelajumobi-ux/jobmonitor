"""Lücken-Auswertung: Welche Anforderungen kommen in deinen gefundenen Stellen am häufigsten vor, wie gut
deckst du sie ab, und wie stark würde dein durchschnittlicher Fit steigen, wenn du sie nachweist?

Grundlage sind die gespeicherten Anforderungen je Stelle (state/seen.sqlite), ohne ausgeblendete Stellen.
"""
from __future__ import annotations

from html import escape

from . import fit
from .cv_data import LEVELS
from .models import Job

STUFEN = {"Grundkenntnisse": LEVELS["grundkenntnisse"], "gut": LEVELS["gut"]}


def _avg_fit(details: list[dict], covered: dict[str, float], cfg: dict) -> float | None:
    values = []
    for d in details:
        job = Job(d["title"], d["company"], d["url"], "")
        fit.apply(job, d["anforderungen"], covered, cfg)
        if job.fit is not None:
            values.append(job.fit)
    return sum(values) / len(values) if values else None


def analyse(details: list[dict], covered: dict[str, float], cfg: dict) -> tuple[float | None, list[dict]]:
    """(Ø-Fit heute, Zeilen je Begriff) – sortiert nach möglichem Fit-Gewinn, dann Häufigkeit."""
    rated = [d for d in details if len(d["anforderungen"]) >= cfg["min_anforderungen"]]
    base = _avg_fit(rated, covered, cfg)
    counts: dict[str, list[int]] = {}
    for d in rated:
        for term, weight in d["anforderungen"].items():
            c = counts.setdefault(term, [0, 0])
            c[0 if weight >= 1 else 1] += 1
    rows = []
    for term, (gefordert, optional) in counts.items():
        have = covered.get(term)
        gains = {}
        for stufe, w in STUFEN.items():
            if have is not None and have >= w:
                continue
            new = _avg_fit(rated, {**covered, term: w}, cfg)
            gains[stufe] = (new - base) if new is not None and base is not None else 0.0
        rows.append({"term": term, "gefordert": gefordert, "optional": optional, "stand": have, "gewinn": gains})
    rows.sort(key=lambda r: (-max(r["gewinn"].values(), default=0), -(r["gefordert"] + r["optional"]), r["term"]))
    return base, rows


def stand_text(have: float | None) -> str:
    if have is None:
        return "fehlt"
    for name, w in (("sehr gut", 1.0), ("gut", LEVELS["gut"]), ("Grundkenntnisse", LEVELS["grundkenntnisse"])):
        if have >= w - 1e-9:
            return name
    return "Grundkenntnisse"


def render_vorschlaege(items: list[dict], token: str) -> str:
    """Karte „Was du tun kannst“: Lernvorschläge (lernpfade.py) für die teuersten Lücken."""
    if not items:
        return ""
    blocks = []
    for block in items:
        lis = []
        for v in block["items"]:
            art = "Zertifikat" if v.get("art") == "zertifikat" else "Projekt"
            if v["stand"]:
                aktion = f'<span class="chip">im Master-CV: {escape(v["stand"])}</span>'
            else:
                aktion = (f'<form method="post" action="/luecken/uebernehmen" style="display:inline">'
                          f'<input type="hidden" name="token" value="{token}">'
                          f'<input type="hidden" name="term" value="{escape(block["term"])}">'
                          f'<input type="hidden" name="index" value="{v["index"]}">'
                          f'<button class="ghost small">Als geplant übernehmen</button></form>')
            lis.append(f'<li><span class="chip">{art}</span> <b>{escape(v["name"])}</b>'
                       f'{" – " + escape(v["zusatz"]) if v.get("zusatz") else ""} {aktion}</li>')
        blocks.append(f'<h3>{escape(block["term"])} <span class="muted">(bis +{block["gewinn"]:.1f} Ø-Fit)</span></h3>'
                      f'<ul class="lern">{"".join(lis)}</ul>')
    return (f'<div class="card"><h2>Was du tun kannst</h2><p class="muted">Vorschläge für die Lücken, die dich am '
            f'meisten Fit kosten (aus lernpfade.yaml, frei erweiterbar). „Als geplant übernehmen“ trägt den Eintrag '
            f'mit Status geplant in deinen Master-CV ein – er zählt erst für den Fit und erscheint erst im '
            f'Lebenslauf, wenn du ihn auf in Arbeit/erreicht setzt. Prüfungsdetails vor dem Buchen beim Anbieter '
            f'nachsehen.</p>{"".join(blocks)}</div>')


def kenntnis_knoepfe(term: str, stand: float | None, token: str) -> str:
    """„Habe ich: Grundkenntnisse / gut / sehr gut“ – trägt den Begriff mit einem Klick in den Master-CV ein."""
    if stand is not None and stand >= 1.0:
        return ""
    knoepfe = "".join(f'<button name="level" value="{escape(lv)}" class="ghost small">{escape(lv)}</button>'
                      for lv in ("Grundkenntnisse", "gut", "sehr gut"))
    return (f'<form method="post" action="/luecken/kenntnis" class="row" style="gap:6px;flex-wrap:wrap">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="term" '
            f'value="{escape(term)}"><span class="muted" style="font-size:12px">Habe ich:</span>{knoepfe}</form>')


def render(base: float | None, rows: list[dict], n_jobs: int, token: str = "") -> str:
    if not rows:
        return '<div class="card"><p class="muted">Noch zu wenige Stellen mit erkennbaren Anforderungen.</p></div>'
    trs = []
    for r in rows:
        gain = " · ".join(f"{escape(k)}: +{v:.1f}" for k, v in r["gewinn"].items()) or "–"
        cls = "err" if r["stand"] is None else ("muted" if not r["gewinn"] else "")
        optional = f" (+{r['optional']} optional)" if r["optional"] else ""
        trs.append(f'<tr><td><b>{escape(r["term"])}</b></td><td>{r["gefordert"]}{optional}</td>'
                   f'<td class="{cls}">{escape(stand_text(r["stand"]))}</td><td>{gain}</td>'
                   f'<td>{kenntnis_knoepfe(r["term"], r["stand"], token) if token else ""}</td></tr>')
    base_txt = f"{base:.0f} %" if base is not None else "–"
    return f"""<div class="card"><p>Ø-Fit über {n_jobs} Stellen mit genug Angaben: <b>{base_txt}</b>.
Die Spalte „Ø-Fit-Gewinn“ zeigt, um wie viele Prozentpunkte dein Durchschnitt steigen würde, wenn du den Begriff
mit diesem Level im Master-CV belegst (z. B. durch ein Projekt, ein Zertifikat oder Praxis).</p>
<p class="muted">Kannst du etwas schon, das hier fehlt? Ein Klick auf das Level trägt es als Kenntnis in deinen
Master-CV ein (passende Kategorie, alter Stand bleibt als .bak). Bitte ehrlich – das Level fließt in den Fit ein.</p>
<table><tr><td class="muted">Begriff</td><td class="muted">gefordert in</td><td class="muted">dein Stand</td>
<td class="muted">Ø-Fit-Gewinn</td><td class="muted">in den Lebenslauf</td></tr>{"".join(trs)}</table></div>"""
