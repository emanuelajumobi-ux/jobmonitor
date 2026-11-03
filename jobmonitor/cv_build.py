"""Lebenslauf lokal bauen: cv_master.yaml + profile.yaml → LaTeX (Jinja2-Vorlage) → PDF mit latexmk.

Läuft nur auf deinem Rechner (`make cv`). Ergebnisse landen in cv/out/ (gitignored). Der Zuschnitt auf eine
Stelle sortiert und wählt nur aus – es wird nichts hinzuerfunden.
"""
from __future__ import annotations

import copy
import logging
import re
import shutil
import subprocess
from pathlib import Path

from ruamel.yaml import YAML

from . import cv_check
from .cv_data import CvDataError, _entries, covered_terms, load_cv_master
from .scoring import has
from .state import State

log = logging.getLogger(__name__)

LATEX_SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
                 "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
LATEX_RE = re.compile("|".join(re.escape(c) for c in LATEX_SPECIAL))
ENGINES = {"pdflatex": "-pdf", "xelatex": "-xelatex", "lualatex": "-lualatex"}
PLACEHOLDER_RE = re.compile(r"\[[^\]\n]+\]")
CV_LISTS = ("stationen", "ausbildung", "kenntnisse", "zertifikate", "projekte", "sprachen", "interessen")


class CvBuildError(Exception):
    pass


def latex_escape(value) -> str:
    """Filter `tex` der Vorlage: & % $ # _ { } ~ ^ \\ escapen, None → ''."""
    if value is None:
        return ""
    return LATEX_RE.sub(lambda m: LATEX_SPECIAL[m.group()], str(value))


def environment(template_dir: Path):
    import jinja2  # nur lokal installiert (requirements-cv.txt)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        block_start_string=r"\BLOCK{", block_end_string="}",
        variable_start_string=r"\VAR{", variable_end_string="}",
        comment_start_string=r"\#{", comment_end_string="}",
        trim_blocks=True, lstrip_blocks=True, autoescape=False, undefined=jinja2.StrictUndefined,
    )
    env.filters["tex"] = latex_escape
    return env


def _relevance(entry: dict, terms: dict[str, list[str]]) -> int:
    text = " ".join([str(entry.get("name", "")), str(entry.get("beschreibung", ""))]
                    + [str(t) for t in entry.get("technologien") or []]).lower()
    return sum(1 for variants in terms.values() if any(has(text, v) for v in variants))


def tailor(cv: dict, anforderungen: dict[str, float], begriffe: dict, max_projekte: int) -> dict:
    """Kopie des Lebenslaufs mit passenden Kenntnissen/Projekten zuerst. Reihenfolge sonst stabil."""
    cv = copy.deepcopy(cv)
    terms = {t: [t.lower()] + [s.lower() for s in begriffe.get(t) or []] for t in anforderungen}
    if cv.get("kenntnisse"):
        kategorien = []
        for k in _entries(cv["kenntnisse"]):
            if "eintraege" in k:
                k["eintraege"] = sorted(_entries(k["eintraege"]), key=lambda e: -_relevance(e, terms))
                k["_relevanz"] = sum(_relevance(e, terms) for e in k["eintraege"])
            else:
                k["_relevanz"] = _relevance(k, terms)
            kategorien.append(k)
        cv["kenntnisse"] = sorted(kategorien, key=lambda k: -k.pop("_relevanz"))
    if cv.get("projekte"):
        projekte = _entries(cv["projekte"])
        sichtbar = sorted((p for p in projekte if p.get("im_cv") is not False), key=lambda p: -_relevance(p, terms))
        cv["projekte"] = sichtbar[:max_projekte]
    return cv


