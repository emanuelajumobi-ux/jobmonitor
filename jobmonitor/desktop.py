"""Job-Monitor als App-Fenster (macOS-Webansicht über pywebview) statt Browser-Tab.

Start: Job-Monitor.app (erzeugt mit `make app`) oder `python -m jobmonitor desktop`. Der lokale Server läuft
wie bisher nur auf 127.0.0.1; das Fenster zeigt ihn an. Schließen des Fensters synchronisiert und beendet.
Ein zweiter Start holt das vorhandene Fenster nach vorn. Ohne pywebview fällt es auf den Browser zurück.
"""
from __future__ import annotations

import logging
import sys
import threading
import urllib.request
from pathlib import Path

from .gui import PORT, App, already_running, make_server, serve
from .gui_sync import sync

log = logging.getLogger(__name__)
APP_NAME = "Job-Monitor"
ICON = Path(__file__).parent / "assets" / "icon.png"


def _brand(root: Path) -> None:
    """Name im Menü und Icon im Dock (sonst stünde dort „Python“). Gibt es Job-Monitor.app, kommt das Icon von
    dort, so wie macOS es gerade darstellt (hell, dunkel, getönt oder transparent)."""
    try:
        from AppKit import NSApplication, NSImage, NSWorkspace
        from Foundation import NSBundle
    except ImportError:
        return
    info = NSBundle.mainBundle().infoDictionary()
    if info is not None:
        info["CFBundleName"] = APP_NAME
    bundle = root / f"{APP_NAME}.app"
    if bundle.exists():
        image = NSWorkspace.sharedWorkspace().iconForFile_(str(bundle))
    elif ICON.exists():
        image = NSImage.alloc().initWithContentsOfFile_(str(ICON))
    else:
        return
    NSApplication.sharedApplication().setApplicationIconImage_(image)


def _shadow(window) -> None:
    """pywebview schaltet bei transparenten Fenstern den Schatten ab – für ein normales Fenster wieder an."""
    try:
        native = window.native.window if hasattr(window.native, "window") else window.native
        native.setHasShadow_(True)
        native.invalidateShadow()
    except Exception:   # nur Optik
        log.debug("Fensterschatten nicht gesetzt", exc_info=True)


