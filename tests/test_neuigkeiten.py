"""Neuigkeiten je Version (Release-Text), Hinweis in der App, Glückwunsch bei der ersten Einladung."""
import importlib.util
from pathlib import Path

from jobmonitor import __version__, spenden, updates

WURZEL = Path(__file__).resolve().parent.parent


def _tool():
    spec = importlib.util.spec_from_file_location("neuigkeiten", WURZEL / "tools" / "neuigkeiten.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_abschnitt_je_version():
    tool = _tool()
    if not tool.DATEI.exists():          # öffentliches Repo ohne tools/-Kopie der Datei: nichts zu prüfen
        return
    assert tool.abschnitt(__version__), f"NEUIGKEITEN.md braucht einen Abschnitt „## {__version__}“"
    text = "## 2.0.0\n\n- **Neu:** a\n\n## 1.9.0\n\n- b\n"
    assert tool.abschnitt("2.0.0", text) == "- **Neu:** a" and tool.abschnitt("1.9.0", text) == "- b"
    assert tool.abschnitt("3.0.0", text) == ""


def test_hinweis_zeigt_liste():
    html = updates.notizen_html("- **Alles vorbereiten:** ein Klick\n- <b>x</b>\n\nInstallieren: herunterladen …")
    assert "<li><b>Alles vorbereiten:</b> ein Klick</li>" in html and "&lt;b&gt;" in html
    assert "Installieren" not in html


def test_erste_einladung_nur_einmal(tmp_path):
    cfg = {"spenden": {"url": "https://ko-fi.com/test"}}
    erste = spenden.einladung(tmp_path, cfg, "Beispiel AG")
    assert "Glückwunsch zur Einladung bei Beispiel AG" in erste and "ko-fi.com/test" in erste
    assert spenden.einladung(tmp_path, cfg, "Andere GmbH") == ""


def test_feedback_link_ohne_persoenliches():
    from urllib.parse import parse_qs, urlsplit
    from jobmonitor import feedback
    teile = urlsplit(feedback.link("fehler"))
    q = parse_qs(teile.query)
    assert teile.netloc == "github.com" and teile.path == "/emanuelajumobi-ux/jobmonitor/issues/new"
    assert q["title"] == ["[Fehler] "] and __version__ in q["body"][0] and "keine persönlichen Daten" in q["body"][0]
    assert "Fehler melden" in feedback.karte() and "Idee vorschlagen" in feedback.karte()
