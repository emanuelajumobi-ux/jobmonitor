"""CLI: python -m jobmonitor run [--force] [--dry-run] [--no-mail] [--only bundesagentur|hsnr|companies]"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from .config import ROOT
from .runner import Options, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobmonitor")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="Quellen abfragen und Bericht erzeugen")
    p_run.add_argument("--mitteilung", action="store_true",
                       help="danach Mitteilung bei neuen Stellen (lokaler Zeitplan)")
    p_run.add_argument("--force", action="store_true", help="3-Tage-Regel ignorieren")
    p_run.add_argument("--dry-run", action="store_true", help="nichts speichern, Bericht nur ausgeben")
    p_run.add_argument("--no-mail", action="store_true", help="keine Mail verschicken")
    p_run.add_argument("--only", choices=["bundesagentur", "hsnr", "stellenwerk", "arbeitnow", "adzuna", "companies",
                                          "mail_alerts"])
    p_run.add_argument("-v", "--verbose", action="store_true")
    p_cv = sub.add_parser("cv", help="Lebenslauf lokal als LaTeX/PDF bauen (make cv)")
    p_cv_stelle = p_cv.add_mutually_exclusive_group()
    p_cv_stelle.add_argument("--job", help="Stellen-ID aus dem Bericht für einen zugeschnittenen Lebenslauf")
    p_cv_stelle.add_argument("--stelle", help="Datei mit dem Anzeigentext einer selbst gefundenen Stelle")
    p_cv_stelle.add_argument("--url", help="Link zu einer selbst gefundenen Stelle (Firmen-Karriereseite)")
    p_cv.add_argument("--firma", help="Firmenname (sonst aus der Anzeige bzw. dem Dateinamen)")
    p_cv.add_argument("--link", help="Link zur Anzeige für applications.csv (bei --stelle)")
    p_cv.add_argument("--nur-tex", action="store_true", help="nur .tex erzeugen, kein PDF")
    p_cv.add_argument("-v", "--verbose", action="store_true")
    p_gui = sub.add_parser("gui", help="Lokale Oberfläche im Browser (Lebenslauf per Klick)")
    p_gui.add_argument("--port", type=int, default=8790)   # gui.PORT; 8765 gehört AnkiConnect
    p_gui.add_argument("--no-browser", action="store_true", help="Browser nicht automatisch öffnen")
    p_gui.add_argument("-v", "--verbose", action="store_true")
    sub.add_parser("app", help="Job-Monitor.app (Start ohne Terminalfenster) in diesem Ordner erzeugen")
    p_pdf = sub.add_parser("pdf-webkit", help="intern: HTML-Datei mit WebKit als A4-PDF speichern (macOS)")
    p_pdf.add_argument("html")
    p_pdf.add_argument("pdf")
    sub.add_parser("desktop", help="Oberfläche als App-Fenster (wird von Job-Monitor.app gestartet)")
    sub.add_parser("nachbewerten", help="Gespeicherte Stellen einmalig mit KI-Anforderungen nachbewerten")
    sub.add_parser("ki-test", help="Anmeldung an der Claude-API prüfen (ein Mini-Aufruf, z. B. per WIF in Actions)")
    p_note = sub.add_parser("benachrichtigen", help="Mitteilung bei neuen Stellen (täglich per launchd)")
    p_note.add_argument("--test", action="store_true", help="Probe-Mitteilung senden")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # kaputte PDF-Xrefs sind harmlos, aber laut
    load_dotenv(ROOT / ".env")
    if args.cmd == "pdf-webkit":
        from pathlib import Path
        from .pdf_webkit import main as webkit
        return webkit(Path(args.html).resolve(), Path(args.pdf).resolve())
    if args.cmd == "cv":
        return build_cv(args)
    if args.cmd == "ki-test":
        return ki_test()
    if args.cmd == "nachbewerten":
        return nachbewerten()
    if args.cmd == "app":
        from .mac_app import create
        print(f"Erzeugt: {create(ROOT).name} – ins Dock ziehen oder im Finder doppelklicken.")
        return 0
    if args.cmd == "desktop":
        from .desktop import run as run_desktop
        return run_desktop(ROOT)
    if args.cmd == "benachrichtigen":
        from datetime import date

        from . import benachrichtigung as bn
        try:
            if args.test:
                print(bn.senden(ROOT, "Probe", "So sehen Mitteilungen über neue Stellen aus."))
            else:
                from .gui_wartung import pipeline_laeufe
                print(bn.pruefen(ROOT, date.today().isoformat(), laeufe=pipeline_laeufe))
        except bn.BenachrichtigungError as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0
    if args.cmd == "gui":
        from .gui import serve
        return serve(ROOT, args.port, open_browser=not args.no_browser)
    if not os.environ.get("GITHUB_ACTIONS") and not os.environ.get("ANTHROPIC_API_KEY"):
        # Lokaler Lauf (Zeitplan, Probelauf): KI-Schlüssel aus dem macOS-Schlüsselbund, falls hinterlegt
        from . import ki
        if (schluessel := ki.schluessel()):
            os.environ["ANTHROPIC_API_KEY"] = schluessel
    if not os.environ.get("GITHUB_ACTIONS"):
        from . import mailzugang        # Postfach aus dem Assistenten (lokale Läufe ohne .env)
        mailzugang.umgebung_setzen(ROOT)
    ergebnis = run(Options(force=args.force, dry_run=args.dry_run, no_mail=args.no_mail, only=args.only))
    if getattr(args, "mitteilung", False) and not args.dry_run:
        from datetime import date
        from . import benachrichtigung
        n = benachrichtigung.neue_im_bericht(ROOT, date.today().isoformat())
        if n:
            try:
                benachrichtigung.senden(ROOT, f"{n} neue Stelle{'n' if n != 1 else ''}",
                                        "Öffne Job-Monitor, um sie anzusehen.")
            except Exception as exc:   # Mitteilung ist Zusatz, der Lauf zählt
                logging.getLogger(__name__).info("Mitteilung nicht gesendet: %s", exc)
    return ergebnis


def build_cv(args) -> int:
    from .config import load_config
    from .cv_build import CvBuildError, build

    cfg = load_config()
    stelle = None
    if args.stelle or args.url:
        try:
            stelle = eigene_stelle(args, cfg)
        except Exception as exc:   # StelleError, CvDataError: Meldung ohne Traceback
            print(f"Stelle nicht gelesen: {exc}", file=sys.stderr)
            return 1
    hinweise: list = []
    try:
        path = build(ROOT, cfg, args.job, compile_pdf=not args.nur_tex, stelle=stelle, hinweise=hinweise)
    except CvBuildError as exc:
        print(f"Lebenslauf nicht erzeugt: {exc}", file=sys.stderr)
        return 1
    print(f"Fertig: {path.relative_to(ROOT)}")
    print("Prüfung: keine Auffälligkeiten." if not hinweise else "Prüfung:")
    for h in hinweise:
        print(f"  {h}")
    return 0


def eigene_stelle(args, cfg: dict) -> dict:
    """Selbst angegebene Stelle einlesen, Fit ausgeben, in applications.csv eintragen."""
    from pathlib import Path

    from .eigene_stelle import fetcher_from, from_file, from_url, prepare

    if args.url:
        job = from_url(args.url, fetcher_from(cfg), args.firma)
    else:
        job = from_file(Path(args.stelle).expanduser(), args.firma, args.link)
    stelle = prepare(job, ROOT, cfg)
    print(f"{stelle['title']} – {stelle['company']}")
    print(stelle["fit_line"])
    print("In applications.csv eingetragen (Status: neu)." if stelle["eingetragen"]
          else "Steht schon in applications.csv.")
    return stelle


def ki_test() -> int:
    """Ein Mini-Aufruf ohne persönliche Daten: Klappt die Anmeldung (API-Schlüssel oder WIF)?"""
    from . import llm
    if not llm.verfuegbar():
        print("Keine Anmeldung eingerichtet (weder ANTHROPIC_API_KEY noch WIF-Variablen mit OIDC-Token).")
        return 1
    usage: list = []
    antwort = llm._ask("claude-haiku-5-5", 'Antworte nur mit {"ok": true}', max_tokens=200, usage=usage)
    weg = "WIF (Workload Identity Federation)" if llm.foederation() else "API-Schlüssel"
    if llm.json_aus(antwort) != {"ok": True}:
        print(f"Anmeldung per {weg} fehlgeschlagen oder unerwartete Antwort (Details im Log darüber).")
        if llm.foederation():
            print("Merkmale des GitHub-Tokens (damit vergleicht die Regel in der Claude Console):")
            for k, v in llm.token_merkmale().items():
                print(f"  {k}: {v}")
        return 1
    print(f"KI-Verbindung per {weg} in Ordnung ({usage[0][0]} Eingabe-, {usage[0][1]} Ausgabe-Tokens).")
    return 0



def nachbewerten() -> int:
    """Einmalig: gespeicherte Stellen mit KI-Anforderungen neu bewerten (siehe nachbewertung.py)."""
    from . import llm
    from .config import load_config
    from .cv_data import load_cv_master
    from .http import Fetcher
    from .nachbewertung import nachbewerten as lauf
    from .state import State
    if not llm.verfuegbar():
        print("Keine KI-Anmeldung eingerichtet (ANTHROPIC_API_KEY oder WIF).")
        return 1
    cfg = load_config(ROOT / "config.yaml")
    cv, _ = load_cv_master(ROOT)
    if not cv:
        print("Keine cv_master.yaml – ohne Lebenslauf gibt es keinen Fit.")
        return 1
    h = cfg["http"]
    state = State(ROOT / "state" / "seen.sqlite")
    try:
        out = lauf(state, cv, cfg, Fetcher(h["user_agent"], h["min_delay_seconds"], h["timeout_seconds"], h["retries"]))
    finally:
        state.close()
    from . import fit_begriffe
    state = State(ROOT / "state" / "seen.sqlite")
    fit_begriffe.merken(state, out["vorschlaege"])
    state.close()
    print(f"Nachbewertet: {out['aktualisiert']} von {out['geprueft']} Stellen "
          f"({out['ohne_text']} ohne lesbare Anzeige, bleiben wie sie sind).")
    if out["vorschlaege"]:
        print("Anforderungen ohne Fit-Begriff: "
              + ", ".join(f"{b} ({n}×)" for b, n in out["vorschlaege"].most_common(12)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