def ki_anwenden(cv: dict, full_cv: dict, zuschnitt: dict, begriffe: dict, max_projekte: int) -> tuple[dict, list[str]]:
    """KI-Zuschnitt (ki.lebenslauf) prüfen und anwenden: nur Auswahl und Reihenfolge vorhandener Aufgaben und
    Projekte. Der neue Profiltext wird verworfen, wenn er eine Fachkenntnis nennt, die der Lebenslauf nicht belegt."""
    cv, hinweise = copy.deepcopy(cv), []
    profil = str(zuschnitt.get("profil") or "").strip()
    if profil:
        from .ki import unbelegt
        fremd = unbelegt(profil, full_cv, begriffe)
        if fremd:
            hinweise.append(f"KI-Profiltext verworfen: nennt {', '.join(fremd[:3])}, das der Master-CV nicht belegt.")
        elif 60 <= len(profil) <= 600:
            cv["profil"] = profil
            hinweise.append("Profiltext von der KI auf die Stelle zugeschnitten – bitte gegenlesen.")
    for i, station in enumerate(cv.get("stationen") or []):
        original = (full_cv.get("stationen") or [])[i].get("aufgaben") if i < len(full_cv.get("stationen") or []) else None
        wahl = (zuschnitt.get("aufgaben") or {}).get(str(i))
        if not isinstance(station, dict) or not original or not isinstance(wahl, list):
            continue
        idx = list(dict.fromkeys(j for j in wahl if isinstance(j, int) and 0 <= j < len(original)))
        if len(idx) >= min(3, len(original)):
            station["aufgaben"] = [original[j] for j in idx]
    sichtbar = [p for p in _entries(full_cv.get("projekte") or []) if p.get("im_cv") is not False]
    wahl = zuschnitt.get("projekte")
    if isinstance(wahl, list) and sichtbar:
        idx = list(dict.fromkeys(j for j in wahl if isinstance(j, int) and 0 <= j < len(sichtbar)))
        if idx:
            cv["projekte"] = [copy.deepcopy(sichtbar[j]) for j in idx][:max_projekte]
    return cv, hinweise


def complete_cv(cv: dict) -> dict:
    """Fehlende Abschnitte als leere Listen und Kenntnisse ohne Level als 'gut', damit die Vorlage
    (StrictUndefined) nicht stolpert."""
    cv = {"profil": "", **{key: [] for key in CV_LISTS}, **cv}
    for key in CV_LISTS:
        cv[key] = [item if not isinstance(item, dict) else dict(item) for item in cv[key] or []]
    for k in cv["kenntnisse"]:
        if isinstance(k, dict) and "eintraege" in k:
            k["eintraege"] = [{"level": "gut", **e} for e in _entries(k["eintraege"])]
    return cv


def _merge(schema, data):
    if isinstance(schema, dict):
        data = data if isinstance(data, dict) else {}
        return {**data, **{key: _merge(value, data.get(key)) for key, value in schema.items()}}
    return schema if data is None else data


def load_profile(root: Path) -> dict | None:
    """cv/profile.yaml (Fallback: profile.yaml in der Repo-Wurzel), ergänzt um das Schema aus
    cv/profile.example.yaml, damit fehlende Felder leer statt fehlerhaft sind."""
    path = next((p for p in (root / "cv" / "profile.yaml", root / "profile.yaml") if p.exists()), None)
    if path is None:
        return None
    yaml = YAML(typ="safe")
    profile = yaml.load(path.read_text(encoding="utf-8")) or {}
    example = root / "cv" / "profile.example.yaml"
    schema = (yaml.load(example.read_text(encoding="utf-8")) or {}) if example.exists() else {}
    return _merge(schema, profile)


def placeholders(node, path: str = "") -> list[str]:
    """Pfade aller Werte, die noch Platzhalter wie [Beginn] enthalten (ohne die Werte selbst)."""
    if isinstance(node, dict):
        return [hit for key, value in node.items() for hit in placeholders(value, f"{path}.{key}".lstrip("."))]
    if isinstance(node, list):
        return [hit for i, item in enumerate(node) for hit in placeholders(item, f"{path}[{i}]")]
    return [path] if isinstance(node, str) and PLACEHOLDER_RE.search(node) else []


def render(cv: dict, profile: dict, template_path: Path, extra: dict | None = None) -> str:
    env = environment(template_path.parent)
    return env.get_template(template_path.name).render(cv=complete_cv(cv), profile=profile, **(extra or {}))


