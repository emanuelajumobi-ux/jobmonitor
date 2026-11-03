"""Tägliche Mitteilung auf dem Mac, wenn die Pipeline neue Stellen gefunden hat (statt Bericht per Mail).

Ein launchd-Auftrag (~/Library/LaunchAgents) startet einmal am Tag `python -m jobmonitor benachrichtigen`. Das holt den
Stand der Pipeline von GitHub (nur `git fetch`, die Arbeitskopie bleibt unberührt), liest die neuen Stellen aus
state/seen.sqlite und zeigt eine Mitteilung von Job-Monitor; ein Klick öffnet die App. Ohne neue Stellen kommt nichts.
Schläft der Mac zur Uhrzeit, holt macOS den Auftrag beim Aufwachen nach. Ein- und ausschalten: Einstellungen.
"""
from __future__ import annotations

import json
import logging
import os
import plistlib
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from .config import modus

log = logging.getLogger(__name__)
LABEL = "de.local.jobmonitor.benachrichtigung"
AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOGFILE = Path.home() / "Library" / "Logs" / "job-monitor.log"
STAND = ".gui_benachrichtigung.json"     # zuletzt gemeldeter Tag (lokal, gitignored)
DB = "state/seen.sqlite"
STANDARD_ZEIT = "08:30"                  # Pipeline läuft 06:17/07:17 Uhr und braucht einige Minuten
ANTWORTEN = "state/antworten.json"
TOP_FIT_AB = 75                          # eigene Mitteilung je Stelle ab diesem Fit (config: benachrichtigung)
MAX_EINZELN = 3                          # höchstens so viele Einzel-Mitteilungen je Art


class BenachrichtigungError(Exception):
    pass


# --- Ein/aus über launchd ---
def plist(root: Path, stunde: int, minute: int, python: str = sys.executable) -> dict:
    return {"Label": LABEL, "ProgramArguments": [python, "-m", "jobmonitor", "benachrichtigen"],
            "WorkingDirectory": str(root), "StartCalendarInterval": {"Hour": stunde, "Minute": minute},
            "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
            "StandardOutPath": str(LOGFILE), "StandardErrorPath": str(LOGFILE)}


def _zeit(text: str) -> tuple[int, int]:
    try:
        stunde, minute = (int(x) for x in (text or STANDARD_ZEIT).split(":"))
    except ValueError:
        raise BenachrichtigungError("Uhrzeit bitte als HH:MM angeben.") from None
    if not (0 <= stunde < 24 and 0 <= minute < 60):
        raise BenachrichtigungError("Uhrzeit bitte als HH:MM angeben.")
    return stunde, minute


def status(agent: Path = AGENT) -> dict:
    """{"an": bool, "zeit": "HH:MM"} aus dem installierten launchd-Auftrag."""
    if not agent.exists():
        return {"an": False, "zeit": STANDARD_ZEIT}
    try:
        cal = plistlib.loads(agent.read_bytes()).get("StartCalendarInterval") or {}
        return {"an": True, "zeit": f"{cal.get('Hour', 8):02d}:{cal.get('Minute', 30):02d}"}
    except Exception:
        return {"an": True, "zeit": STANDARD_ZEIT}


def _launchctl(*args: str, run=subprocess.run):
    return run(["launchctl", *args], capture_output=True, text=True)


def einschalten(root: Path, zeit: str, agent: Path = AGENT, run=subprocess.run) -> str:
    stunde, minute = _zeit(zeit)
    python = str(root / ".venv" / "bin" / "python") if (root / ".venv" / "bin" / "python").exists() else sys.executable
    agent.parent.mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    _launchctl("bootout", f"{domain}/{LABEL}", run=run)          # alte Uhrzeit ersetzen
    agent.write_bytes(plistlib.dumps(plist(root, stunde, minute, python)))
    proc = _launchctl("bootstrap", domain, str(agent), run=run)
    if proc.returncode != 0:
        raise BenachrichtigungError(f"launchctl: {(proc.stderr or proc.stdout).strip()}")
    return f"Tägliche Mitteilung um {stunde:02d}:{minute:02d} Uhr eingeschaltet."


