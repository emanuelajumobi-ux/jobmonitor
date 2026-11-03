"""Anschreiben-Prüfer: Firma, fremde Firma, Stelle, Anrede, Länge, Frist, PDF; Einbindung in Bau und Oberfläche."""
import shutil
from datetime import date

import pytest

from jobmonitor import bewerbung as bw
from jobmonitor.anschreiben_check import check_pdf, check_text
from jobmonitor.config import load_config
from jobmonitor.gui import App, pruefung_html
from tests.test_bewerbung import STELLE, blank_pdf, root  # noqa: F401  (Fixture)

GOOD = ("mit großem Interesse habe ich Ihre Ausschreibung als Werkstudent Cloud Operations bei der Beispiel AG "
        "gelesen. " + "Im Studium habe ich Azure und Terraform eingesetzt und dabei viel gelernt. " * 12)


def letter(text=GOOD, anrede="Sehr geehrte Damen und Herren,"):
    return {"text": text, "anrede": anrede, "empfaenger": ""}


def texts(hinweise):
    return " | ".join(str(h) for h in hinweise)


def test_good_letter_has_no_hints(cfg):
    assert check_text(letter(), STELLE, cfg, ["Andere GmbH"], date(2026, 11, 1)) == []


def test_company_missing_or_copied(cfg):
    text = GOOD.replace("Beispiel AG", "Musterfirma GmbH")
    out = check_text(letter(text), STELLE, cfg, ["Musterfirma GmbH", "REWE Group"])
    assert [h.stufe for h in out] == ["warnung", "warnung"]
    assert "„Beispiel AG“ kommt im Text nicht vor" in out[0].text and "„Musterfirma GmbH“" in out[1].text
    # Rechtsform und Schreibweise egal; eigene Firma nicht als „fremd“ melden
    assert check_text(letter(GOOD.replace("Beispiel AG", "BEISPIEL")), STELLE, cfg, ["Beispiel AG"]) == []


def test_title_reference(cfg):
    text = GOOD.replace("als Werkstudent Cloud Operations ", "")
    out = check_text(letter(text.replace("Azure", "Python")), STELLE, cfg)
    assert texts(out).startswith("Tipp: Der Stellentitel")
    assert check_text(letter(text), STELLE, cfg) != [] and "Stellentitel" in texts(check_text(letter(text), STELLE,
                                                                                             cfg))
    assert "Stellentitel" not in texts(check_text(letter(text.replace("Azure", "Cloud")), STELLE, cfg))


@pytest.mark.parametrize("anrede, erwartet", [
    ("Sehr geehrte Damen und Herren", "endet nicht mit einem Komma"),
    ("Sehr geehrte Herr Müller,", "„Sehr geehrter Herr …“"),
    ("Sehr geehrter Frau Schmidt,", "„Sehr geehrte Frau …“"),
    ("Sehr geehrte Frau,", "fehlt der Name"),
])
def test_salutation(cfg, anrede, erwartet):
    assert erwartet in texts(check_text(letter(anrede=anrede), STELLE, cfg))


def test_salutation_ok(cfg):
    for anrede in ("Sehr geehrter Herr Dr. Müller,", "Sehr geehrte Frau Schmidt,", "Hallo Team,"):
        assert check_text(letter(anrede=anrede), STELLE, cfg) == []


def test_length_and_ich(cfg):
    assert "nur 16 Wörter" in texts(check_text(letter(GOOD[:110]), STELLE, cfg))
    assert "Wörter; mit bis zu 380" in texts(check_text(letter(GOOD + "Noch mehr Text dazu. " * 60), STELLE, cfg))
    ich = GOOD + " ".join(f"Ich kann Punkt {i} gut." for i in range(5))
    assert "5 Sätze beginnen mit „Ich“" in texts(check_text(letter(ich), STELLE, cfg))


def test_deadline(cfg):
    stelle = {**STELLE, "frist": "2026-10-15"}
    assert "Bewerbungsfrist (15.10.2026) ist abgelaufen" in texts(check_text(letter(), stelle, cfg, today=date(2026, 11, 1)))
    assert check_text(letter(), stelle, cfg, today=date(2026, 10, 1)) == []


def test_pdf_pages(tmp_path):
    blank_pdf(tmp_path / "a.pdf", pages=2)
    blank_pdf(tmp_path / "b.pdf")
    assert "2 Seiten" in texts(check_pdf(tmp_path / "a.pdf")) and check_pdf(tmp_path / "b.pdf") == []


def test_gui_card_titles():
    assert "Prüfung des Anschreibens: keine Auffälligkeiten" in pruefung_html([], "Anschreiben")
    assert "Prüfung des Lebenslaufs: keine Auffälligkeiten" in pruefung_html([])


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="LaTeX nur lokal installiert")
def test_build_and_page_show_both_checks(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    other = bw.open_workspace(root, cfg, {**STELLE, "id": "fff00000", "company": "Musterfirma GmbH"})
    assert other.exists()
    folder = bw.open_workspace(root, cfg, STELLE)
    bw.save_letter(folder, "Ich möchte zur Musterfirma GmbH.", "Sehr geehrte Damen und Herren,", "")
    hinweise = {}
    bw.build_mappe(root, cfg, folder, date(2026, 11, 20), hinweise)
    assert "Beispiel AG“ kommt im Text nicht vor" in texts(hinweise["anschreiben"])
    assert "Musterfirma GmbH“ – Anschreiben aus einer anderen Bewerbung" in texts(hinweise["anschreiben"])
    assert isinstance(hinweise["lebenslauf"], list)

    app = App(root)
    html = app.bewerbung_post(folder.name, {"aktion": "anschreiben", "text": "Ich möchte zur Musterfirma GmbH.",
                                            "anrede": "Sehr geehrte Damen und Herren,", "empfaenger": ""}).decode()
    assert "Prüfung des Anschreibens" in html and "Prüfung des Lebenslaufs" not in html
    html = app.bewerbung_post(folder.name, {"aktion": "mappe", "text": "Ich möchte zur Musterfirma GmbH.",
                                            "anrede": "Sehr geehrte Damen und Herren,", "empfaenger": ""}).decode()
    assert "Prüfung des Anschreibens" in html and "Prüfung des Lebenslaufs" in html
