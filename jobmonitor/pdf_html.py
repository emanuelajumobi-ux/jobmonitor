"""PDF aus HTML – für alle ohne LaTeX (cv.format: html, oder auto ohne latexmk).

Wie das PDF entsteht, ohne zusätzliche Installation:
- macOS: WebKit (die Engine von Safari) über pyobjc, in einem eigenen Prozess (pdf_webkit.py), A4 mit @page-Rändern.
- Windows: Microsoft Edge im Hintergrund (--headless --print-to-pdf), auf Windows 10/11 immer vorhanden.
- Sonst: ein Chromium-Browser (Chrome, Chromium, Edge, Brave), falls installiert.
Die Vorlagen (cv/template.html.j2, cv/anschreiben.html.j2) sind normales HTML/CSS mit Jinja2 und dem LaTeX-Layout
nachempfunden; deine LaTeX-Vorlage bleibt das Original, wenn LaTeX installiert ist.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BROWSER = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
BROWSER_NAMEN = ["chromium", "chromium-browser", "google-chrome", "microsoft-edge", "msedge", "brave-browser"]


class PdfError(Exception):
    pass


def _webkit() -> bool:
    if sys.platform != "darwin":
        return False
    import importlib.util
    return importlib.util.find_spec("WebKit") is not None   # pyobjc-framework-WebKit, kommt mit pywebview


def browser() -> str | None:
    for pfad in BROWSER:
        if Path(pfad).is_file():
            return pfad
    return next((p for n in BROWSER_NAMEN if (p := shutil.which(n))), None)


def verfuegbar() -> bool:
    return _webkit() or browser() is not None


def environment(template_dir: Path):
    import jinja2

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(template_dir)), autoescape=True,
                             trim_blocks=True, lstrip_blocks=True, undefined=jinja2.StrictUndefined)
    env.filters["tex"] = lambda v: "" if v is None else v      # gleiche Filter wie in den LaTeX-Vorlagen
    return env


def drucken(html_path: Path, pdf_path: Path, run=subprocess.run) -> Path:
    """HTML-Datei (Bilder relativ zu ihrem Ordner) als A4-PDF speichern."""
    html_path, pdf_path = html_path.resolve(), pdf_path.resolve()
    pdf_path.unlink(missing_ok=True)
    if _webkit():
        from .prozess import befehl
        cmd = befehl("pdf-webkit", str(html_path), str(pdf_path))
    elif (b := browser()) is not None:
        cmd = [b, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
               f"--print-to-pdf={pdf_path}", html_path.as_uri()]
    else:
        raise PdfError("Kein Programm für PDFs gefunden: LaTeX installieren oder einen Browser wie Chrome/Edge.")
    from .prozess import umgebung
    proc = run(cmd, capture_output=True, text=True, timeout=120, env=umgebung())
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise PdfError(f"PDF nicht erstellt: {(proc.stderr or proc.stdout or '').strip()[-300:] or 'unbekannter Fehler'}")
    return pdf_path
