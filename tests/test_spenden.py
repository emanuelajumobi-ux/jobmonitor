"""Freiwillige Unterstützung: nur mit gültigem Link sichtbar, Glückwunsch beim Eintragen einer Zusage."""
from jobmonitor import spenden, tracking
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

KO = {"spenden": {"url": "https://ko-fi.com/beispiel"}}


def test_link_nur_wenn_gueltig():
    assert spenden.url(KO) == "https://ko-fi.com/beispiel" and "Unterstützen" in spenden.karte(KO)
    assert spenden.url({"spenden": {"url": "javascript:alert(1)"}}) == "" and spenden.karte({}) == ""
    assert "Glückwunsch zur Zusage bei Beispiel AG" in spenden.zusage({}, "Beispiel AG")
    assert "Unterstützen" not in spenden.zusage({}, "X") and "ko-fi.com" in spenden.zusage(KO, "X")


def test_zusage_in_der_app(root):  # noqa: F811
    text = (root / "config.yaml").read_text(encoding="utf-8")
    (root / "config.yaml").write_text(text.replace('spenden:\n  url: ""', 'spenden:\n  url: "https://ko-fi.com/beispiel"')
                                      if 'spenden:\n  url: ""' in text else text + '\nspenden:\n  url: "https://ko-fi.com/beispiel"\n',
                                      encoding="utf-8")
    tracking.save(root / "applications.csv", [{"firma": "Beispiel AG", "typ": "Stelle", "status": "beworben",
                                                "datum": "2026-10-01", "link": "https://x/1", "notizen": ""}])
    app = App(root, compile_pdf=False)
    assert 'id="unterstuetzen"' in app.einstellungen().decode()
    html = app.bewerbungen_save({"link_0": "https://x/1", "status_0": "Zusage", "datum_0": "2026-10-01",
                                 "notizen_0": ""}).decode()
    assert "Glückwunsch zur Zusage bei Beispiel AG" in html and "ko-fi.com/beispiel" in html
    html = app.bewerbungen_save({"link_0": "https://x/1", "status_0": "Zusage", "datum_0": "2026-10-01",
                                 "notizen_0": "x"}).decode()
    assert "Glückwunsch" not in html                                            # nur beim Wechsel auf Zusage