def _slug(text: str) -> str:
    text = text.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40]


def build(root: Path, cfg: dict, job_id: str | None = None, compile_pdf: bool = True,
          stelle: dict | None = None, hinweise: list | None = None, ki_zuschnitt: dict | None = None) -> Path:
    """Erzeugt cv/out/lebenslauf[-firma-id].tex (+ .pdf). Gibt den Pfad der Hauptdatei zurück.

    `job_id`: Stelle aus dem Bericht (state/seen.sqlite). `stelle`: selbst angegebene Stelle als
    {"id", "company", "anforderungen", ...}, z. B. aus eigene_stelle.py.
    `hinweise`: Liste, in die der Lebenslauf-Prüfer (cv_check.py) seine Hinweise schreibt.
    `ki_zuschnitt`: Ergebnis von ki.lebenslauf (nur mit Stelle), wird geprüft angewendet.
    """
    try:
        cv, _ = load_cv_master(root)
    except CvDataError as exc:
        raise CvBuildError(str(exc)) from None
    if cv is None:
        raise CvBuildError("cv_master.yaml fehlt (Repo-Wurzel oder cv/).")
    profile = load_profile(root)
    if profile is None:
        raise CvBuildError("cv/profile.yaml fehlt. Kopiere cv/profile.example.yaml und trage deine Daten ein.")
    for where, data in (("cv_master.yaml", cv), ("profile.yaml", profile)):
        hits = placeholders(data)
        if hits:
            log.warning("Platzhalter in %s noch nicht ausgefüllt: %s", where, ", ".join(hits))

    ccfg = cfg["cv"]
    name, extra = "lebenslauf", {"stelle": None}
    detail = stelle
    if job_id:
        state = State(root / "state" / "seen.sqlite", readonly=True)
        detail = state.job_detail(job_id)
        state.close()
        if detail is None:
            raise CvBuildError(f"Stelle '{job_id}' nicht gefunden (ID aus dem Bericht, ggf. vorher `git pull`).")
    full_cv = cv
    if detail is not None:
        cv = tailor(cv, detail["anforderungen"], cfg["fit"]["begriffe"], ccfg["max_projekte_zugeschnitten"])
        if ki_zuschnitt:
            cv, ki_hinweise = ki_anwenden(cv, full_cv, ki_zuschnitt, cfg["fit"]["begriffe"],
                                          ccfg["max_projekte_zugeschnitten"])
            if hinweise is not None:
                hinweise += [cv_check.Hinweis("tipp", h) for h in ki_hinweise]
        covered = covered_terms(cv, cfg["fit"]["begriffe"])
        extra["stelle"] = {**detail, "passt": [t for t in detail["anforderungen"] if t in covered]}
        name = f"lebenslauf-{_slug(detail['company'])}-{detail['id']}"

    out_dir = root / ccfg["ausgabe"]
    out_dir.mkdir(parents=True, exist_ok=True)
    foto = profile.get("foto")
    src = Path(foto).expanduser() if foto else None
    if src is not None and not src.is_absolute():
        src = root / src
    if src is not None and src.is_file():
        shutil.copy(src, out_dir / f"foto{src.suffix.lower()}")
        profile = {**profile, "foto": f"foto{src.suffix.lower()}"}   # LaTeX mag keine Leerzeichen im Pfad
    elif foto:
        log.warning("Foto aus profile.yaml nicht gefunden, PDF ohne Foto.")
        profile = {**profile, "foto": ""}

    if pdf_format(ccfg) == "html":
        from . import pdf_html
        template = html_vorlage(root, ccfg.get("vorlage_html", "cv/template.html.j2"))
        html_path = out_dir / f"{name}.html"
        html_path.write_text(pdf_html.environment(template.parent).get_template(template.name).render(
            cv=complete_cv(cv), profile=profile, **extra), encoding="utf-8")
        _pruefen(hinweise, full_cv, cv, detail, cfg)
        if not compile_pdf:
            return html_path
        pdf = html_pdf(html_path)
        if hinweise is not None:
            hinweise += cv_check.check_pdf(pdf, cfg)
        return pdf

    template = root / ccfg["vorlage"]
    if not template.exists():
        raise CvBuildError(f"Vorlage {ccfg['vorlage']} fehlt.")
    for helper in template.parent.iterdir():   # .cls/.sty/Bilder neben der Vorlage mitnehmen
        if helper.suffix in (".cls", ".sty") and helper.is_file():
            shutil.copy(helper, out_dir / helper.name)
    tex_path = out_dir / f"{name}.tex"
    tex_path.write_text(render(cv, profile, template, extra), encoding="utf-8")

    _pruefen(hinweise, full_cv, cv, detail, cfg)
    if not compile_pdf:
        return tex_path
    latex_log: list[str] = []
    pdf = compile_tex(tex_path, ccfg["engine"], latex_log)
    if hinweise is not None:
        hinweise += cv_check.check_log("".join(latex_log), cfg) + cv_check.check_pdf(pdf, cfg)
    return pdf


