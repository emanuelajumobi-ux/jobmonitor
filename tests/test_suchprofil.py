"""Suchprofile Werkstudent/Junior: Auswahl, Rollenfilter, Migration, Bericht, Quellen, Anschreiben, Oberfläche."""
import copy
import re
import shutil
import sqlite3
from datetime import date

import responses

from jobmonitor import bewerbung as bw
from jobmonitor import suchprofil, tracking
from jobmonitor.config import ROOT, load_config
from jobmonitor.drafts import render
from jobmonitor.gui import App
from jobmonitor.models import Job
from jobmonitor.report import Report
from jobmonitor.runner import Options, run
from jobmonitor.scoring import evaluate_profiles
from jobmonitor.sources.ats import jsonld
from jobmonitor.state import State
from tests.conftest import FIXTURES


def with_junior(cfg: dict, enabled: bool = True) -> dict:
    cfg = copy.deepcopy(cfg)
    cfg["profile"]["junior"]["enabled"] = enabled
    return cfg


def without_junior(cfg: dict) -> dict:
    return with_junior(cfg, enabled=False)


def job(title, **kw):
    return Job(title=title, company=kw.pop("company", "Beispiel AG"), url=kw.pop("url", "https://x/1"), source="t",
               location=kw.pop("location", "Köln"), **kw)


# --- Profilauswahl ---
def test_only_enabled_profiles_active(cfg):
    assert [p.key for p in suchprofil.alle(cfg)] == ["werkstudent", "junior", "abschlussarbeit"]
    assert [p.key for p in suchprofil.aktive(cfg)] == ["werkstudent", "junior"]     # Abschlussarbeit erst bei Bedarf
    assert [p.key for p in suchprofil.aktive(without_junior(cfg))] == ["werkstudent"]
    assert [p.key for p in suchprofil.aktive(with_junior(cfg))] == ["werkstudent", "junior"]


def test_profile_values(cfg):
    ws, junior, thesis = suchprofil.alle(cfg)
    assert "Bachelorarbeit Cloud Security" in thesis.begriffe("bundesagentur") and not thesis.enabled
    assert "Werkstudent Cloud" in ws.begriffe("bundesagentur") and ws.angebotsart is None
    assert "Junior Cloud Engineer" in junior.begriffe("bundesagentur") and junior.angebotsart == 1
    assert "Werkstudent" in ws.zielrolle and "Junior" in junior.zielrolle
    assert not set(ws.rollen) & set(junior.rollen)


def test_get_falls_back_to_first_profile(cfg):
    assert suchprofil.get(cfg, "junior").key == "junior"
    assert suchprofil.get(cfg, None).key == "werkstudent"       # ältere Stellen ohne Profil
    assert suchprofil.get(cfg, "gibtsnicht").key == "werkstudent"


def test_legacy_config_without_profile_block():
    cfg = {"filter": {"rollen": {"werkstudent": 30}}, "entwuerfe": {"zielrolle": "Werkstudent IT"},
           "sources": {"bundesagentur": {"suchbegriffe": ["Werkstudent IT"]}, "hsnr": {"enabled": True}}}
    [p] = suchprofil.aktive(cfg)
    assert p.key == "werkstudent" and p.rollen == {"werkstudent": 30} and p.zielrolle == "Werkstudent IT"
    assert p.begriffe("bundesagentur") == ["Werkstudent IT"] and p.begriffe("stellenwerk") == []


def test_slug_pattern(cfg):
    pattern = suchprofil.get(cfg, "junior").slug_re()
    assert pattern.search("junior-cloud-engineer-m-w-d") and pattern.search("entry-level-devops")
    assert not pattern.search("senior-cloud-architect")
    assert not pattern.search("studenten-und-absolventen") and not pattern.search("berufseinsteiger")   # Übersichten
    combined = jsonld.role_re([jsonld.ROLE_SLUG.pattern, pattern.pattern])
    assert combined.search("werkstudent-cloud") and combined.search("trainee-it-security")


# --- Rollenfilter ---
def test_junior_title_needs_junior_profile(cfg):
    profile = suchprofil.aktive(without_junior(cfg))
    assert evaluate_profiles(job("Junior Cloud Engineer (m/w/d)", description="Azure, Terraform"), cfg,
                             profile) is None
    j = evaluate_profiles(job("Junior Cloud Engineer (m/w/d)", description="Azure, Terraform"), cfg,
                          suchprofil.aktive(with_junior(cfg)))
    assert j is not None and j.profil == "junior" and j.reason.startswith("Junior mit Bezug zu")


