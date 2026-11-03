import shutil
from datetime import date

import pytest
from pypdf import PdfReader, PdfWriter

from jobmonitor import bewerbung as bw
from jobmonitor import tracking
from jobmonitor.config import ROOT, load_config
from jobmonitor.gui import App
from jobmonitor.models import Job
from jobmonitor.state import State
from tests.conftest import FIXTURES

PROFILE = ("name: Max Muster\nadresse: {strasse: Musterweg 1, plz: '50667', ort: Köln}\n"
           "email: max@example.com\ntelefon: '+49 221 0000000'\nzeitraum: ab März 2027 mit 20 Stunden pro Woche\n")
STELLE = {"id": "abc12345", "title": "Werkstudent:in Cloud Operations (m/w/d)", "company": "Beispiel AG",
          "url": "https://x/1", "anforderungen": {"Azure": 1.0, "Terraform": 1.0, "Kubernetes": 0.5, "Englisch": 1.0}}


def blank_pdf(path, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        writer.write(fh)


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    shutil.copy(FIXTURES / "cv_master_example.yaml", tmp_path / "cv" / "cv_master.yaml")
    for name in ("template.tex.j2", "profile.example.yaml", "anschreiben.tex.j2", "anschreiben_vorlage.txt"):
        shutil.copy(ROOT / "cv" / name, tmp_path / "cv" / name)
    (tmp_path / "cv" / "profile.yaml").write_text(PROFILE, encoding="utf-8")
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    tracking.save(tmp_path / "applications.csv", [])
    return tmp_path


def test_clean_title():
    assert bw.clean_title("Werkstudent:in IT Service Desk (w/m/d)") == "Werkstudent IT Service Desk"
    assert bw.clean_title("Werkstudent*in (all gender) IT Security") == "Werkstudent IT Security"


def test_draft_fills_building_blocks(root):
    cfg = load_config(root / "config.yaml")
    text = bw.draft(root, cfg, STELLE)
    assert "„Werkstudent Cloud Operations“" in text and "Cyber Security Management (B. Sc.) an der Hochschule Niederrhein" in text
    assert "Seit März 2025 arbeite ich als Werkstudent IT-Operations bei Beispiel GmbH." in text
    assert "Erfahrungen mit Azure und Terraform." in text and "Englisch" not in text   # keine Sprachen
    assert "ab März 2027 mit 20 Stunden pro Woche" in text and "{" not in text
    assert bw.placeholders(text) and "Beispiel AG" in bw.placeholders(text)[0]       # [Warum Beispiel AG? …]


def test_workspace_and_anlagen(root):
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    assert folder.name == "beispiel-ag-abc12345" and bw.workspace(root, cfg, folder.name) == folder
    assert bw.workspace(root, cfg, "../config") is None
    blank_pdf(root / "cv" / "private" / "notenuebersicht.pdf")
    blank_pdf(root / "cv" / "private" / "anlagen" / "2-badge.pdf")
    blank_pdf(root / "cv" / "private" / "anlagen" / "1-abitur.pdf")
    found = {a["name"]: [p.name for p in a["pdfs"]] for a in bw.anlagen(root, cfg)}
    assert found == {"Notenübersicht": ["notenuebersicht.pdf"], "Immatrikulationsbescheinigung": [],
                     "Zeugnisse und Zertifikate": ["1-abitur.pdf", "2-badge.pdf"]}


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="LaTeX nur lokal installiert")
def test_build_mappe(root):
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    bw.save_letter(folder, "Absatz eins mit 100% & mehr.\n\nAbsatz zwei.", "", "IT-Abteilung\n50667 Köln")
    blank_pdf(root / "cv" / "private" / "notenuebersicht.pdf", pages=2)
    blank_pdf(root / "cv" / "private" / "anlagen" / "zeugnis.pdf")
    mappe, fehlend = bw.build_mappe(root, cfg, folder, date(2026, 11, 20))
    assert fehlend == ["Immatrikulationsbescheinigung"]
    anschreiben = PdfReader(str(folder / "anschreiben.pdf"))
    text = anschreiben.pages[0].extract_text()
    assert "BewerbungalsWerkstudentCloudOperations" in text.replace(" ", "")   # Extraktion trennt „W erkstudent“
    assert "Köln, 20.11.2026" in text and "Absatz eins mit 100% & mehr." in text
    assert "Sehr geehrte Damen und Herren" in text and "Anlagen:" in text and "Notenübersicht" in text
    cv_pages = len(PdfReader(str(folder / "lebenslauf.pdf")).pages)
    assert len(PdfReader(str(mappe)).pages) == len(anschreiben.pages) + cv_pages + 2 + 1
    row = tracking.load(root / "applications.csv")[0]
    assert row["status"] == "Entwurf" and row["link"] == "https://x/1"


def test_build_without_text_or_profile(root):
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    with pytest.raises(bw.BewerbungError, match="Noch kein"):
        bw.build_anschreiben(root, cfg, folder)
    bw.save_letter(folder, "Text", "", "")
    (root / "cv" / "profile.yaml").unlink()
    with pytest.raises(bw.BewerbungError, match="profile.yaml fehlt"):
        bw.build_anschreiben(root, cfg, folder)


def test_gui_page_flow(root):
    state = State(root / "state" / "seen.sqlite")
    job = Job(STELLE["title"], STELLE["company"], STELLE["url"], "test")
    job.fit_anforderungen = STELLE["anforderungen"]
    state.save_job_detail(job, "2026-11-01")
    state.close()
    app = App(root, compile_pdf=False)
    slug = app.bewerbung_open(job.short_id)
    html = app.bewerbung(slug).decode()
    assert "Bewerbung: Werkstudent Cloud Operations" in html and "Platzhalter" in html and app.token in html
    html = app.bewerbung_post(slug, {"aktion": "speichern", "text": "Fertiger Text.", "anrede": "Hallo Team,",
                                     "empfaenger": ""}).decode()
    assert "Gespeichert" in html and "Platzhalter in [eckigen" not in html
    assert bw.letter(root / "cv" / "bewerbungen" / slug)["anrede"] == "Hallo Team,"
    assert "Deine Bewerbungsordner" in app.bewerbungen().decode()
    assert app.bewerbung("../x") is None and app.bewerbung_file(slug, "../../config.yaml") is None
