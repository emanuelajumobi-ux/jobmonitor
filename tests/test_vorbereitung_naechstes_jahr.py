"""Eckdaten je Stelle, Master-CV aktuell halten, Rückkehr aus dem Ruhemodus, Sicherung, frühere Bewerbungen bei
derselben Firma und Firmen-Kurzprofil. Die Claude-API wird nie echt aufgerufen."""
import json
from datetime import date

from jobmonitor import fit
from jobmonitor import gui_bericht as gbe
from jobmonitor.models import Job
from jobmonitor.report import Report
from jobmonitor.state import State
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

# Gesprächstermin in zwei Tagen (relativ zu heute – ein festes Datum läge irgendwann in der Vergangenheit)
from datetime import date as _date, timedelta as _timedelta
TERMIN_TAG = _date.today() + _timedelta(days=2)
TERMIN = f"{TERMIN_TAG.isoformat()}T14:00"



def test_eckdaten(tmp_path):
    roh = {"stunden": "20 h/Woche", "verguetung": "16 €/h", "remote": None, "start": "null", "abschlussarbeit": "ja",
           "x": "egal"}
    assert fit.eckdaten(roh) == {"stunden": "20 h/Woche", "verguetung": "16 €/h"}
    assert fit.eckdaten({"abschlussarbeit": True, "remote": "x" * 50})["remote"] == "x" * 30
    e = {"stunden": "20 h/Woche", "remote": "2 Tage", "abschlussarbeit": True}
    assert fit.eckdaten_text(e) == ["20 h/Woche", "Remote: 2 Tage", "Abschlussarbeit möglich"]
    # gespeichert, nachbewertet und wieder gelesen
    state = State(tmp_path / "s.sqlite")
    job = Job(title="Werkstudent Cloud", company="A", url="https://a/1", source="T", eckdaten=e)
    state.save_job_detail(job, "2026-11-03")
    assert state.job_details()[0]["eckdaten"] == e and state.job_detail(job.short_id)["eckdaten"] == e
    state.update_detail(job.short_id, {"Azure": 1.0}, 50, {"stunden": "10 h"})
    assert state.job_details()[0]["eckdaten"] == {"stunden": "10 h"}
    # Bericht und Berichtsseite
    job.fit_anforderungen, job.score = {}, 70
    text = "\n".join(Report(date(2026, 11, 3), [], [job])._job(job))
    assert "Eckdaten: 20 h/Woche · Remote: 2 Tage · Abschlussarbeit möglich" in text
    stelle = gbe._stelle(text.splitlines()[0], text.splitlines()[1:])
    assert stelle.eckdaten == ["20 h/Woche", "Remote: 2 Tage", "Abschlussarbeit möglich"]
    assert '<span class="chip eck">20 h/Woche</span>' in gbe._stelle_html(stelle)


def test_mit_ki_liest_eckdaten():
    antwort = json.dumps({"anforderungen": [{"begriff": "Azure", "pflicht": True}],
                          "eckdaten": {"stunden": "20 h/Woche", "verguetung": None}})
    job = Job(title="Werkstudent", company="A", url="u", source="T", description="x" * 400)
    cfg = {"begriffe": {"Azure": []}, "optional_marker": [], "min_anforderungen": 1, "ki": {"enabled": True}}
    fit.mit_ki([job], {}, cfg, ask=lambda *a, **k: antwort)
    assert job.eckdaten == {"stunden": "20 h/Woche"}
    assert "eckdaten" in fit.ki_system({"Azure": []}) and fit.KI_VERSION >= 2


CV_ALT = {"profil": "Student im 5. Semester mit Praxis.",
          "ausbildung": [{"abschluss": "Cyber Security (B. Sc.)", "von": "09/2024", "bis": "voraussichtlich 02/2027",
                          "punkte": ["Aktuell 5. Semester. Schwerpunkte: Netze"]},
                         {"abschluss": "Abitur", "von": "07/2021", "bis": "07/2024"}],
          "projekte": [{"name": "Hackathon", "zeitraum": "10/2026 – 01/2027", "status": "in_arbeit"},
                       {"name": "Alt", "zeitraum": "01/2025", "status": "erreicht"}],
          "zertifikate": [{"name": "AZ-104", "datum": "voraussichtlich 01/2027", "status": "geplant"},
                          {"name": "AZ-900", "datum": "05/2025", "status": "erreicht"}]}


