"""Seite „Einstellungen“: alles, was sonst ein Terminal-Befehl wäre, per Klick.

- Pipeline auf GitHub: letzte Läufe ansehen, Lauf starten (gh workflow run).
- Probelauf auf diesem Mac: ohne Speichern und ohne Mail (python -m jobmonitor run --dry-run), auch je Quelle.
- Suchprofile an/aus und Dateien bearbeiten (config.yaml, lernpfade.yaml, Vorlagen) – mit Prüfung und .bak.
- App neu bauen (make app), fehlende Pakete installieren (make setup-cv/setup-app), Selbsttest (make test),
  alte Lebenslauf-Dateien in den Papierkorb (make cv-clean), Protokoll ansehen.
Länger laufende Aufgaben laufen im Hintergrund; ihre Ausgabe steht in .gui_aufgaben/ (gitignored).
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path

from ruamel.yaml import YAML

from .config import MODI

TASK_DIR = ".gui_aufgaben"
LOGFILE = Path.home() / "Library" / "Logs" / "job-monitor.log"
QUELLEN = {"": "alle Quellen", "bundesagentur": "Bundesagentur", "hsnr": "Hochschule Niederrhein",
           "stellenwerk": "Stellenwerk", "companies": "Firmen-Karriereseiten", "mail_alerts": "Mail-Alerts"}
# Dateien, die die Oberfläche als Text bearbeiten darf, und was nach dem Speichern geprüft wird
DATEIEN = {
    "config.yaml": ("Einstellungen der Pipeline (Suche, Filter, Fit, Prüfer …)", "config"),
    "companies.yaml": ("Firmen und Hochschul-Stellenbörsen (Karriereseiten, Initiativ, Warnhinweise)", "companies"),
    "lernpfade.yaml": ("Lernvorschläge zur Lücken-Auswertung", "yaml"),
    "cv/anschreiben_vorlage.txt": ("Textbausteine für Anschreiben-Entwürfe", "text"),
    "cv/nachfassen_vorlage.txt": ("Vorlage für die Nachfrage beim Nachfassen", "text"),
}
PAKETE = {"requests": "Grundpaket", "ruamel.yaml": "Grundpaket", "pypdf": "Grundpaket", "jinja2": "Lebenslauf (PDF)",
          "webview": "App-Fenster", "pytest": "Selbsttest"}
REQUIREMENTS = ["requirements.txt", "requirements-cv.txt", "requirements-app.txt"]


class WartungError(Exception):
    pass


def esc(value) -> str:
    return escape(str(value if value is not None else ""))


# --- Hintergrund-Aufgaben ---
@dataclass
class Aufgabe:
    name: str
    titel: str
    proc: subprocess.Popen
    log: Path
    start: datetime

    @property
    def laeuft(self) -> bool:
        return self.proc.poll() is None

    def ausgabe(self, zeilen: int = 60) -> str:
        try:
            text = self.log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return "\n".join(text.splitlines()[-zeilen:])


class Aufgaben:
    """Je Name höchstens eine laufende Aufgabe; die letzte bleibt mit Ergebnis sichtbar."""

    def __init__(self, root: Path, popen=subprocess.Popen):
        self.root, self.popen, self.alle = root, popen, {}

    def starten(self, name: str, titel: str, cmd: list[str]) -> Aufgabe:
        alt = self.alle.get(name)
        if alt is not None and alt.laeuft:
            raise WartungError(f"„{alt.titel}“ läuft noch.")
        folder = self.root / TASK_DIR
        folder.mkdir(exist_ok=True)
        log = folder / f"{name}.log"
        with open(log, "w", encoding="utf-8") as fh:
            fh.write(f"$ {' '.join(cmd)}\n")
            fh.flush()
            from .prozess import umgebung
            proc = self.popen(cmd, cwd=self.root, stdout=fh, stderr=subprocess.STDOUT, text=True, env=umgebung())
        self.alle[name] = Aufgabe(name, titel, proc, log, datetime.now())
        return self.alle[name]

    def laeuft(self) -> bool:
        return any(a.laeuft for a in self.alle.values())


def python() -> str:
    return sys.executable


def probelauf_cmd(quelle: str) -> list[str]:
    if quelle not in QUELLEN:
        raise WartungError("Unbekannte Quelle.")
    from .prozess import befehl
    return befehl("run", "--force", "--dry-run", "--no-mail") + (["--only", quelle] if quelle
                                                                                        else [])


def pakete_cmd(root: Path) -> list[str]:
    files = [f for f in REQUIREMENTS if (root / f).exists()]
    return [python(), "-m", "pip", "install", "-q"] + [a for f in files for a in ("-r", f)]


def fehlende_pakete() -> list[str]:
    return [f"{name} ({zweck})" for name, zweck in PAKETE.items() if importlib.util.find_spec(name) is None]


# --- GitHub-Pipeline über gh ---
def gh() -> str | None:
    return shutil.which("gh") or next((p for p in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh") if Path(p).exists()),
                                      None)


def pipeline_laeufe(root: Path, run=subprocess.run) -> tuple[list[dict], str]:
    """(letzte Läufe, Fehlermeldung)."""
    exe = gh()
    if exe is None:
        return [], "GitHub-CLI (gh) nicht gefunden."
    try:
        proc = run([exe, "run", "list", "--workflow", "monitor.yml", "--limit", "5", "--json",
                    "status,conclusion,createdAt,event,url,displayTitle"], cwd=root, capture_output=True, text=True,
                   timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"GitHub nicht erreichbar ({exc})."
    if proc.returncode != 0:
        return [], (proc.stderr.strip() or "GitHub-Abfrage fehlgeschlagen.")[:300]
    try:
        return json.loads(proc.stdout or "[]"), ""
    except ValueError:
        return [], "Antwort von GitHub unlesbar."


def pipeline_starten(root: Path, ohne_mail: bool, run=subprocess.run) -> str:
    exe = gh()
    if exe is None:
        raise WartungError("GitHub-CLI (gh) nicht gefunden.")
    proc = run([exe, "workflow", "run", "monitor.yml", "-f", "force=true", "-f",
                f"no_mail={'true' if ohne_mail else 'false'}"], cwd=root, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise WartungError((proc.stderr.strip() or "Start fehlgeschlagen.")[:300])
    return "Lauf auf GitHub gestartet. Er braucht ein paar Minuten; danach holt „Jetzt synchronisieren“ die Ergebnisse."


# --- Dateien und Suchprofile ---
def datei_pfad(root: Path, name: str) -> Path:
    if name not in DATEIEN:
        raise WartungError("Diese Datei kann hier nicht bearbeitet werden.")
    return root / name


def pruefen(name: str, text: str) -> None:
    art = DATEIEN[name][1]
    if art in ("config", "yaml", "companies"):
        try:
            data = YAML(typ="safe").load(text)
        except Exception as exc:   # ruamel wirft verschiedene Fehlerklassen
            marke = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
            zeile = f" (Zeile {marke.line + 1})" if marke is not None else ""
            raise WartungError(f"Kein gültiges YAML{zeile}: {str(exc).splitlines()[0][:200]}") from None
        if not isinstance(data, dict):
            raise WartungError("Die Datei muss aus Schlüssel: Wert-Einträgen bestehen.")
        if art == "config":
            fehlend = [k for k in ("run", "http", "sources", "filter", "fit", "cv", "mail") if k not in data]
            if fehlend:
                raise WartungError(f"Pflichtabschnitte fehlen: {', '.join(fehlend)}.")
        if art == "companies":
            _firmen_pruefen(data)


def _firmen_pruefen(data: dict) -> None:
    """companies.yaml: Liste `firmen` (und optional `hochschulen`), je Eintrag Name und Karriereseite (http/https),
    keine doppelten Namen – sonst bricht der nächste Lauf der Pipeline ab oder fragt Firmen doppelt ab."""
    if not isinstance(data.get("firmen"), list):
        raise WartungError("Der Abschnitt „firmen:“ fehlt oder ist keine Liste.")
    for abschnitt in ("firmen", "hochschulen"):
        namen = set()
        for i, e in enumerate(data.get(abschnitt) or [], 1):
            if not isinstance(e, dict) or not str(e.get("name") or "").strip():
                raise WartungError(f"{abschnitt}, Eintrag {i}: „name“ fehlt.")
            url = str(e.get("karriereseite_url") or "")
            if not url.startswith(("http://", "https://")):
                raise WartungError(f"{abschnitt}, „{e['name']}“: karriereseite_url muss mit https:// beginnen.")
            if e["name"].lower() in namen:
                raise WartungError(f"{abschnitt}: „{e['name']}“ steht doppelt in der Liste.")
            namen.add(e["name"].lower())


def speichern(root: Path, name: str, text: str) -> Path:
    path = datei_pfad(root, name)
    text = text.replace("\r\n", "\n")
    text = text if text.endswith("\n") else text + "\n"
    pruefen(name, text)
    if path.exists():
        shutil.copy(path, path.with_name(path.name + ".bak"))
    path.write_text(text, encoding="utf-8")
    return path


PROFIL_RE = r"(^  {key}:\n(?:    [^\n]*\n|\s*\n)*?    enabled:\s*)(true|false)"


def profil_setzen(root: Path, key: str, an: bool) -> None:
    """profile.<key>.enabled in config.yaml umschalten, ohne den Rest der Datei neu zu formatieren."""
    path = root / "config.yaml"
    text = path.read_text(encoding="utf-8")
    if not re.match(r"^[a-z0-9_]+$", key):
        raise WartungError("Unbekanntes Suchprofil.")
    neu, n = re.subn(PROFIL_RE.format(key=key), lambda m: m.group(1) + ("true" if an else "false"), text, count=1,
                     flags=re.MULTILINE)
    if n != 1:
        raise WartungError(f"Suchprofil „{key}“ nicht in config.yaml gefunden.")
    if an:
        from . import suchprofil
        cfg = YAML(typ="safe").load(text)
        if len([p for p in suchprofil.alle(cfg) if p.enabled and p.key != key]) >= suchprofil.MAX_AKTIV:
            raise WartungError(f"Höchstens {suchprofil.MAX_AKTIV} Suchprofile gleichzeitig aktiv – schalte erst ein "
                               "anderes ab.")
    speichern(root, "config.yaml", neu)


MODUS_RE = r"^(  modus:[ \t]*)([a-z]+)( *)(?=#|$)"
MODUS_TEXT = {
    "aktiv": "Täglich suchen, Postfach auf Antworten prüfen, Anzeigen auf „noch online“ prüfen, Mitteilungen.",
    "ruhe": "Einmal pro Woche suchen, damit die Firmenliste gepflegt bleibt und du früh siehst, wenn eine Quelle "
            "nicht mehr funktioniert. Kein Postfach, keine Mitteilungen.",
    "aus": "Die Pipeline startet weiter jeden Morgen, hört aber sofort wieder auf. Nichts wird abgefragt. "
           "„Lauf jetzt starten“ sucht trotzdem einmal.",
}


def modus_setzen(root: Path, wert: str) -> None:
    """run.modus in config.yaml setzen, ohne den Rest der Datei neu zu formatieren (fehlt die Zeile: anlegen)."""
    if wert not in MODI:
        raise WartungError("Unbekannter Modus.")
    path = root / "config.yaml"
    text = path.read_text(encoding="utf-8")
    run_block = re.search(r"^run:\n((?:[ \t]+[^\n]*\n|[ \t]*\n)*)", text, flags=re.MULTILINE)
    if not run_block:
        raise WartungError("Abschnitt „run:“ nicht in config.yaml gefunden.")
    block, n = re.subn(MODUS_RE,     # Kommentar dahinter bleibt in seiner Spalte
                       lambda m: m.group(1) + wert + " " * (max(1, len(m.group(2) + m.group(3)) - len(wert))
                                                            if m.group(3) else 0),
                       run_block.group(1), count=1, flags=re.MULTILINE)
    if not n:
        block = f"  modus: {wert}\n" + block
    speichern(root, "config.yaml", text[:run_block.start(1)] + block + text[run_block.end(1):])


# --- Aufräumen und Protokoll ---
def cv_out_aufraeumen(root: Path, cfg: dict, trash: Path | None = None) -> str:
    out = root / cfg["cv"]["ausgabe"]
    if not out.is_dir() or not any(out.iterdir()):
        return "cv/out ist schon leer."
    trash = trash or Path.home() / ".Trash"
    trash.mkdir(parents=True, exist_ok=True)
    target = trash / f"cv-out-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.move(str(out), str(target))
    return f"Alte Lebenslauf-Dateien in den Papierkorb verschoben ({target.name})."


def protokoll(zeilen: int = 80, path: Path = LOGFILE) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-zeilen:])
    except OSError:
        return ""


# --- Seite ---
def _aufgabe_html(a: Aufgabe | None) -> str:
    if a is None:
        return ""
    if a.laeuft:
        state = f'<p class="muted">läuft seit {a.start:%H:%M:%S} …</p>'
    elif a.proc.returncode == 0:
        state = '<p class="ok">Fertig.</p>'
    else:
        state = f'<p class="err">Beendet mit Fehler (Code {a.proc.returncode}).</p>'
    return f'{state}<pre class="out">{esc(a.ausgabe())}</pre>'


def _form(token: str, aktion: str, label: str, extra: str = "", ghost: bool = False, confirm: str = "") -> str:
    onsubmit = f' onsubmit="return confirm(\'{esc(confirm)}\')"' if confirm else ""
    return (f'<form method="post" action="/einstellungen" style="display:inline"{onsubmit}>'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="aktion" value="{aktion}">'
            f'{extra}<button class="{"ghost " if ghost else ""}small">{esc(label)}</button></form>')


def laeufe_html(laeufe: list[dict], gh_fehler: str) -> str:
    """Tabelle der letzten Pipeline-Läufe; wird nach dem Seitenaufbau nachgeladen (gh braucht ~1 s oder länger)."""
    rows = "".join(
        f'<tr><td>{esc(r.get("createdAt", "")[:16].replace("T", " "))} UTC</td><td>{esc(r.get("event"))}</td>'
        f'<td class="{"ok" if r.get("conclusion") == "success" else "err" if r.get("conclusion") else "muted"}">'
        f'{esc(r.get("conclusion") or r.get("status"))}</td>'
        f'<td><a href="{esc(r.get("url"))}" target="_blank" rel="noopener">ansehen</a></td></tr>' for r in laeufe)
    return f'<table>{rows}</table>' if rows else f'<p class="muted">{esc(gh_fehler or "Noch keine Läufe.")}</p>'


LAEUFE_JS = """<script>fetch("/einstellungen/laeufe").then(r => r.ok ? r.text() : Promise.reject(r.status))
.then(html => { document.getElementById("laeufe").innerHTML = html; })
.catch(() => { document.getElementById("laeufe").innerHTML = '<p class="muted">Läufe nicht geladen.</p>'; });</script>"""


def sicherung_karte(token: str, vorhandene: list[Path], anzahl: int) -> str:
    """Einstellungen → Sicherung: lokale Daten als verschlüsseltes Disk-Image (oder ZIP) sichern."""
    liste = "".join(f'<li>{esc(p.name)} <span class="muted">· {datetime.fromtimestamp(p.stat().st_mtime):%d.%m.%Y}'
                    f'</span></li>' for p in vorhandene[:5])
    return f"""<div class="card" id="sicherung"><h2>Sicherung</h2>
