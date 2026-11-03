"""Einstellungen → Dateien bearbeiten: Übersicht, Gliederung, Fehler mit Zeile, vorherige Fassung wiederherstellen."""
from jobmonitor import gui_dateien as gdt
from jobmonitor import gui_wartung as gw
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


def test_gliederung():
    text = "run:\n  modus: aktiv\nfilter:\n  min_score: 35\nunbekannt: 1\n"
    assert gdt.gliederung("config.yaml", text) == [(1, "Suche: Rhythmus und Modus", gdt.CONFIG_ABSCHNITTE["run"][1]),
                                                   (3, "Filter und Ausschlüsse", gdt.CONFIG_ABSCHNITTE["filter"][1]),
                                                   (5, "unbekannt", "")]
    firmen = "firmen:\n  - name: Zurich\n    x: 1\n  - name: 'AXA'\nhochschulen: []\n"
    assert [t for _, t, _ in gdt.gliederung("companies.yaml", firmen)] == ["Firmen", "  Zurich", "  AXA",
                                                                          "Hochschulbörsen"]
    assert gdt.gliederung("cv/anschreiben_vorlage.txt", "Hallo") == []


def test_fehler_mit_zeile():
    try:
        gw.pruefen("lernpfade.yaml", "a: 1\nb:\n  - x\n - y\n")
    except gw.WartungError as exc:
        meldung = str(exc)
    assert gdt.fehler_zeile(meldung) == 4 and "Einrückung" in gdt.fehler_html(meldung)
    assert gdt.fehler_zeile("ohne") is None


def test_uebersicht_und_editor(root):  # noqa: F811
    app = App(root, compile_pdf=False)
    html = app.einstellungen().decode()
    assert "Einstellungen der Suche" in html and 'href="/firmen">Firmen</a>' in html
    html = app.datei("config.yaml").decode()
    assert 'class="sprung"' in html and "Suche: Rhythmus und Modus" in html and 'id="zeilen"' in html
    assert "Vorherige Fassung wiederherstellen" not in html                    # noch keine .bak
    alt = (root / "config.yaml").read_text(encoding="utf-8")
    html = app.datei_post({"name": "config.yaml", "text": alt + "\nfoo: [\n"}).decode()
    assert "Nicht gespeichert" in html and 'data-fehler="' in html and 'data-fehler=""' not in html
    app.datei_post({"name": "config.yaml", "text": alt + "\n# Notiz\n"})
    assert "# Notiz" in (root / "config.yaml").read_text(encoding="utf-8")
    html = app.datei_post({"name": "config.yaml", "aktion": "wiederherstellen"}).decode()
    assert "Vorherige Fassung wiederhergestellt" in html
    assert (root / "config.yaml").read_text(encoding="utf-8").rstrip("\n") == alt.rstrip("\n")
    assert app.datei_post({"name": "../x", "aktion": "wiederherstellen"}) is None
