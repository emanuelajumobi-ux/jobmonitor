"""Stufen 2 und 3: PDFs aus HTML (ohne LaTeX), lokaler Zeitplan statt GitHub Actions, erster Start mit
Standard-Dateien und der Einrichtungs-Assistent mit Lebenslauf-Import. Keine echten KI-Aufrufe, kein launchctl."""
import io
import json
import plistlib
import subprocess
from pathlib import Path

import pytest
from pypdf import PdfWriter

from jobmonitor import cv_build, erststart, gui_assistent as gas, ki, llm, pdf_html, prozess, suchprofil, zeitplan
from jobmonitor import gui_master as gm
from jobmonitor.config import load_config
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

PROFIL = {"name": "Erika Beispiel", "email": "erika@example.org", "telefon": "+49 170 1234567",
          "adresse": {"strasse": "Musterweg 5", "plz": "50667", "ort": "Köln"}}


def test_format_auswahl(monkeypatch):
    assert cv_build.pdf_format({"format": "latex"}) == "latex"
    assert cv_build.pdf_format({"format": "html"}) == "html" and cv_build.pdf_format({}) == "latex"
    monkeypatch.setattr(cv_build.shutil, "which", lambda n: None)
    assert cv_build.pdf_format({"format": "auto"}) == "html"
    monkeypatch.setattr(cv_build.shutil, "which", lambda n: "/usr/bin/latexmk")
    assert cv_build.pdf_format({"format": "auto"}) == "latex"


def test_lebenslauf_als_html(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    cfg["cv"]["format"] = "html"
    html = cv_build.build(root, cfg, compile_pdf=False).read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "Max Muster" in html and "Berufserfahrung" in html
    assert "@page { size: A4" in html and "\\section" not in html


def test_pdf_befehl(tmp_path, monkeypatch):
    seite = tmp_path / "a.html"
    seite.write_text("<p>x</p>")
    aufrufe = []

    def run(cmd, **kw):
        aufrufe.append((cmd, kw))
        Path(tmp_path / "a.pdf").write_bytes(b"%PDF-1.7 ok")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(pdf_html, "_webkit", lambda: True)
    assert pdf_html.drucken(seite, tmp_path / "a.pdf", run=run).name == "a.pdf"
    assert aufrufe[0][0][-3:] == ["pdf-webkit", str(seite.resolve()), str((tmp_path / "a.pdf").resolve())]
    assert "PYTHONPATH" in aufrufe[0][1]["env"]
    monkeypatch.setattr(pdf_html, "_webkit", lambda: False)
    monkeypatch.setattr(pdf_html, "browser", lambda: "/opt/edge")
    pdf_html.drucken(seite, tmp_path / "a.pdf", run=run)
    assert aufrufe[1][0][0] == "/opt/edge" and any(a.startswith("--print-to-pdf=") for a in aufrufe[1][0])
    monkeypatch.setattr(pdf_html, "browser", lambda: None)
    with pytest.raises(pdf_html.PdfError, match="LaTeX installieren"):
        pdf_html.drucken(seite, tmp_path / "a.pdf", run=run)


def test_prozess_befehl(monkeypatch):
    assert prozess.befehl("run")[1:] == ["-m", "jobmonitor", "run"]
    monkeypatch.setattr("sys.frozen", True, raising=False)
    assert prozess.befehl("run")[1:] == ["run"]


def test_zeitplan_mac_und_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(zeitplan, "plist_pfad", lambda: tmp_path / "LaunchAgents" / "de.jobmonitor.suche.plist")
    aufrufe = []

    def run(cmd, **kw):
        aufrufe.append(cmd)
        return subprocess.CompletedProcess(cmd, 1 if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"] else 0, "", "")
    text = zeitplan.einschalten(tmp_path, "06:45", run=run, plattform="darwin")
    assert "täglich um 06:45" in text and zeitplan.laden(tmp_path) == {"an": True, "uhrzeit": "06:45"}
    plist = plistlib.loads((tmp_path / "LaunchAgents" / "de.jobmonitor.suche.plist").read_bytes())
    assert plist["StartCalendarInterval"] == {"Hour": 6, "Minute": 45} and plist["ProgramArguments"][-2:] == ["run", "--mitteilung"]
    assert any(c[:2] == ["launchctl", "bootstrap"] for c in aufrufe)
    zeitplan.ausschalten(tmp_path, run=run, plattform="darwin")
    assert not zeitplan.laden(tmp_path)["an"] and not (tmp_path / "LaunchAgents" / "de.jobmonitor.suche.plist").exists()
    zeitplan.einschalten(tmp_path, "07:00", run=run, plattform="win32")
    assert any(c[:2] == ["schtasks", "/Create"] and "07:00" in c for c in aufrufe)
    with pytest.raises(zeitplan.ZeitplanError, match="HH:MM"):
        zeitplan.einschalten(tmp_path, "7 Uhr", run=run, plattform="darwin")


def test_zeitplan_nicht_neben_github(root):  # noqa: F811
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "monitor.yml").write_text("on: schedule")
    run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "origin/main", "")  # noqa: E731
    assert zeitplan.github_aktiv(root, run)
    with pytest.raises(zeitplan.ZeitplanError, match="GitHub Actions"):
        zeitplan.einschalten(root, "07:00", run=run, plattform="darwin")
    assert "nicht nötig" in zeitplan.karte(root, "t", str, github=True)