<p class="muted">Sichert, was nur auf diesem Mac liegt ({anzahl} Dateien): persönliche Angaben, Zeugnisse und
Zertifikate, Bewerbungsordner, KI-Vorbereitungen – dazu Master-CV und Einstellungen. Mit Passwort als verschlüsseltes
Disk-Image (AES-256), ohne als ZIP. Nicht enthalten: der API-Schlüssel (Schlüsselbund). Ablage: Dokumente →
Job-Monitor Sicherungen.</p>
<form method="post" action="/einstellungen" class="grid2" style="align-items:end">
<input type="hidden" name="token" value="{token}"><input type="hidden" name="aktion" value="sicherung">
<div><label for="sp1">Passwort (empfohlen, mind. 8 Zeichen)</label>
<input id="sp1" type="password" name="passwort" autocomplete="new-password"></div>
<div><label for="sp2">Passwort wiederholen</label><input id="sp2" type="password" name="passwort2"
autocomplete="new-password"></div>
<div class="row"><button>Sicherung erstellen</button>{_form(token, "sicherung_ordner", "Ordner zeigen", ghost=True)
if vorhandene else ""}</div></form>
{f'<ul style="margin-top:10px">{liste}</ul>' if liste else '<p class="muted">Noch keine Sicherung.</p>'}
<p class="muted">Das Passwort wird nirgends gespeichert – ohne es lässt sich das Image nicht öffnen.</p></div>"""


def zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def pipeline_ki(daten: dict, monat: str, s: dict) -> str:
    """Zeile „Pipeline“ der KI-Karte aus state/seen.sqlite (meta ki_nutzung, siehe runner.ki_nutzung_merken)."""
    m, lauf = daten.get(monat) or {}, daten.get("letzter_lauf") or {}
    if not m:
        return '<p class="muted">Pipeline (GitHub, per WIF): diesen Monat noch keine KI-Aufrufe.</p>'
    summe = lambda d: sum(int(d.get(k, 0)) for k in ("eingabe", "ausgabe", "cache_lesen", "cache_schreiben"))  # noqa
    warn = []
    if summe(m) > int(s["pipeline_warnung_monat"]):
        warn.append(f"mehr als {zahl(int(s['pipeline_warnung_monat']))} Tokens diesen Monat")
    if lauf and summe(lauf) > int(s["pipeline_warnung_lauf"]):
        warn.append(f"letzter Lauf ({lauf.get('datum', '')}) mit {zahl(summe(lauf))} Tokens ungewöhnlich groß")
    text = (f'Pipeline (GitHub, per WIF) diesen Monat: {zahl(m.get("aufrufe", 0))} Aufrufe · '
            f'{zahl(m.get("eingabe", 0) + m.get("cache_lesen", 0) + m.get("cache_schreiben", 0))} Eingabe-Tokens '
            f'(davon {zahl(m.get("cache_lesen", 0))} günstig aus dem Cache) · {zahl(m.get("ausgabe", 0))} Ausgabe-Tokens.')
    if warn:
        return (f'<p class="err">{esc(text)} Achtung: {esc("; ".join(warn))} – Kosten in der Console beim Dienstkonto '
                f'prüfen.</p>')
    return f'<p class="muted">{esc(text)}</p>'


def ki_karte(token: str, herkunft: str, nutzung: dict, s: dict, pipeline: str = "") -> str:
    """Einstellungen → KI: Schlüssel (Schlüsselbund), Modell, Nutzung im laufenden Monat (App und Pipeline)."""
    if herkunft == ".env":
        schluessel = '<p class="ok">Schlüssel aus .env (ANTHROPIC_API_KEY) aktiv.</p>'
    elif herkunft:
        schluessel = ('<p class="ok">Schlüssel im macOS-Schlüsselbund hinterlegt.</p>'
                      + _form(token, "ki_entfernen", "Schlüssel entfernen", ghost=True,
                              confirm="API-Schlüssel aus dem Schlüsselbund löschen?"))
    else:
        schluessel = f"""<form method="post" action="/einstellungen" class="row" style="align-items:end">
