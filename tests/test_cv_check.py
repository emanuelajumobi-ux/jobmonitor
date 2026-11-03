"""Lebenslauf-Prüfer: Inhalt, LaTeX-Log, PDF-Länge, Zuschnitt, Einbindung in Bau und Oberfläche."""
import shutil
from datetime import date

import pytest
from pypdf import PdfWriter

from jobmonitor.cv_build import build
from jobmonitor.cv_check import Hinweis, check_content, check_log, check_pdf, check_tailoring
from jobmonitor.gui import pruefung_html
from jobmonitor.models import Job
from jobmonitor.state import State
from tests.test_cv_build import project  # noqa: F401  (Fixture)

BASE = {"stationen": [{"rolle": "Werkstudent IT", "organisation": "A AG", "von": "07/2026", "bis": "",
                       "aufgaben": ["Clients betreut"]}],
        "ausbildung": [{"abschluss": "B. Sc.", "von": "09/2024", "bis": "voraussichtlich 02/2028"}],
        "kenntnisse": [{"kategorie": "Cloud", "eintraege": [{"name": "Azure"}]}]}


def texts(hinweise):
    return " | ".join(str(h) for h in hinweise)


def test_clean_cv_has_no_hints(cfg):
    assert check_content(BASE, cfg) == []


def test_empty_sections_warn(cfg):
    out = check_content({**BASE, "stationen": [], "kenntnisse": []}, cfg)
    assert [h.stufe for h in out] == ["warnung", "warnung"]
    assert "Berufserfahrung" in texts(out) and "Kenntnisse" in texts(out)


def test_long_and_many_bullets(cfg):
    station = {**BASE["stationen"][0], "aufgaben": ["x" * 200] + [f"Aufgabe {i}" for i in range(6)]}
    projekt = {"name": "Homelab", "beschreibung": "y" * 300}           # Absatz: Grenze 320, also ok
    out = texts(check_content({**BASE, "stationen": [station], "projekte": [projekt]}, cfg))
    assert "7 Stichpunkte" in out and "200 Zeichen" in out and "Homelab" not in out
    ausgeblendet = {"name": "Alt", "beschreibung": "z" * 500, "im_cv": False}
    assert "Alt" not in texts(check_content({**BASE, "projekte": [ausgeblendet]}, cfg))


def test_date_formats(cfg):
    cv = {**BASE, "zertifikate": [{"name": "AZ-900", "datum": "März 2026"}],
          "projekte": [{"name": "P", "zeitraum": "2025-03 – 06/2025"}]}
    [h] = check_content(cv, cfg)
    assert h.stufe == "warnung" and "März 2026" in h.text and "2025-03" in h.text and "06/2025" not in h.text


def test_duplicate_skills(cfg):
    cv = {**BASE, "kenntnisse": [{"kategorie": "Cloud", "eintraege": [{"name": "Azure"}, {"name": "Docker"}]},
                                 {"kategorie": "DevOps", "eintraege": [{"name": "docker"}]}]}
    assert texts(check_content(cv, cfg)) == "Tipp: Doppelt unter Kenntnisse: Docker"


def test_profile_text_length(cfg):
    assert "Profiltext" in texts(check_content({**BASE, "profil": "w " * 300}, cfg))


def test_limits_from_config(cfg):
    station = {**BASE["stationen"][0], "aufgaben": ["a", "b", "c"]}
    strict = {**cfg, "cv": {**cfg["cv"], "pruefung": {"max_stichpunkte": 2}}}
    assert check_content({**BASE, "stationen": [station]}, cfg) == []
    assert "3 Stichpunkte" in texts(check_content({**BASE, "stationen": [station]}, strict))


def test_latex_log(cfg):
    log = ("Overfull \\hbox (0.5pt too wide) in paragraph at lines 10--11\n"
           "Overfull \\hbox (24.3pt too wide) in paragraph at lines 40--41\n"
           "Missing character: There is no ✓ in font cmr10!\n"
           "LaTeX Warning: File `foto.jpg' not found on input line 47.\n")
    out = check_log(log, cfg)
    assert all(h.stufe == "warnung" for h in out) and len(out) == 3
    assert "1 Stelle(n)" in out[0].text and "24 pt" in out[0].text
    assert "✓" in out[1].text and "foto.jpg" in out[2].text
    assert check_log("This is pdfTeX\nOutput written on lebenslauf.pdf (2 pages).", cfg) == []


def pdf_with_pages(path, n):
    writer = PdfWriter()
    for _ in range(n):
        writer.add_blank_page(595, 842)
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


def test_pdf_length(tmp_path, cfg):
    out = check_pdf(pdf_with_pages(tmp_path / "lang.pdf", 3), cfg)
    assert out[0].stufe == "warnung" and "3 Seiten" in out[0].text
    assert "letzte Seite hat nur 0 Zeile(n)" in out[1].text
    assert check_pdf(pdf_with_pages(tmp_path / "eine.pdf", 1), cfg) == []


def test_tailoring_lost_terms(cfg):
    begriffe = cfg["fit"]["begriffe"]
    full = {**BASE, "projekte": [{"name": "IaC", "beschreibung": "Infrastruktur mit Terraform"},
                                 {"name": "Alt", "beschreibung": "Ansible", "im_cv": False}]}
    tailored = {**BASE, "projekte": []}
    [h] = check_tailoring(full, tailored, {"Terraform": 1.0, "Ansible": 1.0, "Azure": 1.0}, begriffe)
    assert "Terraform" in h.text and "Ansible" not in h.text and "Azure" not in h.text
    assert check_tailoring(full, full, {"Terraform": 1.0}, begriffe) == []


def test_build_collects_hints(project, cfg):  # noqa: F811
    hinweise = []
    build(project, cfg, compile_pdf=False, hinweise=hinweise)
    assert all(isinstance(h, Hinweis) for h in hinweise)
    build(project, cfg, compile_pdf=False)                                # ohne Liste: wie bisher
    state = State(project / "state" / "seen.sqlite")
    job = Job("Werkstudent Cloud", "Beispiel AG", "https://x/1", "test")
    job.fit_anforderungen = {"Azure": 1.0, "Docker": 1.0}   # Docker steht nur im Projekt Homelab
    state.save_job_detail(job, date(2026, 11, 1).isoformat())
    state.close()
    small = {**cfg, "cv": {**cfg["cv"], "max_projekte_zugeschnitten": 0}}
    hinweise = []
    build(project, small, job.short_id, compile_pdf=False, hinweise=hinweise)
    lost = next(h.text for h in hinweise if "nach dem Kürzen" in h.text)
    assert "Docker" in lost and "Azure" not in lost


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="LaTeX nur lokal installiert")
def test_build_checks_pdf_and_log(project, cfg):  # noqa: F811
    hinweise = []
    strict = {**cfg, "cv": {**cfg["cv"], "pruefung": {"max_seiten": 0}}}
    pdf = build(project, strict, hinweise=hinweise)
    assert pdf.exists() and "Seiten" in texts(hinweise)
    assert not pdf.with_suffix(".log").exists()                          # Hilfsdateien trotzdem aufgeräumt


def test_gui_card():
    assert "keine Auffälligkeiten" in pruefung_html([])
    html = pruefung_html([Hinweis("tipp", "kurz <b>"), Hinweis("warnung", "zu lang")])
    assert html.index("zu lang") < html.index("kurz") and "&lt;b&gt;" in html and 'class="warnung"' in html
