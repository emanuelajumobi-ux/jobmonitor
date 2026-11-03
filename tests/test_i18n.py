"""Englische Oberfläche: Übersetzung der fertigen Seite, Einstellung, Sprache beim ersten Start."""
from jobmonitor import erststart, i18n
from jobmonitor.config import load_config
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

ECHT = i18n.systemsprache        # vor dem Abschirmen in conftest.ohne_echte_ki gemerkt


def test_text_und_muster():
    assert i18n.text("Speichern") == "Save" and i18n.text("  Speichern\n") == "  Save\n"
    assert i18n.text("3 von 5 erfüllt") == "3 of 5 met"
    assert i18n.text("Flossbach von Storch SE ·") == "Flossbach von Storch SE ·"        # {n} nur für Zahlen
    assert i18n.text("Vorschau Klassisch") == "Preview Classic"                         # Teil selbst übersetzt
    assert i18n.text("Englisch: erfüllt Git: fehlt") == "Englisch: met Git: missing"
    assert i18n.text("Unbekannter Text bleibt") == "Unbekannter Text bleibt"


def test_seite_laesst_daten_stehen():
    html = i18n.seite('<html lang="de"><title>Stellen · Job-Monitor</title><p title="Hilfe zu dieser Seite">'
                      'Speichern</p><input value="Speichern" placeholder="Im Text suchen">'
                      '<button onclick="return confirm(\'Schlüssel aus dem Schlüsselspeicher löschen?\')">Kopieren'
                      '</button><textarea>Speichern</textarea><pre>Speichern</pre><script>x = \'Kopiert\';</script>')
    assert 'lang="en"' in html and "<title>Jobs · Job-Monitor</title>" in html
    assert 'title="Help for this page">Save</p>' in html and 'value="Speichern"' in html
    assert 'placeholder="Search in text"' in html and "confirm('Delete the key from the keychain?')" in html
    assert "<textarea>Speichern</textarea>" in html and "<pre>Speichern</pre>" in html and "'Copied'" in html


def test_einstellung_und_app(root):  # noqa: F811
    app = App(root, compile_pdf=False)
    assert "Sprache · Language" in app.einstellungen().decode()
    html = app.einstellungen_post({"aktion": "sprache_gui", "sprache": "en"}).decode()
    assert i18n.sprache(load_config(root / "config.yaml")) == "en"
    assert "Interface language saved." in html and ">Settings<" in html and 'lang="en"' in html
    assert ">Applications<" in app.bewerbungen().decode()
    app.einstellungen_post({"aktion": "sprache_gui", "sprache": "de"})
    assert ">Einstellungen<" in app.einstellungen().decode()
    assert "Unbekannte Sprache" in app.einstellungen_post({"aktion": "sprache_gui", "sprache": "fr"}).decode()


def test_setzen_ohne_gui_block(tmp_path):
    import re
    from jobmonitor.erststart import DATEIEN
    text = DATEIEN["config.yaml"].read_text(encoding="utf-8")
    (tmp_path / "config.yaml").write_text(re.sub(r"^gui:.*?(?=^\S)", "", text, flags=re.M | re.S), encoding="utf-8")
    assert "sprache:" not in (tmp_path / "config.yaml").read_text(encoding="utf-8")
    i18n.setzen(tmp_path, "en")
    assert i18n.sprache(load_config(tmp_path / "config.yaml")) == "en"
    i18n.setzen(tmp_path, "de")
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert text.count("sprache:") == 1 and "modus:" in text


def test_erster_start_in_systemsprache(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "systemsprache", lambda run=None: "en")
    erststart.vorbereiten(tmp_path)
    assert i18n.sprache(load_config(tmp_path / "config.yaml")) == "en"


def test_systemsprache():
    class Antwort:
        def __init__(self, out):
            self.stdout = out
    import sys
    if sys.platform == "darwin":
        assert ECHT(lambda *a, **k: Antwort("de_DE\n")) == "de"
        assert ECHT(lambda *a, **k: Antwort("en_GB\n")) == "en"
