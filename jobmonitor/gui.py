"""Lokale Oberfläche im Browser: Lebenslauf für eine gefundene oder eigene Stelle per Klick bauen.

Start: Doppelklick auf Job-Monitor.command, `make gui` oder `python -m jobmonitor gui`. Der Server hört nur auf
127.0.0.1 (nicht im Netzwerk erreichbar). Formulare tragen ein zufälliges Token, damit fremde Webseiten keine
Aktionen auslösen können. Nichts davon läuft in der Pipeline.
"""
from __future__ import annotations

import html
import json
import logging
import re
import secrets
import subprocess
import threading
import time
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, quote

from . import ablehnung, abschicken, demo, ki_extra, selbstupdate, designs, feedback, firmen_finder, i18n, portal, spenden, sprache, teilen, erststart, mailzugang, updates, wohnort, zeitplan, antworten, anzeigen_check
from . import benachrichtigung as bn
from . import bewerbung as bw
from . import gui_bericht as gbe
from . import fit
from . import fristen
from . import gui_bewerbung as gbw
from . import gui_hilfe as gh
from . import gui_dateien as gdt
from . import gui_ki as gki
from . import ki_anbieter as gki_anbieter
from . import gui_layout as layout
from . import gui_bewerbungen as gb
from . import gui_firmen as gf
from . import gui_heute as ghe
from . import gui_rueckkehr as grk
from . import gui_suchprofile as gsp
from . import gui_luecken as gl
from . import gui_master as gm
from . import gui_trend as gtr
from . import gui_assistent as gas
from . import gui_profil as gp
from . import gui_unterlagen as gu
from . import gui_wartung as gw
from . import cv_aktuell, erinnerungen, ki, lernpfade, llm, sicherung, suchprofil, tracking, traumjob
from . import fit_begriffe as fb
from .gui_sync import sync
from .config import MODI, load_companies, load_config, modus
from .cv_build import CvBuildError, _slug, build
from .cv_data import CvDataError, covered_terms, load_cv_master
from .eigene_stelle import StelleError, fetcher_from, from_file, from_url, prepare
from .models import Job
from .report import fit_line
from .state import State

from .gui_app_bewerbungen import BewerbungenSeiten  # noqa: E402

log = logging.getLogger(__name__)
PORT = 8790                   # nicht 8765: den nutzt AnkiConnect
PDF_NAME = re.compile(r"^[\w.-]+\.pdf$")


# Eckdaten-Filter der Stellenliste (gui_layout.JS) – je Karrierestufe die passenden. Ohne Angabe in der Anzeige bleibt
# eine Stelle bei Stunden, Remote, Voll- und Teilzeit sichtbar; „Abschlussarbeit“ und „Vergütung“ verlangen die Angabe.
ECK = {"h": "bis 20 h/Woche", "vz": "Vollzeit", "tz": "Teilzeit möglich", "r": "Remote möglich",
       "t": "Abschlussarbeit möglich", "v": "Vergütung angegeben"}
ECK_STUFE = {"werkstudent": ["h", "r", "t"], "praktikum": ["r", "v", "t"], "abschlussarbeit": ["r", "v"],
             "ausbildung": ["v", "tz"], "einstieg": ["vz", "r", "v"], "berufserfahren": ["tz", "r", "v"],
             "minijob": ["v", "r"],
             "": ["r", "v"]}


def eck_filter(stufen: list[str]) -> str:
    keys = list(dict.fromkeys(k for s in stufen or [""] for k in ECK_STUFE.get(s, ECK_STUFE[""])))
    boxen = "".join(f'<label><input type="checkbox" data-eck="{k}"> {ECK[k]}</label>' for k in keys)
    return (f'<div class="eckfilter" role="group" aria-label="Nach Eckdaten filtern">{boxen}<span class="muted">'
            f'Ohne Angabe in der Anzeige bleibt eine Stelle sichtbar (außer bei Abschlussarbeit und Vergütung).'
            f'</span></div>')


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def page(title: str, body: str, extra_css: str = "") -> bytes:
    """Seite ohne Seitenleiste (Start, Beendet). Seiten mit Navigation baut App.page()."""
    return layout.document(title, body, extra_css=extra_css)



def pruefung_html(hinweise: list, was: str = "Lebenslauf") -> str:
    """Ergebnis des Lebenslauf- bzw. Anschreiben-Prüfers (cv_check.py, anschreiben_check.py) als Karte."""
    titel = {"Lebenslauf": "Prüfung des Lebenslaufs", "Anschreiben": "Prüfung des Anschreibens"}[was]
    if not hinweise:
        return f'<div class="card ok-card"><p class="ok">{titel}: keine Auffälligkeiten.</p></div>'
    items = "".join(f'<li class="{esc(h.stufe)}"><b>{"Warnung" if h.stufe == "warnung" else "Tipp"}:</b> '
                    f'{esc(h.text)}</li>' for h in sorted(hinweise, key=lambda h: h.stufe != "warnung"))
    return f'<div class="card"><h2>{titel}</h2><ul class="checks">{items}</ul></div>'



