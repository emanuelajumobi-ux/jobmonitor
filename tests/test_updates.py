"""Update-Hinweis der installierten App: höchstens einmal am Tag prüfen, nur neuere Versionen melden, abschaltbar."""
import sys
from datetime import date

from jobmonitor import __version__, updates

CFG = {"updates": {"enabled": True, "repo": "emanuelajumobi-ux/jobmonitor"}}


class Antwort:
    def __init__(self, tag, status=200):
        self.status_code, self._tag = status, tag

    def json(self):
        return {"tag_name": self._tag, "html_url": "https://github.com/emanuelajumobi-ux/jobmonitor/releases/x",
                "body": "Neu: Update-Hinweis\n<script>"}


def test_versionen():
    assert updates.version_tupel("v1.10.0") > updates.version_tupel("1.9.3")
    assert updates.version_tupel("1.0.0") == (1, 0, 0) and updates.version_tupel("") == (0,)


def test_pruefen_einmal_am_tag(tmp_path):
    aufrufe = []

    def get(url, **kw):
        aufrufe.append(url)
        return Antwort("v99.0.0")
    neu = updates.pruefen(tmp_path, CFG, get, date(2026, 11, 3))
    assert neu["version"] == "99.0.0" and aufrufe == ["https://api.github.com/repos/emanuelajumobi-ux/jobmonitor/releases/latest"]
    assert updates.pruefen(tmp_path, CFG, get, date(2026, 11, 3))["version"] == "99.0.0" and len(aufrufe) == 1
    html = updates.hinweis(neu)
    assert "Version 99.0.0 ist da" in html and f"du hast {__version__}" in html and "&lt;script&gt;" in html
    assert updates.pruefen(tmp_path, CFG, lambda u, **kw: Antwort(f"v{__version__}"), date(2026, 11, 4)) is None
    assert updates.hinweis(None) == ""


def test_offline_und_abschalten(tmp_path, monkeypatch):
    def kaputt(url, **kw):
        raise OSError("offline")
    assert updates.pruefen(tmp_path, CFG, kaputt, date(2026, 11, 3)) is None
    assert not updates.aktiv(tmp_path, CFG)                                   # Entwicklungsordner: aus
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert updates.aktiv(tmp_path, CFG) and not updates.aktiv(tmp_path, {"updates": {"repo": "kein repo"}})
    updates.schalten(tmp_path, False)
    assert not updates.aktiv(tmp_path, CFG) and "Wieder nach Updates suchen" in updates.karte(tmp_path, CFG, "t")
    assert "javascript:" not in updates.hinweis({"version": "2.0.0", "url": "javascript:alert(1)", "notizen": ""})
