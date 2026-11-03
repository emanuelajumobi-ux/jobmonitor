"""Lücken-Seite, Karte „Gefragt im Verlauf“: Wie oft verlangen die gefundenen Stellen eine Kenntnis, Monat für Monat?

Grundlage sind die gespeicherten Anforderungen je Stelle (state/seen.sqlite, Monat = erstes Auftauchen). Gezählt wird
der Anteil der Stellen eines Monats, nicht die absolute Zahl – sonst sähe jeder Monat mit vielen Funden wie ein
Aufschwung aus. „Steigend“ / „fallend“: Anteil der letzten zwei Monate gegenüber den Monaten davor um mindestens
`SCHWELLE` Prozentpunkte verändert. Aussagekräftig erst ab etwa drei Monaten mit Stellen.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from html import escape

MONATE = 6
TOP = 8
SCHWELLE = 10        # Prozentpunkte
MIN_STELLEN = 3      # Monate mit weniger Stellen zählen für den Trend nicht


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def _monate(heute: date, n: int) -> list[str]:
    out, j, m = [], heute.year, heute.month
    for _ in range(n):
        out.append(f"{j:04d}-{m:02d}")
        j, m = (j, m - 1) if m > 1 else (j - 1, 12)
    return out[::-1]


def verlauf(details: list[dict], heute: date, monate: int = MONATE, top: int = TOP) -> dict:
    """{"monate": [(JJJJ-MM, Stellen)], "zeilen": [{term, anteile: [% oder None], trend}]}"""
    liste = _monate(heute, monate)
    stellen: Counter = Counter()
    je_monat: dict[str, Counter] = {m: Counter() for m in liste}
    for d in details:
        m = (d.get("first_seen") or "")[:7]
        if m in je_monat:
            stellen[m] += 1
            je_monat[m].update(set(d.get("anforderungen") or {}))
    gesamt = Counter()
    for c in je_monat.values():
        gesamt.update(c)
    zeilen = []
    for term, _ in gesamt.most_common(top):
        anteile = [round(100 * je_monat[m][term] / stellen[m]) if stellen[m] else None for m in liste]
        zeilen.append({"term": term, "anteile": anteile, "trend": _trend(anteile, [stellen[m] for m in liste])})
    return {"monate": [(m, stellen[m]) for m in liste], "zeilen": zeilen}


def _trend(anteile: list[int | None], n: list[int]) -> str:
    gueltig = [(a, k) for a, k in zip(anteile, n) if a is not None and k >= MIN_STELLEN]
    if len(gueltig) < 3:
        return ""
    jetzt, vorher = [a for a, _ in gueltig[-2:]], [a for a, _ in gueltig[:-2]]
    diff = sum(jetzt) / len(jetzt) - sum(vorher) / len(vorher)
    return "steigend" if diff >= SCHWELLE else "fallend" if diff <= -SCHWELLE else "gleich"


MONATSNAMEN = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def render(v: dict, covered: dict[str, float]) -> str:
    if not v["zeilen"]:
        return ""
    kopf = "".join(f'<th title="{n} Stellen">{MONATSNAMEN[int(m[5:]) - 1]}</th>' for m, n in v["monate"])
    pfeil = {"steigend": "↑ steigend", "fallend": "↓ fallend", "gleich": "→ gleich", "": ""}
    zeilen = ""
    for z in v["zeilen"]:
        zellen = "".join(f'<td title="{a} % der Stellen">' + (f'<i style="--p:{a}"></i>' if a else "") + '</td>'
                         if a is not None else '<td class="leer">–</td>' for a in z["anteile"])
        fehlt = "" if covered.get(z["term"], 0) > 0 else ' <span class="chip">fehlt dir</span>'
        zeilen += (f'<tr><td><b>{esc(z["term"])}</b>{fehlt}</td>{zellen}'
                   f'<td class="trend {z["trend"]}">{pfeil[z["trend"]]}</td></tr>')
    monate_mit = sum(1 for _, n in v["monate"] if n >= MIN_STELLEN)
    hinweis = ("" if monate_mit >= 3 else
               f" Erst {monate_mit} Monat(e) mit genug Stellen – ein Trend zeigt sich ab etwa drei Monaten.")
    return (f'<div class="card"><div class="head"><h2>Gefragt im Verlauf</h2><span class="muted">Anteil der Stellen '
            f'je Monat</span></div><p class="muted">Die {len(v["zeilen"])} häufigsten Anforderungen der letzten '
            f'{len(v["monate"])} Monate.{hinweis}</p><table class="trendtab"><thead><tr><th></th>{kopf}<th></th></tr>'
            f'</thead><tbody>{zeilen}</tbody></table></div>')


CSS = """
.trendtab { width:100%; border-collapse:collapse; font-size:13px; }
.trendtab th { color:var(--muted); font-weight:500; text-align:center; padding:4px; }
.trendtab td { padding:5px 4px; border-top:1px solid var(--line); vertical-align:bottom; }
.trendtab td:first-child { white-space:nowrap; }
.trendtab td i { display:block; height:calc(var(--p) * .22px + 2px); min-height:2px; max-width:28px; margin:0 auto;
                 background:var(--accent, #4a7); border-radius:3px; }
.trendtab td.leer { color:var(--faint); text-align:center; }
.trendtab .trend { white-space:nowrap; color:var(--muted); text-align:right; }
.trendtab .trend.steigend { color:var(--ok, #2a7); } .trendtab .trend.fallend { color:var(--err, #c44); }
"""