def _datum(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if len(iso) >= 10 else iso


def _kurz(firma: str) -> str:
    """„SUPERSCREENS GmbH“ → „SUPERSCREENS“ für knappe Knopfbeschriftungen."""
    return re.sub(r"\s+(GmbH|AG|SE|KG|mbH|e\.V\.|GmbH & Co\. KG)$", "", firma.strip())[:28]

class App(BewerbungenSeiten):
    """Zustand und Aktionen, getrennt vom HTTP-Teil (testbar)."""

    def __init__(self, root: Path, compile_pdf: bool = True):
        self.root = root
        self.token = secrets.token_urlsafe(16)
        self.sicherung_ziel = sicherung.ZIEL
        self._ki_cv = False          # je Seitenaufbau: KI-Zuschnitt für Lebensläufe verfügbar (siehe ki_lebenslauf)
        self._laeufe: tuple[float, tuple[list[dict], str]] | None = None
        self.compile_pdf = compile_pdf
        self.notice = ""        # Ergebnis der Synchronisierung beim Start (einmal oben anzeigen)
        self.erinnert: set[str] = set()   # schon in Apple-Erinnerungen eingetragen (erinnerungen.py)
        self.aufgaben = gw.Aufgaben(root)  # Hintergrund-Aufgaben der Seite Einstellungen
        try:
            llm.einstellen(load_config(root / "config.yaml"))   # KI-Anbieter (ki_anbieter.py)
        except Exception:
            pass
        self.native = False                # im App-Fenster (desktop.py): durchscheinende Seitenleiste
        self.new_ids: set[str] = set()   # Stellen, die seit dem letzten Besuch dazugekommen sind
        self.trash: Path | None = None   # None = macOS-Papierkorb (~/.Trash); Tests setzen einen eigenen Ordner
        self.ready = True       # False, solange die App-Version beim Start noch synchronisiert
        self.window = None      # pywebview-Fenster, wenn als App gestartet (desktop.py)
        self.sync_hint = ""     # „Synchronisiert 09:14“ unten in der Seitenleiste
        self.echt: Path | None = None   # im Demo-Modus: der eigene Datenordner (root zeigt solange auf die Demo)

    def page(self, title: str, body: str, active: str = "", extra_css: str = "") -> bytes:
        """Seite mit Seitenleiste; Zähler zeigen, wo es Neues gibt."""
        try:
            badges = self.badges()
        except Exception:   # Zähler sind nur Zusatz – eine fehlende Datei soll keine Seite verhindern
            log.exception("Zähler für die Seitenleiste nicht berechnet")
            badges = {}
        try:
            cfg = load_config(self.root / "config.yaml")
            llm.einstellen(cfg)                       # KI-Anbieter für Knöpfe und Hinweise dieser Seite
            traum = cfg.get("traumprofil") or {}
        except Exception:
            cfg, traum = {}, {}
        traum_name = (traum.get("name") or "Traumprofil") if traum and traum.get("enabled", True) is not False else None
        if self.echt is not None:
            body = demo.banner(self.token) + body
        if (knopf := gh.knopf(active)):                 # „?“ unten rechts: Hilfe zu dieser Seite
            body, extra_css = body + knopf, extra_css + gh.KNOPF_CSS
        seite = layout.document(title, body, layout.nav(active, badges, self.token, self.sync_hint, traum_name,
                                                        spenden.url(cfg)),
                                extra_css, self.token, self.native, i18n.darstellung(cfg))
        return self.uebersetzt(seite)

    def darstellung(self, wert: str) -> None:
        """Einstellungen → Darstellung; im App-Fenster folgt auch das Fenstermaterial (desktop.erscheinung)."""
        i18n.darstellung_setzen(self.root, wert)
        if self.native:
            from .desktop import erscheinung
            erscheinung(wert)

    def uebersetzt(self, seite: bytes) -> bytes:
        """Englische Oberfläche (Einstellungen → Sprache): fertige Seite übersetzen (i18n.py)."""
        try:
            en = i18n.sprache(load_config(self.root / "config.yaml")) == "en"
        except Exception:
            en = False
        return i18n.seite(seite.decode()).encode() if en else seite

    def badges(self) -> dict[str, tuple[int, str]]:
        cfg = load_config(self.root / "config.yaml")
        apps = tracking.load(self.root / "applications.csv")
        hidden = {r.get("link") for r in apps if r.get("status") == gb.HIDDEN}
        jobs = [d for d in self.jobs() if d["url"] not in hidden]
        alle = antworten.laden(self.root)
        nachfassen = len(tracking.follow_ups(apps, date.today(), cfg["tracking"]["nachfassen_nach_tagen"],
                                             antworten.beantwortet(alle)))
        nachfassen += len(gb.offene_antworten(self.root, apps))     # neue Antworten von Firmen ebenso
        due = len(gf.due(self.root, date.today(), (cfg.get("gui") or {}).get("manuell_pruefen_tage", 14)))
        liste, status, _ = gf.beobachten(self.root, cfg)
        due += sum(1 for w in liste if status.get(f"{w.art}:{w.name}", ("",))[0] != "pruefung")   # in Prüfung: still
        return {
            "stellen": (sum(1 for d in jobs if d["id"] in self.new_ids), ""),
            "traum": (sum(1 for d in jobs if d["traum"]), ""),
            "bewerbungen": (nachfassen, "warn") if nachfassen else (sum(1 for r in apps if r.get("status") == "neu"), ""),
            "firmen": (due, "warn"),
        }

    def startup(self) -> None:
        """Synchronisieren und Besuch merken (beim Start; in der App im Hintergrund). Mit lokalem Zeitplan: fällige
        Suche sofort nachholen und stündlich prüfen, solange die App offen ist."""
        self.notice = self.sync_card()
        self.remember_visit()
        self.ready = True
        try:
            cfg = load_config(self.root / "config.yaml")
            if updates.aktiv(self.root, cfg):          # neue Version? (Netz, darum im Hintergrund)
                threading.Thread(target=lambda: setattr(self, "update_neu", updates.pruefen(self.root, cfg)),
                                 daemon=True).start()
        except Exception:
            log.exception("Update-Prüfung nicht gestartet")
        if zeitplan.laden(self.root).get("an"):
            zeitplan.pruefen_und_starten(self.root, self.aufgaben)
            self._zeitplan_stop = threading.Event()
            threading.Thread(target=zeitplan.wachen, args=(self.root, self.aufgaben, self._zeitplan_stop),
                             daemon=True).start()

    def remember_visit(self) -> None:
        """Merkt sich lokal (gitignored), welche Stellen du schon gesehen hast. Beim allerersten Start gilt
        nichts als neu, damit die Liste nicht komplett markiert ist."""
        path = self.root / ".gui_gesehen.json"
        current = {d["id"] for d in self.jobs()}
        try:
            seen = set(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            seen = None
        self.new_ids = current - seen if seen is not None else set()
        path.write_text(json.dumps(sorted(current | (seen or set()))), encoding="utf-8")

    def ki_aktion(self, form: dict) -> bytes:
        """KI-Helfer ohne eigene Seite (ki_extra.py): Lebenslauf verstehen und prüfen, Muster aus Absagen."""
        cfg = load_config(self.root / "config.yaml")
        aktion = form.get("aktion", "")
        try:
            if aktion == "absagen":
                ki_extra.absagen_muster(self.root, cfg, self.absagen_zeilen())
                return self.rueckblick()
            cv, _ = load_cv_master(self.root)
            if not cv:
                raise ki.KiError("Keine cv_master.yaml.")
            if aktion == "cv_verstehen":
                n = len(ki_extra.cv_verstehen(self.root, cfg, cv))
                msg = f"{n} Vorschläge – unten unter „Was dein Lebenslauf noch belegt“." if n else \
                    "Keine weiteren Kenntnisse gefunden – dein Lebenslauf nennt alles schon."
            elif aktion == "cv_uebernehmen":
                gewaehlt = [k.split(":", 1)[1] for k in form if k.startswith("begriff:")]
                for term in gewaehlt:
                    gm.kenntnis_speichern(self.root, term, form.get(f"level:{term}", "gut"),
                                          cfg["fit"]["begriffe"].get(term) or [])
                msg = (f"{len(gewaehlt)} Kenntnis(se) in deinen Master-CV eingetragen – Fit ist neu berechnet." if
                       gewaehlt else "Nichts ausgewählt.")
            elif aktion == "cv_check":
                n = len(ki_extra.cv_check(self.root, cfg, cv))
                msg = f"{n} Vorschläge – unten unter „Lebenslauf-Check“."
            else:
                return self.master(message='<div class="card err">Unbekannte Aktion.</div>')
        except (ki.KiError, CvDataError) as exc:
            back = self.rueckblick if aktion == "absagen" else self.master
            return back(message=f'<div class="card err">{esc(exc)}</div>')
        return self.master(message=f'<div class="card"><p class="ok">{esc(msg)}</p></div>')

    def aktualisieren(self) -> bytes:
        """„Jetzt aktualisieren“: neue Version laden, Hilfsskript starten, App beenden (selbstupdate.py)."""
        neu = getattr(self, "update_neu", None)
        if not neu or self.window is None or not selbstupdate.moeglich():
            return self.index('<div class="card err">Automatisches Update hier nicht möglich – bitte über '
                              '„Herunterladen“ installieren.</div>')
        try:
            repo = (load_config(self.root / "config.yaml").get("updates") or {})["repo"]
            app_neu = selbstupdate.herunterladen(repo, neu["version"])
            selbstupdate.tauschen_starten(app_neu)
        except (selbstupdate.UpdateError, KeyError, OSError, subprocess.SubprocessError) as exc:
            log.exception("Update fehlgeschlagen")
            return self.index(f'<div class="card err">Update nicht möglich: {esc(exc)} Die bisherige Version läuft '
                              f'weiter; „Herunterladen“ geht wie gewohnt.</div>')
        threading.Timer(1.5, self.window.destroy).start()   # Seite noch zeigen, dann beenden (desktop.py synct)
        return self.page("Update", f'<h1>Version {esc(neu["version"])} wird installiert</h1><p class="sub">Job-Monitor '
                                   f'beendet sich und startet gleich in der neuen Version. Deine Daten bleiben.</p>')

    def demo_starten(self) -> bytes:
        if self.echt is None:
            self.echt = self.root
        self.root = demo.anlegen()
        return self.index()

    def demo_beenden(self) -> bytes:
        if self.echt is not None:
            self.root, self.echt = self.echt, None
        return self.einrichten() if not erststart.eingerichtet(self.root) else self.index()

    def sync_card(self) -> str:
        from datetime import datetime
        if self.echt is not None:
            return '<div class="card"><p class="muted">In der Demo wird nichts synchronisiert.</p></div>'
        result = sync(self.root)
        self.sync_hint = (f"Synchronisiert {datetime.now():%H:%M}" if result.ok
                          else "Synchronisieren fehlgeschlagen")
        cls = "ok" if result.ok else "err"
        details = (f'<details><summary class="muted">Details</summary><pre>{esc(result.log)}</pre></details>'
                   if result.log and not result.ok else "")
        return f'<div class="card"><p class="{cls}">{esc(result.message)}</p>{details}</div>'

    def form(self, action: str, fields: str, label: str, ghost: bool = False, small: bool = False,
             icon_name: str = "", title: str = "", ki: str = "") -> str:
        classes = " ".join(c for c in ("ghost" if ghost else "", "small" if small else "",
                                       "icon" if icon_name and not label else "") if c)
        inner = (layout.icon(icon_name, 16) if icon_name else "") + esc(label)
        attrs = ((f' class="{classes}"' if classes else "")
                 + (f' title="{esc(title)}" aria-label="{esc(title)}"' if title else "")
                 + (f' data-ki="{esc(ki)}"' if ki else ""))
        return (f'<form method="post" action="{action}" style="display:inline">'
                f'<input type="hidden" name="token" value="{self.token}">{fields}<button{attrs}>{inner}</button></form>')

    # --- Startseite ---
    def jobs(self) -> list[dict]:
        cfg = load_config(self.root / "config.yaml")
        state = State(self.root / "state" / "seen.sqlite", readonly=True)
        details = state.job_details()
        state.close()
        try:
            cv, _ = load_cv_master(self.root)
        except CvDataError:
            cv = None
        covered = covered_terms(cv, cfg["fit"]["begriffe"]) if cv else {}
        traum_cfg = cfg.get("traumprofil") or {}
        bekannt = {p.key for p in suchprofil.alle(cfg)}
        erstes = suchprofil.alle(cfg)[0].key
        for d in details:   # Fit live mit dem aktuellen Lebenslauf neu berechnen
            d["profil"] = d.get("profil") if d.get("profil") in bekannt else erstes   # ältere Stellen: erstes Profil
            job = Job(d["title"], d["company"], d["url"], "")
            fit.apply(job, d["anforderungen"], covered, cfg["fit"])
            d["fit"], d["fit_line"] = job.fit, fit_line(job)
            d["passt"], d["fehlt"] = job.fit_passt, job.fit_fehlt
            # Traumprofil aus Titel + erkannten Anforderungen (der volle Anzeigentext ist nicht gespeichert)
            d["traum"], d["traum_grund"] = traumjob.classify(d["title"], " ".join(d["anforderungen"]), traum_cfg)
        return details

    def einrichten(self, form: dict | None = None, uploads: dict | None = None) -> bytes:
        """Einrichtungs-Assistent (gui_assistent.py); ohne Formular nur die Seite."""
        ki_an = bool(ki.schluessel())
        message = ""
        if form and form.get("aktion") == "sprache_gui":
            try:
                i18n.setzen(self.root, form.get("sprache", ""))
            except gw.WartungError as exc:
                message = f'<div class="card err">{esc(exc)}</div>'
            form = None
        if form:
            try:
                ergebnis = gas.ausfuehren(self.root, form, uploads or {}, ki_an)
                if ergebnis == "fertig":
                    if form.get("zeitplan") and not zeitplan.github_aktiv(self.root):
                        try:
                            zeitplan.einschalten(self.root)
                            zeitplan.pruefen_und_starten(self.root, self.aufgaben)
                        except zeitplan.ZeitplanError as exc:
                            log.warning("Zeitplan nicht eingerichtet: %s", exc)
                    return self.index('<div class="card"><p class="ok">Eingerichtet. Die erste Suche läuft im '
                                      'Hintergrund; Ergebnisse erscheinen hier und unter „Letzter Bericht“.</p></div>')
                message = f'<div class="card"><p class="ok">{esc(ergebnis)}</p></div>'
            except (gas.AssistentError, ki.KiError, wohnort.WohnortError, gw.WartungError, CvDataError) as exc:
                message = f'<div class="card err">{esc(exc)}</div>'
        sprache_html = (i18n.karte(self.token, i18n.sprache(load_config(self.root / "config.yaml")), "/einrichten")
                        + (demo.einstieg(self.token) if self.echt is None else ""))
        return self.page("Einrichten", gas.render(self.root, self.token, ki_an, message) + sprache_html, "", gas.CSS)

    def index(self, message: str = "", show_hidden: bool = False, nur_traum: bool = False, profil: str = "") -> bytes:
        """Stellen: oben der Befund, darunter die Liste nach Fit und rechts die Belege (häufigste Lücken,
        Cloud Security). Aufbau nach tasteskill (App-Bildschirm) und apple-design, siehe gui_layout.CSS."""
        self._offline_cache = None
        if not erststart.eingerichtet(self.root):       # neuer Nutzer: erst der Assistent
            return self.einrichten()
        message = updates.hinweis(getattr(self, "update_neu", None), self.token,
                                  self.window is not None and selbstupdate.moeglich()) + message
        if self.notice:
            message, self.notice = self.notice + message, ""
        cfg = load_config(self.root / "config.yaml")
        from .location import zentrum
        if zentrum(cfg.get("ort")) is None:
            message += ('<div class="card info row" style="justify-content:space-between"><p>Noch kein Wohnort '
                        'festgelegt – bis dahin zählen nur Remote-Stellen.</p><a class="btn small" '
                        'href="/einstellungen#wohnort">Wohnort festlegen</a></div>')
        self._ki_cv = self.ki_cv_an(cfg)
        apps = tracking.load(self.root / "applications.csv")
        self._apps = apps
        status_of = {link: r.get("status", "") for link, r in gb.by_link(apps).items()}
        traum_name = (cfg.get("traumprofil") or {}).get("name", "Traumprofil")
        alle = self.jobs()
        sichtbar = [d for d in alle if status_of.get(d["url"]) != gb.HIDDEN]
        hidden_n = len(alle) - len(sichtbar)
        traum_n = sum(1 for d in sichtbar if d["traum"])
        # Suchprofile als Reiter, sobald mehr als eins aktiv ist oder Stellen hat (z. B. Werkstudent und Junior)
        profile = [p for p in suchprofil.alle(cfg) if p.enabled or any(d["profil"] == p.key for d in alle)]
        namen = {p.key: p.name for p in profile} if len(profile) > 1 else {}
        profil = profil if profil in namen else ""
        # Profil-Plakette an der Zeile nur, wenn wirklich Stellen aus mehreren Profilen da sind (sonst Lärm)
        mit_profil = namen if len({d["profil"] for d in alle}) > 1 else {}
        if show_hidden:
            jobs = [d for d in alle if status_of.get(d["url"]) == gb.HIDDEN]
        elif nur_traum:
            jobs = [d for d in sichtbar if d["traum"]]
        elif profil:
            jobs = [d for d in sichtbar if d["profil"] == profil]
        else:
            jobs = sichtbar
        self.erinnert = erinnerungen.eingetragen(self.root)
        mit_fit = sorted((d for d in jobs if d["fit"] is not None), key=lambda d: (-d["fit"], d["title"]))
        ohne_fit = [d for d in jobs if d["fit"] is None]
        card = lambda d: self._job_card(d, status_of.get(d["url"], ""), traum_name,  # noqa: E731
                                        mit_profil.get(d["profil"], ""), cfg)
        groups = "".join(f'<div class="group"><span>{label}</span><span class="num">{len(rows)}</span></div>'
                         + "".join(card(d) for d in rows)
                         for label, rows in (("Nach Fit", mit_fit), ("Zu wenig Angaben in der Anzeige", ohne_fit)) if rows)
        if not groups:
            groups = (f'<div class="empty">Gerade keine {esc(traum_name)}-Stellen. Neue erscheinen hier und ganz oben im '
                      f'Bericht.</div>' if nur_traum else
                      '<div class="empty">Keine Stellen. Neue kommen mit dem nächsten Lauf der Pipeline.</div>')

        if modus(cfg) != "aktiv":
            message += (f'<div class="card info row" style="justify-content:space-between"><p>Suche steht auf '
                        f'„{esc(MODI[modus(cfg)])}“ – {"einmal pro Woche, ohne Mitteilungen" if modus(cfg) == "ruhe" else "die Pipeline sucht nicht"}.'
                        f'</p><a class="btn ghost small" href="/einstellungen">Ändern</a></div>')
        message += gf.due_link(len(gf.due(self.root, date.today(),
                                          (cfg.get("gui") or {}).get("manuell_pruefen_tage", 14))))
        offen = self.offene_fristen(cfg, sichtbar)
        if offen:
            message += (f'<div class="card info row" style="justify-content:space-between"><p>{len(offen)} '
                        f'Bewerbungsfrist(en) noch nicht in deinen Erinnerungen.</p>'
                        f'{self.form("/erinnern", "<input type=hidden name=art value=fristen>", "Alle eintragen", ghost=True, small=True)}'
                        f'</div>')
        if self.new_ids:
            message += (f'<div class="card info"><p>{len(self.new_ids)} neue Stelle(n) seit deinem letzten Besuch '
                        f'– in der Liste mit „neu“ markiert.</p></div>')

        tab = "hidden" if show_hidden else "traum" if nur_traum else f"profil:{profil}" if profil else "alle"
        stufen = [suchprofil.stufe_von(p) for p in suchprofil.alle(cfg)
                  if (p.key == profil if profil else p.enabled)]
        eck_html = eck_filter(stufen)
        tabs = [("alle", "/", "Alle", len(sichtbar))]
        tabs += [(f"profil:{key}", f"/?profil={quote(key)}", name, sum(1 for d in sichtbar if d["profil"] == key))
                 for key, name in namen.items()]
        traum_an = bool(cfg.get("traumprofil")) and (cfg.get("traumprofil") or {}).get("enabled", True) is not False
        if traum_an:
            tabs.append(("traum", "/?traum=1", traum_name, traum_n))
        if hidden_n:
            tabs.append(("hidden", "/?alle=1", "Ausgeblendet", hidden_n))
        tabs_html = "".join(f'<a href="{href}"{" class=active aria-current=page" if key == tab else ""}>{esc(label)}'
                            f'<span>{n}</span></a>' for key, href, label, n in tabs)

        # Befund: aus denselben Zahlen wie Liste und rechte Spalte berechnet
        stark = sum(1 for d in sichtbar if (d["fit"] or 0) >= 75)
        luecken = Counter(t for d in sichtbar for t in d.get("fehlt") or [])
        befund = f"<b>{stark} von {len(sichtbar)}</b> Stellen passen zu über 75 %"
        if traum_n:
            befund += f", {'eine ist' if traum_n == 1 else f'{traum_n} sind'} {esc(traum_name)}"
        befund += "."
        if luecken:
            term, n = luecken.most_common(1)[0]
            befund += f" Am häufigsten fehlt dir <b>{esc(term)}</b> (in {n} {'Stelle' if n == 1 else 'Stellen'})."
        if nur_traum:
            befund = f"Stellen, bei denen Cloud- und Security-Themen zusammenkommen: <b>{traum_n}</b>."

        beste = next((d for d in sorted(sichtbar, key=lambda d: -(d["fit"] or -1)) if d["fit"] is not None), None)
        stand = max((d["first_seen"] for d in alle), default="")
        actions = ((f'<span class="muted num">Stand {stand[8:10]}.{stand[5:7]}.</span>' if stand else "")
                   + self.form("/cv", '<input type="hidden" name="art" value="allgemein">', "Allgemeiner Lebenslauf",
                               ghost=True, small=True)
                   + (f'<a class="btn" href="/bewerbung?job={esc(beste["id"])}" title="Beste offene Stelle: '
                      f'{esc(beste["title"])} ({beste["fit"]} %)">Bewerbung: {esc(_kurz(beste["company"]))}</a>'
                      if beste else ""))
        title = traum_name if nur_traum else f"Stellen · {namen[profil]}" if profil else "Stellen"

        top = luecken.most_common(5)
        luecken_html = "".join(f'<div class="gap-item"><b>{esc(t)}</b><span>{n} {"Stelle" if n == 1 else "Stellen"}'
                               f'</span><i style="--p:{n / top[0][1] * 100:.0f}"></i></div>' for t, n in top) \
            or '<p class="muted">In keiner Stelle fehlt dir etwas.</p>'
        traum = [d for d in sichtbar if d["traum"]][:3]
        traum_html = "".join(f'<div class="traum-item"><a href="{esc(d["url"])}" target="_blank" rel="noopener">'
                             f'{esc(d["title"])}</a><p>{esc(d["company"])} · {d["fit"] if d["fit"] is not None else "–"} % · '
                             f'{esc(d["traum_grund"])}</p></div>' for d in traum) \
            or '<p class="muted">Gerade keine. Neue erscheinen hier zuerst.</p>'
        heute = ("" if show_hidden or nur_traum or profil else
                 self._rueckkehr_karte(cfg) + self._ablehnung_karte(cfg, sichtbar)
                 + ghe.render(ghe.auswahl(sichtbar, status_of, self.offline_links(), date.today(), cfg.get("heute"))))
        body = f"""{layout.head(title, befund, actions)}
{message}{heute}
<nav class="filters" aria-label="Stellen filtern">{tabs_html}<label class="search">{layout.icon("search", 16)}
<input id="filter" placeholder="Titel, Firma, Skill oder ID" aria-label="Stellen durchsuchen"></label></nav>
{eck_html}
<div class="board"><section aria-label="Stellen">{groups}</section>
<aside class="rail"><div class="card"><div class="head"><h2>Häufigste Lücken</h2><a href="/luecken">Auswertung ›</a></div>
{luecken_html}</div>
{f'<div class="card"><div class="head"><h2>{esc(traum_name)}</h2><a href="/?traum=1">Alle ›</a></div>{traum_html}</div>' if traum_an else ""}</aside></div>"""
        return self.page("Stellen", body, "traum" if nur_traum else "stellen", ghe.CSS)

    def _rueckkehr_karte(self, cfg: dict) -> str:
        data = grk.laden(self.root)
        if not data:
            return ""
        try:
            veraltet = len(cv_aktuell.pruefen(gm.load(self.root), date.today()))
        except Exception:
            veraltet = 0
        try:
            quellen = len(gf.beobachten(self.root, cfg)[0])
        except Exception:
            quellen = 0
        return grk.render(self.token, data, grk.punkte(veraltet, quellen, bool(bn.status().get("an"))))

    def rueckkehr(self, form: dict) -> bytes:
        grk.abhaken(self.root, form.get("punkt", ""))
        return self.index()

    def offline_links(self) -> dict[str, str]:
        """Links aus deiner Liste, deren Anzeige laut Pipeline nicht mehr online ist (einmal je Seitenaufruf gelesen)."""
        if getattr(self, "_offline_cache", None) is None:
            self._offline_cache = anzeigen_check.offline(anzeigen_check.laden(self.root))
        return self._offline_cache

    def _job_card(self, d: dict, status: str, traum_name: str, profil_name: str = "", cfg: dict | None = None) -> str:
        cfg = cfg or load_config(self.root / "config.yaml")
        job_field = f'<input type="hidden" name="job_id" value="{esc(d["id"])}">'
        meta = [f'<span>{esc(d["company"])} · <span class="num">gefunden {esc(_datum(d["first_seen"]))}</span></span>']
        if d["id"] in self.new_ids:
            meta.append('<span class="chip new">neu</span>')
        if profil_name:
            meta.append(f'<span class="chip">{esc(profil_name)}</span>')
        if d["traum"]:
            meta.append(f'<span class="mark" title="{esc(d["traum_grund"])}">{esc(traum_name)}</span>')
        frist_txt = fristen.label(d.get("frist"), date.today())
        abgelaufen = "abgelaufen" in frist_txt
        erinnerung = erinnerungen.fuer_frist(d, cfg) if erinnerungen.verfuegbar() else None
        erinnert = erinnerung is not None and erinnerung.schluessel in self.erinnert
        if frist_txt:
            meta.append(f'<span class="chip {"abgelaufen" if abgelaufen else "frist"}">{esc(frist_txt)}'
                        f'{" · in Erinnerungen" if erinnert else ""}</span>')
        if status:
            meta.append(f'<span class="chip">{esc(status)}</span>')
        elif (frueher := gb.frueher_bei_firma(getattr(self, "_apps", []), d["company"], d["url"])):
            meta.append(f'<span class="chip" title="{esc(frueher[0].get("status"))} am {esc(frueher[0].get("datum"))}">'
                        f'schon bei {esc(d["company"])} beworben</span>')
        if d["url"] in self.offline_links():
            meta.append('<span class="chip abgelaufen" title="Die Anzeige ist nicht mehr erreichbar">nicht mehr online</span>')
        meta += [f'<span class="chip eck" title="Eckdaten laut Anzeige (von der KI gelesen)">{esc(e)}</span>'
                 for e in fit.eckdaten_text(d.get("eckdaten") or {})]
        meta += [f'<span class="chip hinweis" title="Hinweis der KI zur Anzeige">⚠ {esc(h)}</span>'
                 for h in (d.get("eckdaten") or {}).get("hinweise") or []]

        # Signatur: jede erkannte Anforderung als Einheit, erfüllt gefüllt, fehlend als Umriss
        passt = set(d.get("passt") or [])
        reqs = sorted(d["anforderungen"], key=lambda t: (t not in passt, t.lower()))
        tip = "\n".join(f"{t}: {'erfüllt' if t in passt else 'fehlt'}" for t in reqs)
        req = (f'<div class="req" title="{esc(tip)}"><div class="units">'
               + "".join(f'<i class="{"" if t in passt else "miss"}"></i>' for t in reqs)
               + f'</div><small class="num">{sum(t in passt for t in reqs)} von {len(reqs)} erfüllt</small></div>'
               if reqs else '<div class="req"><small>keine Anforderungen erkannt</small></div>')
        fitnum = ('<div class="fitnum none" title="Zu wenig Angaben in der Anzeige für einen Fit">–</div>'
                  if d["fit"] is None else
                  f'<div class="fitnum{" hi" if d["fit"] >= 75 else ""}" title="Fit {d["fit"]} %">{d["fit"]}'
                  f'<small>%</small></div>')

        mark = (self.form("/markieren", job_field + '<input type="hidden" name="aktion" value="merken">',
                          "", ghost=True, icon_name="bookmark", title="Merken")
                if status in ("", gb.HIDDEN) else "")
        hide = (self.form("/markieren", job_field + '<input type="hidden" name="aktion" value="ausblenden">',
                          "", ghost=True, icon_name="x", title="Ausblenden") if status != gb.HIDDEN else "")
        bell = (self.form("/erinnern", job_field + '<input type="hidden" name="art" value="frist">', "", ghost=True,
                          icon_name="bell", title=f"Frist in Erinnerungen eintragen ({erinnerung.faellig:%d.%m.})")
                if erinnerung is not None and not erinnert else "")
        cv = self.form("/cv", f'<input type="hidden" name="art" value="job">{job_field}', "", ghost=True,
                       icon_name="file", title="Lebenslauf für diese Stelle",
                       ki="KI schneidet den Lebenslauf auf die Stelle zu …" if self._ki_cv else "")
        search = " ".join([d["title"], d["company"], d["id"], profil_name or "", *reqs]).lower()   # Suchfeld oben
        ef = fit.eckdaten_filter(d.get("eckdaten") or {})
        return f"""<article class="job{" expired" if abgelaufen else ""}" data-s="{esc(search)}" data-h="{ef["h"]}" data-r="{ef["r"]}" data-t="{ef["t"]}" data-v="{ef["v"]}" data-vz="{ef["vz"]}" data-tz="{ef["tz"]}">
<div style="min-width:0"><h3><a href="{esc(d["url"])}" target="_blank" rel="noopener" title="Anzeige öffnen · ID {esc(d["id"])}">{esc(d["title"])}</a></h3>
<div class="meta">{"".join(meta)}</div></div>{req}{fitnum}
<div class="actions"><a class="btn ghost small" href="/bewerbung?job={esc(d["id"])}">Bewerbung</a>{cv}{bell}{mark}{hide}</div></article>"""

    def eigene(self, message: str = "") -> bytes:
        ki_attr = ' data-ki="KI liest die Anforderungen der Anzeige …"' if ki.schluessel() else ""
        body = f"""{layout.head("Eigene Stelle", "Für Anzeigen, die der Monitor nicht gefunden hat. Fit prüfen, "
                                "Lebenslauf bauen und in deine Bewerbungen übernehmen.")}
{message}
<form method="post" action="/cv"><input type="hidden" name="token" value="{self.token}">
<input type="hidden" name="art" value="eigene">
<div class="card"><h2>Anzeige</h2>
<label>Anzeigentext (einfach aus der Anzeige kopieren, erste Zeile = Titel)</label>
<textarea name="text" rows="12" placeholder="Werkstudent Marketing (m/w/d)&#10;Deine Aufgaben: …"></textarea>
<label>… oder Link zur Anzeige (nur Firmen-Karriereseiten, nicht LinkedIn/StepStone/Indeed)</label>
<input name="url" placeholder="https://firma.de/jobs/…">
<div class="grid2"><div><label>Firma (Pflicht)</label><input name="firma" required></div>
<div><label>Link für die Bewerbungsliste (optional, bei Text)</label><input name="link"></div></div></div>
<div class="sticky row"><button{ki_attr}>Fit prüfen und Lebenslauf erstellen</button></div></form>"""
        return self.page("Eigene Stelle", body, "eigene")

    # --- Aktionen ---
    def ki_cv_an(self, cfg: dict) -> bool:
        return bool(ki.settings(cfg).get("lebenslauf", True)) and bool(ki.schluessel())

    def ki_lebenslauf(self, cfg: dict, stelle: dict | None, cache: Path | None = None,
                      sprache_: str = "de") -> tuple[dict | None, str]:
        """KI-Zuschnitt für einen Lebenslauf zu `stelle` (title, company, url, anforderungen). Ohne Schlüssel oder
        bei Fehlern: (None, Hinweis) – gebaut wird dann wie bisher regelbasiert."""
        if not stelle or not self.ki_cv_an(cfg):
            return None, ""
        try:
            cv, _ = load_cv_master(self.root)
            if sprache_ == "en":
                cv = sprache.cv_en(self.root) or cv
            if not cv:
                return None, ""
            anzeige = ki.anzeige(self.root, stelle.get("url") or "", fetcher_from(cfg), cache)
            return ki.lebenslauf(self.root, cfg, stelle, anzeige, cv, cfg["cv"]["max_projekte_zugeschnitten"]), ""
        except (ki.KiError, CvDataError) as exc:
            return None, f'<div class="card"><p class="muted">Lebenslauf ohne KI zugeschnitten: {esc(exc)}</p></div>'

    def make_cv(self, form: dict) -> bytes:
        cfg = load_config(self.root / "config.yaml")
        art = form.get("art", "")
        stelle, job_id, info = None, None, ""
        try:
            if art == "job":
                job_id = form.get("job_id", "")
            elif art == "eigene":
                stelle = self._eigene(form, cfg)
                info = ("In applications.csv eingetragen (Status: neu)." if stelle["eingetragen"]
                        else "Steht schon in applications.csv.")
                info += (" Anforderungen von der KI gelesen." if stelle.get("ki") else
                         " Anforderungen per Stichwort erkannt" + (" (für die KI-Prüfung: Einstellungen → KI)."
                                                                   if not ki.schluessel() else "."))
            hinweise: list = []
            detail = stelle
            if job_id:
                state = State(self.root / "state" / "seen.sqlite", readonly=True)
                detail = state.job_detail(job_id)
                state.close()
            zuschnitt, ki_info = self.ki_lebenslauf(cfg, detail)
            path = build(self.root, cfg, job_id or None, compile_pdf=self.compile_pdf, stelle=stelle,
                         hinweise=hinweise, ki_zuschnitt=zuschnitt)
        except (StelleError, CvBuildError, CvDataError) as exc:
            error = f'<div class="card err">{esc(exc)}</div>'
            return self.eigene(error) if art == "eigene" else self.index(error)
        if job_id:
            stelle = next((d for d in self.jobs() if d["id"].startswith(job_id)), None)
        rel = path.relative_to(self.root)
        weiter = ""
        if stelle:
            folder = bw.open_workspace(self.root, cfg, stelle)
            weiter = f'<a class="btn ghost" href="/bewerbung/{quote(folder.name)}">Weiter zur Bewerbung</a>'
        head = f"{esc(stelle['title'])} – {esc(stelle['company'])}" if stelle else "Allgemeiner Lebenslauf"
        fit_html = f"<p>{esc(stelle['fit_line'])}</p>" if stelle else ""
        link = (f'<a class="btn" href="/pdf/{quote(path.name)}" target="_blank" data-open>'
                f'{layout.icon("file", 16)}PDF öffnen</a>' if path.suffix == ".pdf" else "")
        body = f"""<h1>Fertig</h1><div class="card"><h2>{head}</h2>{fit_html}
<p class="ok">{esc(info)}</p><p class="muted">{esc(rel)}</p>
<div class="row">{link}{weiter}{self.form("/reveal", f'<input type="hidden" name="name" value="{esc(path.name)}">',
                                     "Im Finder zeigen", ghost=True)}
<a class="btn ghost" href="/">Zur Stellenliste</a></div></div>{ki_info}{pruefung_html(hinweise)}"""
        return self.page("Fertig", body, "eigene" if art == "eigene" else "stellen")

    def _eigene(self, form: dict, cfg: dict) -> dict:
        text, url = form.get("text", "").strip(), form.get("url", "").strip()
        firma, link = form.get("firma", "").strip() or None, form.get("link", "").strip() or None
        if not firma:
            raise StelleError("Bitte die Firma angeben.")
        if url and not text:
            job = from_url(url, fetcher_from(cfg), firma)
        elif text:
            stem = _slug(firma)[:40] or "stelle"
            path = self.root / "cv" / "stellen" / f"{stem}-{date.today().isoformat()}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n", encoding="utf-8")
            job = from_file(path, firma, link or url or None)
        else:
            raise StelleError("Bitte Anzeigentext einfügen oder einen Link angeben.")
        ask = ki.frage_funktion(self.root, cfg) if ki.schluessel() else None
        return prepare(job, self.root, cfg, ki_ask=ask)

    # --- Bewerbung je Stelle ---
    def bewerbung_open(self, job_id: str) -> str | None:
        stelle = next((d for d in self.jobs() if d["id"] == job_id), None)
        if stelle is None:
            return None
        return bw.open_workspace(self.root, load_config(self.root / "config.yaml"), stelle).name

    def bewerbung(self, slug: str, message: str = "") -> bytes | None:
        cfg = load_config(self.root / "config.yaml")
        folder = bw.workspace(self.root, cfg, slug)
        if folder is None:
            return None
        stelle = bw.meta(folder)
        data = bw.letter(folder)
        lang = sprache.fuer_bewerbung(folder)
        if data is None:   # erster Besuch: Entwurf aus der Vorlage
            bw.save_letter(folder, bw.draft(self.root, cfg, stelle, lang),
                           bw.ANREDE_EN if lang == "en" else bw.ANREDE, "")
            data = bw.letter(folder)
        try:
            cv, _ = load_cv_master(self.root)
        except CvDataError:
            cv = None
        job = Job(stelle["title"], stelle["company"], stelle["url"], "")
        fit.apply(job, stelle.get("anforderungen") or {}, covered_terms(cv or {}, cfg["fit"]["begriffe"]), cfg["fit"])
        e = erinnerungen.fuer_frist(stelle, cfg) if erinnerungen.verfuegbar() else None
        if e is not None and e.schluessel not in erinnerungen.eingetragen(self.root):
            message += (f'<div class="card info row" style="justify-content:space-between"><p>Frist am '
                        f'{date.fromisoformat(stelle["frist"]):%d.%m.%Y}. Erinnerung am {e.faellig:%d.%m.} um '
                        f'{e.faellig:%H:%M} eintragen?</p>' + self.form(
                            "/erinnern", f'<input type="hidden" name="art" value="bewerbung"><input type="hidden" '
                            f'name="slug" value="{esc(slug)}">', "In Erinnerungen", small=True) + '</div>')
        self._offline_cache = None
        frueher = gb.frueher_bei_firma(tracking.load(self.root / "applications.csv"), stelle["company"], stelle["url"])
        message = gb.frueher_html(frueher, stelle["company"]) + message
        ki_an = bool(ki.schluessel()) and self.ki_cv_an(cfg)
        anlagen = bw.anlagen(self.root, cfg)
        andere = [bw.meta(f).get("company", "") for f in bw.workspaces(self.root, cfg) if f != folder]
        design = designs.fuer_bewerbung(cfg, folder, stelle)
        punkte = abschicken.pruefen(folder, data, stelle, cfg, anlagen, andere,
                                    stelle.get("url") in self.offline_links(), design=design)
        ziel = f"/bewerbung/{quote(slug)}"
        anzeige_text, gesichert = bw.anzeige(folder)
        try:
            hat_en = sprache.cv_en(self.root) is not None
        except CvDataError:
            hat_en = True          # Fehler zeigt der Bau des Lebenslaufs an
        design_html = (designs.auswahl_html(self.token, ziel, design, esc)
                       + sprache.auswahl_html(self.token, ziel, lang, sprache.erkennen(anzeige_text), hat_en,
                                              bool(ki.schluessel()), esc)
                       + ki_extra.fit_erklaert_html(self.root, stelle, ziel, self.token, bool(ki.schluessel()), esc)
                       + (f'<div class="card"><h2>Gespräch üben</h2><p class="muted">Die KI stellt dir Fragen, wie sie '
                          f'im Gespräch für diese Stelle kommen könnten, und gibt nach jeder Antwort Rückmeldung.</p>'
                          f'<a class="btn ghost small" href="/uebung?link={quote(stelle.get("url") or "", safe="")}">'
                          f'Übungsgespräch</a></div>' if ki.schluessel() and stelle.get("url") else "")
                       + gbw.anzeige_karte(self.token, ziel, stelle, anzeige_text, gesichert)
                       + self.portal_karte(folder, cfg, stelle, data, lang, ziel))
        body = gbw.render(slug, stelle, data, fit_line(job), bw.files(folder), anlagen, self.token, message, ki_an,
                          abschicken.render(punkte, self.token, ziel, bool(ki.schluessel())), design_html)
        return self.page("Bewerbung", body, "bewerbungen", portal.CSS + gbw.CSS)

    def portal_karte(self, folder: Path, cfg: dict, stelle: dict, data: dict, lang: str, ziel: str) -> str:
        en = lang == "en"
        try:
            cv = (sprache.cv_en(self.root) if en else None) or load_cv_master(self.root)[0] or {}
        except CvDataError:
            cv = {}
        profile = bw.load_profile(self.root) or {}
        zeitraum = None if en else bw.zeitraum_aus(profile, suchprofil.get(cfg, stelle.get("profil")))
        gemerkt = portal.gekuerzt(folder)
        grenze = int(gemerkt.get("_grenze") or 500)
        return portal.render(portal.felder(profile, cv, data, zeitraum, en), self.token, ziel, grenze,
                             bool(ki.schluessel()), gemerkt) + f"<script>{portal.JS}</script>"

    def bewerbung_post(self, slug: str, form: dict) -> bytes | None:
        cfg = load_config(self.root / "config.yaml")
        folder = bw.workspace(self.root, cfg, slug)
        if folder is None:
            return None
        aktion = form.get("aktion", "speichern")
        if aktion == "verwerfen":
            stelle = bw.meta(folder)
            target = bw.discard(folder, self.trash)
            msg = f"Bewerbung „{stelle['title']}“ verworfen; der Ordner liegt im Papierkorb ({target.name})."
            if form.get("ausblenden"):
                path = self.root / "applications.csv"
                rows = tracking.load(path)
                gb.mark(rows, {"title": stelle["title"], "company": stelle["company"], "url": stelle["url"]},
                        "ausblenden", date.today())
                tracking.save(path, rows)
                msg += " Die Stelle ist ausgeblendet."
            return self.index(f'<div class="card"><p class="ok">{esc(msg)}</p></div>')
        if aktion == "ordner":
            subprocess.run(["open", str(folder)])
            return self.bewerbung(slug)
        if aktion == "neu":
            bw.save_letter(folder, bw.draft(self.root, cfg, bw.meta(folder), sprache.fuer_bewerbung(folder)),
                           form.get("anrede", ""), form.get("empfaenger", ""))
            return self.bewerbung(slug, '<div class="card"><p class="ok">Neuer Entwurf aus der Vorlage.</p></div>')
        if aktion == "ki":
            return self.bewerbung_ki(slug, folder, cfg, form)
        if aktion == "vorbereiten":
            return self.bewerbung_vorbereiten(slug, folder, cfg, form)
        if aktion in ("fit_erklaeren", "portal_frage"):
            return self.bewerbung_ki_extra(slug, folder, cfg, form, aktion)
        if aktion == "sprache":
            try:
                sprache.waehlen(folder, form.get("sprache", ""))
            except sprache.SpracheError as exc:
                return self.bewerbung(slug, f'<div class="card err">{esc(exc)}</div>')
            lang = form["sprache"]
            data = bw.letter(folder) or {}
            stelle = bw.meta(folder)
            info = ""
            if data.get("text") in (bw.draft(self.root, cfg, stelle, "de"), bw.draft(self.root, cfg, stelle, "en")):
                bw.save_letter(folder, bw.draft(self.root, cfg, stelle, lang),
                               bw.ANREDE_EN if lang == "en" else bw.ANREDE, data.get("empfaenger", ""))
                info = " Der noch unveränderte Entwurf ist jetzt in dieser Sprache."
            elif lang == "en":
                info = " Dein Anschreiben ist noch deutsch – „Entwurf mit KI“ schreibt es auf Englisch neu."
            return self.bewerbung(slug, f'<div class="card"><p class="ok">Sprache: {sprache.SPRACHEN[lang]}.{info} '
                                        f'„Speichern und Mappe bauen“ erzeugt die PDFs neu.</p></div>')
        if aktion == "cv_uebersetzen":
            try:
                cv, _ = load_cv_master(self.root)
                if not cv:
                    raise ki.KiError("Keine cv_master.yaml – es gibt nichts zu übersetzen.")
                pfad = sprache.uebersetzen(self.root, cfg, cv)
            except (ki.KiError, sprache.SpracheError, CvDataError) as exc:
                return self.bewerbung(slug, f'<div class="card err">{esc(exc)}</div>')
            return self.bewerbung(slug, f'<div class="card"><p class="ok">Master-CV übersetzt: {esc(pfad.name)}. Bitte '
                                        f'einmal durchlesen – unter <a href="/dateien">Dateien</a> kannst du '
                                        f'Formulierungen anpassen.</p></div>')
        if aktion == "anzeige_sichern":
            text = bw.anzeige_sichern(self.root, cfg, folder)
            return self.bewerbung(slug, '<div class="card"><p class="ok">Anzeige im Bewerbungsordner gesichert.</p>'
                                        '</div>' if text else
                                  '<div class="card err">Die Anzeige ließ sich nicht abrufen (nicht mehr online, '
                                  'robots.txt oder eine Seite wie LinkedIn, die die App nicht abruft). Du kannst den '
                                  'Text unten selbst einfügen.</div>')
        if aktion == "anzeige_eintragen":
            if not form.get("anzeige", "").strip():
                return self.bewerbung(slug, '<div class="card err">Bitte den Anzeigentext einfügen.</div>')
            bw.anzeige_eintragen(folder, form["anzeige"])
            return self.bewerbung(slug, '<div class="card"><p class="ok">Anzeigentext gespeichert.</p></div>')
        if aktion in ("portal_grenze", "portal_ki"):
            data = portal.gekuerzt(folder)
            grenze = int(form.get("grenze") or 500) if str(form.get("grenze", "")).isdigit() else 500
            data["_grenze"] = grenze if grenze in portal.GRENZEN else 500
            (folder / portal.DATEI).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            if aktion == "portal_ki":
                lang = sprache.fuer_bewerbung(folder)
                feld = form.get("feld", "")
                felder = {f["key"]: f["wert"] for f in portal.felder(
                    bw.load_profile(self.root) or {},
                    (sprache.cv_en(self.root) if lang == "en" else None) or load_cv_master(self.root)[0] or {},
                    bw.letter(folder), None, lang == "en")}
                if feld not in ("kurzprofil", "motivation") or not felder.get(feld):
                    return self.bewerbung(slug)
                try:
                    portal.ki_kuerzen(self.root, cfg, folder, feld, felder[feld], data["_grenze"], lang == "en")
                except ki.KiError as exc:
                    return self.bewerbung(slug, f'<div class="card err">{esc(exc)}</div>')
            return self.bewerbung(slug)
        if aktion == "design":       # eigenes Formular: nur das Design dieser Bewerbung
            try:
                designs.waehlen(folder, form.get("design", ""))
            except ValueError as exc:
                return self.bewerbung(slug, f'<div class="card err">{esc(exc)}</div>')
            name = designs.DESIGNS[form["design"]]["name"]
            return self.bewerbung(slug, f'<div class="card"><p class="ok">Design „{esc(name)}“ gewählt. „Speichern und '
                                        f'Mappe bauen“ erzeugt die PDFs neu.</p></div>')
        if aktion == "ki_pruefen":   # eigenes Formular ohne Textfeld: nichts speichern
            stelle = bw.meta(folder)
            try:
                anzeige = ki.anzeige(self.root, stelle.get("url") or "", fetcher_from(cfg), folder / "anzeige.txt")
                ergebnis = abschicken.ki_pruefen(self.root, cfg, (bw.letter(folder) or {}).get("text", ""), stelle,
                                                 anzeige)
            except ki.KiError as exc:
                return self.bewerbung(slug, f'<div class="card err">{esc(exc)}</div>')
            return self.bewerbung(slug, abschicken.ki_html(ergebnis))
        bw.save_letter(folder, form.get("text", ""), form.get("anrede", ""), form.get("empfaenger", ""))
        hinweise: dict[str, list] = {}
        if aktion == "mappe":
            bw.anzeige_sichern(self.root, cfg, folder)      # Anzeige für später sichern (Gespräch, Nachfassen)
        zuschnitt, ki_info = (self.ki_lebenslauf(cfg, bw.meta(folder), folder / "anzeige.txt",
                                                 sprache.fuer_bewerbung(folder))
                              if aktion in ("lebenslauf", "mappe") else (None, ""))
        try:
            if aktion == "anschreiben":
                done = [bw.build_anschreiben(self.root, cfg, folder, hinweise=hinweise.setdefault("anschreiben", [])
                                             ).name]
            elif aktion == "lebenslauf":
                done = [bw.build_lebenslauf(self.root, cfg, folder, hinweise.setdefault("lebenslauf", []),
                                            zuschnitt).name]
            elif aktion == "mappe":
                mappe, fehlend = bw.build_mappe(self.root, cfg, folder, hinweise=hinweise, ki_zuschnitt=zuschnitt)
                done = [mappe.name]
                if fehlend:
                    done.append("ohne " + ", ".join(fehlend) + " (Datei fehlt)")
            else:
                return self.bewerbung(slug, '<div class="card"><p class="ok">Gespeichert.</p></div>')
        except bw.BewerbungError as exc:
            return self.bewerbung(slug, f'<div class="card err">{esc(exc)}</div>')
        first = done[0]
        open_link = f' <a href="/bewerbung/{quote(slug)}/{quote(first)}" target="_blank" data-open>öffnen</a>'
        pruefung = "".join(pruefung_html(h, "Anschreiben" if was == "anschreiben" else "Lebenslauf")
                           for was, h in hinweise.items())
        return self.bewerbung(slug, f'<div class="card"><p class="ok">Gespeichert und erstellt: {esc(" · ".join(done))}.'
                                    f'{open_link}</p></div>{ki_info}{pruefung}')

    def bewerbung_ki(self, slug: str, folder: Path, cfg: dict, form: dict) -> bytes:
        """Anschreiben-Entwurf mit KI aus Anzeige und Master-CV; der bisherige Text bleibt als .bak daneben."""
        stelle = bw.meta(folder)
        en = sprache.fuer_bewerbung(folder) == "en"
        try:
            text, anzeige = self._ki_anschreiben(cfg, folder, stelle, en)
        except (ki.KiError, CvDataError) as exc:
            return self.bewerbung(slug, f'<div class="card err">{esc(exc)}</div>')
        alt = folder / "anschreiben.json"
        if alt.is_file():
            alt.with_name("anschreiben.json.bak").write_text(alt.read_text(encoding="utf-8"), encoding="utf-8")
        anrede = form.get("anrede", "")
        if en and anrede.strip() in ("", bw.ANREDE):
            anrede = bw.ANREDE_EN
        bw.save_letter(folder, text, anrede, form.get("empfaenger", ""))
        data = bw.letter(folder)
        andere = [bw.meta(f).get("company", "") for f in bw.workspaces(self.root, cfg) if f != folder]
        quelle = ("aus Anzeigentext und Master-CV" if anzeige else
                  "nur aus Titel und erkannten Anforderungen – die Anzeige selbst war nicht lesbar")
        return self.bewerbung(slug, f'<div class="card"><p class="ok">KI-Entwurf erstellt ({quelle}). Bitte lesen, '
                                    f'Platzhalter ersetzen und anpassen – der vorige Text liegt als '
                                    f'anschreiben.json.bak im Ordner.</p></div>'
                                    + pruefung_html(bw.anschreiben_check.check_text(data, stelle, cfg, andere),
                                                    "Anschreiben"))

    def bewerbung_ki_extra(self, slug: str, folder: Path, cfg: dict, form: dict, aktion: str) -> bytes:
        """Fit erklären bzw. eine Freitextfrage aus dem Bewerbungsportal beantworten (ki_extra.py)."""
        stelle = bw.meta(folder)
        en = sprache.fuer_bewerbung(folder) == "en"
        try:
            cv, _ = load_cv_master(self.root)
            if en:
                cv = sprache.cv_en(self.root) or cv
            if not cv:
                raise ki.KiError("Keine cv_master.yaml.")
            anzeige = ki.anzeige(self.root, stelle.get("url") or "", fetcher_from(cfg), folder / "anzeige.txt")
            if aktion == "fit_erklaeren":
                job = Job(stelle["title"], stelle["company"], stelle["url"], "")
                fit.apply(job, stelle.get("anforderungen") or {}, covered_terms(cv, cfg["fit"]["begriffe"]), cfg["fit"])
                ki_extra.fit_erklaeren(self.root, cfg, stelle, job.fit_passt, job.fit_fehlt, job.fit, anzeige, cv)
                return self.bewerbung(slug)
            frage = form.get("frage", "").strip()
            if not frage:
                return self.bewerbung(slug, '<div class="card err">Bitte die Frage aus dem Portal einfügen.</div>')
            daten = portal.gekuerzt(folder)
            grenze = int(daten.get("_grenze") or 500)
            antwort = ki_extra.portal_antwort(self.root, cfg, frage, grenze, stelle, anzeige, cv,
                                              (bw.letter(folder) or {}).get("text", ""), en)
            daten.setdefault("fragen", []).insert(0, {"frage": frage[:600], "antwort": antwort})
            (folder / portal.DATEI).write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
            return self.bewerbung(slug)
        except (ki.KiError, CvDataError) as exc:
            return self.bewerbung(slug, f'<div class="card err">{esc(exc)}</div>')

    def _ki_anschreiben(self, cfg: dict, folder: Path, stelle: dict, en: bool) -> tuple[str, str]:
        """(KI-Anschreiben, Anzeigentext) – auf Englisch mit dem englischen Master-CV."""
        cv, _ = load_cv_master(self.root)
        if en:
            cv = sprache.cv_en(self.root) or cv
        if not cv:
            raise ki.KiError("Keine cv_master.yaml – ohne Lebenslauf kann die KI nichts belegen.")
        anzeige = ki.anzeige(self.root, stelle.get("url") or "", fetcher_from(cfg), folder / "anzeige.txt")
        ziel = suchprofil.get(cfg, stelle.get("profil"))
        text = ki.anschreiben(self.root, cfg, stelle, anzeige, cv, ziel,
                              bw.zeitraum_aus(bw.load_profile(self.root) or {}, ziel), englisch=en)
        return text, anzeige

    def bewerbung_vorbereiten(self, slug: str, folder: Path, cfg: dict, form: dict) -> bytes:
        """„Alles vorbereiten“: Text speichern, Anzeige sichern, Anschreiben mit KI (nur solange es noch der
        unveränderte Entwurf ist), Lebenslauf zuschneiden und Mappe bauen – ein Klick statt vier."""
        stelle = bw.meta(folder)
        lang = sprache.fuer_bewerbung(folder)
        bw.save_letter(folder, form.get("text", ""), form.get("anrede", ""), form.get("empfaenger", ""))
        schritte, hinweise_html = [], ""
        anzeige = bw.anzeige_sichern(self.root, cfg, folder)
        schritte.append("Anzeige gesichert" if anzeige else "Anzeige nicht abrufbar (Text ggf. unten selbst einfügen)")
        data = bw.letter(folder) or {}
        unveraendert = data.get("text") == bw.draft(self.root, cfg, stelle, lang)
        if unveraendert and ki.schluessel():
            try:
                text, _ = self._ki_anschreiben(cfg, folder, stelle, lang == "en")
                anrede = data.get("anrede", "")
                if lang == "en" and anrede in ("", bw.ANREDE):
                    anrede = bw.ANREDE_EN
                bw.save_letter(folder, text, anrede, data.get("empfaenger", ""))
                schritte.append("Anschreiben mit KI entworfen")
            except (ki.KiError, CvDataError) as exc:
                schritte.append(f"Anschreiben aus der Vorlage (KI: {exc})")
        elif unveraendert:
            schritte.append("Anschreiben aus der Vorlage (für einen KI-Entwurf: KI in den Einstellungen einrichten)")
        else:
            schritte.append("dein Anschreiben übernommen")
        zuschnitt, ki_info = self.ki_lebenslauf(cfg, stelle, folder / "anzeige.txt", lang)
        hinweise: dict[str, list] = {}
        try:
            mappe, fehlend = bw.build_mappe(self.root, cfg, folder, hinweise=hinweise, ki_zuschnitt=zuschnitt)
        except bw.BewerbungError as exc:
            return self.bewerbung(slug, f'<div class="card err">Vorbereitet: {esc(" · ".join(schritte))}. Die Mappe '
                                        f'ließ sich nicht bauen: {esc(exc)}</div>')
        schritte.append("Lebenslauf " + ("mit KI " if zuschnitt else "") + "zugeschnitten")
        schritte.append(f"Mappe gebaut{' (ohne ' + ', '.join(fehlend) + ')' if fehlend else ''}")
        offen = len(bw.placeholders((bw.letter(folder) or {}).get("text", "")))
        hinweise_html = "".join(pruefung_html(h, "Anschreiben" if was == "anschreiben" else "Lebenslauf")
                                for was, h in hinweise.items())
        return self.bewerbung(slug, f'<div class="card"><p class="ok">Alles vorbereitet: {esc(" · ".join(schritte))}. '
                                    f'<a href="/bewerbung/{quote(slug)}/{quote(mappe.name)}" target="_blank" '
                                    f'data-open>Mappe öffnen</a></p><p class="muted">Bitte das Anschreiben lesen'
                                    f'{f" und {offen} Platzhalter ersetzen" if offen else ""}, dann „Speichern und Mappe '
                                    f'bauen“. Für Online-Portale stehen die Felder unten unter „Für Bewerbungsportale“ '
                                    f'zum Kopieren bereit.</p></div>{ki_info}{hinweise_html}{teilen.erste_mappe(self.root, i18n.sprache(cfg))}')

    def resolve_file(self, url_path: str) -> Path | None:
        """Lokale Datei zu einem Link der Oberfläche (nur PDFs aus cv/out, Bewerbungsordnern, Unterlagen)."""
        from urllib.parse import unquote
        parts = [unquote(p) for p in url_path.split("?")[0].strip("/").split("/")]
        if len(parts) == 2 and parts[0] == "pdf":
            return self.pdf_path(parts[1])
        if len(parts) == 3 and parts[0] == "bewerbung":
            return self.bewerbung_file(parts[1], parts[2])
        if len(parts) == 3 and parts[0] == "unterlagen" and parts[1].isdigit():
            return gu.file_path(self.root, load_config(self.root / "config.yaml"), int(parts[1]), parts[2])
        if parts == ["master", "nachweis"]:
            pfad = (parse_qs(url_path.partition("?")[2]).get("pfad") or [""])[0]
            return gu.nachweis_path(self.root, load_config(self.root / "config.yaml"), pfad)
        return None

    def open_file(self, url_path: str) -> bool:
        """PDF in Vorschau (Standard-App) öffnen – im App-Fenster schöner als eine PDF-Ansicht im Fenster."""
        path = self.resolve_file(url_path)
        if path is None:
            return False
        subprocess.run(["open", str(path)])
        return True

    def bewerbung_file(self, slug: str, name: str) -> Path | None:
        folder = bw.workspace(self.root, load_config(self.root / "config.yaml"), slug)
        if folder is None or not bw.FILE_RE.match(name) or not (folder / name).is_file():
            return None
        return folder / name

    # --- Profil und Unterlagen ---
    def profil(self, message: str = "", form: dict | None = None) -> bytes:
        return self.page("Profil", gp.render(self.root, self.token, message, form), "profil")

    def profil_post(self, form: dict) -> bytes:
        try:
            gp.update(self.root, form)
        except gp.ProfilError as exc:
            return self.profil(f'<div class="card err">Nicht gespeichert: {esc(exc)}</div>', form)
        return self.profil('<div class="card"><p class="ok">Gespeichert. Gilt sofort für Lebenslauf und Anschreiben.'
                           '</p></div>')

    def unterlagen(self, message: str = "") -> bytes:
        return self.page("Unterlagen", gu.render(self.root, load_config(self.root / "config.yaml"), self.token, message),
                         "unterlagen")

    def unterlagen_upload(self, target: str, uploads: dict) -> bytes:
        files = uploads.get("datei") or []
        if not files:
            return self.unterlagen('<div class="card err">Keine Datei ausgewählt.</div>')
        cfg = load_config(self.root / "config.yaml")
        try:
            if target == "foto":
                saved = [gu.save_foto(self.root, files)]
            elif target.isdigit() and int(target) < len(gu.slots(cfg)):
                saved = gu.save_anlage(self.root, cfg, int(target), files)
            else:
                return self.unterlagen('<div class="card err">Unbekanntes Ziel.</div>')
        except gu.UploadError as exc:
            return self.unterlagen(f'<div class="card err">{esc(exc)}</div>')
        return self.unterlagen(f'<div class="card"><p class="ok">Gespeichert: {esc(", ".join(saved))}</p></div>')

    def nachweis_upload(self, form: dict, uploads: dict) -> bytes:
        """Zertifikats-Nachweis aus dem Master-CV-Editor (fetch); Antwort als JSON."""
        files = uploads.get("datei") or []
        if not files or not files[0][1]:
            return json.dumps({"fehler": "Keine Datei ausgewählt."}).encode()
        try:
            pfad = gu.save_nachweis(self.root, load_config(self.root / "config.yaml"), form.get("name", ""),
                                    files[0][0], files[0][1])
        except gu.UploadError as exc:
            return json.dumps({"fehler": str(exc)}, ensure_ascii=False).encode()
        return json.dumps({"pfad": pfad}, ensure_ascii=False).encode()

    def unterlagen_delete(self, form: dict) -> bytes:
        cfg = load_config(self.root / "config.yaml")
        slot = form.get("slot", "")
        ok = slot.isdigit() and gu.delete_anlage(self.root, cfg, int(slot), form.get("name", ""))
        msg = f'„{form.get("name")}“ entfernt.' if ok else "Datei nicht gefunden."
        return self.unterlagen(f'<div class="card"><p class="{"ok" if ok else "err"}">{esc(msg)}</p></div>')

    # --- Firmen ---
    def firmen(self, message: str = "") -> bytes:
        cfg = load_config(self.root / "config.yaml")
        days = (cfg.get("gui") or {}).get("manuell_pruefen_tage", 14)
        state = State(self.root / "state" / "seen.sqlite", readonly=True)
        details = state.job_details(limit=1000)
        state.close()
        vorschlaege = gf.suggestions(self.root, details, cfg["filter"].get("ausschluss_firmen") or [])
        liste, status, behoben = gf.beobachten(self.root, cfg)
        try:
            from .initiativ_liste import kandidaten
            from .models import normalize
            kand = kandidaten(load_companies(self.root / "companies.yaml"), None,
                              {normalize(d["company"]) for d in details}, cfg)
        except (OSError, ValueError, KeyError):
            kand = []
        bewerbungen = {r.get("firma", "").lower(): r.get("status", "") for r in tracking.load(self.root / "applications.csv")
                       if r.get("typ") == "Initiativ" and r.get("status")}
        message += firmen_finder.karte(self.root, self.token, bool(ki.schluessel()))
        message += gf.initiativ_karte(kand, bewerbungen)
        return self.page("Firmen", gf.render(self.root, self.token, date.today(), days, message, vorschlaege,
                                             liste, cfg, status, behoben, {tip.firma for tip, _ in kand}), "firmen")

    def firmen_finden(self, form: dict) -> bytes:
        """Liste passender Firmen mit KI (firmen_finder.py)."""
        cfg = load_config(self.root / "config.yaml")
        try:
            cv, _ = load_cv_master(self.root)
            anzahl = int(form.get("anzahl") or 20) if str(form.get("anzahl", "")).isdigit() else 20
            liste = firmen_finder.finden(self.root, cfg, cv or {}, form.get("wunsch", ""), anzahl)
        except (ki.KiError, CvDataError) as exc:
            return self.firmen(f'<div class="card err">{esc(exc)}</div>')
        return self.firmen(f'<div class="card"><p class="ok">{len(liste)} passende Firmen gefunden – unten unter '
                           f'„Passende Firmen finden“. Karriereseite prüfen, dann hinzufügen.</p></div>')

    def firmen_ignorieren(self, form: dict) -> bytes:
        gf.ignore(self.root, form.get("name", ""))
        return self.firmen(f'<div class="card"><p class="ok">„{esc(form.get("name"))}“ wird nicht mehr '
                           f'vorgeschlagen.</p></div>')

    def firmen_neu(self, form: dict) -> bytes:
        try:
            name = gf.add(self.root, form)
        except gf.FirmaError as exc:
            return self.firmen(f'<div class="card err">Nicht hinzugefügt: {esc(exc)}</div>')
        return self.firmen(f'<div class="card"><p class="ok">„{esc(name)}“ hinzugefügt. Die Pipeline erkennt die '
                           f'Stellenquelle beim nächsten Lauf.</p></div>')

    def firmen_aktiv(self, form: dict) -> bytes:
        aktiv = bool(form.get("aktiv"))
        ok = gf.set_active(self.root, form.get("name", ""), aktiv)
        msg = f'„{form.get("name")}“ {"aktiviert" if aktiv else "deaktiviert"}.' if ok else "Firma nicht gefunden."
        return self.firmen(f'<div class="card"><p class="{"ok" if ok else "err"}">{esc(msg)}</p></div>')

    # --- Erinnerungen (Apple) ---
    def offene_fristen(self, cfg: dict, jobs: list[dict]) -> list:
        if not erinnerungen.verfuegbar():
            return []
        done = erinnerungen.eingetragen(self.root)
        return [e for d in jobs if (e := erinnerungen.fuer_frist(d, cfg)) and e.schluessel not in done]

    def erinnern(self, form: dict) -> bytes:
        cfg = load_config(self.root / "config.yaml")
        art = form.get("art", "")
        if art == "besuch":
            days = (cfg.get("gui") or {}).get("manuell_pruefen_tage", 14)
            entry = next((m for m in gf.manual_entries(self.root) if m["name"] == form.get("name")), None)
            todo = [erinnerungen.fuer_besuch(entry["name"], entry["url"],
                                             gf.next_visit(self.root, entry["name"], date.today(), days), cfg)] \
                if entry else []
            back = self.firmen
        elif art == "bewerbung":
            folder = bw.workspace(self.root, cfg, form.get("slug", ""))
            todo = [e for e in [erinnerungen.fuer_frist(bw.meta(folder), cfg)] if e] if folder else []
            back = (lambda msg: self.bewerbung(folder.name, msg)) if folder else self.index
        else:   # frist (eine Stelle) oder fristen (alle offenen)
            apps = tracking.load(self.root / "applications.csv")
            hidden = {r.get("link") for r in apps if r.get("status") == gb.HIDDEN}
            jobs = [d for d in self.jobs() if d["url"] not in hidden]
            if art == "frist":
                jobs = [d for d in jobs if d["id"] == form.get("job_id")]
            todo = self.offene_fristen(cfg, jobs)
            back = self.index
        if not todo:
            return back('<div class="card err">Nichts einzutragen (keine offene Frist bzw. Eintrag nicht gefunden).'
                        '</div>')
        neu, fehler = [], ""
        for e in todo:
            try:
                if erinnerungen.anlegen(self.root, cfg, e) == "neu":
                    neu.append(e)
            except erinnerungen.ErinnerungError as exc:
                fehler = str(exc)
                break
        liste = erinnerungen.settings(cfg)["liste"]
        msg = ""
        if neu:
            wann = ", ".join(f"{e.faellig:%d.%m.}" for e in neu[:5]) + (" …" if len(neu) > 5 else "")
            msg += (f'<div class="card"><p class="ok">{len(neu)} Erinnerung(en) in der Liste „{esc(liste)}“ angelegt '
                    f'({wann}).</p></div>')
        elif not fehler:
            msg += f'<div class="card"><p class="ok">Steht schon in der Liste „{esc(liste)}“.</p></div>'
        if fehler:
            msg += f'<div class="card err">{esc(fehler)}</div>'
        return back(msg)

    def firmen_besucht(self, form: dict) -> bytes:
        gf.mark_visited(self.root, form.get("name", ""), date.today())
        return self.firmen(f'<div class="card"><p class="ok">„{esc(form.get("name"))}“ als besucht markiert.</p></div>')

    # --- Bericht ---
    def bericht(self) -> bytes:
        return self.page("Bericht", gbe.seite(self.root), "bericht", gbe.CSS)

    def bericht_tag(self, stem: str) -> bytes | None:
        body = gbe.seite(self.root, stem)
        return None if body is None else self.page("Bericht", body, "bericht", gbe.CSS)

    # --- Lücken ---
    def _lernplan_karte(self, nur_traum: bool) -> str:
        plan = ki.gespeicherter_lernplan(self.root)
        knopf = (f'<form method="post" action="/luecken/lernplan" class="row" style="margin-top:10px">'
                 f'<input type="hidden" name="token" value="{self.token}">'
                 f'<input type="hidden" name="traum" value="{"1" if nur_traum else ""}">'
                 f'<button class="{"ghost " if plan else ""}small" data-ki="KI erstellt deinen Lernplan …">'
                 f'{"Lernplan neu erstellen" if plan else "Lernplan mit KI erstellen"}</button>'
                 f'<span class="muted">Aus deinen teuersten Lücken und deinem Master-CV.</span></form>'
                 if ki.schluessel() else
                 '<p class="muted"><a href="/einstellungen#ki">Lernplan mit KI: API-Schlüssel hinterlegen</a></p>')
        if not plan:
            return f'<div class="card"><h2>Lernplan</h2>{knopf}</div>'
        stand = f"{plan['datum'][8:10]}.{plan['datum'][5:7]}.{plan['datum'][:4]}"
        return (f'<div class="card"><div class="head"><h2>Lernplan</h2><span class="muted">von der KI, Stand {stand}'
                f'</span></div><div class="ki-text">{ki.als_html(plan["text"], esc)}</div>{knopf}</div>')

    def _fit_begriffe_karte(self, cfg: dict) -> str:
        """Vorschläge der KI für neue Fit-Begriffe übernehmen oder ausblenden, eigene Begriffe ergänzen."""
        try:
            state = State(self.root / "state" / "seen.sqlite", readonly=True)
            gespeichert = Counter(json.loads(state.get_meta(fb.META) or "{}"))
            state.close()
        except Exception:
            gespeichert = Counter()
        berichte = sorted((self.root / "reports").glob("*.md")) if (self.root / "reports").is_dir() else []
        bericht = fb.aus_bericht(berichte[-1].read_text(encoding="utf-8")) if berichte else Counter()
        offen = fb.offen(gespeichert, bericht, cfg["fit"]["begriffe"], fb.ignoriert(self.root))[:15]
        hidden = lambda aktion, term: (f'<input type="hidden" name="token" value="{self.token}">'  # noqa: E731
                                       f'<input type="hidden" name="aktion" value="{aktion}">'
                                       f'<input type="hidden" name="term" value="{esc(term)}">')
        zeilen = "".join(
            f'<tr><td><b>{esc(term)}</b> <span class="muted">in {n} Anzeige{"n" if n != 1 else ""}</span></td>'
            f'<td class="act"><form method="post" action="/fitbegriffe" style="display:inline">{hidden("uebernehmen", term)}'
            f'<button class="small">Übernehmen</button></form> <form method="post" action="/fitbegriffe" '
            f'style="display:inline">{hidden("ignorieren", term)}<button class="ghost small">Ausblenden</button></form>'
            f'</td></tr>' for term, n in offen)
        vorschlaege = (f'<p class="muted">Diese Anforderungen fand die KI in Anzeigen, sie zählen aber noch nicht im Fit. '
                       f'„Übernehmen“ macht sie zum Fit-Begriff; belegt dein Master-CV sie (z. B. Deutsch unter '
                       f'Sprachen), steigt dein Fit.</p><table>{zeilen}</table>' if zeilen else
                       '<p class="muted">Gerade keine neuen Vorschläge der KI.</p>')
        return f"""<div class="card" id="fitbegriffe"><h2>Fit-Begriffe</h2>{vorschlaege}
<form method="post" action="/fitbegriffe" class="grid2" style="align-items:end;margin-top:12px">
<input type="hidden" name="token" value="{self.token}"><input type="hidden" name="aktion" value="neu">
<div><label for="fb-term">Eigener Begriff</label><input id="fb-term" name="term" placeholder="z. B. SAP" required></div>
<div><label for="fb-syn">Andere Schreibweisen (optional, mit Komma)</label>
<input id="fb-syn" name="synonyme" placeholder="z. B. sap s/4hana, sap erp"></div>
<div><button>Hinzufügen</button></div></form>
<p class="muted">Gilt ab dem nächsten Lauf; gespeicherte Stellen werden danach nach und nach neu bewertet.
<a href="/einstellungen/datei?name=config.yaml&amp;suche=%20%20begriffe%3A">Alle Fit-Begriffe als Datei bearbeiten</a></p>
</div>"""

    def fitbegriffe(self, form: dict) -> bytes:
        cfg = load_config(self.root / "config.yaml")
        term, aktion = form.get("term", "").strip(), form.get("aktion", "")
        if aktion == "ignorieren":
            fb.ignorieren(self.root, term)
            return self.luecken(message=f'<div class="card"><p class="ok">„{esc(term)}“ ausgeblendet.</p></div>')
        try:
            synonyme = form.get("synonyme", "").split(",") if aktion == "neu" else []
            fb.hinzufuegen(self.root, term, synonyme, cfg["fit"]["begriffe"])
        except (fb.BegriffError, gw.WartungError) as exc:
            return self.luecken(message=f'<div class="card err">{esc(exc)}</div>')
        ergebnis = sync(self.root)
        hoch = ("Zu GitHub hochgeladen." if ergebnis.ok else
                f"Hochladen klappte nicht ({ergebnis.message}); beim nächsten Synchronisieren erneut.")
        return self.luecken(message=f'<div class="card"><p class="ok">„{esc(term)}“ ist jetzt ein Fit-Begriff. {esc(hoch)} '
                                    f'Ab dem nächsten Lauf zählt er; gespeicherte Stellen werden nach und nach neu '
                                    f'bewertet.</p></div>')

    def luecken_kenntnis(self, form: dict) -> bytes:
        """Begriff aus der Lücken-Auswertung mit einem Klick als Kenntnis in den Master-CV."""
        cfg = load_config(self.root / "config.yaml")
        term = form.get("term", "")
        if term not in cfg["fit"]["begriffe"]:
            return self.luecken(message='<div class="card err">Unbekannter Begriff.</div>')
        try:
            text = gm.kenntnis_speichern(self.root, term, form.get("level", ""), cfg["fit"]["begriffe"][term] or [])
        except CvDataError as exc:
            return self.luecken(message=f'<div class="card err">{esc(exc)}</div>')
        return self.luecken(message=f'<div class="card"><p class="ok">{esc(text)} Fit und Lücken sind schon neu '
                                    f'berechnet; hochgeladen wird beim Synchronisieren.</p></div>')

    def lernplan(self, form: dict) -> bytes:
        cfg = load_config(self.root / "config.yaml")
        nur_traum = bool(form.get("traum"))
        state = State(self.root / "state" / "seen.sqlite", readonly=True)
        details = state.job_details(limit=1000)
        state.close()
        hidden = {r["link"] for r in tracking.load(self.root / "applications.csv") if r.get("status") == gb.HIDDEN}
        details = [d for d in details if d["url"] not in hidden]
        if nur_traum:
            traum_cfg = cfg.get("traumprofil") or {}
            details = [d for d in details if traumjob.classify(d["title"], " ".join(d["anforderungen"]), traum_cfg)[0]]
        try:
            cv, _ = load_cv_master(self.root)
            _, rows = gl.analyse(details, covered_terms(cv or {}, cfg["fit"]["begriffe"]), cfg["fit"])
            ki.lernplan(self.root, cfg, rows, cv or {}, lernpfade.load(self.root))
        except (ki.KiError, CvDataError) as exc:
            return self.luecken(nur_traum, f'<div class="card err">{esc(exc)}</div>')
        return self.luecken(nur_traum, '<div class="card"><p class="ok">Lernplan erstellt (oben). Was du davon '
                                       'umsetzt, trägst du im Master-CV als Projekt oder Zertifikat ein – dann steigt '
                                       'dein Fit.</p></div>')

    def luecken(self, nur_traum: bool = False, message: str = "") -> bytes:
        cfg = load_config(self.root / "config.yaml")
        state = State(self.root / "state" / "seen.sqlite", readonly=True)
        details = state.job_details(limit=1000)
        state.close()
        hidden = {r["link"] for r in tracking.load(self.root / "applications.csv") if r.get("status") == gb.HIDDEN}
        details = [d for d in details if d["url"] not in hidden]
        traum_cfg = cfg.get("traumprofil") or {}
        traum_name = traum_cfg.get("name", "Traumprofil")
        if nur_traum:
            details = [d for d in details
                       if traumjob.classify(d["title"], " ".join(d["anforderungen"]), traum_cfg)[0]]
        try:
            cv, _ = load_cv_master(self.root)
        except CvDataError as exc:
            return self.page("Lücken", f'<h1>Lücken-Auswertung</h1><div class="card err">{esc(exc)}</div>', "luecken")
        covered = covered_terms(cv or {}, cfg["fit"]["begriffe"])
        base, rows = gl.analyse(details, covered, cfg["fit"])
        n = sum(1 for d in details if len(d["anforderungen"]) >= cfg["fit"]["min_anforderungen"])
        traum_an = bool(traum_cfg) and traum_cfg.get("enabled", True) is not False
        umschalten = ('<a href="/luecken">alle Stellen</a>' if nur_traum
                      else f'<a href="/luecken?traum=1">nur {esc(traum_name)}</a>' if traum_an else "")
        scope = f"nur {esc(traum_name)}-Stellen" if nur_traum else "alle gefundenen Stellen"
        lern = gl.render_vorschlaege(lernpfade.vorschlaege(rows, lernpfade.load(self.root), cv or {}), self.token)
        lern = self._lernplan_karte(nur_traum) + lern
        body = (f'<h1>Lücken-Auswertung</h1><p class="sub">Was {scope} verlangen (ohne ausgeblendete). '
                f'{umschalten} · <a href="/master">Master-CV bearbeiten</a></p>'
                + message + lern + gl.render(base, rows, n, self.token)
                + gtr.render(gtr.verlauf(details, date.today()), covered) + self._fit_begriffe_karte(cfg))
        return self.page("Lücken-Auswertung", body, "luecken", gtr.CSS)

    def luecken_uebernehmen(self, form: dict) -> bytes:
        try:
            entry = lernpfade.uebernehmen(self.root, form.get("term", ""), int(form.get("index", -1)))
        except (lernpfade.LernpfadError, CvDataError, ValueError) as exc:
            return self.luecken(message=f'<div class="card err">{esc(exc)}</div>')
        return self.luecken(message=f'<div class="card"><p class="ok">„{esc(entry["name"])}“ als geplant in deinen '
                                    f'Master-CV übernommen. Wird beim Beenden hochgeladen; den Stand änderst du unter '
                                    f'<a href="/master">Master-CV</a>.</p></div>')

    # --- Einstellungen (statt Terminal) ---
    def einstellungen(self, message: str = "") -> bytes:
        cfg = load_config(self.root / "config.yaml")
        profile_html = (i18n.karte(self.token, i18n.sprache(cfg)) + i18n.darstellung_karte(self.token, i18n.darstellung(cfg))
                        + zeitplan.karte(self.root, self.token, esc, zeitplan.github_aktiv(self.root))
                        + wohnort.karte(self.token, cfg.get("ort") or {}, bool(ki.schluessel()), esc)
                        + gsp.render_liste(self.token, cfg, self._portale()))
        try:
            state = State(self.root / "state" / "seen.sqlite", readonly=True)
            pipe = json.loads(state.get_meta("ki_nutzung") or "{}")
            state.close()
        except Exception:   # alte oder fehlende Datenbank: Zeile weglassen
            pipe = {}
        llm.einstellen(cfg)
        ki_html = gki.karte(self.token, cfg, ki.herkunft(), ki.nutzung(self.root),
                            int(ki.settings(cfg)["max_aufrufe_monat"]),
                            gw.pipeline_ki(pipe, date.today().strftime("%Y-%m"), ki.settings(cfg)),
                            getattr(self, "_ki_modelle", None))
        sich = teilen.karte(i18n.sprache(cfg)) + spenden.karte(cfg) + feedback.karte() + gw.sicherung_karte(self.token, sicherung.vorhandene(self.sicherung_ziel),
                                  len(sicherung.inhalt(self.root)))
        github = zeitplan.github_aktiv(self.root)
        postfach = (f'<div class="card" id="postfach"><h2>Postfach</h2>'
                    f'{mailzugang.formular(self.root, self.token, esc, "/einstellungen")}</div>' if not github else "")
        body = gw.render(self.token, profile_html + postfach, self.aufgaben, gw.fehlende_pakete(), gw.protokoll(),
                         message, bn.status(), modus(cfg), ki_html, sich, github,
                         version_html=updates.karte(self.root, cfg, self.token),
                         aus=frozenset(k for k, v in (cfg.get("sources") or {}).items()
                                       if isinstance(v, dict) and v.get("enabled") is False))
        return self.page("Einstellungen", body, "einstellungen", gdt.CSS + gki.WAHL_CSS)

    def _portale(self) -> int:
        """Aktive Stellenwerk-Portale (für die Schätzung der Abrufe je Lauf)."""
        try:
            return gsp.portale(load_companies(self.root / "companies.yaml"))
        except (OSError, ValueError):
            return 0

    def suchprofil(self, key: str = "", fehler: str = "", eingabe: dict | None = None, hinweis: str = "") -> bytes:
        cfg = load_config(self.root / "config.yaml")
        if key and key not in (cfg.get("profile") or {}):
            return self.einstellungen('<div class="card err">Unbekanntes Suchprofil.</div>')
        body = gsp.render_formular(self.token, cfg, key, self._portale(), fehler, eingabe, bool(ki.schluessel()),
                                   hinweis)
        return self.page("Suchprofil", body, "einstellungen")

    def suchprofil_post(self, form: dict) -> bytes:
        cfg = load_config(self.root / "config.yaml")
        key = form.get("key", "")
        if form.get("aktion") == "ki":
            if not form.get("wunsch", "").strip():
                return self.suchprofil(key, "Bitte kurz beschreiben, was du suchst – daraus füllt die KI die Felder.",
                                       form)
            try:
                cv, _ = load_cv_master(self.root)
                vorschlag = ki.suchprofil_vorschlag(self.root, cfg, form.get("name", ""), form["wunsch"], cv or {},
                                                    suchprofil.MAX_BEGRIFFE)
            except (ki.KiError, CvDataError) as exc:
                return self.suchprofil(key, str(exc), form)
            return self.suchprofil(key, "", {**form, **vorschlag, "enabled": form.get("enabled", "1" if not key else "")},
                                   "Vorschlag der KI eingesetzt. Bitte prüfen und anpassen – gespeichert wird erst mit "
                                   "„Speichern“.")
        try:
            if form.get("aktion") == "loeschen":
                name = gsp.loeschen(self.root, key, cfg)
                text = f"Suchprofil „{name}“ gelöscht."
            else:
                key, daten = gsp.aus_formular(form, cfg)
                gsp.speichern(self.root, key, daten)
                text = f"Suchprofil „{daten['name']}“ gespeichert."
        except (gsp.SuchprofilError, gw.WartungError) as exc:
            return self.suchprofil(key, str(exc), form)
        ergebnis = sync(self.root)
        msg = (f'<div class="card"><p class="ok">{esc(text)} {esc(ergebnis.message)} Gilt ab dem nächsten Lauf.</p></div>'
               if ergebnis.ok else
               f'<div class="card err">{esc(text)} Das Hochladen hat nicht geklappt ({esc(ergebnis.message)}); '
               f'beim nächsten Synchronisieren wird es erneut versucht.</div>')
        return self.einstellungen(msg)

    def pipeline_laeufe(self) -> bytes:
        """Nachgeladen von der Einstellungsseite; eine Minute zwischengespeichert, damit Hin- und Herklicken nicht
        jedes Mal auf GitHub wartet."""
        jetzt = time.monotonic()
        if not self._laeufe or jetzt - self._laeufe[0] > 60:
            self._laeufe = (jetzt, gw.pipeline_laeufe(self.root))
        return gw.laeufe_html(*self._laeufe[1]).encode()

    def einstellungen_post(self, form: dict) -> bytes:
        aktion = form.get("aktion", "")
        ok = lambda text: f'<div class="card"><p class="ok">{esc(text)}</p></div>'  # noqa: E731
        if self.echt is not None and aktion in ("pipeline", "pipeline_ohne_mail", "probelauf", "zeitplan_an",
                                                "sicherung", "sicherung_ordner", "app", "pakete", "mail"):
            return self.einstellungen('<div class="card err">In der Demo nicht verfügbar – erst „Demo beenden“.</div>')
        try:
            if aktion in ("pipeline", "pipeline_ohne_mail"):
                msg = ok(gw.pipeline_starten(self.root, aktion == "pipeline_ohne_mail"))
                self._laeufe = None                                 # neuer Lauf soll gleich in der Liste stehen
            elif aktion == "darstellung":
                self.darstellung(form.get("darstellung", ""))
                msg = ok("Darstellung gespeichert.")
            elif aktion == "sprache_gui":
                i18n.setzen(self.root, form.get("sprache", ""))
                msg = ok("Sprache der Oberfläche gespeichert." if form.get("sprache") == "de" else
                         "Interface language saved.")
            elif aktion == "modus":
                wert = form.get("modus", "")
                vorher = modus(load_config(self.root / "config.yaml"))
                gw.modus_setzen(self.root, wert)
                if wert == "aktiv" and vorher != "aktiv":
                    grk.starten(self.root, date.today())
                ergebnis = sync(self.root)
                zurueck = " Auf der Startseite steht eine kurze Checkliste für den Neustart." if grk.laden(self.root) \
                    and wert == "aktiv" and vorher != "aktiv" else ""
                msg = (ok(f"Suche steht auf „{MODI[wert]}“. {ergebnis.message} Gilt ab dem nächsten Lauf der Pipeline."
                          f"{zurueck}")
                       if ergebnis.ok else
                       f'<div class="card err">Suche steht auf „{esc(MODI[wert])}“, aber das Hochladen hat nicht '
                       f'geklappt ({esc(ergebnis.message)}). Beim nächsten Synchronisieren wird es erneut versucht.</div>')
            elif aktion == "sicherung":
                if form.get("passwort", "") != form.get("passwort2", ""):
                    raise sicherung.SicherungError("Die beiden Passwörter stimmen nicht überein.")
                datei = sicherung.erstellen(self.root, form.get("passwort", ""), self.sicherung_ziel)
                msg = ok(f"Sicherung erstellt: {datei.name} ({'verschlüsselt' if datei.suffix == '.dmg' else 'ZIP, '
                         'unverschlüsselt'}) in Dokumente → Job-Monitor Sicherungen.")
            elif aktion == "mail":
                msg = ok(mailzugang.verbinden(self.root, form.get("anbieter", ""), form.get("benutzer", ""),
                                              form.get("passwort", ""), form.get("host", "")))
            elif aktion in ("updates_an", "updates_aus"):
                msg = ok(updates.schalten(self.root, aktion == "updates_an"))
            elif aktion in ("mail_bericht_an", "mail_bericht_aus"):
                msg = ok(mailzugang.bericht_schalten(self.root, aktion == "mail_bericht_an"))
            elif aktion == "mail_trennen":
                mailzugang.trennen(self.root)
                msg = ok("Postfach getrennt.")
            elif aktion == "zeitplan_an":
                msg = ok(zeitplan.einschalten(self.root, form.get("uhrzeit", "07:00")))
                zeitplan.pruefen_und_starten(self.root, self.aufgaben)
            elif aktion == "zeitplan_aus":
                msg = ok(zeitplan.ausschalten(self.root))
            elif aktion == "wohnort":
                stadt = form.get("stadt", "")
                tabelle = wohnort.ki_fahrzeiten(self.root, load_config(self.root / "config.yaml"), stadt)
                wohnort.speichern(self.root, stadt, tabelle)
                ergebnis = sync(self.root)
                beispiele = ", ".join(f"{o.title()} {m} min" for o, m in list(tabelle.items())[1:6])
                msg = ok(f"Wohnort ist jetzt {stadt.strip()} mit {len(tabelle)} Orten im Umkreis (z. B. {beispiele}). "
                         f"Die Minuten sind Schätzungen der KI – in config.yaml unter ort.fahrzeiten korrigierbar. "
                         f"{ergebnis.message} Gilt ab dem nächsten Lauf.")
            elif aktion == "sicherung_ordner":
                subprocess.run(["open", str(self.sicherung_ziel)])
                msg = ""
            elif aktion == "ki_anbieter":
                gki.speichern(self.root, form.get("anbieter", ""))
                llm.einstellen(load_config(self.root / "config.yaml"))
                self._ki_modelle = None
                msg = ok(f"Anbieter: {gki.ANBIETER[llm.ANBIETER]['name']}. "
                         + ("Jetzt den Schlüssel eintragen." if not ki.schluessel() else "Schlüssel ist schon hinterlegt."))
            elif aktion == "ki_modelle_laden":
                schluessel = ki.schluessel()
                self._ki_modelle = gki_anbieter.modelle(llm.ANBIETER, None if schluessel == "lokal" else schluessel)
                if llm.ANBIETER == "gemini":
                    gki_anbieter.gemini_pruefen(schluessel, self._ki_modelle)
                msg = ok(f"{len(self._ki_modelle)} Modelle geladen – passende sind vorausgewählt, bitte übernehmen.")
            elif aktion == "ki_modelle":
                gki.speichern(self.root, llm.ANBIETER, {"schnell": form.get("schnell", ""), "gut": form.get("gut", "")})
                llm.einstellen(load_config(self.root / "config.yaml"))
                self._ki_modelle = None
                msg = ok("Modelle übernommen. Die KI-Knöpfe sind jetzt aktiv.")
            elif aktion == "ki_schluessel":
                ki.schluessel_speichern(form.get("schluessel", ""))
                if llm.ANBIETER != "claude" and not llm.MODELLE.get("schnell"):
                    self._ki_modelle = gki_anbieter.modelle(llm.ANBIETER, ki.schluessel())
                    if llm.ANBIETER == "gemini":
                        gki_anbieter.gemini_pruefen(ki.schluessel(), self._ki_modelle)
                    msg = ok("Schlüssel gespeichert und geprüft. Jetzt die Modelle übernehmen.")
                else:
                    msg = ok("Schlüssel sicher gespeichert. Die KI-Knöpfe sind jetzt aktiv.")
            elif aktion == "ki_entfernen":
                ki.schluessel_loeschen()
                msg = ok("API-Schlüssel aus dem Schlüsselbund entfernt.")
            elif aktion == "mitteilung":
                msg = ok(bn.einschalten(self.root, form.get("zeit", "")) if form.get("an") else bn.ausschalten())
            elif aktion == "mitteilung_test":
                weg = bn.senden(self.root, "Probe", "So sehen Mitteilungen über neue Stellen aus.")
                msg = ok("Probe-Mitteilung gesendet." + ("" if weg == "app" else
                         " (Ohne Helfer in Job-Monitor.app: „App neu bauen“, dann zeigt sie Name und Icon der App.)"))
            elif aktion == "probelauf":
                quelle = form.get("quelle", "")
                self.aufgaben.starten("probelauf", f"Probelauf ({gw.QUELLEN.get(quelle, quelle)})",
                                      gw.probelauf_cmd(quelle))
                msg = ok("Probelauf gestartet. Die Ausgabe erscheint unten, die Seite aktualisiert sich selbst.")
            elif aktion == "profil":
                gw.profil_setzen(self.root, form.get("key", ""), bool(form.get("an")))
                msg = ok("Suchprofil geändert. Wird beim Synchronisieren hochgeladen und gilt ab dem nächsten Lauf.")
            elif aktion == "app":
                from .mac_app import create
                msg = ok(f"{create(self.root).name} neu gebaut. Wirkt beim nächsten Start der App.")
            elif aktion == "pakete":
                self.aufgaben.starten("pakete", "Pakete installieren", gw.pakete_cmd(self.root))
                msg = ok("Installation gestartet.")
            elif aktion == "tests":
                self.aufgaben.starten("tests", "Selbsttest", [gw.python(), "-m", "pytest", "-q"])
                msg = ok("Selbsttest gestartet.")
            elif aktion == "cv_out":
                msg = ok(gw.cv_out_aufraeumen(self.root, load_config(self.root / "config.yaml"), self.trash))
            else:
                msg = '<div class="card err">Unbekannte Aktion.</div>'
        except (gw.WartungError, bn.BenachrichtigungError, ki.KiError, sicherung.SicherungError,
                wohnort.WohnortError, zeitplan.ZeitplanError, mailzugang.MailError, gki_anbieter.AnbieterError, subprocess.SubprocessError, OSError) as exc:
            msg = f'<div class="card err">{esc(exc)}</div>'
        return self.einstellungen(msg)

    def datei(self, name: str, message: str = "", text: str | None = None, suche: str = "",
              von: str = "") -> bytes | None:
        if name not in gw.DATEIEN:
            return None
        path = self.root / name
        if text is None:
            text = path.read_text(encoding="utf-8") if path.exists() else ""
        bak = path.with_name(path.name + ".bak").exists()
        return self.page(gdt.INFOS.get(name, (name,))[0],
                         gdt.editor_html(self.token, name, text, message, suche, von, bak, gdt.fehler_zeile(message)),
                         "firmen" if name == "companies.yaml" or von else "einstellungen", gdt.CSS)

    def datei_post(self, form: dict) -> bytes | None:
        """Speichern schließt den Editor: zurück zu Firmen (companies.yaml oder von „Quellen beobachten“ aus, dann mit
        Vermerk „wird überprüft“) bzw. zu den Einstellungen."""
        name, text, von = form.get("name", ""), form.get("text", ""), form.get("von", "")
        if form.get("aktion") == "wiederherstellen":    # .bak zurückholen; die jetzige Fassung wird zur Sicherung
            if name not in gw.DATEIEN:
                return None
            bak = (self.root / name).with_name((self.root / name).name + ".bak")
            if not bak.exists():
                return self.datei(name, '<div class="card err">Es gibt keine vorherige Fassung.</div>')
            try:
                gw.speichern(self.root, name, bak.read_text(encoding="utf-8"))
            except gw.WartungError as exc:
                return self.datei(name, gdt.fehler_html(str(exc)))
            return self.datei(name, '<div class="card"><p class="ok">Vorherige Fassung wiederhergestellt. Die Fassung '
                                    'davor liegt jetzt als Sicherung bereit (noch einmal klicken holt sie zurück).</p>'
                                    '</div>')
        try:
            gw.speichern(self.root, name, text)
        except gw.WartungError as exc:   # Eingabe behalten, damit nichts verloren geht
            return self.datei(name, gdt.fehler_html(str(exc)), text, von=von)
        if von:
            gf.vermerken(self.root, von, date.today())
        msg = (f'<div class="card"><p class="ok">{esc(name)} gespeichert (alter Stand als .bak). Wird beim '
               f'Synchronisieren hochgeladen{" und beim nächsten Lauf überprüft" if von else ""}.</p></div>')
        return self.firmen(msg) if von or name == "companies.yaml" else self.einstellungen(msg)

    def markieren(self, form: dict) -> bytes:
        job = next((d for d in self.jobs() if d["id"] == form.get("job_id")), None)
        if job is None:
            return self.index('<div class="card err">Stelle nicht gefunden.</div>')
        path = self.root / "applications.csv"
        rows = tracking.load(path)
        aktion = form.get("aktion", "")
        if aktion == "rueckgaengig":
            msg = gb.undo_hide(rows, job, form.get("vorher", ""))
            tracking.save(path, rows)
            return self.index(f'<div class="card"><p class="ok">{esc(msg)}</p></div>')
        if aktion == "grund":   # „passt nicht“: Grund zur gerade ausgeblendeten Stelle
            try:
                ablehnung.merken(self.root, job, form.get("grund", ""))
            except ablehnung.AblehnungError as exc:
                return self.index(f'<div class="card err">{esc(exc)}</div>')
            return self.index('<div class="card"><p class="ok">Danke – gemerkt. Aus mehreren Gründen schlägt die '
                              'App Ausschluss-Begriffe vor.</p></div>')
        vorher = gb.by_link(rows).get(job["url"], {}).get("status", "")
        msg = gb.mark(rows, job, aktion, date.today())
        tracking.save(path, rows)
        undo = ""
        if aktion == "ausblenden":   # Vergebung statt Rückfrage: ein Klick macht es rückgängig
            undo = self.form("/markieren", f'<input type="hidden" name="job_id" value="{esc(job["id"])}">'
                                           f'<input type="hidden" name="aktion" value="rueckgaengig">'
                                           f'<input type="hidden" name="vorher" value="{esc(vorher)}">',
                             "Rückgängig", ghost=True, small=True)
        grund = ablehnung.grund_html(job["id"], self.token, esc) if aktion == "ausblenden" else ""
        return self.index(f'<div class="card"><div class="row" style="justify-content:space-between"><p class="ok" '
                          f'style="margin:0">{esc(msg)}</p>{undo}</div>{grund}</div>')

    def _ablehnung_karte(self, cfg: dict, sichtbar: list[dict]) -> str:
        """Vorschläge für Ausschluss-Begriffe aus den Gründen beim Ausblenden (ablehnung.py)."""
        data = ablehnung.laden(self.root)
        if not data.get("stellen"):
            return ""
        geschuetzt = {t for k, syn in cfg["fit"]["begriffe"].items() for t in [k, *(syn or [])]}
        geschuetzt |= set(cfg["filter"].get("fach") or {})
        geschuetzt |= {r for p in suchprofil.alle(cfg) for r in p.rollen}
        f = cfg["filter"]
        alle_ausschluesse = [*(f.get("ausschluss_titel") or []), *(f.get("ausschluss_stufe_titel") or []),
                             *(f.get("ausschluss_fach_titel") or [])]
        liste = ablehnung.vorschlaege(data, [d["title"] for d in sichtbar], alle_ausschluesse,
                                      geschuetzt)
        return ablehnung.karte(liste, self.token, esc)

    def ablehnung(self, form: dict) -> bytes:
        wort, aktion = form.get("wort", "").strip(), form.get("aktion", "")
        if aktion == "ignorieren":
            ablehnung.ignorieren(self.root, wort)
            return self.index(f'<div class="card"><p class="ok">„{esc(wort)}“ wird nicht mehr vorgeschlagen.</p></div>')
        cfg = load_config(self.root / "config.yaml")
        try:
            ablehnung.ausschliessen(self.root, wort, cfg["filter"].get("ausschluss_titel") or [])
        except (ablehnung.AblehnungError, gw.WartungError) as exc:
            return self.index(f'<div class="card err">{esc(exc)}</div>')
        ergebnis = sync(self.root)
        hoch = ("Zu GitHub hochgeladen." if ergebnis.ok else
                f"Hochladen klappte nicht ({ergebnis.message}); beim nächsten Synchronisieren erneut.")
        return self.index(f'<div class="card"><p class="ok">Stellen mit „{esc(wort)}“ im Titel werden ab dem nächsten '
                          f'Lauf aussortiert. {esc(hoch)}</p></div>')

    # --- Master-CV ---
    def ki_anleitung(self, anbieter: str = "") -> bytes:
        if anbieter == "gemini":
            return self.page("Gemini einrichten", gki.ANLEITUNG_GEMINI, "einstellungen", gki.CSS)
        return self.page("Claude einrichten", gki.ANLEITUNG, "einstellungen", gki.CSS)

    def design_vorschau(self, key: str) -> bytes | None:
        """Lebenslauf im Design als HTML mit deinen Daten (iframe in der Galerie)."""
        if not designs.gueltig(key):
            return None
        try:
            return designs.vorschau_html(self.root, load_config(self.root / "config.yaml"), key).encode()
        except Exception as exc:     # z. B. noch kein Master-CV
            return f"<p style='font:14px sans-serif;padding:20px'>Keine Vorschau: {esc(exc)}</p>".encode()

    def master(self, data: dict | None = None, message: str = "") -> bytes:
        cfg = load_config(self.root / "config.yaml")
        data = gm.load(self.root) if data is None else data
        try:
            cov = gm.coverage(data, cfg["fit"]["begriffe"])
        except Exception:   # halbfertige Eingaben sollen die Seite nicht verhindern
            cov = []
        chips = "".join(f'<span class="{"" if w else "no"}" title="{"Gewicht " + format(w, ".2f") if w else "nicht belegt – anklicken zum Eintragen"}"'
                        f'{"" if w else f" data-term=\"{esc(t)}\""}>{esc(t)}</span>' for t, w in cov)
        offen = [t for t, w in cov if not w]
        eintragen = ("" if not offen else
                     f'<div class="row" style="margin-top:10px;gap:8px;align-items:center;flex-wrap:wrap">'
                     f'<span class="muted">Kann ich schon:</span><select name="term" id="kenntnis-term" form="masterform" '
                     f'style="width:auto">' + "".join(f'<option>{esc(t)}</option>' for t in offen) + '</select>'
                     + "".join(f'<button form="masterform" name="aktion" value="kenntnis:{lv}" class="ghost small">'
                               f'{lv}</button>' for lv in gm.LEVEL_WAHL)
                     + '</div>')
        rel = gm.master_path(self.root).relative_to(self.root)
        veraltet = cv_aktuell.pruefen(data, date.today())
        veraltet_html = ("" if not veraltet else
                         '<div class="card"><h2>Bitte prüfen: veraltet?</h2><ul class="checks">'
                         + "".join(f'<li class="warnung">{esc(v.text)}'
                                   + (f' <button form="masterform" name="aktion" value="semester" class="small">'
                                      f'Auf {cv_aktuell.semester_jetzt(data, date.today())}. Semester aktualisieren'
                                      f'</button>' if v.fix == "semester" else "") + '</li>' for v in veraltet)
                         + '</ul></div>')
        ki_knopf = ('<button name="aktion" value="ki_profil" class="ghost" data-ki="KI schlägt einen Profiltext vor …" '
                    'title="Aus deinen Einträgen; ersetzt den Text im Feld Profil, gespeichert wird erst mit Speichern">'
                    'Profiltext mit KI vorschlagen</button>' if ki.schluessel() else "")
        body = f"""
<h1>Master-CV bearbeiten</h1>
<p class="sub">{esc(rel)} · nur Nicht-Persönliches (Kontaktdaten und Foto stehen in cv/profile.yaml).
</p>
{message}
{veraltet_html}
<div class="card cov"><h2>Fit-Begriffe, die dein Lebenslauf belegt</h2>{chips}
<p class="muted">Durchgestrichen = nicht belegt. Einträge mit Status „geplant“ zählen nicht. Kannst du einen
durchgestrichenen Begriff schon? Anklicken, Level wählen – er landet in der passenden Kategorie unter Kenntnisse.</p>
{eintragen}</div>
<form method="post" action="/master" id="masterform">
<input type="hidden" name="token" value="{self.token}"><input type="hidden" name="data" id="payload">
<div id="editor"></div>
<div class="sticky row"><button name="aktion" value="speichern">Speichern</button>
<a class="btn ghost" href="/master">Änderungen verwerfen</a>{ki_knopf}</div></form>
{ki_extra.cv_verstehen_html(self.root, data, self.token, bool(ki.schluessel()), esc)}
{ki_extra.cv_check_html(self.root, data, self.token, bool(ki.schluessel()), esc)}
{designs.galerie_html(esc)}
<script type="application/json" id="schema">{json.dumps(gm.SCHEMA).replace("</", "<\\/")}</script>
<script type="application/json" id="data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>
<script>{gm.EDITOR_JS}</script>"""
        return self.page("Master-CV", body, "master", gm.EDITOR_CSS + designs.CSS)

    def master_save(self, form: dict) -> bytes:
        raw = form.get("data", "")
        if form.get("aktion") == "semester":
            try:
                data = cv_aktuell.semester_korrigieren(json.loads(raw), date.today())
                gm.save(self.root, gm.parse(json.dumps(data, ensure_ascii=False)))
            except (ValueError, CvDataError) as exc:
                return self.master(None, f'<div class="card err">Nicht gespeichert: {esc(exc)}</div>')
            return self.master(None, f'<div class="card"><p class="ok">Semester überall auf '
                                     f'{cv_aktuell.semester_jetzt(data, date.today())}. aktualisiert und gespeichert.'
                                     f'</p></div>')
        if form.get("aktion", "").startswith("kenntnis:"):
            cfg = load_config(self.root / "config.yaml")
            term, level = form.get("term", ""), form["aktion"].split(":", 1)[1]
            try:
                data = json.loads(raw)
                kategorie, neu = gm.kenntnis_eintragen(data, term, level, cfg["fit"]["begriffe"].get(term) or [])
                gm.save(self.root, gm.parse(json.dumps(data, ensure_ascii=False)))
            except (ValueError, CvDataError) as exc:
                return self.master(None, f'<div class="card err">Nicht eingetragen: {esc(exc)}</div>')
            text = (f"„{term}“ ({level}) unter „{kategorie}“ eingetragen und gespeichert." if neu else
                    f"„{term}“ stand schon unter „{kategorie}“ – angepasst und gespeichert.")
            return self.master(None, f'<div class="card"><p class="ok">{esc(text)}</p></div>')
        if form.get("aktion") == "ki_profil":
            try:
                data = json.loads(raw)
                cfg = load_config(self.root / "config.yaml")
                ziel = suchprofil.get(cfg, None).zielrolle
                data["profil"] = ki.profiltext(self.root, cfg, gm.parse(raw), ziel)
            except (ValueError, CvDataError, ki.KiError) as exc:
                try:
                    keep = json.loads(raw)
                except ValueError:
                    keep = None
                return self.master(keep, f'<div class="card err">{esc(exc)}</div>')
            return self.master(data, '<div class="card"><p class="ok">KI-Vorschlag im Feld „Profil“ eingesetzt – noch '
                                     'nicht gespeichert. Bitte lesen, anpassen und dann „Speichern“.</p></div>')
        try:
            data = gm.parse(raw)
            gm.save(self.root, data)
        except CvDataError as exc:
            try:
                keep = json.loads(raw)
            except ValueError:
                keep = None
            return self.master(keep, f'<div class="card err">Nicht gespeichert: {esc(exc)}</div>')
        message = ('<div class="card"><p class="ok">Gespeichert. Gilt sofort für neue Lebensläufe und den Fit; '
                   'wird beim Beenden automatisch hochgeladen.</p></div>')
        return self.master(None, message)

    def pdf_path(self, name: str) -> Path | None:
        if not PDF_NAME.match(name):
            return None
        path = self.root / load_config(self.root / "config.yaml")["cv"]["ausgabe"] / name
        return path if path.is_file() else None


# HTTP-Server (Routing, Formulare lesen, Start) steht in gui_server.py; hier weitergereicht, damit
# `from jobmonitor.gui import serve, handler_for …` wie bisher funktioniert.
from .gui_server import MAX_BODY, already_running, handler_for, make_server, parse_body, serve  # noqa: E402,F401
