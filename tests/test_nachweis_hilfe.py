"""Zertifikats-Nachweise aus dem Master-CV (Upload, Verknüpfung, Zugriff) und die Seite Anleitung."""
import json

import pytest

from jobmonitor import gui_hilfe as gh
from jobmonitor import gui_layout as layout
from jobmonitor import gui_master as gm
from jobmonitor import gui_unterlagen as gu
from jobmonitor.config import load_config
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

PDF = b"%PDF-1.4\n%test\n"


def test_save_and_resolve(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    assert gu.nachweis_ordner(cfg) == (2, "cv/private/anlagen")
    pfad = gu.save_nachweis(root, cfg, "Cisco CCNA", "scan.pdf", PDF)
    assert pfad == "cv/private/anlagen/cisco-ccna.pdf" and (root / pfad).read_bytes() == PDF
    assert gu.save_nachweis(root, cfg, "Cisco CCNA", "neu.pdf", PDF + b"2") == pfad      # ersetzt
    assert (root / pfad).read_bytes() == PDF + b"2"
    assert gu.nachweis_path(root, cfg, pfad) == (root / pfad).resolve()
    (root / "cv" / "profile.yaml").write_text("name: x\n", encoding="utf-8")
    for bad in ("cv/profile.yaml", "../etc/passwd", "cv/private/anlagen/../../profile.yaml", "cv/private/anlagen/x.pdf"):
        assert gu.nachweis_path(root, cfg, bad) is None
    with pytest.raises(gu.UploadError, match="kein PDF"):
        gu.save_nachweis(root, cfg, "X", "bild.png", b"\x89PNG")


def test_upload_endpoint_and_linking(root):  # noqa: F811
    app = App(root, compile_pdf=False)
    res = json.loads(app.nachweis_upload({"name": "AZ-900"}, {"datei": [("az.pdf", PDF)]}))
    assert res == {"pfad": "cv/private/anlagen/az-900.pdf"}
    assert "fehler" in json.loads(app.nachweis_upload({"name": "x"}, {}))
    assert "kein PDF" in json.loads(app.nachweis_upload({"name": "x"}, {"datei": [("a.txt", b"hallo")]}))["fehler"]
    # Verknüpfung im Master-CV, dann Anzeige bei den Unterlagen und Öffnen über den Link
    data = gm.load(root)
    data["zertifikate"][0]["nachweis"] = res["pfad"]
    gm.save(root, data)
    assert gu.verknuepft(root) == {"az-900.pdf": data["zertifikate"][0]["name"]}
    html = app.unterlagen().decode()
    assert "im Master-CV verknüpft" in html and data["zertifikate"][0]["name"] in html
    assert app.resolve_file(f"/master/nachweis?pfad={res['pfad']}") == (root / res["pfad"]).resolve()
    assert app.resolve_file("/master/nachweis?pfad=cv/profile.yaml") is None


def test_editor_has_upload_field(root):  # noqa: F811
    keys = [f["key"] for s in gm.SCHEMA if s["key"] == "zertifikate" for f in s["fields"]]
    assert "nachweis" in keys
    html = App(root, compile_pdf=False).master().decode()
    assert "/master/nachweis" in html and "Neuer Eintrag" in html and "item-head" in html


def test_help_page(root):  # noqa: F811
    assert ("hilfe", "Anleitung", "/hilfe", "System") in layout.NAV
    html = gh.render()
    for anker, titel, _ in gh.ABSCHNITTE:
        assert f'href="#{anker}"' in html and f'id="{anker}"' in html and titel in html
    # Links der Anleitung zeigen auf echte Seiten der App
    for href in ("/", "/bewerbungen", "/eigene", "/master", "/unterlagen", "/profil", "/luecken", "/firmen",
                 "/einstellungen"):
        assert f'href="{href}"' in html
    assert "nie etwas verschickt" in html


def test_zeugnisse_und_zertifikate_sortiert(root):  # noqa: F811
    from jobmonitor import bewerbung
    cfg = load_config(root / "config.yaml")
    i, ordner = gu.nachweis_ordner(cfg)
    alt = gu.save_nachweis(root, cfg, "Alt", "a.pdf", PDF)
    neu = gu.save_nachweis(root, cfg, "Neu", "n.pdf", PDF)
    ohne = gu.save_nachweis(root, cfg, "Ohne Datum", "o.pdf", PDF)
    (root / ordner / "zeugnis-praktikum.pdf").write_bytes(PDF)
    data = gm.load(root)
    data["zertifikate"] = [{"name": "Alt", "datum": "2024", "nachweis": alt},
                           {"name": "Ohne Datum", "datum": "", "nachweis": ohne},
                           {"name": "Neu", "datum": "voraussichtlich 03/2026", "nachweis": neu}]
    gm.save(root, data)
    erwartet = ["zeugnis-praktikum.pdf", "neu.pdf", "alt.pdf", "ohne-datum.pdf"]
    assert [p.name for p in gu.files(root, cfg, i)] == erwartet
    mappe = next(a for a in bewerbung.anlagen(root, cfg) if a["pfad"] == ordner)
    assert [p.name for p in mappe["pdfs"]] == erwartet


def test_profil_schalter(root):  # noqa: F811
    html = App(root, compile_pdf=False).profil().decode()
    assert html.count('role="switch"') == 3 and "wird angezeigt" in html and "ausgeblendet" in html
    assert 'class="check"' not in html.split("Was im Lebenslauf erscheint")[1]


def test_file_dialog_extensions():
    from jobmonitor import desktop
    pytest.importorskip("UniformTypeIdentifiers")
    assert desktop._extensions(["application/pdf"]) == ["pdf"]
    assert "jpg" in desktop._extensions(["image/jpeg", "image/png"])


def test_context_menu_filter():
    from jobmonitor import desktop
    for ident in ("WKMenuItemIdentifierCopy", "WKMenuItemIdentifierPaste", "WKMenuItemIdentifierLookUp", None):
        assert desktop._menu_behalten(ident)
    for ident in ("WKMenuItemIdentifierReload", "WKMenuItemIdentifierInspectElement", "WKMenuItemIdentifierGoBack"):
        assert not desktop._menu_behalten(ident)
