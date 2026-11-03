"""Unterlagen in der Oberfläche hochladen: Anlagen für die Mappe (cv.anlagen in config.yaml) und Bewerbungsfoto.

Alles landet in cv/private/ bzw. den konfigurierten Pfaden (gitignored). Angenommen werden nur echte PDFs
(bzw. JPG/PNG beim Foto, geprüft am Dateiinhalt) bis 20 MB.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import quote

from . import gui_profil
from .cv_build import _slug

MAX_FILE = 20 * 1024 * 1024
NAME_RE = re.compile(r"^[a-z0-9-]{1,80}\.pdf$")
FOTO_DIR = "cv/private"


class UploadError(Exception):
    pass


def slots(cfg: dict) -> list[dict]:
    """Konfigurierte Anlagen: Einzeldatei (Pfad endet auf .pdf, Upload ersetzt) oder Ordner (Upload fügt hinzu)."""
    return [{**a, "ordner": not a["pfad"].lower().endswith(".pdf")} for a in cfg["cv"].get("anlagen") or []]


def _check(data: bytes) -> None:
    if len(data) > MAX_FILE:
        raise UploadError("Datei zu groß (max. 20 MB).")


def save_anlage(root: Path, cfg: dict, index: int, uploads: list[tuple[str, bytes]]) -> list[str]:
    slot = slots(cfg)[index]
    target = root / slot["pfad"]
    saved = []
    for filename, data in uploads:
        _check(data)
        if not data.startswith(b"%PDF-"):
            raise UploadError(f"„{filename}“ ist kein PDF.")
        if slot["ordner"]:
            target.mkdir(parents=True, exist_ok=True)
            stem = _slug(Path(filename).stem)[:60] or "anlage"
            dest, n = target / f"{stem}.pdf", 2
            while dest.exists():
                dest, n = target / f"{stem}-{n}.pdf", n + 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            dest = target
        dest.write_bytes(data)
        saved.append(dest.name)
        if not slot["ordner"]:
            break
    return saved


NACHWEIS_FALLBACK = "cv/private/anlagen"


def nachweis_ordner(cfg: dict) -> tuple[int | None, str]:
    """Ordner für Zertifikats-Nachweise: die erste Ordner-Anlage (Standard „Zeugnisse und Zertifikate“)."""
    return next(((i, s["pfad"]) for i, s in enumerate(slots(cfg)) if s["ordner"]), (None, NACHWEIS_FALLBACK))


def save_nachweis(root: Path, cfg: dict, zertifikat: str, filename: str, data: bytes) -> str:
    """Nachweis-PDF zu einem Zertifikat bei den Unterlagen speichern; ein erneuter Upload ersetzt ihn.
    Gibt den Pfad relativ zum Projekt zurück (wird im Master-CV als `nachweis` verknüpft)."""
    _check(data)
    if not data.startswith(b"%PDF-"):
        raise UploadError(f"„{filename}“ ist kein PDF.")
    _, ordner = nachweis_ordner(cfg)
    target = root / ordner
    target.mkdir(parents=True, exist_ok=True)
    dest = target / f"{_slug(zertifikat)[:60] or 'zertifikat'}.pdf"
    dest.write_bytes(data)
    return dest.relative_to(root).as_posix()


def nachweis_path(root: Path, cfg: dict, pfad: str) -> Path | None:
    """Verknüpften Nachweis auflösen – nur PDFs im Nachweis-Ordner (kein Zugriff auf andere Dateien)."""
    _, ordner = nachweis_ordner(cfg)
    base = (root / ordner).resolve()
    path = (root / pfad).resolve()
    return path if path.suffix == ".pdf" and path.parent == base and path.is_file() else None


def _zertifikate(root: Path) -> list[dict]:
    from .gui_master import load
    return [z for z in load(root).get("zertifikate") or [] if isinstance(z, dict) and z.get("nachweis")]


def verknuepft(root: Path) -> dict[str, str]:
    """Dateiname → Zertifikat, für die Anzeige bei den Unterlagen."""
    return {Path(str(z["nachweis"])).name: str(z.get("name") or "") for z in _zertifikate(root)}


DATUM_RE = re.compile(r"(?:(\d{1,2})\s*[/.]\s*)?((?:19|20)\d{2})")


def _datum_key(text) -> tuple[int, int]:
    """„09/2026“, „voraussichtlich 02/2027“, „2025“ → (Jahr, Monat); ohne Datum (0, 0)."""
    m = DATUM_RE.search(str(text or ""))
    return (int(m.group(2)), int(m.group(1) or 0)) if m else (0, 0)


def ordne(root: Path, pdfs: list[Path]) -> list[Path]:
    """Reihenfolge für „Zeugnisse und Zertifikate“ (Unterlagen und Mappe): erst Zeugnisse und andere Dateien
    ohne Zertifikat nach Dateiname, dann die im Master-CV verknüpften Zertifikate, neueste zuerst."""
    datum = {Path(str(z["nachweis"])).name: _datum_key(z.get("datum")) for z in _zertifikate(root)}
    andere = sorted((p for p in pdfs if p.name not in datum), key=lambda p: p.name)
    zert = sorted((p for p in pdfs if p.name in datum), key=lambda p: (datum[p.name], p.name), reverse=True)
    return andere + zert


def files(root: Path, cfg: dict, index: int) -> list[Path]:
    slot = slots(cfg)[index]
    path = root / slot["pfad"]
    if slot["ordner"]:
        return ordne(root, list(path.glob("*.pdf"))) if path.is_dir() else []
    return [path] if path.is_file() else []


def file_path(root: Path, cfg: dict, index: int, name: str) -> Path | None:
    if not 0 <= index < len(slots(cfg)):
        return None
    return next((p for p in files(root, cfg, index) if p.name == name), None)


def delete_anlage(root: Path, cfg: dict, index: int, name: str) -> bool:
    path = file_path(root, cfg, index, name)
    if path is None:
        return False
    path.unlink()
    return True


def save_foto(root: Path, uploads: list[tuple[str, bytes]]) -> str:
    _, data = uploads[0]
    _check(data)
    if data.startswith(b"\xff\xd8\xff"):
        ext = ".jpg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        ext = ".png"
    else:
        raise UploadError("Das Foto muss ein JPG oder PNG sein.")
    folder = root / FOTO_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("foto.*"):
        old.unlink()
    rel = f"{FOTO_DIR}/foto{ext}"
    (root / rel).write_bytes(data)
    gui_profil.set_foto(root, rel)
    return rel


def foto_path(root: Path) -> Path | None:
    return next(iter(sorted((root / FOTO_DIR).glob("foto.*"))), None) if (root / FOTO_DIR).is_dir() else None


def render(root: Path, cfg: dict, token: str, message: str = "") -> str:
    def upload_form(action: str, accept: str, multiple: bool, label: str) -> str:
        return (f'<form method="post" action="{action}" enctype="multipart/form-data" class="row" style="margin-top:8px">'
                f'<input type="hidden" name="token" value="{token}">'
                f'<input type="file" name="datei" accept="{accept}"{" multiple" if multiple else ""} required '
                f'style="width:auto;flex:1">'
                f'<button>{escape(label)}</button></form>')

    cards = []
    zu = verknuepft(root)
    for i, slot in enumerate(slots(cfg)):
        rows = "".join(
            f'<li><a href="/unterlagen/{i}/{quote(p.name)}" target="_blank" data-open>{escape(p.name)}</a> '
            + (f'<span class="chip new" title="im Master-CV verknüpft">{escape(zu[p.name])}</span> '
               if slot["ordner"] and p.name in zu else '') +
            f'<form method="post" action="/unterlagen/loeschen" style="display:inline" '
            f'onsubmit="return confirm(\'{escape(p.name)} entfernen?\')">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="slot" value="{i}">'
            f'<input type="hidden" name="name" value="{escape(p.name)}">'
            f'<button class="ghost small danger">entfernen</button></form></li>' for p in files(root, cfg, i))
        status = f"<ul>{rows}</ul>" if rows else '<p class="muted">Noch nichts hochgeladen.</p>'
        hint = ("Mehrere PDFs möglich. Reihenfolge wie in der Mappe, automatisch: erst Zeugnisse, dann Zertifikate "
                "mit Nachweis aus dem Master-CV, neueste zuerst." if slot["ordner"]
                else "Ein PDF; ein neuer Upload ersetzt das alte.")
        label = "Hinzufügen" if slot["ordner"] else ("Ersetzen" if rows else "Hochladen")
        cards.append(f'<div class="card"><h2>{escape(slot["name"])}</h2>{status}'
                     f'<p class="muted">{escape(hint)} <span class="chip">{escape(slot["pfad"])}</span></p>'
                     f'{upload_form(f"/unterlagen/{i}", ".pdf,application/pdf", slot["ordner"], label)}</div>')

    foto = foto_path(root)
    foto_html = ('<img src="/unterlagen/foto" alt="Bewerbungsfoto" style="max-width:120px;border-radius:6px">'
                 if foto else '<p class="muted">Noch kein Foto.</p>')
    cards.append(f'<div class="card"><h2>Bewerbungsfoto</h2>{foto_html}'
                 f'<p class="muted">JPG oder PNG. Ob es im Lebenslauf erscheint, stellst du im <a href="/profil">Profil</a> ein.</p>'
                 f'{upload_form("/unterlagen/foto", ".jpg,.jpeg,.png,image/jpeg,image/png", False, "Foto hochladen")}</div>')
    return ('<h1>Unterlagen</h1><p class="sub">Für die Bewerbungsmappe · alles bleibt lokal in cv/private/ '
            f'(gitignored).</p>{message}' + "".join(cards))
