"""Antworten von Firmen auf deine Bewerbungen im Postfach erkennen (Eingangsbestätigung, Einladung, Absage, Zusage).

Läuft in der Pipeline mit demselben IMAP-Zugang wie die Job-Alerts (nur lesen: BODY.PEEK, Postfach read-only, nichts
wird markiert, verschoben oder beantwortet). Geprüft werden nur Mails seit dem Bewerbungsdatum von Einträgen mit Status
beworben / nachgefasst / Antwort. Eine Mail gehört zu einer Bewerbung, wenn
  1. die Absender-Domain zur Firma gehört (Link der Stelle oder Karriereseite aus companies.yaml), oder
  2. der Firmenname im Absender (Name oder Adresse), im Betreff oder im Text steht – z. B. „INFODAS (via softgarden)“,
     no-reply-remondis@concludis.de –, oder
  3. der Betreff den Stellentitel der Bewerbung nennt (z. B. „Ihre Bewerbung als Werkstudent – IT-Governance …“).
Bei 2 und 3 muss es außerdem um eine Bewerbung gehen (Wörter wie Bewerbung, application, Gespräch).

Gespeichert wird in state/antworten.json nur: Link der Bewerbung, Firma, Datum, Art, Absender-Domain und – wenn die
KI ihn erkannt hat – der Gesprächstermin. Betreff und Text werden nicht gespeichert. Den Status änderst du selbst in
der App (Vorschlag mit einem Klick).

Optional (antworten.ki): Mails, die die Muster nur als „Nachricht“ oder „Einladung“ erkennen, ordnet die KI genauer
ein und liest einen genannten Gesprächstermin heraus. Dafür gehen Betreff und Anfang der Mail an die Claude-API, nur
für neue Mails und höchstens `ki_max_je_lauf` pro Lauf.
"""
from __future__ import annotations

import email
import imaplib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

from . import llm
from .models import normalize
from .original import titel_aehnlich
from .sources.mail_alerts import _decode, sender_domain

log = logging.getLogger(__name__)
DATEI = "state/antworten.json"
OFFEN = ("beworben", "nachgefasst", "Antwort")          # auf diese Einträge kann noch eine Antwort kommen
# Art → vorgeschlagener Status in applications.csv (None: nur Hinweis, z. B. Eingangsbestätigung)
STATUS = {"absage": "Absage", "zusage": "Zusage", "einladung": "Antwort", "nachricht": "Antwort", "eingang": None}
LABEL = {"absage": "Absage", "zusage": "Zusage", "einladung": "Einladung zum Gespräch", "nachricht": "Nachricht",
         "eingang": "Eingang bestätigt"}
# Reihenfolge = Vorrang: eine Absage dankt meist auch für die Bewerbung, eine Einladung ist keine Zusage
MUSTER = [
    ("absage", r"\bleider\b|nicht (?:weiter |mehr )?beruecksichtig|\babsage\b|anderen? (?:bewerber|kandidat)|"
               r"unfortunately|not (?:be )?(?:able to )?(?:move|moving|proceed)|other candidates|regret to inform|"
               r"entschieden,? (?:uns )?(?:fuer|gegen)"),
    ("zusage", r"\bzusage\b|vertragsangebot|arbeitsvertrag|job offer|offer letter|pleased to offer"),
    ("einladung", r"einladung|einladen|vorstellungsgespraech|kennenlern|bewerbungsgespraech|\binterview|"
                  r"terminvorschlag|telefon(?:at|interview|termin)|video ?call|teams.?(?:meeting|termin)|"
                  r"invite you|schedule a call"),
    ("eingang", r"eingang ihrer bewerbung|bewerbung (?:ist )?(?:gut |sicher )?eingegangen|eingegangen|"
                r"bestaetig\w* (?:ihnen )?(?:hiermit )?(?:den )?eingang|received your application|"
                r"entered into our|application has been received|thank you for (?:your )?appl"),
]
BEWERBUNG = re.compile(r"bewerb|application|candida|gespraech|interview|stelle|position", re.I)
# Bewerbermanagement-Systeme, die im Namen der Firma schreiben (Name dann im Absender oder Text)
ATS = ("softgarden", "concludis", "onlyfy", "personio", "successfactors", "sapsf", "myworkday", "workday",
       "greenhouse", "lever.co", "smartrecruiters", "join.com", "recruitee", "dvinci", "rexx", "umantis", "b-ite",
       "jobbase", "prescreen", "talention", "haufe", "milch-zucker", "workwise")


@dataclass
class Antwort:
    link: str
    firma: str
    datum: str          # ISO, Datum der Mail
    art: str            # absage, zusage, einladung, nachricht, eingang
    absender: str       # Domain
    termin: str = ""    # Gesprächstermin laut Mail (ISO, YYYY-MM-DDTHH:MM), von der KI erkannt
    roh: str = ""       # Art laut Muster, falls die KI sie geändert hat (bleibt Teil des Schlüssels)

    @property
    def schluessel(self) -> str:
        return f"{self.link}|{self.datum}|{self.roh or self.art}"

    @property
    def status(self) -> str | None:
        return STATUS.get(self.art)

    @property
    def label(self) -> str:
        return LABEL.get(self.art, self.art)