def test_werkstudent_title_stays_werkstudent(cfg):
    j = evaluate_profiles(job("Werkstudent Cloud Security Azure"), cfg, suchprofil.aktive(with_junior(cfg)))
    assert j is not None and j.profil == "werkstudent"


def test_trainee_and_berufseinsteiger(cfg):
    profile = suchprofil.aktive(with_junior(cfg))
    for title in ("Trainee IT-Security (m/w/d)", "Berufseinsteiger Azure Cloud (w/m/d)",
                  "Graduate Program Cloud Engineering"):
        j = evaluate_profiles(job(title), cfg, profile)
        assert j is not None and j.profil == "junior", title


def test_exclusions_apply_to_junior(cfg):
    profile = suchprofil.aktive(with_junior(cfg))
    assert evaluate_profiles(job("Junior / Senior Cloud Engineer"), cfg, profile) is None
    assert evaluate_profiles(job("Junior Sales Manager Cloud"), cfg, profile) is None
    assert evaluate_profiles(job("Junior Cloud Engineer", location="München"), cfg, profile) is None


def test_junior_excludes_ausbildung_and_overview_pages(cfg):
    profile = suchprofil.aktive(with_junior(cfg))
    azubi = job("Ausbildung als Fachinformatiker*in für Systemintegration", kind="trainee",
                description="IT-Sicherheit, Infrastruktur")
    assert evaluate_profiles(azubi, cfg, profile) is None
    assert evaluate_profiles(job("Für Studierende und Absolvent*innen", description="Cloud Security, IAM"), cfg,
                             profile) is None


def test_best_profile_wins_and_flags_not_doubled(cfg):
    original = job("Werkstudent Junior DevOps Engineer", description="spätere Übernahme möglich")
    j = evaluate_profiles(original, cfg, suchprofil.aktive(with_junior(cfg)))
    assert j.profil == "werkstudent"                       # Junior schließt Werkstudent-Titel aus
    assert j.flags.count("Übernahmechance erwähnt") == 1 and original.flags == []


# --- Migration ---
OLD_SCHEMA = """
CREATE TABLE seen (key TEXT PRIMARY KEY, title TEXT, company TEXT, url TEXT, source TEXT, score INTEGER, first_seen TEXT);
CREATE TABLE job_detail (id TEXT PRIMARY KEY, key TEXT, title TEXT, company TEXT, url TEXT, anforderungen_json TEXT,
                         fit INTEGER, first_seen TEXT, frist TEXT);
INSERT INTO seen VALUES ('k','Alt','A','https://a','BA',50,'2026-10-01');
INSERT INTO job_detail VALUES ('aaaa1111','k','Alt','A','https://a','{}',NULL,'2026-10-01',NULL);
"""


def old_db(tmp_path):
    path = tmp_path / "seen.sqlite"
    db = sqlite3.connect(path)
    db.executescript(OLD_SCHEMA)
    db.commit()
    db.close()
    return path


def columns(path, table):
    db = sqlite3.connect(path)
    cols = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    db.close()
    return cols


def test_readonly_does_not_migrate_profil(tmp_path):
    path = old_db(tmp_path)
    before = path.read_bytes()
    state = State(path, readonly=True)
    assert state.job_detail("aaaa")["profil"] is None and state.job_details()[0]["profil"] is None
    state.close()
    assert path.read_bytes() == before and "profil" not in columns(path, "job_detail")


def test_write_access_migrates_and_stores_profil(tmp_path):
    path = old_db(tmp_path)
    state = State(path)
    assert state.job_detail("aaaa")["profil"] is None               # alte Zeile bleibt NULL
    j = Job("Junior Cloud Engineer", "B", "https://b", "BA", score=70, profil="junior")
    state.mark_reported(j, "2026-11-01")
    state.save_job_detail(j, "2026-11-01")
    state.close()
    assert "profil" in columns(path, "job_detail") and "profil" in columns(path, "seen")
    state = State(path, readonly=True)
    assert state.job_detail(j.short_id)["profil"] == "junior"
    assert not state.is_new(j)
    assert state.db.execute("SELECT profil FROM seen WHERE key=?", (j.key,)).fetchone() == ("junior",)
    state.close()