def erscheinung(wert: str) -> None:
    """Hell/Dunkel des App-Fensters (Einstellungen → Darstellung): auch das durchscheinende Material der Seitenleiste
    folgt dann der Wahl statt dem System. „auto“ = wie das System."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSAppearance, NSApplication
        from PyObjCTools import AppHelper
    except ImportError:
        return
    name = {"hell": "NSAppearanceNameAqua", "dunkel": "NSAppearanceNameDarkAqua"}.get(wert)

    def setzen():
        try:
            NSApplication.sharedApplication().setAppearance_(NSAppearance.appearanceNamed_(name) if name else None)
        except Exception:   # nur Optik
            log.debug("Darstellung nicht gesetzt", exc_info=True)
    AppHelper.callAfter(setzen)


def _extensions(mime_types) -> list[str]:
    """Dateiendungen zu den MIME-Typen aus `accept` (z. B. application/pdf → pdf, image/jpeg → jpeg, jpg, jpe)."""
    try:
        from UniformTypeIdentifiers import UTType
    except ImportError:
        return []
    out = []
    for mime in mime_types:
        t = UTType.typeWithMIMEType_(str(mime))
        for ext in (t.tags().get("public.filename-extension") or []) if t is not None else []:
            if str(ext) not in out:
                out.append(str(ext))
    return out


def _fix_file_dialog() -> None:
    """pywebview 6.1 erlaubt bei <input type="file" accept="…"> im Finder fest nur JPG (alles andere ausgegraut).
    Stattdessen die Endungen zum accept-Attribut erlauben; ohne accept bleibt alles wählbar."""
    try:
        from webview.platforms import cocoa
    except ImportError:
        return
    original = cocoa.BrowserView.create_file_dialog
    if getattr(original, "_jobmonitor", False):
        return

    def create_file_dialog(self, dialog_type, directory, allow_multiple, save_filename, file_filter,
                           main_thread=False):
        if file_filter is not None and not isinstance(file_filter, (list, tuple)):   # MIME-Typen von WebKit
            ext = _extensions(file_filter)
            file_filter = [("Dateien", ext)] if ext else None
        return original(self, dialog_type, directory, allow_multiple, save_filename, file_filter, main_thread)

    create_file_dialog._jobmonitor = True
    cocoa.BrowserView.create_file_dialog = create_file_dialog


# Rechtsklick-Menü: diese WebKit-Einträge passen nicht in eine App (Seite neu laden, Navigation, Entwicklerwerkzeuge,
# Links in neuem Fenster); alles andere bleibt, z. B. Kopieren, Einsetzen, Ausschneiden, Alles auswählen, Nachschlagen.
MENU_OHNE = ("Reload", "GoBack", "GoForward", "Stop", "InspectElement", "OpenLinkInNewWindow",
             "OpenImageInNewWindow", "OpenFrameInNewWindow", "OpenMediaInNewWindow", "DownloadLinkedFile",
             "DownloadImage", "DownloadMedia")


def _menu_behalten(identifier) -> bool:
    return not any(str(identifier or "").endswith(name) for name in MENU_OHNE)


def _fix_context_menu() -> None:
    """pywebview leert das Rechtsklick-Menü außerhalb des Debug-Modus ganz – dann geht Kopieren nur mit ⌘C.
    Stattdessen nur die unpassenden Einträge entfernen (Leerzeilen am Rand inklusive)."""
    try:
        import objc
        from webview.platforms import cocoa
    except ImportError:
        return

    def willOpenMenu_withEvent_(self, menu, event):
        for item in list(menu.itemArray()):
            if not _menu_behalten(item.identifier()):
                menu.removeItem_(item)
        items = list(menu.itemArray())
        while items and items[0].isSeparatorItem():
            menu.removeItem_(items.pop(0))
        while items and items[-1].isSeparatorItem():
            menu.removeItem_(items.pop())

    objc.classAddMethods(cocoa.BrowserView.WebKitHost,
                         [objc.selector(willOpenMenu_withEvent_, selector=b"willOpenMenu:withEvent:",
                                        signature=b"v@:@@")])


def _startbild_zu() -> None:
    try:
        from jobmonitor.app_start import startbild_schliessen
        startbild_schliessen()
    except Exception:
        pass


def _im_browser(app, server, url: str, root: Path) -> int:
    """Notlösung ohne App-Fenster: Oberfläche im Standard-Browser; „Beenden“ dort stoppt den Server."""
    import webbrowser
    _startbild_zu()
    app.window = None
    app.native = False
    webbrowser.open(url)
    fertig = threading.Event()
    _shutdown = server.shutdown

    def shutdown():
        _shutdown()
        fertig.set()
    server.shutdown = shutdown
    fertig.wait()
    server.server_close()
    log.info("Beim Beenden: %s", sync(root).message)
    return 0


def run(root: Path, port: int = PORT) -> int:
    try:
        import webview
    except ImportError:
        log.warning("pywebview fehlt (make setup-app) – öffne die Oberfläche im Browser.")
        return serve(root, port)
    if already_running(port):
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{port}/fokus", timeout=2).read() == b"browser":
                import webbrowser
                webbrowser.open(f"http://127.0.0.1:{port}/")   # erste Instanz läuft im Browser: Tab erneut öffnen
        except OSError:
            pass
        return 0

    app = App(root)
    app.ready = False
    server = make_server(app, port)
    if server is None:
        log.error("Kein freier Port gefunden.")
        return 1
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=app.startup, daemon=True).start()   # Sync im Hintergrund, Fenster zeigt solange „Start“

    _brand(root)
    _fix_file_dialog()
    _fix_context_menu()
    app.native = True
    # transparent + vibrancy: macOS-Material hinter dem Fenster, sichtbar in der Seitenleiste (Inhalt bleibt deckend).
    # text_select: pywebview sperrt sonst die Textauswahl im ganzen Fenster (kein Kopieren); Bedienelemente sperrt das CSS.
    mac = sys.platform == "darwin"     # Material hinter dem Fenster gibt es nur unter macOS
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    log.info("Fenster wird geöffnet (%s, pywebview %s)", sys.platform, getattr(webview, "__version__", "?"))
    app.window = webview.create_window(APP_NAME, url, width=1440, height=900, min_size=(900, 600), transparent=mac,
                                       vibrancy=mac, text_select=True)
    app.window.events.shown += lambda: _shadow(app.window)
    app.window.events.shown += lambda: log.info("Fenster angezeigt")
    app.window.events.shown += _startbild_zu
    try:
        from . import i18n
        from .config import load_config
        app.window.events.shown += lambda: erscheinung(i18n.darstellung(load_config(root / "config.yaml")))
    except Exception:   # nur Optik
        log.debug("Darstellung beim Start nicht gesetzt", exc_info=True)
    try:
        webview.start()      # blockiert, bis das Fenster geschlossen ist
    except Exception:        # z. B. Windows ohne WebView2: dann im Browser weiter statt gar nicht
        log.exception("App-Fenster ließ sich nicht öffnen – Oberfläche im Browser")
        return _im_browser(app, server, url, root)

    server.shutdown()
    server.server_close()
    result = sync(root)
    log.info("Beim Beenden: %s", result.message)
    return 0