<input type="hidden" name="token" value="{token}"><input type="hidden" name="aktion" value="ki_schluessel">
<div style="flex:1"><label for="ki_key">API-Schlüssel (console.anthropic.com → API Keys)</label>
<input id="ki_key" type="password" name="schluessel" autocomplete="off" spellcheck="false" placeholder="sk-ant-…"
required></div><button>Im Schlüsselbund speichern</button></form>"""
    return f"""<div class="card" id="ki"><h2>KI (Claude)</h2>
<p class="muted">Die KI nutzt <b>deinen eigenen</b> Claude-API-Schlüssel aus der
<a href="https://console.anthropic.com" target="_blank" rel="noopener">Anthropic Console</a>; die Kosten laufen über dein
Anthropic-Konto, nach Verbrauch. Gesendet werden Anzeigentexte und dein Master-CV direkt an Anthropic – nie Name,
Adresse, Foto oder andere Angaben aus profile.yaml, nie an den Entwickler dieser App. Die KI verschickt nichts.</p>{schluessel}
<p class="muted" style="margin-top:8px">Diese App: Modell {esc(s["model"])} ·
diesen Monat {nutzung["aufrufe"]} von höchstens {esc(s["max_aufrufe_monat"])} Aufrufen · {zahl(nutzung["eingabe"])} Eingabe- und {zahl(nutzung["ausgabe"])}
Ausgabe-Tokens.</p>{pipeline}<p class="muted">Die Kosten in Euro siehst du in der Anthropic Console unter Usage.</p>
</div>"""


def render(token: str, profile_html: str, aufgaben: Aufgaben, fehlend: list[str], log_text: str, message: str = "",
           mitteilung: dict | None = None, suchmodus: str = "aktiv", ki_html: str = "", sicherung_html: str = "",
           github: bool = True, mac: bool | None = None, version_html: str = "") -> str:
    """`github`: Suche läuft über GitHub Actions (sonst lokaler Zeitplan); `mac`: die tägliche Mitteilung zur
    GitHub-Pipeline gibt es nur dort (ohne Angabe: dieses System)."""
    mac = sys.platform == "darwin" if mac is None else mac
    mitteilung = mitteilung or {}
    a = aufgaben.alle
    refresh = ('<script>setTimeout(() => { location.href = "/einstellungen"; }, 3000);</script>'
               if aufgaben.laeuft() else "")
    pipeline = f"""<div class="card"><h2>Pipeline auf GitHub</h2>