def test_zeitplan_startet_in_der_app(tmp_path):
    class Aufgaben:
        def __init__(self):
            self.alle, self.gestartet = {}, []

        def starten(self, name, titel, cmd):
            self.gestartet.append(cmd)
    a = Aufgaben()
    assert not zeitplan.pruefen_und_starten(tmp_path, a)                     # aus
    (tmp_path / zeitplan.DATEI).write_text(json.dumps({"an": True}))
    assert zeitplan.pruefen_und_starten(tmp_path, a) and a.gestartet[0][-2:] == ["run", "--mitteilung"]


def test_erster_start(tmp_path):
    neu = erststart.vorbereiten(tmp_path)
    assert {"config.yaml", "companies.yaml", "cv/template.html.j2", "cv/profile.example.yaml"} <= set(neu)
    cfg = load_config(tmp_path / "config.yaml")
    assert cfg["cv"]["format"] == "auto" and not cfg["traumprofil"]["enabled"] and cfg["filter"]["ausschluss_firmen"] == []
    assert [p.key for p in suchprofil.alle(cfg)] == ["beispiel"] and not erststart.eingerichtet(tmp_path)
    (tmp_path / "config.yaml").write_text("geändert")
    assert erststart.vorbereiten(tmp_path) == [] and (tmp_path / "config.yaml").read_text() == "geändert"


def test_schwaerzen():
    text = ("Erika Beispiel\nMusterweg 5, 50667 Köln\nTel. +49 170 1234567 · erika@example.org\n"
            "geboren am 01.02.2003 in Bonn\nlinkedin.com/in/erika · https://github.com/erika\n"
            "Werkstudentin Controlling, Beispiel GmbH, 2024–2026")
    s = gas.schwaerzen(text, PROFIL)
    for weg in ("Erika", "Beispiel\n", "Musterweg", "50667", "1234567", "erika@", "01.02.2003", "github.com"):
        assert weg not in s
    assert "Werkstudentin Controlling" in s and "Köln" in s


def _pdf_mit_text() -> bytes:
    # Ein echtes PDF mit Text braucht eine Schrift; pypdf kann das nicht erzeugen – hier reicht ein leeres PDF,
    # pdf_text wird im Test ersetzt.
    w = PdfWriter()
    w.add_blank_page(595, 842)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_assistent_von_null(tmp_path, monkeypatch):
    erststart.vorbereiten(tmp_path)
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    prompts = []
    antworten = [json.dumps({"orte": {"Leipzig": 0, "Halle": 30, "Markkleeberg": 20, "Taucha": 25, "Delitzsch": 35}}),
                 json.dumps({"name": "Controlling", "stufe": "werkstudent", "art": "studium",
                             "rollen": {"werkstudent": 30}, "such_bundesagentur": ["Werkstudent Controlling"],
                             "such_stellenwerk": [], "fachgebiet": "eigen",
                             "fach": {"controlling": 14, "finanzen": 10, "reporting": 8}, "fit_begriffe": {"SAP": []},
                             "zielrolle": "Werkstudent Controlling", "absicht": "", "ausblick": ""}),
                 json.dumps({"profil": "BWL-Studentin mit Praxis im Controlling.", "telefon": "0170 1234567",
                             "stationen": [{"rolle": "Werkstudentin Controlling", "organisation": "Beispiel GmbH",
                                            "von": "04/2024", "bis": "", "aufgaben": ["Monatsreporting"]}],
                             "kenntnisse": [{"kategorie": "Software", "eintraege": [{"name": "SAP", "level": "gut"}]}],
                             "sprachen": [{"sprache": "Deutsch", "niveau": "Muttersprache"}]})]

    def ask(model, prompt, **kw):
        prompts.append(prompt)
        kw["usage"].append((100, 50))
        return antworten.pop(0)
    monkeypatch.setattr(llm, "_ask", ask)
    monkeypatch.setattr(gas, "pdf_text", lambda b: "Erika Beispiel · erika@example.org\n" + "Werkstudentin " * 40)
    app = App(tmp_path, compile_pdf=False)
    html = app.index().decode()
    assert "Willkommen bei Job-Monitor" in html and "5. Lebenslauf" in html            # neuer Nutzer → Assistent
    html = app.einrichten({"aktion": "person", **{k: v for k, v in {"name": "Erika Beispiel",
                                                                    "email": "erika@example.org"}.items()}}).decode()
    assert "Angaben gespeichert" in html
    assert "Wohnort Leipzig übernommen (5 Orte)" in app.einrichten({"aktion": "wohnort", "stadt": "Leipzig"}).decode()
    html = app.einrichten({"aktion": "suche", "wunsch": "Werkstudent im Controlling", "stufe": "werkstudent"}).decode()
    assert "Suchprofil „Controlling“ angelegt" in html
    cfg = load_config(tmp_path / "config.yaml")
    p = suchprofil.get(cfg, "controlling")
    assert p.enabled and p.stufe == "werkstudent" and cfg["sources"]["bundesagentur"]["wo"] == "Leipzig"
    html = app.einrichten({"aktion": "lebenslauf"}, {"pdf": [("cv.pdf", _pdf_mit_text())]}).decode()
    assert "Lebenslauf übernommen (1 Einträge)" in html
    cv = gm.load(tmp_path)
    assert cv["stationen"][0]["organisation"] == "Beispiel GmbH" and "telefon" not in cv     # Persönliches entfernt
    assert "Erika" not in prompts[2] and "erika@" not in prompts[2] and "[entfernt]" in prompts[2]
    html = app.einrichten({"aktion": "fertig"}).decode()
    assert "Eingerichtet" in html and erststart.eingerichtet(tmp_path)


