"""Persönliche Angaben (cv/profile.yaml) in der Oberfläche bearbeiten.

Die Datei ist gitignored, wird nie synchronisiert und nie an eine KI geschickt. Kommentare bleiben erhalten
(ruamel round-trip). Fehlt die Datei, wird sie aus cv/profile.example.yaml angelegt.
"""
from __future__ import annotations

import io
import re
import shutil
from html import escape
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

TEXT_FIELDS = [
    ("name", "Name"), ("adresse.strasse", "Straße und Hausnummer"), ("adresse.plz", "PLZ"),
    ("adresse.ort", "Ort"), ("telefon", "Telefon"), ("email", "E-Mail"), ("geburtsdatum", "Geburtsdatum"),
    ("links.linkedin", "LinkedIn (optional)"), ("links.github", "GitHub (optional)"),
    ("studium", "Studium für Anschreiben (optional, sonst aus dem Master-CV)"),
    ("zeitraum", "Zeitraum für Anschreiben, z. B. „ab März 2027 mit 20 Stunden pro Woche“"),
    ("gehalt", "Gehaltsvorstellung für Bewerbungsportale (optional), z. B. „16 € pro Stunde“"),
]
BOOL_FIELDS = [("anzeigen.adresse", "Adresse"),
               ("anzeigen.geburtsdatum", "Geburtsdatum"),
               ("anzeigen.foto", "Foto")]
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ProfilError(Exception):
    pass


def _yaml() -> YAML:
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.width = 4096
    yaml.preserve_quotes = True
    return yaml


def path(root: Path) -> Path:
    return root / "cv" / "profile.yaml"


def load(root: Path) -> CommentedMap:
    target = path(root)
    if not target.exists():
        example = root / "cv" / "profile.example.yaml"
        if not example.exists():
            return CommentedMap()
        shutil.copy(example, target)
    return _yaml().load(target.read_text(encoding="utf-8")) or CommentedMap()


def get(data, dotted: str):
    for key in dotted.split("."):
        data = data.get(key) if isinstance(data, dict) else None
    return data


def set_value(data: CommentedMap, dotted: str, value) -> None:
    *parents, last = dotted.split(".")
    for key in parents:
        if not isinstance(data.get(key), dict):
            data[key] = CommentedMap()
        data = data[key]
    data[last] = value


def save(root: Path, data: CommentedMap) -> None:
    buf = io.StringIO()
    _yaml().dump(data, buf)
    path(root).write_text(buf.getvalue(), encoding="utf-8")


def update(root: Path, form: dict) -> None:
    data = load(root)
    for key, _ in TEXT_FIELDS:
        if key in form:
            set_value(data, key, form[key].strip())
    email = (form.get("email") or "").strip()
    if email and not EMAIL.match(email):
        raise ProfilError("Die E-Mail-Adresse sieht nicht gültig aus.")
    for key, _ in BOOL_FIELDS:
        set_value(data, key, bool(form.get(key)))
    save(root, data)


def set_foto(root: Path, rel_path: str) -> None:
    data = load(root)
    set_value(data, "foto", rel_path)
    save(root, data)


def render(root: Path, token: str, message: str = "", form: dict | None = None) -> str:
    data = load(root)
    value = (lambda k: form.get(k, "")) if form else (lambda k: get(data, k) or "")
    inputs = "".join(f'<div><label>{escape(label)}</label><input name="{key}" value="{escape(str(value(key)))}"></div>'
                     for key, label in TEXT_FIELDS)
    checks = "".join(f'<label class="switch"><input type="checkbox" role="switch" name="{key}" value="1"'
                     f'{" checked" if (form.get(key) if form else get(data, key)) else ""}><span class="track"></span>'
                     f'<span>{escape(label)}</span><span class="state"><span class="on">· wird angezeigt</span>'
                     f'<span class="off">· ausgeblendet</span></span></label>' for key, label in BOOL_FIELDS)
    foto = get(data, "foto") or ""
    foto_html = (f'Foto: <span class="chip">{escape(foto)}</span>' if foto else "Noch kein Foto.")
    return f"""
<h1>Profil</h1>
<p class="sub">cv/profile.yaml · nur auf deinem Mac (gitignored, wird nie hochgeladen).</p>
{message}
<form method="post" action="/profil"><input type="hidden" name="token" value="{token}">
<div class="card"><h2>Kontakt und Briefkopf</h2><div class="grid2">{inputs}</div></div>
<div class="card"><h2>Was im Lebenslauf erscheint</h2><div class="switches">{checks}</div>
<p class="muted" style="margin-top:10px">{foto_html} Hochladen unter <a href="/unterlagen">Unterlagen</a>.</p></div>
<div class="sticky row"><button>Speichern</button><a class="btn ghost" href="/profil">Verwerfen</a></div>
</form>"""
