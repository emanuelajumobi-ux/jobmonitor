"""Einmalige Nachbewertung schon gespeicherter Stellen mit KI-Anforderungen (fit.ki), damit ältere Stellen genauso
bewertet sind wie neue.

Der Anzeigentext ist absichtlich nicht gespeichert; er wird je Stelle einmal neu geladen:
Bundesagentur über die Schnittstelle (jobdetails), Stellenwerk wie in der Quelle selbst, alles andere wie eine selbst
angegebene Stelle (robots.txt, ehrlicher User-Agent, nie LinkedIn & Co.). Ist die Anzeige nicht mehr lesbar, bleibt
die Stelle unverändert. Erledigte Stellen merkt sich state/seen.sqlite (meta „ki_nachbewertet“), ein zweiter Aufruf
bewertet also nur, was noch fehlt. Gespeichert werden wie immer nur Anforderungen und Fit, kein Anzeigentext.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from urllib.parse import urlsplit

from . import fit
from .sources.ats import jsonld
from .cv_data import covered_terms
from .models import Job
from .sources.bundesagentur import DETAIL_URL, BundesagenturSource

log = logging.getLogger(__name__)
META = "ki_nachbewertet"
BA_PREFIX = DETAIL_URL.split("{")[0]


def anzeigentext(url: str, fetcher, ba: BundesagenturSource) -> str:
    """Anzeigentext neu laden; leer, wenn die Anzeige weg oder nicht lesbar ist."""
    from .eigene_stelle import from_url
    try:
        if url.startswith(BA_PREFIX):
            return ba.description(url[len(BA_PREFIX):].split("?")[0])
        if urlsplit(url).netloc.endswith("stellenwerk.de"):    # wie StellenwerkSource (dort ohne robots.txt-Prüfung)
            html = fetcher.get(url, check_robots=False).text
            return next((j.description for j in jsonld.parse_postings(html, url, "", "")), "")
        return from_url(url, fetcher).description
    except Exception as exc:   # Anzeige weg, robots.txt-Verbot, LinkedIn & Co.: dann bleibt die Stelle wie sie ist
        log.info("Anzeige nicht gelesen (%s): %s", url, str(exc)[:120])
        return ""


def erledigt(state) -> set[str]:
    try:
        return set(json.loads(state.get_meta(META) or "[]"))
    except ValueError:
        return set()


def vermerken(state, ids) -> None:
    """Stellen als „mit KI bewertet“ merken (z. B. die neuen Stellen eines Laufs, die fit.mit_ki gelesen hat)."""
    if ids:
        state.set_meta(META, json.dumps(sorted(erledigt(state) | set(ids))))


STAPEL = "ki_stapel"     # offener KI-Stapel (ki_batch.py): {"id", "regel": {Stellen-ID: Stichwort-Anforderungen}}


def nachbewerten(state, cv: dict, cfg: dict, fetcher, ask=None, limit: int | None = None,
                 stapel: bool = False) -> dict:
    """Gespeicherte Stellen, die noch nicht mit KI bewertet sind (höchstens `limit`). Gibt Zähler und
    Begriffsvorschläge zurück. Läuft einmalig per Workflow-Option und in jedem Lauf für Liegengebliebenes.
    `stapel`: über die Batch-Schnittstelle (halber Preis) – dieser Lauf schickt ab, ein späterer holt ab."""
    if stapel and ask is None:
        return _per_stapel(state, cv, cfg, fetcher, limit)
    k = {**fit.KI_DEFAULTS, **(cfg["fit"].get("ki") or {})}
    ba = BundesagenturSource({**cfg["sources"]["bundesagentur"], "suchbegriffe": []}, fetcher)
    covered = covered_terms(cv, cfg["fit"]["begriffe"])
    fertig = erledigt(state)
    out = {"geprueft": 0, "aktualisiert": 0, "ohne_text": 0, "vorschlaege": Counter()}
    for d in state.job_details(limit=5000):
        if d["id"] in fertig:
            continue
        if limit is not None and out["geprueft"] >= limit:
            break
        out["geprueft"] += 1
        text = anzeigentext(d["url"] or "", fetcher, ba)
        if len(text) < k["min_text"]:
            out["ohne_text"] += 1
            fertig.add(d["id"])                       # nicht bei jedem Aufruf erneut versuchen
            continue
        job = Job(title=d["title"], company=d["company"], url=d["url"], source="", description=text)
        ergebnis = fit.ki_anforderungen(job, cfg["fit"]["begriffe"], k["model"], ask)
        if ergebnis is None:                          # KI nicht erreichbar: beim nächsten Aufruf noch einmal
            continue
        bekannt, weitere, eck = ergebnis
        # wie im Lauf: Stichwortsuche auf dem vollen Text, die KI entscheidet (fit.ki_zusammenfuehren)
        regel = fit.requirements(f"{job.title}\n{text}", cfg["fit"]["begriffe"], cfg["fit"]["optional_marker"])
        fit.apply(job, fit.ki_zusammenfuehren(regel, bekannt, weitere), covered, cfg["fit"])
        state.update_detail(d["id"], job.fit_anforderungen, job.fit, eck)
        out["vorschlaege"].update(list(weitere))
        out["aktualisiert"] += 1
        fertig.add(d["id"])
    state.set_meta(META, json.dumps(sorted(fertig)))
    return out


def _per_stapel(state, cv: dict, cfg: dict, fetcher, limit: int | None) -> dict:
    from . import ki_batch
    k = {**fit.KI_DEFAULTS, **(cfg["fit"].get("ki") or {})}
    begriffe = cfg["fit"]["begriffe"]
    out = {"geprueft": 0, "aktualisiert": 0, "ohne_text": 0, "vorschlaege": Counter(), "stapel": ""}
    try:
        offen = json.loads(state.get_meta(STAPEL) or "{}")
    except ValueError:
        offen = {}
    fertig = erledigt(state)
    if offen.get("id"):
        status, antworten = ki_batch.abholen(offen["id"])
        if status == "in_progress":
            out["stapel"] = "läuft noch"
            return out
        covered = covered_terms(cv, begriffe)
        details = {d["id"]: d for d in state.job_details(limit=5000)}
        for jid, antwort in antworten.items():
            d = details.get(jid)
            ergebnis = fit.ki_auswerten(antwort, begriffe, d["title"]) if d else None
            if ergebnis is None:
                continue
            bekannt, weitere, eck = ergebnis
            job = Job(title=d["title"], company=d["company"], url=d["url"], source="")
            fit.apply(job, fit.ki_zusammenfuehren(offen.get("regel", {}).get(jid, d["anforderungen"]), bekannt,
                                                  weitere), covered, cfg["fit"])
            state.update_detail(jid, job.fit_anforderungen, job.fit, eck)
            out["vorschlaege"].update(list(weitere))
            out["aktualisiert"] += 1
            fertig.add(jid)
        state.set_meta(META, json.dumps(sorted(fertig)))
        state.set_meta(STAPEL, "{}")
        out["stapel"] = f"abgeholt ({len(antworten)})"
    ba = BundesagenturSource({**cfg["sources"]["bundesagentur"], "suchbegriffe": []}, fetcher)
    anfragen, regel = {}, {}
    for d in state.job_details(limit=5000):
        if d["id"] in fertig:
            continue
        if limit is not None and out["geprueft"] >= limit:
            break
        out["geprueft"] += 1
        text = anzeigentext(d["url"] or "", fetcher, ba)
        if len(text) < k["min_text"]:
            out["ohne_text"] += 1
            fertig.add(d["id"])
            continue
        job = Job(title=d["title"], company=d["company"], url=d["url"], source="", description=text)
        anfragen[d["id"]] = fit.ki_prompt(job)
        regel[d["id"]] = fit.requirements(f"{job.title}\n{text}", begriffe, cfg["fit"]["optional_marker"])
    state.set_meta(META, json.dumps(sorted(fertig)))
    if anfragen:
        bid = ki_batch.erstellen(k["model"], anfragen, fit.ki_system(begriffe))
        if bid:
            state.set_meta(STAPEL, json.dumps({"id": bid, "regel": regel}, ensure_ascii=False))
            out["stapel"] = (out["stapel"] + "; " if out["stapel"] else "") + f"{len(anfragen)} abgeschickt"
    return out
