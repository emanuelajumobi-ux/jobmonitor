"""Ablauf eines Laufs: Quellen abfragen, bewerten, deduplizieren, Bericht schreiben und verschicken."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import (antworten, anzeigen_check, drafts, fit, fit_begriffe, fristen, initiativ_liste, llm, mailer,
               nachbewertung, original, quellen_verlauf, suchprofil, tracking, traumjob)
from .cv_data import CvDataError, load_cv_master
from .config import ROOT, load_companies, load_config, modus, save_companies
from .http import Fetcher
from .models import Job, SourceResult, normalize
from .report import InitiativTip, Report
from .scoring import evaluate_profiles
from .sources.adzuna import AdzunaSource
from .sources.arbeitnow import ArbeitnowSource
from .sources.ats import jsonld
from .sources.bundesagentur import BundesagenturSource
from .sources.companies import CompaniesSource
from .sources.hsnr import HsnrSource
from .sources.mail_alerts import MailAlertsSource
from .sources.stellenwerk import StellenwerkSource
from .state import State

log = logging.getLogger(__name__)


@dataclass
class Options:
    force: bool = False
    dry_run: bool = False
    no_mail: bool = False
    only: str | None = None
    root: Path = ROOT


def dedupe(jobs: list[Job]) -> list[Job]:
    best: dict[str, Job] = {}
    for job in jobs:
        prev = best.get(job.key)
        if prev is None:
            best[job.key] = job
            continue
        keep, other = (job, prev) if job.score > prev.score else (prev, job)
        if other.source not in keep.source:
            keep.source = f"{keep.source} + {other.source}"
        best[job.key] = keep
    return sorted(best.values(), key=lambda j: (-j.score, j.company.lower()))


def antworten_suchen(apps: list[dict], companies_doc, cfg: dict, today, opts: Options) -> list:
    """Antworten von Firmen auf offene Bewerbungen im Postfach (antworten.py). Nur neue, Fehler sind still,
    im Ruhemodus wird das Postfach nicht gelesen."""
    a_cfg = cfg.get("antworten") or {}
    if not a_cfg.get("enabled", True) or modus(cfg) != "aktiv" or (opts.only and opts.only != "mail_alerts"):
        return []
    alert_cfg = cfg["sources"]["mail_alerts"]
    bekannt = {a.schluessel for a in antworten.laden(opts.root)}
    einordnen = None
    if a_cfg.get("ki") and llm.verfuegbar():
        rest = [int(a_cfg.get("ki_max_je_lauf", 10))]

        def einordnen(antwort, mail):
            if rest[0] > 0:
                rest[0] -= 1
                antworten.ki_einordnen(antwort, mail, a_cfg.get("ki_model", "claude-haiku-5-5"))
    try:
        gefunden = antworten.postfach(apps, companies_doc, {**alert_cfg, **a_cfg}, today, alert_cfg["absender"],
                                      frozenset(bekannt), einordnen)
    except Exception:   # Postfach nicht erreichbar: der Lauf geht weiter
        log.exception("Antworten im Postfach nicht geprüft")
        return []
    neu = [a for a in gefunden if a.schluessel not in bekannt]
    if neu:
        log.info("%d neue Antwort(en) von Firmen erkannt", len(neu))
    return neu


def originale_suchen(evaluated: list[Job], results: list[SourceResult], sources, src_cfg: dict, fetcher: Fetcher,
                     cfg: dict, profile) -> list[Job]:
    """Stellen aus Alert-Mails durch die Originalanzeige ersetzen (Firmenseite oder BA, siehe original.py) und neu
    bewerten – mit dem vollen Text stimmen Score, Fit und Frist. Ergebnis steht bei der Quelle im Bericht."""
    alerts = [j for j in evaluated if j.source == MailAlertsSource.name]
    alert_result = next((r for r in results if r.name == MailAlertsSource.name), None)
    if not alerts or alert_result is None:
        return evaluated
    andere = [j for r in results if r is not alert_result for j in r.jobs]
    ba = next((src for key, src in sources if key == "bundesagentur"), None)
    if ba is None and src_cfg["bundesagentur"]["enabled"]:
        ba = BundesagenturSource(src_cfg["bundesagentur"], fetcher)
    ersetzt, gefunden = original.ergaenzen(alerts, andere, ba, src_cfg["mail_alerts"].get("originalsuche") or {})
    neu = [(evaluate_profiles(j, cfg, profile) or a) if j is not a else a for a, j in zip(alerts, ersetzt)]
    alert_result.notes.append(f"Originalanzeige zu {gefunden} von {len(alerts)} Alert-Stelle(n) gefunden "
                              f"(Firmenseite oder Bundesagentur)")
    return [j for j in evaluated if j.source != MailAlertsSource.name] + neu


def add_warnings(jobs: list[Job], companies_doc) -> None:
    """Hängt den Warnhinweis aus companies.yaml an Stellen passender Firmen (z. B. Konzern des eigenen Arbeitgebers)."""
    rules = [([normalize(n) for n in e.get("match_namen") or []], e["warnhinweis"])
             for e in companies_doc.get("firmen") or [] if e.get("warnhinweis")]
    for job in jobs:
        company = normalize(job.company)
        for names, hint in rules:
            if any(n and n in company for n in names) and hint not in job.flags:
                job.flags.append(f"⚠ {hint}")


def apply_llm_scores(jobs: list[Job], llm_cfg: dict, limit: int = 25) -> None:
    """Mischt eine KI-Einschätzung in den regelbasierten Score (nur wenn in config.yaml aktiviert)."""
    weight = llm_cfg["gewicht"]
    for job in jobs[:limit]:
        ki = llm.score_job(llm_cfg["model"], llm_cfg["profil"], job.title, job.company, job.description)
        if ki is not None:
            job.score = round((1 - weight) * job.score + weight * ki)
            job.flags.append(f"KI-Einschätzung {ki}")
    jobs.sort(key=lambda j: (-j.score, j.company.lower()))


def initiativ_tips(companies_doc, src: CompaniesSource | None, matched_companies: set[str], cfg: dict) -> list[InitiativTip]:
    """Vorschläge für Entwürfe und applications.csv: ohne Firmen mit gerade passenden Stellen, höchstens
    initiativ.max_vorschlaege."""
    return [tip for tip, hat in initiativ_liste.kandidaten(companies_doc, src, matched_companies, cfg)
            if not hat][: cfg["initiativ"]["max_vorschlaege"]]


def ki_nutzung_merken(state: State, today) -> None:
    """KI-Verbrauch dieses Laufs je Monat in state/seen.sqlite (meta „ki_nutzung“) – die App zeigt ihn unter
    Einstellungen → KI, getrennt von deinen eigenen Aufrufen."""
    lauf = dict(llm.NUTZUNG)
    if not lauf["aufrufe"]:
        return
    try:
        daten = json.loads(state.get_meta("ki_nutzung") or "{}")
    except ValueError:
        daten = {}
    monat = daten.setdefault(today.strftime("%Y-%m"), {})
    for k, v in lauf.items():
        monat[k] = monat.get(k, 0) + v
    daten["letzter_lauf"] = {"datum": today.isoformat(), **lauf}
    state.set_meta("ki_nutzung", json.dumps(daten, sort_keys=True))
    log.info("KI-Nutzung dieses Laufs: %d Aufrufe, %d Eingabe- (davon %d aus dem Cache), %d Ausgabe-Tokens",
             lauf["aufrufe"], lauf["eingabe"] + lauf["cache_lesen"] + lauf["cache_schreiben"], lauf["cache_lesen"],
             lauf["ausgabe"])


def ki_nachholen(state: State, cv: dict | None, cfg: dict, fetcher: Fetcher, ki_ids: set) -> None:
    """Stellen, die (noch) keine KI-Bewertung haben – z. B. aus einem Lauf ohne KI-Anmeldung oder weil die KI nicht
    antwortete –, im nächsten Lauf nachholen. Höchstens fit.ki.nachholen_je_lauf je Lauf, Fehler sind still."""
    k = {**fit.KI_DEFAULTS, **(cfg["fit"].get("ki") or {})}
    if not (cfg["fit"]["enabled"] and k["enabled"] and cv and llm.verfuegbar()):
        return
    # Fit-Begriffe geändert (z. B. in der App ergänzt)? Dann gespeicherte Stellen nach und nach neu bewerten.
    stand = hashlib.sha256(json.dumps([fit.KI_VERSION, sorted(cfg["fit"]["begriffe"])],
                                      ensure_ascii=False).encode()).hexdigest()[:16]
    alt = state.get_meta("fit_begriffe_stand")
    if alt and alt != stand:
        state.set_meta(nachbewertung.META, "[]")
        log.info("Fit-Begriffe geändert – gespeicherte Stellen werden nach und nach neu bewertet")
    state.set_meta("fit_begriffe_stand", stand)
    nachbewertung.vermerken(state, ki_ids)
    try:
        out = nachbewertung.nachbewerten(state, cv, cfg, fetcher, limit=int(k["nachholen_je_lauf"]))
    except Exception:
        log.exception("KI-Bewertung älterer Stellen nicht nachgeholt")
        return
    fit_begriffe.merken(state, out["vorschlaege"])
    if out["geprueft"]:
        log.info("KI-Bewertung nachgeholt: %d von %d Stelle(n)", out["aktualisiert"], out["geprueft"])


def run(opts: Options) -> int:
    cfg = load_config(opts.root / "config.yaml")
    llm.einstellen(cfg)                 # KI-Anbieter und Modelle (ki_anbieter.py)
    companies_doc = load_companies(opts.root / "companies.yaml")
    now = datetime.now(ZoneInfo(cfg["run"]["timezone"]))
    today = now.date()
    state_path = opts.root / "state" / "seen.sqlite"
    if opts.dry_run:   # Probelauf: Kopie, damit auch Schema-Änderungen die Datei der Pipeline nicht anfassen
        tmp = Path(tempfile.mkdtemp(prefix="jobmonitor-")) / "seen.sqlite"
        if state_path.exists():
            shutil.copy(state_path, tmp)
        state_path = tmp
    state = State(state_path)

    suchmodus = modus(cfg)
    if suchmodus == "aus" and not opts.force:
        log.info("Suche angehalten (config.yaml → run.modus: aus), überspringe.")
        state.close()
        return 0
    abstand = cfg["run"].get("ruhe_tage", 7) if suchmodus == "ruhe" else cfg["run"]["interval_days"]
    if not opts.force and not state.is_due(now, abstand, cfg["run"]["tolerance_hours"]):
        log.info("Letzter erfolgreicher Lauf %s – noch keine %s Tage her, überspringe.", state.last_success(), abstand)
        state.close()
        return 0

    profile = suchprofil.aktive(cfg)
    if not profile:
        log.error("Kein Suchprofil aktiv (config.yaml → profile: … enabled: true).")
        state.close()
        return 1
    log.info("Suchprofile: %s", ", ".join(p.name for p in profile))
    # Bei mehreren Profilen steht der Profilname an der Quelle (Status im Bericht)
    label = (lambda p: p.name) if len(profile) > 1 else (lambda p: "")

    h = cfg["http"]
    fetcher = Fetcher(h["user_agent"], h["min_delay_seconds"], h["timeout_seconds"], h["retries"])
    src_cfg = cfg["sources"]
    role_pattern = jsonld.role_re([jsonld.ROLE_SLUG.pattern if p.key == suchprofil.DEFAULT_KEY else p.slug_re().pattern
                                   for p in profile])
    ats_terms = list(dict.fromkeys(t for p in profile for t in p.ats_suchbegriffe))
    company_src = CompaniesSource(companies_doc, src_cfg["companies"], fetcher, today, cfg.get("ats_freigabe"),
                                  role_pattern, ats_terms, state)
    sources = []
    if src_cfg["bundesagentur"]["enabled"]:
        for p in profile:
            if p.begriffe("bundesagentur"):
                ba_cfg = {**src_cfg["bundesagentur"], "suchbegriffe": p.begriffe("bundesagentur"),
                          "angebotsart": p.angebotsart}
                sources.append(("bundesagentur", BundesagenturSource(ba_cfg, fetcher, label(p))))
    hsnr_active = any(h.get("quelle") == "hsnr" and h.get("aktiv") for h in companies_doc.get("hochschulen") or [])
    if src_cfg["hsnr"]["enabled"] and hsnr_active:
        sources.append(("hsnr", HsnrSource(src_cfg["hsnr"], suchprofil.alle_fach(cfg), fetcher, state, today)))
    stellenwerk_portale = [h for h in companies_doc.get("hochschulen") or []
                           if h.get("quelle") == "stellenwerk" and h.get("aktiv")]
    if src_cfg["stellenwerk"]["enabled"] and stellenwerk_portale:
        for p in profile:
            if p.begriffe("stellenwerk"):
                sw_cfg = {**src_cfg["stellenwerk"], "suchbegriffe": p.begriffe("stellenwerk")}
                sources.append(("stellenwerk", StellenwerkSource(stellenwerk_portale, sw_cfg, fetcher, state, today,
                                                                 label(p))))
    if (src_cfg.get("arbeitnow") or {}).get("enabled"):
        sources.append(("arbeitnow", ArbeitnowSource(src_cfg["arbeitnow"], fetcher)))
    if (src_cfg.get("adzuna") or {}).get("enabled"):
        for p in profile:   # Suchbegriffe wie bei der Bundesagentur (die ersten max_begriffe je Profil)
            if p.begriffe("bundesagentur"):
                sources.append(("adzuna", AdzunaSource(src_cfg["adzuna"], fetcher, p.begriffe("bundesagentur"),
                                                       label(p))))
    if src_cfg["companies"]["enabled"]:
        sources.append(("companies", company_src))
    if src_cfg["mail_alerts"]["enabled"]:
        rollen = list(dict.fromkeys(r for p in profile for r in p.rollen))
        sources.append(("mail_alerts", MailAlertsSource(src_cfg["mail_alerts"], rollen, today,
                                                        src_cfg["bundesagentur"]["wo"], cfg["ort"].get("fahrzeiten"))))

    results: list[SourceResult] = []
    for key, source in sources:
        if opts.only and opts.only != key:
            continue
        log.info("Quelle: %s", source.name)
        try:
            results.append(source.fetch())
        except Exception as exc:
            log.exception("Quelle %s ausgefallen", source.name)
            results.append(SourceResult(source.name, errors=[f"Ausfall: {exc}"]))
        log.info("  %d Rohtreffer, %d Fehler", len(results[-1].jobs), len(results[-1].errors))

    quellen_verlauf.record(state, today.isoformat(), results, company_src.outcomes)
    hochschul_hinweise = [f"{h['name']}: {h.get('notizen') or 'nicht automatisch angebunden'} – {h['karriereseite_url']}"
                          for h in companies_doc.get("hochschulen") or [] if not h.get("aktiv")]
    if hochschul_hinweise and not opts.only:
        results.append(SourceResult("Weitere Hochschul-Börsen", manual_check=hochschul_hinweise))

    beobachtet = {("quelle", src.name) for _, src in sources} | {
        ("firma", e["name"]) for e in companies_doc.get("firmen") or [] if e.get("aktiv") is not False}
    gesundheit = quellen_verlauf.warnungen(state.source_history(quellen_verlauf.limits(cfg)["verlauf"]), cfg,
                                           beobachtet)
    for w in gesundheit:
        log.warning("Quelle beobachten: %s", w)

    evaluated = [m for r in results for j in r.jobs if (m := evaluate_profiles(j, cfg, profile))]
    evaluated = originale_suchen(evaluated, results, sources, src_cfg, fetcher, cfg, profile)
    matched = dedupe(evaluated)
    matched_companies = {normalize(j.company) for j in matched}
    add_warnings(matched, companies_doc)
    new_jobs = [j for j in matched if state.is_new(j)]
    ba_source = next((src for key, src in sources if key == "bundesagentur"), None)
    if cfg["fit"]["enabled"] and ba_source is not None and (not opts.only or opts.only == "bundesagentur"):
        n = ba_source.add_details(new_jobs)
        if n:
            log.info("BA: %d Anzeigentext(e) für das Fit-Rating nachgeladen", n)
    fit_hinweis, cv, ki_ids = "", None, set()
    if cfg["fit"]["enabled"]:
        try:
            cv, origin = load_cv_master(opts.root)
            if cv is None:
                fit_hinweis = "Fit-Rating aus: keine cv_master.yaml (bzw. Secret CV_MASTER_YAML) gefunden."
            else:
                fit.rate_all(new_jobs, cv, cfg["fit"])
                log.info("Fit-Rating mit %s", origin)
                vorschlaege = fit.mit_ki(new_jobs, cv, cfg["fit"], gelesen=ki_ids)
                if vorschlaege:
                    liste = ", ".join(f"{b} ({n}×)" for b, n in vorschlaege.most_common(8))
                    fit_hinweis = (f"KI fand Anforderungen ohne Fit-Begriff: {liste} – in der App unter "
                                   f"Lücken-Auswertung → Fit-Begriffe mit einem Klick übernehmen.")
                    if not opts.dry_run:
                        fit_begriffe.merken(state, vorschlaege)
        except CvDataError as exc:
            fit_hinweis = f"⚠ Fit-Rating aus: {exc}"
            log.error("Fit-Rating aus: %s", exc)
    llm_cfg = cfg["filter"]["llm"]
    if llm_cfg["enabled"] and llm.verfuegbar():
        apply_llm_scores(new_jobs, llm_cfg)
    for job in new_jobs:
        frist = fristen.find(f"{job.title}\n{job.description}", today)
        job.frist = frist.isoformat() if frist else None
        job.traum, job.traum_grund = traumjob.classify(job.title, job.description, cfg.get("traumprofil") or {})
    tips = initiativ_tips(companies_doc, company_src, matched_companies, cfg)
    initiativ_alle = initiativ_liste.kandidaten(companies_doc, company_src, matched_companies, cfg)

    apps_path = opts.root / "applications.csv"
    apps = tracking.load(apps_path)
    if cfg["tracking"].get("auto_eintragen", True):   # aus: nur was du in der Oberfläche merkst, landet dort
        for job in new_jobs:
            if job.score >= cfg["tracking"]["neu_ab_score"]:
                tracking.add_if_missing(apps, job.company, "Stelle", job.url, today,
                                        f"{job.title} (Score {job.score})")
        for tip in tips:
            tracking.add_if_missing(apps, tip.firma, "Initiativ", tip.url, today)

    neue_antworten = antworten_suchen(apps, companies_doc, cfg, today, opts)
    offline_neu = []
    if ((cfg.get("anzeigen_check") or {}).get("enabled", True) and suchmodus == "aktiv" and not opts.only
            and not opts.dry_run):
        offline_neu = anzeigen_check.pruefen(opts.root, apps, fetcher, today, cfg.get("anzeigen_check") or {})
    offline_rows = [r for r in apps if r.get("link") in set(offline_neu)]
    beantwortet = antworten.beantwortet(antworten.laden(opts.root) + neue_antworten)
    report = Report(today, results, new_jobs, tips,
                    tracking.follow_ups(apps, today, cfg["tracking"]["nachfassen_nach_tagen"], beantwortet), fit_hinweis,
                    (cfg.get("traumprofil") or {}).get("name", "Traumprofil"),
                    {p.key: p.name for p in profile}, gesundheit, neue_antworten, offline_rows,
                    [tip for tip, _ in initiativ_alle])
    text = report.render()

    if cfg["entwuerfe"]["enabled"] and tips and not opts.dry_run:
        by_name = {e["name"]: e for e in companies_doc.get("firmen") or []}
        ziel = suchprofil.get(cfg, cfg["entwuerfe"].get("profil"))
        written = drafts.write_drafts([by_name[t.firma] for t in tips if t.firma in by_name], opts.root,
                                      {**cfg["entwuerfe"], "model": llm_cfg["model"], "zielrolle": ziel.zielrolle,
                                       "absicht": ziel.absicht, "ausblick": ziel.ausblick}, today)
        if written:
            log.info("%d Anschreiben-Entwürfe in drafts/ angelegt", len(written))

    if opts.dry_run:
        print(text)
        state.db.rollback()
        state.close()
        return 0

    reports_dir = opts.root / "reports"
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / f"{today.isoformat()}.md").write_text(text, encoding="utf-8")
    log.info("Bericht: reports/%s.md (%d neue Stellen)", today.isoformat(), len(new_jobs))
    tracking.save(apps_path, apps)
    antworten.speichern(opts.root, neue_antworten)
    save_companies(companies_doc, opts.root / "companies.yaml")
    for job in new_jobs:
        state.mark_reported(job, today.isoformat())
        state.save_job_detail(job, today.isoformat())
    ki_nachholen(state, cv, cfg, fetcher, ki_ids)
    ki_nutzung_merken(state, today)

    all_failed = bool(results) and all(r.failed for r in results)
    if not all_failed:
        state.set_last_success(now)
    state.close()

    # mail.enabled (Pipeline) oder „Bericht täglich mailen“ in der App (mailzugang.py setzt JOBMONITOR_BERICHT_MAIL)
    if (cfg["mail"]["enabled"] or os.environ.get("JOBMONITOR_BERICHT_MAIL")) and not opts.no_mail:
        if mailer.mail_configured():
            try:
                mailer.send_report(report.subject(cfg["mail"]["subject_prefix"]), text)
            except Exception:
                log.exception("Mailversand fehlgeschlagen (Bericht liegt trotzdem im Repo)")
                return 1
        else:
            log.warning("Mail nicht konfiguriert (SMTP_USER/SMTP_PASSWORD/MAIL_TO fehlen) – nur Datei geschrieben.")
    return 1 if all_failed else 0