def ausschalten(agent: Path = AGENT, run=subprocess.run) -> str:
    _launchctl("bootout", f"gui/{os.getuid()}/{LABEL}", run=run)
    agent.unlink(missing_ok=True)
    return "Tägliche Mitteilung ausgeschaltet."


# --- Neue Stellen ---
def _db_von_github(root: Path, ziel: Path) -> bool:
    """state/seen.sqlite und state/antworten.json so, wie die Pipeline sie zuletzt gepusht hat (nur git fetch, die
    Arbeitskopie bleibt unberührt). `ziel`: Pfad für die Datenbank; antworten.json landet daneben."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    fetch = subprocess.run(["git", "fetch", "-q", "origin"], cwd=root, capture_output=True, env=env, timeout=60)
    if fetch.returncode != 0:
        log.info("git fetch fehlgeschlagen: %s", fetch.stderr.decode(errors="replace").strip())
    show = subprocess.run(["git", "show", f"@{{u}}:{DB}"], cwd=root, capture_output=True, timeout=30)
    if show.returncode != 0 or not show.stdout:
        return False
    ziel.write_bytes(show.stdout)
    antw = subprocess.run(["git", "show", f"@{{u}}:{ANTWORTEN}"], cwd=root, capture_output=True, timeout=30)
    if antw.returncode == 0:
        (ziel.parent / "antworten.json").write_bytes(antw.stdout)
    return True


def neue_stellen(db: Path, seit: str) -> list[dict]:
    """Stellen, die die Pipeline nach dem Tag `seit` (ISO) zum ersten Mal gemeldet hat, beste zuerst."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT title, company, fit, first_seen, anforderungen_json FROM job_detail "
                           "WHERE first_seen > ? ORDER BY first_seen DESC, fit IS NULL, fit DESC", (seit,)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return [{"title": t, "company": c, "fit": f, "tag": d, "anforderungen": _liste(a)} for t, c, f, d, a in rows]


def _liste(text) -> list[str]:
    try:
        data = json.loads(text or "[]")
    except ValueError:
        return []
    return list(data) if isinstance(data, (list, dict)) else []


def top_stellen(stellen: list[dict], cfg: dict) -> list[tuple[str, str]]:
    """(Titel, Text) je Stelle mit hohem Fit oder im Traumprofil – höchstens MAX_EINZELN, beste zuerst."""
    from . import traumjob
    ab = (cfg.get("benachrichtigung") or {}).get("top_fit_ab", TOP_FIT_AB)
    traum_cfg = cfg.get("traumprofil") or {}
    out = []
    for s in sorted(stellen, key=lambda s: -(s["fit"] or 0)):
        traum, _ = traumjob.classify(s["title"], " ".join(s["anforderungen"]), traum_cfg)
        fit = f" · Fit {s['fit']} %" if s["fit"] is not None else ""
        if traum:
            out.append((f"{traum_cfg.get('name', 'Traumprofil')}{fit}", f"{s['title']} – {s['company']}"))
        elif (s["fit"] or 0) >= ab:
            out.append((f"Passt sehr gut{fit}", f"{s['title']} – {s['company']}"))
    return out[:MAX_EINZELN]


def neue_antworten(pfad: Path, gesehen: set[str]) -> list[dict]:
    """Antworten von Firmen (antworten.py), die noch nicht gemeldet wurden."""
    try:
        data = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [a for a in data if isinstance(a, dict) and f"{a.get('link')}|{a.get('datum')}|{a.get('art')}" not in gesehen]


def text(stellen: list[dict]) -> tuple[str, str]:
    n = len(stellen)
    beste = stellen[0]
    fit = f" · Fit {beste['fit']} %" if beste["fit"] is not None else ""
    titel = "1 neue Stelle" if n == 1 else f"{n} neue Stellen"
    return titel, f"{beste['title']} – {beste['company']}{fit}"


def _stand(root: Path) -> dict:
    try:
        return json.loads((root / STAND).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


WINDOWS_SKRIPT = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                  "$n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; "
                  "$n.Visible = $true; $n.ShowBalloonTip(10000, $env:JM_TITEL, $env:JM_TEXT, 'Info'); "
                  "Start-Sleep -Seconds 10; $n.Dispose()")


