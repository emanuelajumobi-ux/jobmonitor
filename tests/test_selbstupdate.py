"""Update mit einem Klick: Paket finden und prüfen, entpacken, Tausch-Skript; Knopf im Hinweis."""
import hashlib
import io
import sys
import zipfile
from pathlib import Path

import pytest

from jobmonitor import selbstupdate, updates

REPO = "emanuelajumobi-ux/jobmonitor"


def _zip(name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{name}/inhalt.txt", "neu")
    return buf.getvalue()


class Antwort:
    def __init__(self, status=200, json_=None, body=b""):
        self.status_code, self._json, self.body = status, json_, body

    def json(self):
        return self._json

    def iter_content(self, n):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _get(body: bytes, digest: str | None, url: str | None = None):
    asset = {"name": selbstupdate.paketname(),
             "browser_download_url": url or f"https://github.com/{REPO}/releases/download/v9.9.9/x.zip"}
    if digest is not None:
        asset["digest"] = digest

    def get(adresse, **kw):
        return Antwort(json_={"assets": [asset]}) if "api.github.com" in adresse else Antwort(body=body)
    return get


@pytest.fixture
def programm(tmp_path, monkeypatch):
    alt = tmp_path / ("Job-Monitor.app" if sys.platform == "darwin" else "Job-Monitor")
    alt.mkdir()
    monkeypatch.setattr(selbstupdate, "programm", lambda *a, **k: alt)
    return alt


def test_herunterladen_mit_pruefsumme(programm):
    name = "Job-Monitor.app" if sys.platform == "darwin" else "Job-Monitor"
    body = _zip(name)
    neu = selbstupdate.herunterladen(REPO, "9.9.9", get=_get(body, "sha256:" + hashlib.sha256(body).hexdigest()))
    assert neu.name == name and (neu / "inhalt.txt").read_text() == "neu"
    with pytest.raises(selbstupdate.UpdateError, match="Prüfsumme"):
        selbstupdate.herunterladen(REPO, "9.9.9", get=_get(body, "sha256:" + "0" * 64))
    with pytest.raises(selbstupdate.UpdateError, match="Download-Adresse"):
        selbstupdate.herunterladen(REPO, "9.9.9", get=_get(body, None, "https://example.com/x.zip"))
    with pytest.raises(selbstupdate.UpdateError, match="keine Prüfsumme"):
        selbstupdate.herunterladen(REPO, "9.9.9", get=_get(body, None))


def test_ungueltiges_paket(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../boese.txt", "x")
    (tmp_path / "p.zip").write_bytes(buf.getvalue())
    with pytest.raises(selbstupdate.UpdateError):
        selbstupdate.entpacken(tmp_path / "p.zip", tmp_path / "neu", "win32")


def test_skripte(tmp_path):
    alt, neu = tmp_path / "Job-Monitor.app", tmp_path / ".job-monitor-update" / "neu" / "Job-Monitor.app"
    name, text = selbstupdate.skript(alt, neu, 4242, "darwin")
    assert name == "tauschen.sh" and "kill -0 4242" in text and f'mv "{neu}" "{alt}"' in text and "open" in text
    name, text = selbstupdate.skript(tmp_path / "Job-Monitor", tmp_path / "u" / "neu" / "Job-Monitor", 7, "win32")
    assert name == "tauschen.cmd" and 'PID eq 7' in text and "Job-Monitor.exe" in text
    assert text.strip().splitlines()[-1].startswith("rmdir")          # Aufräumen ganz zuletzt


def test_knopf_im_hinweis():
    neu = {"version": "9.9.9", "url": f"https://github.com/{REPO}/releases/tag/v9.9.9", "notizen": "- a"}
    assert "Jetzt aktualisieren" in updates.hinweis(neu, "tok", True)
    assert "Jetzt aktualisieren" not in updates.hinweis(neu, "tok", False)
    assert not selbstupdate.moeglich()                                   # Tests laufen nicht als installierte App


def test_mac_sonderfaelle(tmp_path, monkeypatch):
    import sys as _sys
    from jobmonitor import updates
    monkeypatch.setattr(_sys, "frozen", True, raising=False)
    monkeypatch.setattr(_sys, "platform", "darwin")
    verschoben = Path("/private/var/folders/x/AppTranslocation/ABC/d/Job-Monitor.app")
    monkeypatch.setattr(selbstupdate, "programm", lambda *a, **k: verschoben)
    assert selbstupdate.verschoben() and not selbstupdate.moeglich() and "Programme" in selbstupdate.grund()
    h = updates.hinweis({"version": "9.9.9", "url": "https://github.com/a/b"}, "t", False, selbstupdate.grund())
    assert "Programme" in h and "Jetzt aktualisieren" not in h          # sagt, was zu tun ist
    nur_lesen = tmp_path / "Programme" / "Job-Monitor.app"                # Standardbenutzer: Ordner nicht beschreibbar
    monkeypatch.setattr(selbstupdate, "programm", lambda *a, **k: nur_lesen)
    monkeypatch.setattr(selbstupdate, "beschreibbar", lambda *a: False)
    assert selbstupdate.moeglich() and selbstupdate.braucht_admin() and selbstupdate.grund() == ""
    assert "Caches" in str(selbstupdate._arbeit())
    h = updates.hinweis({"version": "9.9.9", "url": "https://github.com/a/b"}, "t", True, "", passwort=True)
    assert "Jetzt aktualisieren" in h and "Passwort eines Administrators" in h
    name, text = selbstupdate.skript(nur_lesen, tmp_path / "u" / "neu" / "Job-Monitor.app", 1, "darwin", admin=True)
    assert "with administrator privileges" in text and selbstupdate.ADMIN_SKRIPT in text and "mv " not in text