<p class="muted">Läuft jeden Morgen automatisch (gegen 6:20 bzw. 7:20 Uhr). Hier kannst du einen Lauf sofort starten;
die Ergebnisse holt danach „Synchronisieren“ unten links.</p>
<div id="laeufe"><p class="muted">Letzte Läufe werden von GitHub geladen …</p></div>{LAEUFE_JS}
<div class="row" style="margin-top:10px">{_form(token, "pipeline_ohne_mail", "Lauf jetzt starten")}</div></div>""" if github else ""
    wahl = "".join(
        f'<label class="modus{" an" if k == suchmodus else ""}"><input type="radio" name="modus" value="{k}"'
        f'{" checked" if k == suchmodus else ""} onchange="this.form.requestSubmit()"><b>{esc(name)}</b>'
        f'<span class="muted">{esc(MODUS_TEXT[k])}</span></label>' for k, name in MODI.items())
    suche = f"""<div class="card"><h2>Suche</h2>
<p class="muted">Wenn du gerade keinen Job suchst: Ruhemodus. {"Die Änderung wird sofort zu GitHub hochgeladen und gilt" if github else "Gilt"}
ab dem nächsten Lauf. Gefundene Stellen, Bewerbungen und Einstellungen bleiben erhalten.</p>
<form method="post" action="/einstellungen" class="modi"><input type="hidden" name="token" value="{token}">
<input type="hidden" name="aktion" value="modus">{wahl}</form></div>"""
    an, zeit = mitteilung.get("an"), mitteilung.get("zeit", "08:30")
    hinweis = ("<b>an</b> · täglich um " + esc(zeit) + " Uhr, wenn die Pipeline neue Stellen gefunden hat" if an
               else "<b>aus</b> · keine Mitteilungen")
    if an and suchmodus != "aktiv":
        hinweis += f" – pausiert, solange die Suche auf „{esc(MODI[suchmodus])}“ steht"
    note = f"""<div class="card"><h2>Mitteilung bei neuen Stellen</h2>
