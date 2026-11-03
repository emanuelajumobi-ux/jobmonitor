import pytest

from jobmonitor.location import travel_minutes
from jobmonitor.models import Job, normalize
from jobmonitor.scoring import evaluate


def job(title, location="Köln", desc="", company="Beispiel GmbH", remote=False, kind=""):
    return Job(title=title, company=company, url="https://example.com/1", source="test",
               location=location, description=desc, remote=remote, kind=kind)


def test_werkstudent_azure_koeln_scores_high(cfg):
    j = evaluate(job("Werkstudent Cloud Engineering Azure (m/w/d)", desc="Terraform, Entra ID"), cfg)
    assert j is not None
    assert j.score >= 80
    assert "Köln" in j.reason


@pytest.mark.parametrize("title", [
    "Senior Cloud Engineer Azure (m/w/d)",           # Senior
    "Werkstudent Marketing Cloud (m/w/d)",            # Marketing
    "Werkstudent Interne Kommunikation Cloud (m/w/d)",
    "Werkstudent Datenschutz (m/w/d)",                # reine Datenschutz-Stelle, kein Fach-Stichwort
    "Cloud Engineer Azure (m/w/d)",                   # keine Werkstudenten-/Abschlussrolle
    "Werkstudent Buchhaltung",                        # kein Fach-Stichwort
])
def test_excluded_titles(cfg, title):
    assert evaluate(job(title), cfg) is None


def test_isms_with_strong_tech_keyword_kept(cfg):
    assert evaluate(job("Werkstudent ISMS & Azure Security"), cfg) is not None


def test_ausgeschlossene_firma(cfg):
    cfg["filter"]["ausschluss_firmen"] = ["ausgeschlossen"]
    assert evaluate(job("Werkstudent DevOps", company="Ausgeschlossen GmbH"), cfg) is None


def test_location_far_only_with_remote(cfg):
    assert evaluate(job("Werkstudent DevOps", location="München"), cfg) is None
    j = evaluate(job("Werkstudent DevOps", location="München", remote=True), cfg)
    assert j is not None and "Remote" in j.reason


def test_moenchengladbach_beyond_one_hour(cfg):
    assert travel_minutes("41066 Mönchengladbach") > 60
    assert evaluate(job("Werkstudent IT-Security", location="41066 Mönchengladbach"), cfg) is None


def test_role_from_kind_field(cfg):
    # Hochschulbörse: Rolle steckt im Stellentyp, Fachbezug im PDF-Text
    j = evaluate(job("Informatik (m/w/d)", kind="Werkstudentenstellen", desc="Betrieb unserer Azure Cloud"), cfg)
    assert j is not None


def test_bonus_flags(cfg):
    j = evaluate(job("Werkstudent DevOps", desc="Bachelorarbeit möglich, spätere Übernahme"), cfg)
    assert "Abschlussarbeit möglich" in j.flags and "Übernahmechance erwähnt" in j.flags


def test_short_keyword_needs_word_boundary(cfg):
    # "iam" darf nicht in "Williams" treffen
    assert evaluate(job("Werkstudent bei Williams"), cfg) is None


def test_normalize_and_key():
    assert normalize("Werkstudent*in Cloud (m/w/d)") == "werkstudent cloud"
    a = Job("Werkstudent Cloud (m/w/d)", "inovex GmbH", "u1", "BA")
    b = Job("Werkstudent:in Cloud", "inovex", "u2", "Firma")
    assert a.key == b.key


def test_non_it_internship_with_incidental_keywords_dropped(cfg):
    # Chemie-Praktikum, dessen Text zufällig "Sicherheit" und "Automatisierung" enthält
    j = job("Praktikant:in Innovation Management", location="Leverkusen",
            desc="Arbeitssicherheit, Automatisierung von Laborprozessen, Corporate Identity")
    assert evaluate(j, cfg) is None
    # Mit IT-Bezug im Titel reicht ein Fach-Stichwort in der Beschreibung
    assert evaluate(job("Werkstudent Softwareentwicklung", desc="Deployment auf Azure"), cfg) is not None
