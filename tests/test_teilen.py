"""Weiterempfehlen: Links zur Website, Karte in den Einstellungen, Eintrag in der Seitenleiste, Satz bei Zusage und
einmalig nach der ersten Mappe. Die App verschickt nichts selbst."""
from urllib.parse import parse_qs, urlparse

from jobmonitor import spenden, teilen, tracking
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


def test_links_zeigen_auf_die_website():
    l = teilen.links()
    text = parse_qs(urlparse(l["whatsapp"]).query)["text"][0]
    assert text.endswith(teilen.WEBSITE) and "Job-Monitor" in text
    assert parse_qs(urlparse(l["linkedin"]).query)["url"] == [teilen.WEBSITE]
    assert l["mail"].startswith("mailto:?subject=") and "github.com" not in "".join(l.values())
    assert "Have you heard" in parse_qs(urlparse(teilen.links("en")["whatsapp"]).query)["text"][0]


def test_karte_und_satz():
    html = teilen.karte()
    assert 'id="teilen"' in html and 'data-copy="teilen-link"' in html and "wa.me" in html
    assert "verschickt nichts" in html
    assert "Teile Job-Monitor" in spenden.zusage({}, "Beispiel AG")


def test_erste_mappe_nur_einmal(tmp_path):
    assert "erste Mappe" in teilen.erste_mappe(tmp_path)
    assert teilen.erste_mappe(tmp_path) == ""


def test_in_der_app(root):  # noqa: F811
    app = App(root, compile_pdf=False)
    seite = app.einstellungen().decode()
    assert 'id="teilen"' in seite and 'href="/einstellungen#teilen"' in seite and "Weiterempfehlen" in seite
    tracking.save(root / "applications.csv", [{"firma": "Beispiel AG", "typ": "Stelle", "status": "beworben",
                                                "datum": "2026-10-01", "link": "https://x/1", "notizen": ""}])
    html = app.bewerbungen_save({"link_0": "https://x/1", "status_0": "Zusage", "datum_0": "2026-10-01",
                                 "notizen_0": ""}).decode()
    assert "Teile Job-Monitor" in html


def test_englisch():
    from jobmonitor import i18n
    assert i18n.text("Weiterempfehlen") == "Recommend"
    assert i18n.text("Kennst du jemanden, der auch sucht? Teile Job-Monitor.").startswith("Know someone")