def neue_im_bericht(root: Path, tag: str) -> int:
    """Anzahl neuer Stellen im Bericht des Tages (Summe aller „## Neue Stellen … (n)“)."""
    import re
    try:
        text = (root / "reports" / f"{tag}.md").read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(int(n) for n in re.findall(r"^## Neue Stellen[^\n(]*\((\d+)\)", text, re.M))


def senden(root: Path, titel: str, nachricht: str, run=subprocess.run) -> str:
    """Über Job-Monitor.app (Name, Icon, Klick öffnet die App); ohne übersetztes Hauptprogramm über AppleScript.
    `open -n -g -W`: eigene Instanz im Hintergrund, über LaunchServices (nur so darf sie Mitteilungen senden)."""
    if sys.platform.startswith("win"):   # Windows: Hinweis im Infobereich über PowerShell (ohne Zusatzmodule)
        env = {**os.environ, "JM_TITEL": f"Job-Monitor: {titel}"[:63], "JM_TEXT": nachricht[:255]}
        run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", WINDOWS_SKRIPT], env=env,
            capture_output=True, timeout=30)
        return "windows"
    app = root / "Job-Monitor.app"
    if _swift_app(app):
        with tempfile.NamedTemporaryFile("r", suffix=".txt") as err:
            try:
                run(["open", "-n", "-g", "-W", "--stderr", err.name, "-a", str(app), "--args", "--notify", titel,
                     nachricht], capture_output=True, timeout=150)
                meldung = Path(err.name).read_text(encoding="utf-8", errors="replace")
            except (OSError, subprocess.SubprocessError) as exc:   # AppleScript übernimmt
                log.info("Mitteilung über die App nicht möglich: %s", exc)
                meldung = "FEHLER"
        if "NICHT_ERLAUBT" in meldung or "UNErrorDomain error 1" in meldung:
            raise BenachrichtigungError("macOS erlaubt Job-Monitor keine Mitteilungen. Einschalten unter "
                                        "Systemeinstellungen → Mitteilungen → Job-Monitor.")
        if not meldung.strip():
            return "app"
    q = lambda t: json.dumps(t, ensure_ascii=False)   # noqa: E731  AppleScript kennt keine \\u-Escapes
    skript = f"display notification {q(nachricht)} with title {q('Job-Monitor')} subtitle {q(titel)}"
    run(["osascript", "-e", skript], capture_output=True, timeout=30)
    return "osascript"


def _swift_app(app: Path) -> bool:
    """Hauptprogramm ist das übersetzte launcher.swift (kein Skript) → kann Mitteilungen senden."""
    exe = app / "Contents" / "MacOS" / "Job-Monitor"
    try:
        return exe.read_bytes()[:2] != b"#!"
    except OSError:
        return False


def pipeline_meldung(laeufe: list[dict], stand: dict, heute: str, cfg: dict) -> tuple[str, str, dict] | None:
    """(Titel, Text, neuer Stand) einer Mitteilung über die Pipeline: letzter Lauf fehlgeschlagen (je Lauf einmal)
    oder seit Tagen kein Lauf (höchstens alle 3 Tage). None, wenn alles in Ordnung ist."""
    from datetime import date
    from .config import modus
    fertig = [r for r in laeufe if r.get("status") == "completed"]
    if not fertig or modus(cfg) == "aus":
        return None
    letzter = fertig[0]
    zeit = str(letzter.get("createdAt", ""))
    if letzter.get("conclusion") == "failure" and letzter.get("url") != stand.get("fehler"):
        return ("Job-Monitor: Lauf fehlgeschlagen",
                f"Der Lauf vom {zeit[8:10]}.{zeit[5:7]}. ist fehlgeschlagen – Details in Einstellungen → Pipeline.",
                {"fehler": letzter.get("url")})
    run_cfg = cfg.get("run") or {}
    erlaubt = (int(run_cfg.get("ruhe_tage", 7)) if modus(cfg) == "ruhe" else int(run_cfg.get("interval_days", 1))) + 1
    try:
        tage = (date.fromisoformat(heute) - date.fromisoformat(zeit[:10])).days
        zuletzt = date.fromisoformat(stand.get("stillstand") or "2000-01-01")
    except ValueError:
        return None
    if tage > erlaubt and (date.fromisoformat(heute) - zuletzt).days >= 3:
        return ("Job-Monitor: keine Suche mehr",
                f"Die Pipeline ist seit {tage} Tagen nicht gelaufen – in Einstellungen → Pipeline nachsehen.",
                {"stillstand": heute})
    return None


