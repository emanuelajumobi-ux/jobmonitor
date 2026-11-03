"""Bewerbung je Stelle: Anschreiben-Entwurf aus Textbausteinen, Anschreiben-PDF im CV-Layout, Lebenslauf, Mappe.

Alles liegt lokal in cv/bewerbungen/<firma-id>/ (gitignored): stelle.json (Anzeige-Metadaten), anschreiben.json
(dein bearbeiteter Text), anschreiben.pdf, lebenslauf.pdf und bewerbungsmappe-<firma>.pdf. Es wird nie etwas
verschickt. Persönliche Angaben kommen nur aus cv/profile.yaml.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime
from pathlib import Path

from pypdf import PdfWriter

from . import anschreiben_check, cv_check, suchprofil, tracking
from .cv_build import CvBuildError, _slug, build, compile_tex, environment, html_pdf, html_vorlage, load_profile, pdf_format
from .cv_data import covered_terms, load_cv_master

SLUG_RE = re.compile(r"^[a-z0-9-]{1,80}$")
FILE_RE = re.compile(r"^[a-z0-9.-]+\.pdf$")
PLACEHOLDER = re.compile(r"\[[^\]\n]+\]")
GENDER = re.compile(r"\s*\((?:[mwdxi*]\s*/\s*){1,3}[mwdxi*]\)|\s*\((?:all gender|gn|Mensch\*?)\)|\*in\b|:in\b",
                    re.IGNORECASE)
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]
ANREDE = "Sehr geehrte Damen und Herren,"


class BewerbungError(Exception):
    pass


def clean_title(title: str) -> str:
    return re.sub(r"\s{2,}", " ", GENDER.sub("", title)).strip(" -–")


def _monat(value: str) -> str:
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", (value or "").strip())
    return f"{MONATE[int(m.group(1)) - 1]} {m.group(2)}" if m and 1 <= int(m.group(1)) <= 12 else value


def _aufzaehlung(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " und " + items[-1]


# --- Ordner je Stelle ---
def base_dir(root: Path, cfg: dict) -> Path:
    return root / cfg["cv"]["bewerbungen"]


def open_workspace(root: Path, cfg: dict, stelle: dict) -> Path:
    """Ordner für eine Stelle anlegen bzw. finden. `stelle`: id, title, company, url, anforderungen."""
    slug = f"{_slug(stelle['company'])[:40]}-{_slug(str(stelle['id']))}".strip("-")
    folder = base_dir(root, cfg) / slug
    folder.mkdir(parents=True, exist_ok=True)
    meta = {k: stelle.get(k) for k in ("id", "title", "company", "url", "anforderungen", "frist", "profil")}
    (folder / "stelle.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return folder


def workspace(root: Path, cfg: dict, slug: str) -> Path | None:
    folder = base_dir(root, cfg) / slug
    return folder if SLUG_RE.match(slug) and (folder / "stelle.json").is_file() else None


def workspaces(root: Path, cfg: dict) -> list[Path]:
    base = base_dir(root, cfg)
    folders = [p for p in base.iterdir() if (p / "stelle.json").is_file()] if base.is_dir() else []
    return sorted(folders, key=lambda p: (p / "stelle.json").stat().st_mtime, reverse=True)


def meta(folder: Path) -> dict:
    return json.loads((folder / "stelle.json").read_text(encoding="utf-8"))


def letter(folder: Path) -> dict | None:
    path = folder / "anschreiben.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def save_letter(folder: Path, text: str, anrede: str, empfaenger: str) -> None:
    data = {"text": text.replace("\r\n", "\n").strip(), "anrede": anrede.strip() or ANREDE,
            "empfaenger": empfaenger.replace("\r\n", "\n").strip()}
    (folder / "anschreiben.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def files(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.glob("*.pdf"))


# --- Entwurf ---
def passende(cv: dict, anforderungen: dict[str, float], begriffe: dict) -> list[str]:
    """Belegte Anforderungen (Gefordertes zuerst), ohne Sprachen – „Erfahrungen mit Englisch“ klingt schief."""
    covered = covered_terms(cv, begriffe)
    sprachen = {str(s.get("sprache") or s.get("name") or "").lower() for s in cv.get("sprachen") or []
                if isinstance(s, dict)}
    order = sorted(anforderungen, key=lambda t: (-anforderungen[t], t.lower()))
    return [t for t in order if t in covered and t.lower() not in sprachen]


def _rolle(rolle: str) -> str:
    """„Werkstudent, IT-Enterprise Operations“ → „Werkstudent im Bereich IT-Enterprise Operations“."""
    head, sep, rest = (rolle or "").partition(", ")
    return f"{head} im Bereich {rest}" if sep else rolle


def zeitraum_aus(profile: dict, ziel) -> str | None:
    """Werkstudent: „zeitraum“ aus profile.yaml; andere Profile (z. B. Junior): „zeitraum_junior“, sonst None."""
    return profile.get(f"zeitraum_{ziel.key}") or (profile.get("zeitraum") if ziel.key == suchprofil.DEFAULT_KEY
                                                    else None)


def draft(root: Path, cfg: dict, stelle: dict) -> str:
    """Entwurf aus cv/anschreiben_vorlage.txt. Fehlende Angaben bleiben als [Platzhalter] stehen."""
    vorlage = (root / cfg["cv"]["anschreiben_vorlage"]).read_text(encoding="utf-8")
    body = "\n".join(line for line in vorlage.splitlines() if not line.startswith("#")).strip()
    cv, _ = load_cv_master(root)
    cv = cv or {}
    profile = load_profile(root) or {}

    ausbildung = (cv.get("ausbildung") or [{}])[0]
    studium = profile.get("studium") or (
        f"{ausbildung.get('abschluss')} an der {ausbildung.get('institution')}" if ausbildung.get("abschluss")
        else "[Studiengang und Hochschule]")
    aktuell = next((s for s in cv.get("stationen") or [] if not s.get("bis")), None)
    station_satz = (f"Seit {_monat(aktuell.get('von', ''))} arbeite ich als {_rolle(aktuell.get('rolle'))} bei "
                    f"{aktuell.get('organisation')}." if aktuell else "")
    passt = passende(cv, stelle.get("anforderungen") or {}, cfg["fit"]["begriffe"])[:4]
    ziel = suchprofil.get(cfg, stelle.get("profil"))
    zeitraum = zeitraum_aus(profile, ziel)
    values = {
        "firma": stelle["company"], "stelle": clean_title(stelle["title"]), "studium": studium,
        "station_satz": station_satz, "passt": _aufzaehlung(passt) if passt else "[deinen passenden Kenntnissen]",
        "zeitraum": zeitraum or ("[ab wann und wie viele Stunden pro Woche]" if ziel.key == suchprofil.DEFAULT_KEY
                                 else "[ab wann du nach dem Abschluss anfangen kannst]"),
        "zielrolle": ziel.zielrolle or "[Zielrolle]", "absicht": ziel.absicht or "[welche Stelle du suchst]",
        "ausblick": ziel.ausblick,
    }
    text = re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), body)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n[ \t]+", "\n", text)).strip()


def placeholders(text: str) -> list[str]:
    return PLACEHOLDER.findall(text or "")


# --- Anlagen ---
def anlagen(root: Path, cfg: dict) -> list[dict]:
    """Konfigurierte Anlagen mit gefundenen PDFs (Ordner: erst Zeugnisse, dann Zertifikate neueste zuerst)."""
    from .gui_unterlagen import ordne
    out = []
    for a in cfg["cv"].get("anlagen") or []:
        path = root / a["pfad"]
        pdfs = ordne(root, list(path.glob("*.pdf"))) if path.is_dir() else ([path] if path.is_file() else [])
        out.append({"name": a["name"], "pfad": a["pfad"], "pdfs": pdfs})
    return out


# --- Bauen ---
def build_anschreiben(root: Path, cfg: dict, folder: Path, today: date | None = None,
                      hinweise: list | None = None) -> Path:
    """`hinweise`: Liste, in die der Anschreiben-Prüfer (anschreiben_check.py) seine Hinweise schreibt."""
    data = letter(folder)
    if not data or not data["text"]:
        raise BewerbungError("Noch kein Anschreiben-Text gespeichert.")
    profile = load_profile(root)
    if profile is None:
        raise BewerbungError("cv/profile.yaml fehlt (Name und Kontaktdaten für den Briefkopf).")
    stelle = meta(folder)
    today = today or date.today()
    ort = (profile.get("adresse") or {}).get("ort") or ""
    context = {
        "profile": profile, "firma": stelle["company"],
        "empfaenger": [z for z in data["empfaenger"].splitlines() if z.strip()],
        "ort_datum": f"{ort + ', ' if ort else ''}{today:%d.%m.%Y}",
        "betreff": f"Bewerbung als {clean_title(stelle['title'])}", "anrede": data["anrede"],
        "absaetze": [a.strip() for a in re.split(r"\n\s*\n", data["text"]) if a.strip()],
        "anlagen": ["Lebenslauf"] + [a["name"] for a in anlagen(root, cfg) if a["pdfs"]],
    }
    latex_log: list[str] = []
    try:
        if pdf_format(cfg["cv"]) == "html":
            from . import pdf_html
            template = html_vorlage(root, cfg["cv"].get("anschreiben_html", "cv/anschreiben.html.j2"))
            html_path = folder / "anschreiben.html"
            html_path.write_text(pdf_html.environment(template.parent).get_template(template.name).render(**context),
                                 encoding="utf-8")
            pdf = html_pdf(html_path)
        else:
            template = root / cfg["cv"]["anschreiben_tex"]
            tex = environment(template.parent).get_template(template.name).render(**context)
            tex_path = folder / "anschreiben.tex"
            tex_path.write_text(tex, encoding="utf-8")
            pdf = compile_tex(tex_path, cfg["cv"]["engine"], latex_log)
    except CvBuildError as exc:
        raise BewerbungError(str(exc)) from None
    if hinweise is not None:
        andere = [meta(f)["company"] for f in workspaces(root, cfg) if f != folder]
        hinweise += anschreiben_check.check_text(data, stelle, cfg, andere, today)
        hinweise += cv_check.check_log("".join(latex_log), cfg) + anschreiben_check.check_pdf(pdf)
    return pdf


def build_lebenslauf(root: Path, cfg: dict, folder: Path, hinweise: list | None = None,
                     ki_zuschnitt: dict | None = None) -> Path:
    try:
        pdf = build(root, cfg, stelle=meta(folder), hinweise=hinweise, ki_zuschnitt=ki_zuschnitt)
    except CvBuildError as exc:
        raise BewerbungError(str(exc)) from None
    target = folder / "lebenslauf.pdf"
    shutil.copy(pdf, target)
    return target


def build_mappe(root: Path, cfg: dict, folder: Path, today: date | None = None,
                hinweise: dict[str, list] | None = None, ki_zuschnitt: dict | None = None) -> tuple[Path, list[str]]:
    """Anschreiben + Lebenslauf + Anlagen als ein PDF. Gibt (Pfad, fehlende Anlagen) zurück und setzt die Stelle
    in applications.csv auf Entwurf (falls noch nicht weiter). `hinweise`: {"anschreiben": [], "lebenslauf": []}
    bekommt die Ergebnisse beider Prüfer."""
    hinweise = hinweise if hinweise is not None else {}
    parts = [build_anschreiben(root, cfg, folder, today, hinweise.setdefault("anschreiben", [])),
             build_lebenslauf(root, cfg, folder, hinweise.setdefault("lebenslauf", []), ki_zuschnitt)]
    fehlend = []
    for a in anlagen(root, cfg):
        parts += a["pdfs"]
        if not a["pdfs"]:
            fehlend.append(a["name"])
    stelle = meta(folder)
    target = folder / f"bewerbungsmappe-{_slug(stelle['company'])[:40]}.pdf"
    writer = PdfWriter()
    for part in parts:
        writer.append(str(part))
    with open(target, "wb") as fh:
        writer.write(fh)

    apps_path = root / "applications.csv"
    rows = tracking.load(apps_path)
    tracking.add_if_missing(rows, stelle["company"], "Stelle", stelle["url"], today or date.today(), stelle["title"])
    row = next(r for r in rows if r.get("link") == stelle["url"])
    if row.get("status") in ("", "neu", "verworfen"):
        row["status"] = "Entwurf"
    tracking.save(apps_path, rows)
    return target, fehlend


def discard(folder: Path, trash: Path | None = None) -> Path:
    """Bewerbungsordner in den Papierkorb verschieben (wiederherstellbar). Gibt das Ziel zurück."""
    trash = trash or Path.home() / ".Trash"
    trash.mkdir(parents=True, exist_ok=True)
    target = trash / folder.name
    if target.exists():
        target = trash / f"{folder.name}-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.move(str(folder), str(target))
    return target
