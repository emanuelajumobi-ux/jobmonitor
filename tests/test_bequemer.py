"""Bequemer bewerben: Kopierhilfe für Portale, „Alles vorbereiten“, Anzeige sichern, Bewerbung auf Englisch."""
import json
from datetime import date

import pytest

from jobmonitor import bewerbung as bw
from jobmonitor import cv_build, ki, portal, sprache
from jobmonitor.config import load_config
from jobmonitor.cv_data import CvDataError, load_cv_master
from jobmonitor.gui import App
from tests.test_bewerbung import STELLE, root  # noqa: F401  (Fixture)
from tests.test_ki import FakeAsk

ENGLISCH = ("We are looking for a working student to join our cloud team. You will support our engineers with "
            "the operation of our Azure platform and help to automate the deployment of our services. Your "
            "profile: you are enrolled in computer science or a similar field, you have first experience with "
            "Terraform and you enjoy working in an international team. We offer flexible working hours and the "
            "chance to grow with us. Apply now and become part of the team that builds the future of our cloud.")


def test_kuerzen_an_satzgrenze():
    text = "Erster Satz ist kurz. Zweiter Satz ist etwas länger als der erste. Dritter Satz."
    assert portal.kuerzen(text, 200) == text
    assert portal.kuerzen(text, 40) == "Erster Satz ist kurz."
    assert portal.kuerzen("einwortohnepunkt " * 10, 30).endswith("…")
    assert len(portal.kuerzen("einwortohnepunkt " * 10, 30)) <= 30


def test_felder(root):  # noqa: F811
    cv, _ = load_cv_master(root)
    profile = bw.load_profile(root)
    felder = {f["key"]: f for f in portal.felder({**profile, "gehalt": "16 € pro Stunde"}, cv,
                                                 {"text": "Absatz eins.\n\n[Platzhalter]\n\nAbsatz zwei.",
                                                  "anrede": "Guten Tag,"}, "ab März 2027")}
    assert felder["vorname"]["wert"] == "Max" and felder["nachname"]["wert"] == "Muster"
    assert felder["email"]["wert"] == "max@example.com" and felder["plz"]["wert"] == "50667"
    assert felder["gehalt"]["wert"] == "16 € pro Stunde" and felder["verfuegbar"]["wert"] == "ab März 2027"
    assert felder["motivation"]["wert"] == "Absatz eins. Absatz zwei."            # ohne Platzhalter-Absatz
    assert felder["anschreiben"]["wert"].startswith("Guten Tag,") and "Max Muster" in felder["anschreiben"]["wert"]
    assert felder["kenntnisse"]["lang"] and "Azure" in felder["kenntnisse"]["wert"]
    html = portal.render(list(felder.values()), "tok", "/bewerbung/x", 300, True, {})
    assert 'data-copy="portal-email"' in html and "Für Bewerbungsportale" in html


def test_sprache_erkennen_und_beschriften(tmp_path):
    assert sprache.erkennen(ENGLISCH) == "en"
    assert sprache.erkennen("Wir suchen für unser Team in Köln eine Werkstudentin oder einen Werkstudenten, die "
                            "mit uns die Cloud-Plattform betreibt. Du bist eingeschrieben und hast Lust auf die "
                            "Arbeit in einem Team, das für die Kunden da ist. Wir bieten dir flexible Zeiten und "
                            "die Möglichkeit, bei uns zu wachsen und Verantwortung zu übernehmen.") == "de"
    assert sprache.erkennen("zu kurz") is None
    out = sprache.beschriften('<html lang="de"><h2>Berufserfahrung</h2><span>seit 07/2026</span>'
                              '<h2>Zertifikate und Weiterbildung</h2><p>Projektelemente</p>'
                              '<p>Mit freundlichen Grüßen</p>\\usepackage[ngerman]{babel}')
    assert 'lang="en"' in out and "Work Experience" in out and "since 07/2026" in out
    assert "Certifications and Training" in out and "Projektelemente" in out and "Kind regards" in out
    assert "[english]{babel}" in out
    assert sprache.datum(date(2026, 11, 3)) == "3 November 2026"
    assert sprache.profil_en({"anzeigen": {"foto": True, "geburtsdatum": True, "adresse": True}})["anzeigen"] == \
        {"foto": False, "geburtsdatum": False, "adresse": True}
    assert sprache.fuer_bewerbung(tmp_path) == "de"
    sprache.waehlen(tmp_path, "en")
    assert sprache.fuer_bewerbung(tmp_path) == "en"
    with pytest.raises(sprache.SpracheError):
        sprache.waehlen(tmp_path, "fr")


