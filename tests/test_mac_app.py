import plistlib
import shutil
import sys
import threading
from http.server import HTTPServer

import pytest

from jobmonitor.gui import App, already_running, handler_for
from jobmonitor.mac_app import APP_NAME, create, launcher


def test_launcher_quotes_path(tmp_path):
    script = launcher(tmp_path / 'Claude Code' / 'job "monitor" $HOME')
    assert 'cd "' in script and 'job \\"monitor\\" \\$HOME' in script and "jobmonitor desktop" in script
    assert "/Library/TeX/texbin" in script   # latexmk auch beim Start aus dem Dock


def test_create_bundle(tmp_path):
    root = tmp_path / "Claude Code"
    root.mkdir()
    app = create(root)
    assert app == root / APP_NAME
    exe = app / "Contents" / "MacOS" / "Job-Monitor"
    start = app / "Contents" / "Resources" / "start.sh"
    assert exe.exists() and exe.stat().st_mode & 0o111
    assert start.stat().st_mode & 0o111 and str(root) in start.read_text(encoding="utf-8")
    # Mit swiftc: übersetztes Hauptprogramm (startet start.sh, sendet Mitteilungen), sonst das Skript selbst
    # (nur auf dem Mac: launcher.swift braucht AppKit, auf Linux gibt es swiftc ohne AppKit)
    assert (exe.read_bytes()[:2] == b"#!") == (sys.platform != "darwin" or shutil.which("swiftc") is None)
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleName"] == "Job-Monitor" and info["CFBundleExecutable"] == "Job-Monitor"
    if shutil.which("iconutil"):
        assert (app / "Contents" / "Resources" / "AppIcon.icns").stat().st_size > 10_000


def test_already_running_and_focus(tmp_path):
    app = App(tmp_path)
    calls = []

    class FakeWindow:
        def restore(self):
            calls.append("restore")

        def show(self):
            calls.append("show")

    app.window = FakeWindow()
    server = HTTPServer(("127.0.0.1", 0), handler_for(app, []))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        assert already_running(port)
        import urllib.request
        assert urllib.request.urlopen(f"http://127.0.0.1:{port}/fokus").read() == b"ok"
        assert calls == ["restore", "show"]
    finally:
        server.shutdown()
        server.server_close()
    assert not already_running(port)


def test_splash_while_syncing(tmp_path):
    app = App(tmp_path)
    app.ready = False
    server = HTTPServer(("127.0.0.1", 0), handler_for(app, []))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        import urllib.request
        html = urllib.request.urlopen(f"http://127.0.0.1:{server.server_address[1]}/").read().decode()
        assert "Synchronisiere" in html and 'http-equiv="refresh"' in html
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.skipif(shutil.which("osascript") is None, reason="nur auf macOS")
def test_desktop_falls_back_without_pywebview(monkeypatch, tmp_path):
    import builtins
    from jobmonitor import desktop
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "webview":
            raise ImportError
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(desktop, "serve", lambda root, port: 42)
    assert desktop.run(tmp_path) == 42


def test_adaptive_icon_from_assets_car(tmp_path, monkeypatch):
    import jobmonitor.mac_app as mac_app
    car = tmp_path / "Assets.car"
    car.write_bytes(b"car")
    monkeypatch.setattr(mac_app, "ASSETS_CAR", car)
    root = tmp_path / "repo"
    root.mkdir()
    app = mac_app.create(root)
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleIconName"] == "AppIcon" and info["CFBundleIconFile"] == "AppIcon"
    assert (app / "Contents" / "Resources" / "Assets.car").read_bytes() == b"car"


def test_icon_source_complete():
    import json
    from jobmonitor.mac_app import ICON_SOURCE, LAYERS
    manifest = json.loads((ICON_SOURCE / "icon.json").read_text(encoding="utf-8"))
    names = {layer["image-name"] for group in manifest["groups"] for layer in group["layers"]}
    assert names == {f"{n}.svg" for n in LAYERS}
    assert all((ICON_SOURCE / "Assets" / n).exists() for n in names)