def ascii_text(text: str) -> str:
    """Kleinbuchstaben, Umlaute wie in vielen Systemmails umschrieben (ae, oe, ue, ss)."""
    text = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text)


def klassifizieren(betreff: str, text: str) -> str:
    t = ascii_text(f"{betreff} {text[:4000]}")
    return next((art for art, muster in MUSTER if re.search(muster, t)), "nachricht")


def _registrierbar(host: str) -> str:
    parts = host.lower().strip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def firmen_key(name: str) -> str:
    from .original import firma_key
    return firma_key(name)


BOARDS = ("arbeitsagentur.", "stellenwerk.", "hs-niederrhein.", "linkedin.", "indeed.", "stepstone.", "xing.",
          "glassdoor.", "jobexport.", "empfehlungsbund.", "jobanzeiger.", "join.com", "personio.", "softgarden.")


def domains(row: dict, companies_doc) -> set[str]:
    """Domains, von denen die Firma schreibt: Link der Stelle und Karriereseite (ohne Jobbörsen und ATS)."""
    urls = [row.get("link", "")]
    key = firmen_key(row.get("firma", ""))
    for f in (companies_doc or {}).get("firmen") or []:
        if key and firmen_key(f.get("name", "")) == key:
            urls.append(f.get("karriereseite_url") or "")
    out = set()
    for url in urls:
        host = urlsplit(url).netloc.lower()
        if host and not any(b in host for b in BOARDS):
            out.add(_registrierbar(host))
    return out


def _titel(row: dict) -> str:
    """Stellentitel aus den Notizen („Titel (Score 88)“ oder frei eingetragener Text)."""
    return re.sub(r"\s*\(Score \d+\)\s*$", "", (row.get("notizen") or "").splitlines()[0] if row.get("notizen") else "")


def passt(row: dict, doms: set[str], absender: str, anzeigename: str, betreff: str, text: str) -> bool:
    dom = sender_domain(absender)
    if dom and _registrierbar(dom) in doms:
        return True
    if not BEWERBUNG.search(f"{betreff} {text[:2000]}"):
        return False
    key = firmen_key(row.get("firma", ""))
    if key and len(key) >= 3:
        kopf = ascii_text(f"{anzeigename} {absender.replace('-', ' ').replace('.', ' ')} {betreff}")
        if re.search(rf"\b{re.escape(ascii_text(key))}\b", kopf):
            return True
        if any(a in dom for a in ATS) and re.search(rf"\b{re.escape(ascii_text(key))}\b", ascii_text(text[:6000])):
            return True
    titel = _titel(row)
    if titel:
        rest = re.sub(r"^(?:re:\s*)?(?:ihre bewerbung(?: als| auf| bei| fuer)?|your application(?: as| for)?)\s*",
                      "", ascii_text(betreff).split(" / ")[0])
        return bool(rest) and titel_aehnlich(rest, titel) >= 0.6
    return False


def zuordnen(mail: dict, rows: list[dict], companies_doc) -> list[Antwort]:
    """Eine Mail ({von, betreff, text, datum}) den offenen Bewerbungen zuordnen; Mail vor dem Bewerbungsdatum zählt nicht."""
    anzeigename, absender = parseaddr(mail["von"])
    absender = absender.lower()
    out = []
    for row in rows:
        if row.get("status") not in OFFEN or mail["datum"] < (row.get("datum") or ""):
            continue
        if passt(row, domains(row, companies_doc), absender, anzeigename, mail["betreff"], mail["text"]):
            out.append(Antwort(row.get("link", ""), row.get("firma", ""), mail["datum"],
                               klassifizieren(mail["betreff"], mail["text"]), sender_domain(absender)))
    return out


# --- Postfach (Pipeline) ---
def _text(msg) -> str:
    teile = []
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "text/html") and not part.get_filename():
            raw = part.get_payload(decode=True) or b""
            text = raw.decode(part.get_content_charset() or "utf-8", "replace")
            if part.get_content_type() == "text/html":
                text = re.sub(r"<[^>]+>", " ", text)
            teile.append(text)
            if part.get_content_type() == "text/plain":
                break
    return " ".join(teile)[:8000]


KI_ARTEN = ("nachricht", "einladung")      # nur diese lässt die KI nachprüfen
TERMIN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


def ki_prompt(mail: dict) -> str:
    return (
        "Eine Firma antwortet auf eine Bewerbung. Ordne die Mail ein und lies einen Gesprächstermin heraus.\n\n"
        f"MAILDATUM: {mail['datum']}\nBETREFF: {mail['betreff']}\nTEXT:\n{mail['text'][:3000]}\n\n"
        'Antworte nur mit JSON: {"art": "...", "termin": "..."}\n'
        "- art: eingang (nur Eingangsbestätigung), einladung (Einladung zu Gespräch, Interview, Kennenlernen oder "
        "Terminvorschlag), absage, zusage (Angebot, Vertrag) oder nachricht (alles andere, z. B. Rückfrage).\n"
        "- termin: nur wenn ein konkreter Termin mit Datum und Uhrzeit feststeht, als YYYY-MM-DDTHH:MM "
        "(relative Angaben vom Maildatum aus); bei mehreren Vorschlägen oder ohne Uhrzeit leer.")


