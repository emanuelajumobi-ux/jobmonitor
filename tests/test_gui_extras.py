"""Bewerbung verwerfen, Profil bearbeiten, Unterlagen hochladen."""
import shutil
import threading
import urllib.error
import urllib.request
import uuid
from http.server import HTTPServer

import pytest

from jobmonitor import bewerbung as bw
from jobmonitor import gui_profil as gp
from jobmonitor import gui_unterlagen as gu
from jobmonitor import tracking
from jobmonitor.config import ROOT, load_config
from jobmonitor.gui import App, handler_for, parse_body
from tests.conftest import FIXTURES

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
JPG = b"\xff\xd8\xff\xe0" + b"0" * 100
STELLE = {"id": "abc12345", "title": "Werkstudent Cloud", "company": "Beispiel AG", "url": "https://x/1",
          "anforderungen": {}}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    shutil.copy(FIXTURES / "cv_master_example.yaml", tmp_path / "cv" / "cv_master.yaml")
    for name in ("profile.example.yaml", "anschreiben_vorlage.txt"):
        shutil.copy(ROOT / "cv" / name, tmp_path / "cv" / name)
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    tracking.save(tmp_path / "applications.csv", [])
    app = App(tmp_path, compile_pdf=False)
    app.trash = tmp_path / "Papierkorb"
    return app


def test_discard_moves_to_trash_and_can_hide(app):
    cfg = load_config(app.root / "config.yaml")
    folder = bw.open_workspace(app.root, cfg, STELLE)
    (folder / "anschreiben.pdf").write_bytes(PDF)
    html = app.bewerbung_post(folder.name, {"aktion": "verwerfen", "ausblenden": "1"}).decode()
    assert "verworfen" in html and not folder.exists()
    assert (app.trash / folder.name / "anschreiben.pdf").exists()                 # wiederherstellbar
    assert tracking.load(app.root / "applications.csv")[0]["status"] == "verworfen"
    folder = bw.open_workspace(app.root, cfg, STELLE)                            # zweites Mal: Name mit Zeitstempel
    app.bewerbung_post(folder.name, {"aktion": "verwerfen"})
    assert len(list(app.trash.iterdir())) == 2


def test_profile_created_from_example_and_comments_kept(app):
    html = app.profil().decode()
    assert "Straße und Hausnummer" in html and (app.root / "cv" / "profile.yaml").exists()
    form = {"name": " Max Muster ", "adresse.ort": "Köln", "email": "max@example.com", "anzeigen.adresse": "1",
            "zeitraum": "ab März 2027"}
    assert "Gespeichert" in app.profil_post(form).decode()
    text = (app.root / "cv" / "profile.yaml").read_text(encoding="utf-8")
    assert "# profile.example.yaml" in text                                       # Kommentare bleiben
    data = gp.load(app.root)
    assert data["name"] == "Max Muster" and data["adresse"]["ort"] == "Köln" and data["zeitraum"] == "ab März 2027"
    assert data["anzeigen"]["adresse"] is True and data["anzeigen"]["foto"] is False
    html = app.profil_post({**form, "email": "kaputt"}).decode()
    assert "nicht gültig" in html and 'value="kaputt"' in html and gp.load(app.root)["email"] == "max@example.com"


def test_anlagen_upload_rules(app):
    cfg = load_config(app.root / "config.yaml")
    noten = next(i for i, s in enumerate(gu.slots(cfg)) if not s["ordner"])
    ordner = next(i for i, s in enumerate(gu.slots(cfg)) if s["ordner"])
    assert gu.save_anlage(app.root, cfg, noten, [("Noten WS.pdf", PDF)]) == ["notenuebersicht.pdf"]
    assert gu.save_anlage(app.root, cfg, ordner, [("Abi Zeugnis.pdf", PDF), ("Abi Zeugnis.pdf", PDF)]) == \
        ["abi-zeugnis.pdf", "abi-zeugnis-2.pdf"]
    with pytest.raises(gu.UploadError, match="kein PDF"):
        gu.save_anlage(app.root, cfg, ordner, [("virus.pdf", b"MZ\x90")])
    assert [p.name for p in bw.anlagen(app.root, cfg)[ordner]["pdfs"]] == ["abi-zeugnis-2.pdf", "abi-zeugnis.pdf"]
    assert gu.file_path(app.root, cfg, ordner, "../../config.yaml") is None
    assert "entfernt" in app.unterlagen_delete({"slot": str(ordner), "name": "abi-zeugnis-2.pdf"}).decode()
    assert len(gu.files(app.root, cfg, ordner)) == 1


def test_foto_upload_updates_profile(app):
    assert gu.save_foto(app.root, [("ich.jpeg", JPG)]) == "cv/private/foto.jpg"
    assert gp.load(app.root)["foto"] == "cv/private/foto.jpg"
    with pytest.raises(gu.UploadError, match="JPG oder PNG"):
        gu.save_foto(app.root, [("x.gif", b"GIF89a")])


def multipart(fields: dict, files: list[tuple[str, str, bytes]]) -> tuple[str, bytes]:
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for name, filename, data in files:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                 f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + b"\r\n"
    return f"multipart/form-data; boundary={boundary}", body + f"--{boundary}--\r\n".encode()


def test_parse_body_multipart():
    ctype, body = multipart({"token": "t", "x": "ä"}, [("datei", "a.pdf", PDF), ("datei", "b.pdf", PDF)])
    form, uploads = parse_body(ctype, body)
    assert form == {"token": "t", "x": "ä"} and [f for f, _ in uploads["datei"]] == ["a.pdf", "b.pdf"]
    assert uploads["datei"][0][1] == PDF


def test_upload_over_http_needs_token(app):
    server = HTTPServer(("127.0.0.1", 0), handler_for(app, []))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        for token, expected in (("falsch", 403), (app.token, 200)):
            ctype, body = multipart({"token": token}, [("datei", "foto.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50)])
            req = urllib.request.Request(base + "/unterlagen/foto", data=body, headers={"Content-Type": ctype})
            try:
                status = urllib.request.urlopen(req).status
            except urllib.error.HTTPError as exc:
                status = exc.code
            assert status == expected
        assert urllib.request.urlopen(base + "/unterlagen/foto").headers["Content-Type"] == "image/png"
    finally:
        server.shutdown()
        server.server_close()