def pruefen(root: Path, heute: str, run=subprocess.run, db_holen=_db_von_github, cfg: dict | None = None,
            laeufe=None) -> str:
    """Einmal am Tag (launchd): Antworten von Firmen und Top-Stellen einzeln, dazu eine Zusammenfassung.
    laeufe(root) → (Läufe, Fehler) wie gui_wartung.pipeline_laeufe: meldet zusätzlich fehlgeschlagene Läufe
    (auch im Ruhemodus – das sind die Mitteilungen, die man nicht verpassen sollte)."""
    from .antworten import LABEL
    if cfg is None:
        from .config import load_config
        cfg = load_config(root / "config.yaml") if (root / "config.yaml").exists() else {}
    stand = _stand(root)
    pipeline = {k: stand[k] for k in ("fehler", "stillstand") if k in stand}
    meldung = pipeline_meldung(laeufe(root)[0], pipeline, heute, cfg) if laeufe else None
    if meldung:
        senden(root, meldung[0], meldung[1], run=run)
        pipeline.update(meldung[2])
    seit = stand.get("bis") or _gestern(heute)    # beim ersten Mal nur, was seit gestern dazukam
    gesehen = set(stand.get("antworten") or [])
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "seen.sqlite"
        antw = Path(tmp) / "antworten.json"
        if not db_holen(root, db):
            if not (root / DB).exists():
                (root / STAND).write_text(json.dumps({**stand, **pipeline}, ensure_ascii=False), encoding="utf-8")
                return "Kein Stand der Pipeline gefunden."
            db, antw = root / DB, root / ANTWORTEN
        stellen = neue_stellen(db, seit)
        antworten = neue_antworten(antw, gesehen) if stand else []   # beim ersten Mal nichts Altes melden
        alle_antworten = neue_antworten(antw, set())
    gesendet = []
    still = modus(cfg) != "aktiv"   # Ruhemodus/angehalten: nichts senden, Stand aber weiterschieben (kein Stapel danach)
    for a in [] if still else antworten[:MAX_EINZELN]:
        senden(root, f"Antwort von {a.get('firma')}", f"{LABEL.get(a.get('art'), a.get('art'))} · am "
               f"{str(a.get('datum'))[8:10]}.{str(a.get('datum'))[5:7]}. – in Bewerbungen ansehen", run=run)
        gesendet.append("Antwort")
    for titel, nachricht in [] if still else top_stellen(stellen, cfg):
        senden(root, titel, nachricht, run=run)
        gesendet.append(titel)
    if stellen and not still:
        titel, nachricht = text(stellen)
        senden(root, titel, nachricht, run=run)
        gesendet.append(titel)
    neu_stand = {"bis": max([s["tag"] for s in stellen] + [stand.get("bis") or ""]) or seit,
                 "antworten": sorted(f"{a.get('link')}|{a.get('datum')}|{a.get('art')}" for a in alle_antworten),
                 **pipeline}
    (root / STAND).write_text(json.dumps(neu_stand, ensure_ascii=False), encoding="utf-8")
    if still:
        return "Ruhemodus: keine Mitteilungen" + (f" außer „{meldung[0]}“." if meldung else ".")
    if meldung:
        gesendet.insert(0, meldung[0])
    if not gesendet:
        return "Keine neuen Stellen und keine Antworten."
    return f"{len(gesendet)} Mitteilung(en) gesendet: {', '.join(gesendet)}"


def _gestern(heute: str) -> str:
    from datetime import date, timedelta
    return (date.fromisoformat(heute) - timedelta(days=1)).isoformat()