<p class="muted">Statt eines Berichts per Mail: eine Mitteilung von Job-Monitor auf diesem Mac, z. B. „3 neue Stellen ·
Werkstudent Marketing – Beispiel GmbH · Fit 85 %“. Dazu je eine eigene Mitteilung für sehr gut passende Stellen (ab Fit
75 % oder Traumprofil) und für neue Antworten von Firmen. Ein Klick öffnet die App. Ohne Neues kommt nichts; schläft
der Mac zur Uhrzeit, kommt sie beim Aufwachen.</p>
<form method="post" action="/einstellungen" class="row" style="align-items:center;gap:14px">
<input type="hidden" name="token" value="{token}"><input type="hidden" name="aktion" value="mitteilung">
<label class="switch"><input type="checkbox" role="switch" name="an" value="1"{" checked" if an else ""}
onchange="this.form.requestSubmit()"><span class="track"></span><span>Täglich benachrichtigen</span></label>
<label style="margin:0;display:flex;align-items:center;gap:8px">um <input type="time" name="zeit" value="{esc(zeit)}"
style="width:auto" onchange="if (this.form.an.checked) this.form.requestSubmit()"> Uhr</label></form>
<p class="muted" style="margin-top:8px">Status: {hinweis}</p>
<div class="row">{_form(token, "mitteilung_test", "Probe-Mitteilung senden", ghost=True)}</div></div>""" if mac else ""

    optionen = "".join(f'<option value="{k}">{esc(v)}</option>' for k, v in QUELLEN.items())
    probe = f"""<div class="card"><h2>Probelauf auf diesem Rechner</h2>