def test_veraltete_angaben():
    from jobmonitor import cv_aktuell as ca
    assert ca.semester_jetzt(CV_ALT, date(2026, 11, 3)) == 5 and ca.semester_jetzt(CV_ALT, date(2027, 3, 1)) == 6
    assert ca.pruefen(CV_ALT, date(2026, 11, 3)) == []                                 # alles aktuell
    texte = [v.text for v in ca.pruefen(CV_ALT, date(2027, 8, 15))]
    assert "laut Studienbeginn bist du jetzt im 6. Semester" in texte[0]
    assert any("voraussichtlich 02/2027" in t for t in texte) and any("AZ-104" in t for t in texte)
    assert any("Hackathon" in t for t in texte) and not any("AZ-900" in t or "„Alt“" in t for t in texte)
    neu = ca.semester_korrigieren(CV_ALT, date(2027, 4, 1))
    assert neu["profil"] == "Student im 6. Semester mit Praxis." and neu["ausbildung"][0]["punkte"][0].startswith(
        "Aktuell 6. Semester")
    assert CV_ALT["profil"].startswith("Student im 5.")                                 # Original unverändert


def test_semester_knopf_im_master_cv(root, monkeypatch):  # noqa: F811
    from jobmonitor import gui_master as gm
    from jobmonitor.gui import App
    data = gm.load(root)
    data["profil"] = "Student im 2. Semester."
    data["ausbildung"][0]["von"] = "09/2024"
    gm.save(root, data)
    app = App(root, compile_pdf=False)
    html = app.master().decode()
    assert "Bitte prüfen: veraltet?" in html and 'value="semester"' in html
    html = app.master_save({"aktion": "semester", "data": json.dumps(gm.load(root))}).decode()
    assert "Semester überall auf" in html and "2. Semester" not in gm.load(root)["profil"]


def test_rueckkehr_aus_dem_ruhemodus(root, monkeypatch):  # noqa: F811
    from jobmonitor import benachrichtigung as bn
    from jobmonitor import gui_rueckkehr as grk
    from jobmonitor import gui_wartung as gw
    from jobmonitor.gui import App
    from jobmonitor.gui_sync import SyncResult
    monkeypatch.setattr("jobmonitor.gui.sync", lambda r: SyncResult(True, "ok"))
    monkeypatch.setattr(gw, "pipeline_laeufe", lambda r: ([], ""))
    monkeypatch.setattr(bn, "status", lambda: {"an": False, "zeit": "08:30"})
    app = App(root, compile_pdf=False)
    app.einstellungen_post({"aktion": "modus", "modus": "ruhe"})
    assert not grk.laden(root) and "Willkommen zurück" not in app.index().decode()
    html = app.einstellungen_post({"aktion": "modus", "modus": "aktiv"}).decode()
    assert "kurze Checkliste für den Neustart" in html and grk.laden(root)["seit"] == date.today().isoformat()
    html = app.index().decode()
    assert "Willkommen zurück" in html and "5 Punkt(e) offen" in html and "ist aus – unter Einstellungen" in html
    html = app.rueckkehr({"punkt": "cv"}).decode()
    assert "4 Punkt(e) offen" in html and "Master-CV auf den neuesten Stand" not in html
    assert "Willkommen zurück" not in app.rueckkehr({"punkt": "alle"}).decode() and not grk.laden(root)
    app.einstellungen_post({"aktion": "modus", "modus": "aktiv"})          # aktiv → aktiv: keine neue Liste
    assert not grk.laden(root)


def test_sicherung(root, tmp_path, monkeypatch):  # noqa: F811
    import subprocess
    import zipfile

    import pytest

    from jobmonitor import sicherung
    from jobmonitor.gui import App
    (root / "cv" / "private").mkdir()
    (root / "cv" / "private" / "zeugnis.pdf").write_bytes(b"%PDF")
    (root / ".gui_ki.json").write_text("{}", encoding="utf-8")
    (root / ".env").write_text("ANTHROPIC_API_KEY=geheim", encoding="utf-8")
    inhalt = {str(p) for p in sicherung.inhalt(root)}
    assert {"cv/profile.yaml", "cv/private/zeugnis.pdf", ".gui_ki.json", "config.yaml"} <= inhalt and ".env" not in inhalt
    ziel = tmp_path / "ziel"
    z = sicherung.erstellen(root, "", ziel)
    namen = zipfile.ZipFile(z).namelist()
    assert "Job-Monitor/cv/private/zeugnis.pdf" in namen and "Job-Monitor/LIESMICH.txt" in namen
    assert not any(".env" in n for n in namen)
    with pytest.raises(sicherung.SicherungError, match="mindestens 8"):
        sicherung.erstellen(root, "kurz", ziel)
    aufrufe = []

    def run(cmd, **kw):
        aufrufe.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(sicherung.sys, "platform", "darwin")
    dmg = sicherung.erstellen(root, "langes-passwort", ziel, run)
    cmd, kw = aufrufe[0]
    assert dmg.suffix == ".dmg" and "-stdinpass" in cmd and "AES-256" in cmd and kw["input"] == "langes-passwort"
    assert "langes-passwort" not in " ".join(cmd)                           # Passwort nie als Argument
    # In den Einstellungen
    monkeypatch.setattr("jobmonitor.gui_wartung.pipeline_laeufe", lambda r: ([], ""))
    app = App(root, compile_pdf=False)
    app.sicherung_ziel = ziel
    html = app.einstellungen().decode()
    assert 'id="sicherung"' in html and z.name in html
    assert "stimmen nicht überein" in app.einstellungen_post({"aktion": "sicherung", "passwort": "abcdefgh",
                                                              "passwort2": "abcdefgX"}).decode()
    html = app.einstellungen_post({"aktion": "sicherung", "passwort": "", "passwort2": ""}).decode()
    assert "Sicherung erstellt" in html and "unverschlüsselt" in html