def test_assistent_ohne_ki(tmp_path):
    erststart.vorbereiten(tmp_path)
    app = App(tmp_path, compile_pdf=False)
    seite = app.einrichten().decode()
    assert "Schlüssel hier eintragen" in seite and 'action="/einrichten"' in seite and "ki_schluessel" in seite
    assert "Wohnort Halle übernommen (1 Orte)" in app.einrichten({"aktion": "wohnort", "stadt": "Halle"}).decode()
    html = app.einrichten({"aktion": "suche", "wunsch": "Pflege, Gesundheit, Klinik", "stufe": "ausbildung"}).decode()
    assert "angelegt" in html
    p = next(p for p in suchprofil.alle(load_config(tmp_path / "config.yaml")) if p.enabled)
    assert p.angebotsart == 4 and "pflege" in p.fach and "azubi" in p.rollen
    assert "Bitte kurz beschreiben" in app.einrichten({"aktion": "suche", "wunsch": " "}).decode()
    assert "mindestens drei Stichwörter" in app.einrichten({"aktion": "suche", "wunsch": "Pflege"}).decode()


# --- Postfach für alle Anbieter ---
class FakeImap:
    def __init__(self, host, port, timeout=None, ok=True):
        self.host, self.ok = host, ok

    def login(self, user, pw):
        import imaplib
        if pw != "app-pass":
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def select(self, box, readonly=False):
        return "OK", [b"3"]

    def logout(self):
        pass


def test_postfach_verbinden(tmp_path, monkeypatch):
    from jobmonitor import mailzugang
    gespeichert = {}
    monkeypatch.setattr(mailzugang, "_passwort_speichern", lambda u, w, run=None: gespeichert.update({u: w}))
    monkeypatch.setattr(mailzugang, "passwort", lambda u, run=None: gespeichert.get(u))
    text = mailzugang.verbinden(tmp_path, "gmail", "lena@gmail.com", "app-pass", imap=FakeImap)
    assert "verbunden (Gmail)" in text and gespeichert == {"lena@gmail.com": "app-pass"}
    assert mailzugang.laden(tmp_path) == {"anbieter": "gmail", "host": "imap.gmail.com", "benutzer": "lena@gmail.com"}
    assert "app-pass" not in (tmp_path / mailzugang.DATEI).read_text()                  # Passwort nie in der Datei
    monkeypatch.delenv("IMAP_USER", raising=False)
    assert mailzugang.umgebung_setzen(tmp_path)
    import os
    assert os.environ["IMAP_HOST"] == "imap.gmail.com" and os.environ["IMAP_PASSWORD"] == "app-pass"
    for k in ("IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(mailzugang.MailError, match="App-Passwort prüfen"):
        mailzugang.verbinden(tmp_path, "gmx", "lena@gmx.de", "falsch", imap=FakeImap)
    with pytest.raises(mailzugang.MailError, match="Outlook"):
        mailzugang.verbinden(tmp_path, "anderer", "lena@outlook.de", "x", "outlook.office365.com", imap=FakeImap)
    with pytest.raises(mailzugang.MailError, match="IMAP-Server"):
        mailzugang.verbinden(tmp_path, "anderer", "lena@firma.de", "app-pass", "", imap=FakeImap)
    assert "imap.firma.de" in mailzugang.verbinden(tmp_path, "anderer", "lena@firma.de", "app-pass", "imap.firma.de",
                                                    imap=FakeImap) or mailzugang.laden(tmp_path)["host"] == "imap.firma.de"


def test_assistent_postfach_und_neutrale_vorlagen(tmp_path):
    erststart.vorbereiten(tmp_path)
    html = App(tmp_path, compile_pdf=False).einrichten().decode()
    assert "7. Postfach (optional)" in html and "6. Firmen beobachten (optional)" in html and "App-Passwort" in html and "Outlook/Hotmail geht" in html
    vorlage = (tmp_path / "cv" / "anschreiben_vorlage.txt").read_text(encoding="utf-8")
    assert "Ich studiere" not in vorlage and "{absicht}" in vorlage
