"""HTTP-Server der lokalen Oberfläche: Routing der Seiten (GET) und Formulare (POST), Formulare und Uploads lesen,
Server starten. Die Seiten selbst baut gui.App.

Der Server hört nur auf 127.0.0.1. POST-Anfragen brauchen das zufällige Token der App, damit fremde Webseiten keine
Aktionen auslösen können.
"""
from __future__ import annotations

import logging
import secrets
import signal
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote

from . import gui_hilfe as gh
from . import gui_unterlagen as gu
from .config import load_config
from .gui import PORT, App, page
from .gui_sync import sync

log = logging.getLogger("jobmonitor.gui")

MAX_BODY = 25 * 1024 * 1024   # Uploads (Zeugnisse, Foto) bis 20 MB plus Formular

def parse_body(content_type: str, raw: bytes) -> tuple[dict, dict[str, list[tuple[str, bytes]]]]:
    """Formularfelder und hochgeladene Dateien. multipart/form-data für Uploads, sonst urlencoded."""
    if not content_type.startswith("multipart/form-data"):
        form = {k: v[0] for k, v in parse_qs(raw.decode("utf-8"), keep_blank_values=True).items()}
        return form, {}
    from email.parser import BytesParser
    from email.policy import default

    msg = BytesParser(policy=default).parsebytes(f"Content-Type: {content_type}\r\n\r\n".encode() + raw)
    form, uploads = {}, {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        data = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is not None:
            if data:
                uploads.setdefault(name, []).append((filename, data))
        else:
            form[name] = data.decode("utf-8")
    return form, uploads


def handler_for(app: App, server_ref: list):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.debug(fmt, *args)

        def _send(self, body: bytes, ctype: str = "text/html; charset=utf-8", status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location: str):
            self.send_response(303)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/ping":   # erkennt eine schon laufende Oberfläche (zweiter Start öffnet nur den Browser)
                return self._send(b"jobmonitor", "text/plain; charset=utf-8")
            if path == "/fokus":  # zweiter Start der App: vorhandenes Fenster nach vorn holen
                if app.window is not None:
                    app.window.restore()
                    app.window.show()
                return self._send(b"ok", "text/plain; charset=utf-8")
            if not app.ready and path in ("/", "/index.html"):
                return self._send(app.uebersetzt(page("Start", '<meta http-equiv="refresh" content="1"><div class="splash">'
                                                '<h1>Job-Monitor</h1><p>Synchronisiere mit GitHub …</p></div>')))
            alle = "alle=1" in query.split("&")
            traum = "traum=1" in query.split("&")
            if path in ("/", "/index.html"):
                profil = (parse_qs(query).get("profil") or [""])[0]
                return self._send(app.index(show_hidden=alle, nur_traum=traum, profil=profil))
            if path == "/master":
                return self._send(app.master())
            if path == "/einrichten":
                return self._send(app.einrichten())
            if path == "/ki-anleitung":
                return self._send(app.ki_anleitung())
            if path.startswith("/designs/vorschau/"):
                html = app.design_vorschau(path.removeprefix("/designs/vorschau/"))
                if html is not None:
                    return self._send(html)
            if path == "/bewerbungen":
                return self._send(app.bewerbungen(show_hidden=alle))
            if path == "/luecken":
                return self._send(app.luecken(nur_traum=traum))
            if path == "/eigene":
                return self._send(app.eigene())
            if path == "/profil":
                return self._send(app.profil())
            if path == "/firmen":
                return self._send(app.firmen())
            if path == "/einstellungen":
                return self._send(app.einstellungen())
            if path == "/einstellungen/suchprofil":
                return self._send(app.suchprofil((parse_qs(query).get("key") or [""])[0][:40]))
            if path == "/einstellungen/laeufe":
                return self._send(app.pipeline_laeufe())
            if path == "/hilfe":
                return self._send(app.page("Anleitung", gh.render(), "hilfe", gh.CSS))
            if path == "/einstellungen/datei":
                q = parse_qs(query)
                html = app.datei((q.get("name") or [""])[0], suche=(q.get("suche") or [""])[0][:200],
                                 von=(q.get("von") or [""])[0][:200])
                if html is not None:
                    return self._send(html)
            if path == "/unterlagen":
                return self._send(app.unterlagen())
            if path == "/unterlagen/foto":
                foto = gu.foto_path(app.root)
                if foto:
                    ctype = "image/png" if foto.suffix == ".png" else "image/jpeg"
                    return self._send(foto.read_bytes(), ctype)
            if path == "/master/nachweis":
                pdf = app.resolve_file(self.path)
                if pdf:
                    return self._send(pdf.read_bytes(), "application/pdf")
            if path.startswith("/unterlagen/"):
                slot, _, name = path.removeprefix("/unterlagen/").partition("/")
                if slot.isdigit():
                    pdf = gu.file_path(app.root, load_config(app.root / "config.yaml"), int(slot), name)
                    if pdf:
                        return self._send(pdf.read_bytes(), "application/pdf")
            if path == "/bewerbung":
                job_id = parse_qs(query).get("job", [""])[0]
                slug = app.bewerbung_open(job_id)
                if slug:
                    return self._redirect(f"/bewerbung/{quote(slug)}")
            if path.startswith("/bewerbung/"):
                parts = path.removeprefix("/bewerbung/").split("/")
                if len(parts) == 1:
                    body = app.bewerbung(parts[0])
                    if body:
                        return self._send(body)
                elif len(parts) == 2:
                    pdf = app.bewerbung_file(*parts)
                    if pdf:
                        return self._send(pdf.read_bytes(), "application/pdf")
            if path == "/rueckblick":
                return self._send(app.rueckblick())
            if path == "/bericht":
                return self._send(app.bericht())
            if path.startswith("/bericht/"):
                body = app.bericht_tag(path.removeprefix("/bericht/"))
                if body:
                    return self._send(body)
            if self.path.startswith("/pdf/"):
                path = app.pdf_path(self.path.removeprefix("/pdf/"))
                if path:
                    return self._send(path.read_bytes(), "application/pdf")
            self._send(b"Nicht gefunden", "text/plain; charset=utf-8", 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._send("Datei zu groß (max. 20 MB).".encode(), "text/plain; charset=utf-8", 413)
            form, uploads = parse_body(self.headers.get("Content-Type", ""), self.rfile.read(length))
            if not secrets.compare_digest(form.get("token", ""), app.token):
                return self._send(b"Ungueltiges Token. Seite neu laden.", "text/plain; charset=utf-8", 403)
            if self.path == "/cv":
                return self._send(app.make_cv(form))
            if self.path == "/master":
                return self._send(app.master_save(form))
            if self.path == "/bewerbungen":
                return self._send(app.bewerbungen_save(form))
            if self.path == "/einstellungen":
                return self._send(app.einstellungen_post(form))
            if self.path == "/einstellungen/suchprofil":
                return self._send(app.suchprofil_post(form))
            if self.path == "/einstellungen/datei":
                html = app.datei_post(form)
                if html is not None:
                    return self._send(html)
            if self.path == "/einrichten":
                return self._send(app.einrichten(form, uploads))
            if self.path == "/ablehnung":
                return self._send(app.ablehnung(form))
            if self.path == "/rueckkehr":
                return self._send(app.rueckkehr(form))
            if self.path == "/fitbegriffe":
                return self._send(app.fitbegriffe(form))
            if self.path == "/luecken/kenntnis":
                return self._send(app.luecken_kenntnis(form))
            if self.path == "/luecken/lernplan":
                return self._send(app.lernplan(form))
            if self.path == "/luecken/uebernehmen":
                return self._send(app.luecken_uebernehmen(form))
            if self.path == "/erinnern":
                return self._send(app.erinnern(form))
            if self.path == "/bewerbungen/nachgefasst":
                return self._send(app.nachgefasst(form))
            if self.path == "/bewerbungen/antwort":
                return self._send(app.antwort(form))
            if self.path == "/bewerbungen/firmenprofil":
                return self._send(app.firmenprofil(form))
            if self.path == "/bewerbungen/nachbereitung":
                return self._send(app.nachbereitung(form))
            if self.path == "/bewerbungen/anki":
                return self._send(app.anki(form))
            if self.path == "/bewerbungen/nachfassen_ki":
                return self._send(app.nachfassen_ki(form))
            if self.path == "/bewerbungen/vorbereitung":
                return self._send(app.vorbereitung(form))
            if self.path == "/bewerbungen/termin":
                return self._send(app.termin(form))
            if self.path == "/markieren":
                return self._send(app.markieren(form))
            if self.path == "/profil":
                return self._send(app.profil_post(form))
            if self.path == "/firmen/finden":
                return self._send(app.firmen_finden(form))
            if self.path == "/firmen/neu":
                return self._send(app.firmen_neu(form))
            if self.path == "/firmen/aktiv":
                return self._send(app.firmen_aktiv(form))
            if self.path == "/firmen/besucht":
                return self._send(app.firmen_besucht(form))
            if self.path == "/firmen/ignorieren":
                return self._send(app.firmen_ignorieren(form))
            if self.path == "/master/nachweis":
                return self._send(app.nachweis_upload(form, uploads), "application/json; charset=utf-8")
            if self.path == "/unterlagen/loeschen":
                return self._send(app.unterlagen_delete(form))
            if self.path.startswith("/unterlagen/"):
                return self._send(app.unterlagen_upload(self.path.removeprefix("/unterlagen/"), uploads))
            if self.path.startswith("/bewerbung/"):
                body = app.bewerbung_post(self.path.removeprefix("/bewerbung/"), form)
                if body:
                    return self._send(body)
            if self.path == "/darstellung":
                try:
                    app.darstellung(form)
                except Exception:   # nur Komfort: ohne Speichern bleibt die Umschaltung bis zum nächsten Seitenwechsel
                    log.exception("Darstellung nicht gespeichert")
                return self._send(b"ok", "text/plain")
            if self.path == "/oeffnen":
                ok = app.open_file(form.get("pfad", ""))
                return self._send(b"ok" if ok else b"nicht gefunden", "text/plain; charset=utf-8", 200 if ok else 404)
            if self.path == "/sync":
                return self._send(app.index(app.sync_card()))
            if self.path == "/reveal":
                path = app.pdf_path(form.get("name", "")) or app.root / "cv" / "out"
                subprocess.run(["open", "-R", str(path)])
                return self._send(app.index())
            if self.path == "/quit" and app.window is not None:   # App: Fenster schließen, desktop.py synchronisiert
                self._send(app.uebersetzt(page("Beendet", "<h1>Wird beendet …</h1><p>Synchronisiere mit GitHub.</p>")))
                threading.Thread(target=app.window.destroy, daemon=True).start()
                return
            if self.path == "/quit":
                card = app.sync_card()
                self._send(app.uebersetzt(page("Beendet", f"<h1>Beendet</h1>{card}<p>Du kannst dieses Fenster schließen.</p>")))
                threading.Thread(target=server_ref[0].shutdown, daemon=True).start()
                return
            self._send(b"Nicht gefunden", "text/plain; charset=utf-8", 404)

    return Handler


def already_running(port: int) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=1) as resp:
            return resp.read() == b"jobmonitor"
    except OSError:
        return False


def make_server(app: App, port: int) -> HTTPServer | None:
    """HTTP-Server auf 127.0.0.1, ab `port` den ersten freien Port."""
    server_ref: list = []
    for candidate in range(port, port + 20):
        try:
            server = HTTPServer(("127.0.0.1", candidate), handler_for(app, server_ref))
        except OSError:
            continue
        server_ref.append(server)
        return server
    return None


def serve(root: Path, port: int = PORT, open_browser: bool = True) -> int:
    """Browser-Variante (make gui, Job-Monitor.command). Die App-Variante steht in desktop.py."""
    if already_running(port):
        print("Läuft schon – öffne nur den Browser.")
        if open_browser:
            webbrowser.open(f"http://127.0.0.1:{port}/")
        return 0
    app = App(root)
    print("Synchronisiere mit GitHub …")
    app.startup()
    server = make_server(app, port)
    if server is None:
        print("Kein freier Port gefunden.")
        return 1
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Lebenslauf-Werkstatt läuft auf {url}  (Beenden: Button „Beenden“, Ctrl+C oder Fenster schließen)")

    def on_close(signum, frame):   # Terminalfenster geschlossen (SIGHUP) oder beendet (SIGTERM)
        raise KeyboardInterrupt

    signal.signal(signal.SIGHUP, on_close)
    signal.signal(signal.SIGTERM, on_close)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Synchronisiere vor dem Beenden …")
        result = sync(root)
        print(result.message)
    server.server_close()
    return 0