def test_frueher_bei_der_firma(root):  # noqa: F811
    from jobmonitor import bewerbung as bw
    from jobmonitor import gui_bewerbungen as gb
    from jobmonitor import tracking
    from jobmonitor.config import load_config
    from jobmonitor.gui import App
    from tests.test_bewerbung import STELLE
    rows = [{"firma": "Beispiel AG", "typ": "Stelle", "status": "Absage", "datum": "2027-03-12",
             "link": "https://x/alt", "notizen": "Werkstudent IT-Security"},
            {"firma": "Beispiel", "typ": "Initiativ", "status": "beworben", "datum": "2027-04-01", "link": "https://i"},
            {"firma": "Beispiel AG", "typ": "Stelle", "status": "neu", "datum": "2027-04-02", "link": "https://x/neu"},
            {"firma": "Andere GmbH", "typ": "Stelle", "status": "beworben", "datum": "2027-04-02", "link": "https://y"},
            {"firma": "Beispiel AG", "typ": "Stelle", "status": "Entwurf", "datum": "2027-04-03",
             "link": STELLE["url"]}]
    treffer = gb.frueher_bei_firma(rows, "Beispiel AG", STELLE["url"])
    assert [r["link"] for r in treffer] == ["https://i", "https://x/alt"]      # neueste zuerst, ohne neu/andere/selbst
    tracking.save(root / "applications.csv", rows)
    folder = bw.open_workspace(root, load_config(root / "config.yaml"), STELLE)
    html = App(root, compile_pdf=False).bewerbung(folder.name).decode()
    assert "Bei Beispiel AG hast du dich schon beworben" in html and "Werkstudent IT-Security – Absage am 12.03.2027" in html


def test_firmenprofil(root, monkeypatch):  # noqa: F811
    import re

    import responses

    from jobmonitor import ki, llm, tracking
    from jobmonitor.gui import App
    from jobmonitor.http import Fetcher
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    with responses.RequestsMock() as rs:
        rs.get(re.compile(r"https://firma\.de/robots\.txt"), body="")
        rs.get("https://firma.de/", body="<main><p>Wir sind ein Cloud-Dienstleister mit 200 Leuten in Köln.</p></main>")
        assert "Cloud-Dienstleister" in ki.firmen_text(["https://firma.de/", "https://www.linkedin.com/company/x"],
                                                       Fetcher("test", 0, 5, 0))
    prompts = []

    def ask(model, prompt, **kw):
        prompts.append(prompt)
        kw["usage"].append((10, 10))
        return "## Was die Firma macht\n- Cloud-Dienstleister in Köln\n## Noch herausfinden\n- Teamgröße"
    monkeypatch.setattr(llm, "_ask", ask)
    monkeypatch.setattr(ki, "firmen_text", lambda urls, f: "Wir sind ein Cloud-Dienstleister.")
    tracking.save(root / "applications.csv", [{"firma": "Firma", "typ": "Stelle", "status": "Antwort",
                                                "datum": "2026-10-20", "link": "https://firma.de/job/1",
                                                "notizen": "Werkstudent", "termin": TERMIN}])
    app = App(root, compile_pdf=False)
    assert "Firmenprofil mit KI erstellen" in app.bewerbungen().decode()
    html = app.firmenprofil({"link": "https://firma.de/job/1"}).decode()
    assert "Firmenprofil für Firma erstellt" in html and "<h3>Was die Firma macht</h3>" in html
    assert "Wir sind ein Cloud-Dienstleister." in prompts[0] and "Nichts erfinden" in prompts[0]
    assert ki.firmenprofile(root)["firma"]["text"].startswith("## Was die Firma macht")
    assert "Bewerbung nicht gefunden" in app.firmenprofil({"link": "https://y"}).decode()