def ki_einordnen(antwort: Antwort, mail: dict, model: str, ask=None) -> bool:
    """Art (und Termin) einer Antwort mit KI prüfen; True, wenn die KI geantwortet hat."""
    data = llm.json_aus((ask or llm._ask)(model, ki_prompt(mail), effort="low", max_tokens=500))
    if not isinstance(data, dict) or data.get("art") not in LABEL:
        return False
    if data["art"] != antwort.art:
        antwort.roh, antwort.art = antwort.roh or antwort.art, data["art"]
    termin = str(data.get("termin") or "")
    if antwort.art == "einladung" and TERMIN.match(termin):
        antwort.termin = termin
    return True


def postfach(rows: list[dict], companies_doc, cfg: dict, today: date, ausschluss: list[str],
             bekannt: frozenset = frozenset(), einordnen=None) -> list[Antwort]:
    """Mails seit der ältesten offenen Bewerbung lesen (höchstens `tage_zurueck` Tage) und zuordnen.
    einordnen(antwort, mail): optionale KI-Prüfung, nur für noch nicht bekannte Antworten der Arten KI_ARTEN."""
    offen = [r for r in rows if r.get("status") in OFFEN and r.get("datum")]
    if not offen or not (os.environ.get("IMAP_USER") and os.environ.get("IMAP_PASSWORD")):
        return []
    seit = max(min(r["datum"] for r in offen), (today - timedelta(days=cfg.get("tage_zurueck", 120))).isoformat())
    since = date.fromisoformat(seit).strftime("%d-%b-%Y")
    eigene = os.environ["IMAP_USER"].lower()
    host = os.environ.get("IMAP_HOST") or "imap.mail.me.com"
    gefunden = []
    with imaplib.IMAP4_SSL(host, int(os.environ.get("IMAP_PORT") or "993")) as imap:
        imap.login(os.environ["IMAP_USER"], os.environ["IMAP_PASSWORD"])
        imap.select(cfg.get("ordner", "INBOX"), readonly=True)
        _, data = imap.search(None, "SINCE", since)
        for msg_id in data[0].split():
            _, head = imap.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            kopf = email.message_from_bytes(head[0][1])
            von = _decode(kopf.get("From", ""))
            adresse = parseaddr(von)[1].lower()
            dom = sender_domain(adresse)
            if adresse == eigene or any(dom == s or dom.endswith("." + s) for s in ausschluss):
                continue                     # eigene Mails und Job-Alerts
            betreff = _decode(kopf.get("Subject", ""))
            try:
                datum = parsedate_to_datetime(kopf.get("Date")).date().isoformat()
            except (TypeError, ValueError):
                datum = today.isoformat()
            vorab = {"von": von, "betreff": betreff, "text": "", "datum": datum}
            # Text nur laden, wenn Absender oder Betreff schon zu einer Bewerbung passen könnten
            if not (zuordnen(vorab, rows, companies_doc) or BEWERBUNG.search(betreff) or any(a in dom for a in ATS)):
                continue
            _, body = imap.fetch(msg_id, "(BODY.PEEK[])")
            mail = {**vorab, "text": _text(email.message_from_bytes(body[0][1]))}
            for a in zuordnen(mail, rows, companies_doc):
                if einordnen and a.art in KI_ARTEN and a.schluessel not in bekannt:
                    einordnen(a, mail)
                gefunden.append(a)
    return gefunden


# --- Ablage ---
def laden(root: Path) -> list[Antwort]:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return [Antwort(**a) for a in data if isinstance(a, dict)]
    except (OSError, ValueError, TypeError):
        return []


def _ablage(a: Antwort) -> dict:
    """Termin und Muster-Art nur, wenn die KI sie gesetzt hat."""
    return {k: v for k, v in asdict(a).items() if v or k not in ("termin", "roh")}


def speichern(root: Path, neue: list[Antwort]) -> list[Antwort]:
    """Neue Antworten anhängen (ohne Doppelte). Gibt die wirklich neuen zurück."""
    alle = laden(root)
    bekannt = {a.schluessel for a in alle}
    frisch = [a for a in neue if a.schluessel not in bekannt and not bekannt.add(a.schluessel)]
    if frisch:
        (root / DATEI).parent.mkdir(parents=True, exist_ok=True)
        (root / DATEI).write_text(json.dumps([_ablage(a) for a in alle + frisch], ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    return frisch


def neueste(antworten: list[Antwort]) -> dict[str, Antwort]:
    """Link → wichtigste Antwort (neueste; bei gleichem Tag die mit Statusänderung)."""
    out: dict[str, Antwort] = {}
    for a in sorted(antworten, key=lambda a: (a.datum, a.status is not None)):
        out[a.link] = a
    return out


def beantwortet(antworten: list[Antwort]) -> set[str]:
    """Links mit einer echten Antwort (nicht nur Eingangsbestätigung) – dafür kein Nachfassen mehr."""
    return {a.link for a in antworten if a.status}
