"""HTML → A4-PDF mit WebKit (macOS), als eigener Prozess: python -m jobmonitor.pdf_webkit eingabe.html ausgabe.pdf

Eigener Prozess, weil WebKit eine eigene Ereignisschleife braucht (die App-Oberfläche läuft schon in einer).
Ränder kommen aus @page der Vorlage; die Druckränder von macOS stehen auf 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

TIMEOUT_S = 60


def main(html: Path, out: Path) -> int:
    from AppKit import (NSApplication, NSBackingStoreBuffered, NSPrintInfo, NSPrintJobSavingURL, NSPrintSaveJob,
                        NSWindow)
    from Foundation import NSURL, NSDate, NSMakeRect, NSObject, NSRunLoop
    from WebKit import WKWebView, WKWebViewConfiguration

    NSApplication.sharedApplication()
    zustand = {"geladen": False, "fertig": None}

    class Laden(NSObject):
        def webView_didFinishNavigation_(self, view, navigation):
            zustand["geladen"] = True

    class Drucken(NSObject):
        def printOperationDidRun_success_contextInfo_(self, op, success, ctx):
            zustand["fertig"] = bool(success)

    def warten(bedingung, sekunden: float) -> bool:
        ende = NSDate.dateWithTimeIntervalSinceNow_(sekunden)
        while not bedingung() and NSDate.date().compare_(ende) < 0:
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
        return bedingung()

    rahmen = NSMakeRect(0, 0, 595, 842)
    view = WKWebView.alloc().initWithFrame_configuration_(rahmen, WKWebViewConfiguration.alloc().init())
    laden = Laden.alloc().init()
    view.setNavigationDelegate_(laden)
    fenster = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(NSMakeRect(-4000, -4000, 595, 842), 0,
                                                                           NSBackingStoreBuffered, False)
    fenster.setContentView_(view)
    view.loadFileURL_allowingReadAccessToURL_(NSURL.fileURLWithPath_(str(html)),
                                              NSURL.fileURLWithPath_(str(html.parent)))
    if not warten(lambda: zustand["geladen"], TIMEOUT_S):
        print("HTML nicht geladen", file=sys.stderr)
        return 1
    warten(lambda: False, 0.3)                       # Bilder und Schriften fertig zeichnen lassen

    info = NSPrintInfo.sharedPrintInfo().copy()
    info.setPaperSize_((595.28, 841.89))
    for rand in ("Top", "Bottom", "Left", "Right"):
        getattr(info, f"set{rand}Margin_")(0)
    info.setJobDisposition_(NSPrintSaveJob)
    info.dictionary()[NSPrintJobSavingURL] = NSURL.fileURLWithPath_(str(out))
    op = view.printOperationWithPrintInfo_(info)
    op.setShowsPrintPanel_(False)
    op.setShowsProgressPanel_(False)
    op.view().setFrame_(rahmen)
    drucken = Drucken.alloc().init()
    op.runOperationModalForWindow_delegate_didRunSelector_contextInfo_(
        fenster, drucken, b"printOperationDidRun:success:contextInfo:", None)
    if not warten(lambda: zustand["fertig"] is not None, TIMEOUT_S) or not zustand["fertig"]:
        print("Drucken fehlgeschlagen", file=sys.stderr)
        return 1
    return 0 if out.is_file() else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()))