# --- Bericht ---
def test_report_sections_per_profile():
    ws = Job("Werkstudent Cloud", "A", "https://a", "BA", score=70)
    jr = Job("Junior Cloud Engineer", "B", "https://b", "BA", score=65, profil="junior")
    report = Report(date(2026, 10, 31), [], [ws, jr], profile={"werkstudent": "Werkstudent", "junior": "Junior"})
    text = report.render()
    assert "## Neue Stellen – Werkstudent (1)" in text and "## Neue Stellen – Junior (1)" in text
    assert text.index("Werkstudent Cloud") < text.index("## Neue Stellen – Junior") < text.index("Junior Cloud")
    assert "(Werkstudent: 1, Junior: 1)" in report.subject("Job-Monitor")


def test_report_single_profile_unchanged():
    text = Report(date(2026, 10, 31), [], [Job("Werkstudent Cloud", "A", "https://a", "BA")],
                  profile={"werkstudent": "Werkstudent"}).render()
    assert "## Neue Stellen (1)" in text and "Neue Stellen –" not in text


def test_report_empty_junior_section():
    text = Report(date(2026, 10, 31), [], [Job("Werkstudent Cloud", "A", "https://a", "BA")],
                  profile={"werkstudent": "Werkstudent", "junior": "Junior"}).render()
    assert "## Neue Stellen – Junior (0)" in text and "Keine neuen passenden Junior-Stellen" in text