<p class="muted">Fragt die Quellen ab und zeigt den Bericht, ohne etwas zu speichern oder eine Mail zu schicken.
Alle Quellen dauern einige Minuten.</p>
{_form(token, "probelauf", "Probelauf starten", f'<select name="quelle" style="width:auto;margin-right:8px">{optionen}</select>')}
{_aufgabe_html(a.get("probelauf"))}</div>"""

    from .gui_dateien import uebersicht_html
    einst = f"""{profile_html}
{uebersicht_html()}"""

    aufraeumen = _form(token, "cv_out", "Alte Lebenslauf-Dateien aufräumen", ghost=True,
                       confirm="Alle Dateien in cv/out in den Papierkorb verschieben? Bewerbungsordner bleiben.")
    if getattr(sys, "frozen", False):   # installierte App: Pakete und Tests sind fest eingebaut
        app = (f'<div class="card"><h2>App und Wartung</h2>{version_html}<div class="row">{aufraeumen}</div><p '
               f'class="muted">Neue Versionen gibt es als Download; deine Daten im Ordner '
               f'{esc(str(Path.home() / "Documents" / "Job-Monitor"))} bleiben beim Ersetzen der App erhalten. '
               f'Protokoll: .gui_aufgaben/app.log im selben Ordner.</p></div>')
    else:
        paket_html = (f'<p class="err">Fehlt: {esc(", ".join(fehlend))}</p>' if fehlend
                      else '<p class="ok">Alle Pakete installiert.</p>')
        app = f"""<div class="card"><h2>App und Wartung</h2>{version_html}
<div class="row">{_form(token, "app", "App neu bauen", ghost=True) if mac else ""}
{_form(token, "pakete", "Pakete installieren/aktualisieren", ghost=True)}
{_form(token, "tests", "Selbsttest", ghost=True)}
{aufraeumen}</div>
{paket_html}
{_aufgabe_html(a.get("pakete"))}{_aufgabe_html(a.get("tests"))}</div>"""

    log_html = (f'<details><summary>Protokoll der App (letzte Zeilen)</summary><pre class="out">{esc(log_text)}</pre>'
                f'</details>' if log_text else "")
    return (f'<h1>Einstellungen</h1><p class="sub">Alles, was du sonst im Terminal machen würdest.</p>{message}'
            f'{suche}{pipeline}{note}{ki_html}{probe}{einst}{sicherung_html}{app}<div class="card">{log_html or "<p class=muted>Noch kein Protokoll.</p>"}'
            f'</div>{refresh}')