def test_uebersetzen(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    cfg = load_config(root / "config.yaml")
    cv, _ = load_cv_master(root)
    texte = sprache._texte(cv)

    class Uebersetzer(FakeAsk):
        def __call__(self, model, prompt, **kw):
            super().__call__(model, prompt, **kw)
            return json.dumps({"texte": [f"EN {t}" for _, t in texte]})

    ask = Uebersetzer()
    pfad = sprache.uebersetzen(root, cfg, cv, ask=ask)
    en = sprache.cv_en(root)
    assert pfad.name == "cv_master.en.yaml" and en["profil"].startswith("EN ")
    level = [e.get("level") for k in cv["kenntnisse"] for e in k["eintraege"] if isinstance(e, dict)]
    assert [e.get("level") for k in en["kenntnisse"] for e in k["eintraege"] if isinstance(e, dict)] == level
    assert all("EN " not in str(s.get("von")) for s in en["stationen"])                   # Zeiträume bleiben
    with pytest.raises(sprache.SpracheError):
        sprache.uebersetzen(root, cfg, cv, ask=FakeAsk('{"texte": ["nur einer"]}'))
    pfad.write_text("profil: x\nemail: a@b.de\n", encoding="utf-8")
    with pytest.raises(CvDataError):                                                       # Schutz wie beim Master-CV
        sprache.cv_en(root)


def test_englisch_bauen(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    text = bw.draft(root, cfg, STELLE, "en")
    assert text.startswith("I am applying for the position of Werkstudent Cloud Operations at Beispiel AG")
    assert "Azure and Terraform" in text and "{" not in text
    (root / "cv" / "cv_master.en.yaml").write_text("profil: Cloud security student.\nkenntnisse: []\n",
                                                    encoding="utf-8")
    html = cv_build.build(root, cfg, compile_pdf=False, design="modern", stelle=bw.meta(folder),
                          sprache="en").read_text(encoding="utf-8")
    assert 'lang="en"' in html and "Cloud security student." in html and "Profile" in html
    assert "Berufserfahrung" not in html and "Curriculum Vitae" in html


def test_bewerbungsseite(root, monkeypatch):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    folder = bw.open_workspace(root, cfg, STELLE)
    app = App(root, compile_pdf=False)
    html = app.bewerbung(folder.name).decode()
    assert "Alles vorbereiten" in html and "Sprache der Bewerbung" in html and "Für Bewerbungsportale" in html
    assert "Anzeige sichern" in html

    html = app.bewerbung_post(folder.name, {"aktion": "anzeige_eintragen", "anzeige": ENGLISCH}).decode()
    assert "Anzeigentext gespeichert" in html and "Gesicherte Anzeige" in html
    assert "Die Anzeige ist auf Englisch" in html                                         # Vorschlag
    html = app.bewerbung_post(folder.name, {"aktion": "sprache", "sprache": "en"}).decode()
    assert "Sprache: Englisch" in html and "Master-CV" in html                            # englische Fassung fehlt
    assert bw.letter(folder)["text"].startswith("I am applying") and bw.letter(folder)["anrede"] == bw.ANREDE_EN

    html = app.bewerbung_post(folder.name, {"aktion": "portal_grenze", "grenze": "1000"}).decode()
    assert 'value="1000" selected' in html

    gebaut = []
    monkeypatch.setattr(bw, "anzeige_sichern", lambda root_, cfg_, folder_: ENGLISCH)
    monkeypatch.setattr(bw, "build_mappe", lambda *a, **kw: (gebaut.append(kw) or (folder / "mappe.pdf", [])))
    monkeypatch.setattr(ki, "schluessel", lambda run=None: None)
    letter = bw.letter(folder)
    html = app.bewerbung_post(folder.name, {"aktion": "vorbereiten", "text": letter["text"],
                                            "anrede": letter["anrede"], "empfaenger": ""}).decode()
    assert "Alles vorbereitet" in html and "Anzeige gesichert" in html and "Mappe gebaut" in html and gebaut

    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    monkeypatch.setattr(App, "ki_cv_an", lambda self, cfg_: False)
    aufrufe = []
    monkeypatch.setattr(App, "_ki_anschreiben", lambda self, *a: (aufrufe.append(a) or ("KI text for Beispiel AG.", "")))
    html = app.bewerbung_post(folder.name, {"aktion": "vorbereiten", "text": letter["text"],
                                            "anrede": letter["anrede"], "empfaenger": ""}).decode()
    assert "Anschreiben mit KI entworfen" in html and aufrufe and aufrufe[0][-1] is True     # englisch
    assert bw.letter(folder)["text"] == "KI text for Beispiel AG."
    html = app.bewerbung_post(folder.name, {"aktion": "vorbereiten", "text": "Mein eigener Text.",
                                            "anrede": "Dear Ms Smith,", "empfaenger": ""}).decode()
    assert "dein Anschreiben übernommen" in html and len(aufrufe) == 1                     # eigener Text bleibt


def test_eigene_stelle_mit_ki(root, monkeypatch):  # noqa: F811
    from jobmonitor import eigene_stelle
    from jobmonitor.models import Job
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    cfg = load_config(root / "config.yaml")
    text = ("Wir suchen Verstärkung für den Betrieb unserer Cloud-Plattform. " * 6 +
            "Du bringst Erfahrung mit Azure mit, wünschenswert sind Kenntnisse in Terraform.")
    job = Job("Werkstudent Cloud", "Beispiel AG", "https://example.com/x", "eigene", description=text)
    antwort = json.dumps({"anforderungen": [{"begriff": "Azure", "bekannt": True, "pflicht": True},
                                            {"begriff": "Englisch", "bekannt": True, "pflicht": True}],
                          "eckdaten": {"stunden": "20 h/Woche"}})
    ask = ki.frage_funktion(root, cfg, ask=FakeAsk(antwort))
    stelle = eigene_stelle.prepare(job, root, cfg, ki_ask=ask)
    assert stelle["ki"] and "Englisch" in stelle["anforderungen"] and stelle["eckdaten"] == {"stunden": "20 h/Woche"}
    ohne = eigene_stelle.prepare(Job("Werkstudent Cloud", "Beispiel AG", "https://example.com/y", "eigene",
                                     description=text), root, cfg)
    assert not ohne["ki"] and "Englisch" not in ohne["anforderungen"]