def _pruefen(hinweise: list | None, full_cv: dict, cv: dict, detail: dict | None, cfg: dict) -> None:
    """Inhaltliche Prüfung des Lebenslaufs (unabhängig von LaTeX oder HTML)."""
    if hinweise is None:
        return
    from datetime import date
    from .cv_aktuell import pruefen as veraltet
    hinweise += [cv_check.Hinweis("warnung", f"{v.text} (Master-CV)") for v in veraltet(full_cv, date.today())]
    hinweise += cv_check.check_content(complete_cv(cv), cfg)
    if detail is not None:
        hinweise += cv_check.check_tailoring(full_cv, cv, detail["anforderungen"], cfg["fit"]["begriffe"])


def pdf_format(ccfg: dict) -> str:
    """„latex“ (deine .tex-Vorlage) oder „html“ (cv/*.html.j2, pdf_html.py). cv.format: latex | html | auto –
    auto nimmt LaTeX, wenn latexmk installiert ist, sonst HTML."""
    fmt = ccfg.get("format", "latex")
    if fmt == "auto":
        return "latex" if shutil.which("latexmk") else "html"
    return "html" if fmt == "html" else "latex"


def html_vorlage(root: Path, rel: str) -> Path:
    """HTML-Vorlage aus dem Datenordner, sonst die mitgelieferte im Programmordner."""
    from .config import CODE
    for basis in (root, CODE):
        if (basis / rel).is_file():
            return basis / rel
    raise CvBuildError(f"Vorlage {rel} fehlt.")


def html_pdf(html_path: Path) -> Path:
    from . import pdf_html
    try:
        return pdf_html.drucken(html_path, html_path.with_suffix(".pdf"))
    except pdf_html.PdfError as exc:
        raise CvBuildError(str(exc)) from None


def compile_tex(tex_path: Path, engine: str = "pdflatex", log_sink: list | None = None) -> Path:
    """latexmk im Ordner der .tex-Datei; räumt Hilfsdateien auf. Gibt den PDF-Pfad zurück.
    `log_sink` bekommt vor dem Aufräumen den Inhalt des LaTeX-Logs (für den Lebenslauf-Prüfer)."""
    if shutil.which("latexmk") is None:
        raise CvBuildError("latexmk nicht gefunden (TeX Live installieren).")
    proc = subprocess.run(["latexmk", ENGINES.get(engine, "-pdf"), "-interaction=nonstopmode", "-halt-on-error",
                           tex_path.name], cwd=tex_path.parent, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stdout.splitlines()[-25:])
        raise CvBuildError(f"LaTeX-Fehler:\n{tail}")
    log_file = tex_path.with_suffix(".log")
    if log_sink is not None and log_file.exists():
        log_sink.append(log_file.read_text(encoding="utf-8", errors="replace"))
    subprocess.run(["latexmk", "-c", tex_path.name], cwd=tex_path.parent, capture_output=True)
    return tex_path.with_suffix(".pdf")