# --- Pipeline mit beiden Profilen ---
@responses.activate
def test_run_with_junior_queries_ba_per_profile(tmp_path, monkeypatch):
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    (tmp_path / "applications.csv").write_text("firma,typ,status,datum,link,notizen,termin\n", encoding="utf-8")
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    text = text.replace("    enabled: false              # für die Zeit nach dem Abschluss einschalten",
                        "    enabled: true")
    (tmp_path / "config.yaml").write_text(text, encoding="utf-8")
    (tmp_path / "companies.yaml").write_text("firmen: []\nhochschulen: []\n", encoding="utf-8")

    def ba(request):
        params = request.params
        if params.get("angebotsart") == "1":
            items = [{"stellenangebotsTitel": "Junior Cloud Security Engineer (m/w/d)", "firma": "Jr GmbH",
                      "referenznummer": "J-1", "stellenlokationen": [{"adresse": {"ort": "Köln"}}], "entfernung": 3}]
        else:
            items = [{"stellenangebotsTitel": "Werkstudent Azure Cloud (m/w/d)", "firma": "Ws AG",
                      "referenznummer": "W-1", "stellenlokationen": [{"adresse": {"ort": "Köln"}}], "entfernung": 3}]
        import json
        return 200, {}, json.dumps({"ergebnisliste": items})

    responses.add_callback(responses.GET, re.compile(r"https://rest\.arbeitsagentur\.de/.*/v6/jobs.*"), callback=ba)
    responses.get(re.compile(r"https://rest\.arbeitsagentur\.de/.*/v4/jobdetails/.*"), status=404)
    for var in ("SMTP_USER", "IMAP_USER", "ANTHROPIC_API_KEY", "CV_MASTER_YAML"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("jobmonitor.http.time.sleep", lambda s: None)

    assert run(Options(force=True, no_mail=True, root=tmp_path, only="bundesagentur")) == 0
    report = next((tmp_path / "reports").glob("*.md")).read_text(encoding="utf-8")
    assert "Bundesagentur für Arbeit (Werkstudent)" in report and "Bundesagentur für Arbeit (Junior)" in report
    ws_part, jr_part = report.split("## Neue Stellen – Junior")
    assert "Werkstudent Azure Cloud" in ws_part.split("## Neue Stellen – Werkstudent")[1]
    assert "Junior Cloud Security Engineer" in jr_part and "Werkstudent Azure" not in jr_part
    calls = [c.request.params for c in responses.calls if "/v6/jobs" in c.request.url]
    assert any(p.get("was") == "Junior Cloud Engineer" and p.get("angebotsart") == "1" for p in calls)
    assert all("angebotsart" not in p for p in calls if p.get("was", "").startswith("Werkstudent"))
    state = State(tmp_path / "state" / "seen.sqlite", readonly=True)
    assert {d["title"]: d["profil"] for d in state.job_details()} == {
        "Junior Cloud Security Engineer (m/w/d)": "junior", "Werkstudent Azure Cloud (m/w/d)": "werkstudent"}
    state.close()


# --- Anschreiben ---
ENTRY = {"name": "Beispiel AG", "branche": "IT-Dienstleister", "fokus": ["Azure"], "standorte": ["Köln"]}


def test_initiativ_draft_uses_profile_texts(cfg):
    jr = suchprofil.get(cfg, "junior")
    text = render(ENTRY, {}, {"zielrolle": jr.zielrolle, "absicht": jr.absicht, "ausblick": jr.ausblick},
                  date(2026, 10, 31))
    assert "**Initiativbewerbung als Junior Cloud / Cloud Security Engineer**" in text
    assert "den Berufseinstieg im Bereich Cloud" in text and "Werkstudententätigkeit" not in text
    ws = suchprofil.get(cfg, "werkstudent")
    text = render(ENTRY, {}, {"zielrolle": ws.zielrolle, "absicht": ws.absicht, "ausblick": ws.ausblick},
                  date(2026, 10, 31))
    assert "eine Werkstudententätigkeit mit der Möglichkeit" in text and "Langfristig möchte ich" in text


def bewerbung_root(tmp_path, monkeypatch, profile_yaml):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    shutil.copy(FIXTURES / "cv_master_example.yaml", tmp_path / "cv" / "cv_master.yaml")
    for name in ("template.tex.j2", "profile.example.yaml", "anschreiben.tex.j2", "anschreiben_vorlage.txt"):
        shutil.copy(ROOT / "cv" / name, tmp_path / "cv" / name)
    (tmp_path / "cv" / "profile.yaml").write_text(profile_yaml, encoding="utf-8")
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    tracking.save(tmp_path / "applications.csv", [])
    return tmp_path


def test_bewerbung_draft_per_profile(tmp_path, monkeypatch):
    root = bewerbung_root(tmp_path, monkeypatch, "name: Max Muster\nzeitraum: ab März 2027 mit 20 Stunden\n")
    cfg = load_config(root / "config.yaml")
    stelle = {"id": "abc12345", "title": "Junior Cloud Engineer (m/w/d)", "company": "Beispiel AG",
              "url": "https://x/1", "anforderungen": {"Azure": 1.0}, "profil": "junior"}
    text = bw.draft(root, cfg, stelle)
    assert "suche nach meinem Abschluss den Berufseinstieg" in text
    assert "[ab wann du nach dem Abschluss anfangen kannst]" in text and "20 Stunden" not in text
    text = bw.draft(root, cfg, {**stelle, "title": "Werkstudent Cloud", "profil": None})
    assert "eine Werkstudententätigkeit" in text and "ab März 2027 mit 20 Stunden" in text
    folder = bw.open_workspace(root, cfg, stelle)
    assert bw.meta(folder)["profil"] == "junior"


# --- Oberfläche ---
def test_gui_profile_tabs(tmp_path, monkeypatch):
    root = bewerbung_root(tmp_path, monkeypatch, "name: Max Muster\n")
    state = State(root / "state" / "seen.sqlite")
    state.save_job_detail(Job("Werkstudent Cloud Azure", "A AG", "https://a", "t"), "2026-11-01")
    state.save_job_detail(Job("Junior Cloud Engineer", "B AG", "https://b", "t", profil="junior"), "2026-11-02")
    state.close()
    app = App(root, compile_pdf=False)
    html = app.index().decode()
    assert "Junior<span>1</span>" in html and "Werkstudent<span>1</span>" in html and '<span class="chip">Junior</span>' in html
    html = app.index(profil="junior").decode()
    assert "Junior Cloud Engineer" in html and "Werkstudent Cloud Azure" not in html
    html = app.index(profil="<script>").decode()           # unbekanntes Profil → alle Stellen
    assert "Junior Cloud Engineer" in html and "Werkstudent Cloud Azure" in html


def test_gui_without_junior_has_no_profile_tabs(tmp_path, monkeypatch):
    root = bewerbung_root(tmp_path, monkeypatch, "name: Max Muster\n")
    config = root / "config.yaml"
    text = config.read_text(encoding="utf-8")
    config.write_text(re.sub(r"(  junior:\n    enabled:) true", r"\1 false", text), encoding="utf-8")
    state = State(root / "state" / "seen.sqlite")
    state.save_job_detail(Job("Werkstudent Cloud Azure", "A AG", "https://a", "t"), "2026-11-01")
    state.close()
    html = App(root, compile_pdf=False).index().decode()
    assert "?profil=" not in html and "Werkstudent Cloud Azure" in html
