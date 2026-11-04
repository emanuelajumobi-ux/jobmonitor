"""Fit-System überarbeitet: Die KI entscheidet über die Anforderungen, Begriffe außerhalb der Liste zählen mit und
werden gegen den Lebenslauf geprüft, frühere zu ungenaue Begriffe zählen nicht mehr."""
from jobmonitor import fit
from jobmonitor.config import load_config
from jobmonitor.cv_data import covered_terms
from jobmonitor.erststart import DATEIEN
from jobmonitor.models import Job

CFG = {"begriffe": {"Python": [], "Englisch": ["english"]}, "optional_marker": ["von vorteil"],
       "min_anforderungen": 2}
CV = {"kenntnisse": [{"kategorie": "Programmierung", "eintraege": [{"name": "Java", "level": "gut"},
                                                                    {"name": "Python", "level": "sehr gut"}]}],
      "sprachen": [{"sprache": "Englisch", "niveau": "C1"}],
      "projekte": [{"name": "Shop", "technologien": ["React"], "status": "erreicht"}]}


def test_abdeckung_auch_ohne_fit_begriff():
    cov = covered_terms(CV, CFG["begriffe"])
    assert cov["Python"] == 1.0 and "Englisch" in cov
    assert "Java" in cov and cov["Java"] == 0.85                  # kein Fit-Begriff, aber im Lebenslauf
    assert "React" in cov and "Kotlin" not in cov                  # aus einem Projekt; Unbekanntes fehlt
    assert cov.get("Kotlin") is None


def test_ki_entscheidet():
    regel = {"Python": 1.0, "Englisch": 1.0}
    assert fit.ki_zusammenfuehren(regel, {}, {}) == regel                         # KI ohne Ergebnis: Stichwörter
    assert fit.ki_zusammenfuehren(regel, {"Python": 0.5}, {"Java": 1.0, "Python": 1.0}) == {"Python": 0.5, "Java": 1.0}
    job = Job("Werkstudent Softwareentwicklung", "X", "u", "s")
    fit.apply(job, {"Python": 0.5, "Java": 1.0, "Kotlin": 1.0, "Richtlinien": 1.0}, covered_terms(CV, CFG["begriffe"]),
              CFG)
    assert "Richtlinien" not in job.fit_anforderungen                             # früherer, zu ungenauer Begriff
    assert job.fit_passt == ["Java", "Python"] and job.fit_fehlt == ["Kotlin"]
    assert job.fit == round(100 * (0.85 + 0.5) / 2.5)


def test_begriffsliste_aufgeraeumt():
    for b in (load_config()["fit"]["begriffe"], load_config(DATEIEN["config.yaml"])["fit"]["begriffe"]):
        assert "Richtlinien" not in b and "Awareness" not in b and "Java" in b and "C#" in b
        assert "clients" not in b["Hardware"] and "dokumentation" not in b["Sicherheitsrichtlinien"]
        assert "support" not in b["IT-Support"]
    reqs = fit.requirements("Du erstellst Dokumentation für unsere Clients und hältst Richtlinien ein.",
                            load_config()["fit"]["begriffe"], ["von vorteil"])
    assert reqs == {}
