"""Passende Firmen finden (KI), Hell/Dunkel-Schalter, Unterstützen in der Seitenleiste, Designs groß ansehen."""
import json

import pytest

from jobmonitor import firmen_finder, i18n, ki
from jobmonitor.config import load_config
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)
from tests.test_ki import FakeAsk

ANTWORT = {"firmen": [
    {"name": "Muster Energie GmbH", "kategorie": "energie", "branche": "Energieversorger", "standorte": ["Köln"],
     "fokus": ["Cloud"], "karriereseite_url": "https://karriere.muster-energie.de/jobs", "warum": "Azure im Betrieb."},
    {"name": "Jobbörse AG", "kategorie": "sonstige", "karriereseite_url": "https://www.linkedin.com/company/x"},
    {"name": "Ohne Adresse", "kategorie": "msp"},
    {"name": "Muster Energie", "kategorie": "energie", "karriereseite_url": "https://muster-energie.de"},
    {"name": "Kleines Systemhaus", "kategorie": "gibtsnicht", "karriereseite_url": "https://ks.de/karriere"}]}


@pytest.fixture
def app(root, monkeypatch):  # noqa: F811
    (root / "companies.yaml").write_text("firmen: []\n", encoding="utf-8")
    return App(root, compile_pdf=False)


def test_finden_raeumt_auf(app, root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    ask = FakeAsk(json.dumps(ANTWORT))
    liste = firmen_finder.finden(root, load_config(root / "config.yaml"), {"profil": "x"}, "Mittelstand", 10, ask=ask)
    assert [f["name"] for f in liste] == ["Muster Energie GmbH", "Kleines Systemhaus"]   # Börse, ohne URL, doppelt raus
    assert liste[1]["kategorie"] == "sonstige" and "Mittelstand" in ask.prompts[0]
    html = app.firmen().decode()
    assert "Passende Firmen finden" in html and "Muster Energie GmbH" in html and "Neue Liste erstellen" in html
    app.firmen_neu({"name": "Muster Energie GmbH", "karriereseite_url": "https://karriere.muster-energie.de/jobs",
                    "kategorie": "energie"})
    app.firmen_ignorieren({"name": "Kleines Systemhaus"})
    html = app.firmen().decode()
    assert "0 noch offen" in html


def test_ohne_ki_und_fehler(app, root, monkeypatch):  # noqa: F811
    assert "KI einrichten" in app.firmen().decode()
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "sk-ant-test")
    with pytest.raises(ki.KiError):
        firmen_finder.finden(root, load_config(root / "config.yaml"), {}, ask=FakeAsk("keine Liste"))


def test_darstellung_und_unterstuetzen(app, root):  # noqa: F811
    html = app.index().decode()
    assert 'data-darstellung="auto"' in html and "data-theme" not in html.split("<head>")[0]
    app.darstellung({"wert": "dunkel"})
    assert i18n.darstellung(load_config(root / "config.yaml")) == "dunkel"
    assert '<html lang="de" data-theme="dunkel">' in app.index().decode()
    text = (root / "config.yaml").read_text(encoding="utf-8")
    text = text.replace('url: ""', 'url: "https://ko-fi.com/test"') if 'url: ""' in text else text
    (root / "config.yaml").write_text(text, encoding="utf-8")
    if "ko-fi.com/test" in text or "paypal" in text:
        assert 'class="spenden"' in app.index().decode()


def test_designs_gross(app):
    html = app.master().decode()
    assert 'data-gross="modern"' in html and 'id="design-gross"' in html
