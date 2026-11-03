"""Job-Alert-Mails (StepStone, LinkedIn, Indeed, Xing …) per IMAP lesen und Links + Titel extrahieren.

Es wird nichts gescrapt: nur die Mails, die die Portale dir selbst schicken. Die Mails werden nur gelesen
(BODY.PEEK, Postfach read-only), nicht als gelesen markiert, verschoben oder gelöscht.
Zugangsdaten: IMAP_HOST, IMAP_USER, IMAP_PASSWORD (App-Passwort) als Umgebungsvariablen.
"""
from __future__ import annotations

import email
import imaplib
import logging
import os
import re
from datetime import date, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from ..location import is_remote, travel_minutes
from ..models import Job, SourceResult
from ..scoring import matches

log = logging.getLogger(__name__)
NAME = "Job-Alert-Mails"
# Pfadmuster echter Stellenlinks je Portal (Tracking-Links landen sonst als Dubletten im Bericht)
JOB_LINK = re.compile(r"/jobs/view/|/stellenangebote--|/job/|/jobs/|viewjob|/rc/clk|jobListing|/stellen/", re.I)
# Übersichts- und Verwaltungslinks in Alert-Mails (keine einzelne Stelle)
NOT_JOB = re.compile(r"search|/alerts|unsubscribe|abbestellen|premium|/help|settings|einstellungen", re.I)
KEEP_PARAMS = {"jk", "vjk", "jobid", "jobId", "id"}
PLATFORM_NAMES = {"stepstone": "StepStone", "linkedin": "LinkedIn", "indeed": "Indeed", "xing": "XING",
                  "glassdoor": "Glassdoor"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = {k: v[0] for k, v in parse_qs(parts.query).items() if k in KEEP_PARAMS}
    path = re.sub(r"(/jobs/view/\d+).*", r"\1", parts.path)  # LinkedIn: /jobs/view/123/?trk=…
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), ""))


RELAY = re.compile(r"_at_([a-z0-9-]+(?:_[a-z0-9-]+)+?)_[a-z0-9]+_[a-f0-9]+$", re.I)
PLAIN_LINK = re.compile(r"https?://\S+")
INTRO = re.compile(r"^(ihre|deine|your|neue|new)\b.{0,40}(benachrichtigung|job ?alert|jobs? für|jobs? for)", re.I)


def sender_domain(address: str) -> str:
    """Absender-Domain; bei Apples „E-Mail-Adresse verbergen“ (…_at_indeed_com_…@privaterelay.appleid.com)
    die ursprüngliche Domain des Portals."""
    local, _, domain = address.lower().rpartition("@")
    if domain == "privaterelay.appleid.com":
        match = RELAY.search(local)
        if match:
            return match.group(1).replace("_", ".")
    return domain


def platform(sender_domain: str) -> str:
    for key, label in PLATFORM_NAMES.items():
        if key in sender_domain:
            return label
    return sender_domain


def parse_alert_html(html: str, sender_domain: str, role_keywords, default_location: str,
                     skipped: set | None = None, tabelle: dict | None = None) -> list[Job]:
    """Stellen aus einer Alert-Mail (HTML). Stellen ohne Rollen-Stichwort eines aktiven Suchprofils im Titel landen
    in `skipped` (Links), damit der Bericht zeigen kann, ob der Alert falsch eingestellt ist."""
    soup = BeautifulSoup(html, "lxml")
    jobs, seen = [], set()
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = a["href"]
        if not (8 <= len(title) <= 160) or not href.startswith("http") or not JOB_LINK.search(href) \
                or NOT_JOB.search(urlsplit(href).path):
            continue
        url = canonical_url(href)
        if not matches(title, role_keywords):
            if skipped is not None:
                skipped.add(url)
            continue
        if url in seen:
            continue
        seen.add(url)
        # Umgebender Block enthält meist Firma und Ort
        block = a.find_parent(["tr", "td", "table", "div"]) or a
        context = block.get_text(" | ", strip=True)[:400]
        rest = [s.strip() for s in context.split("|") if s.strip() and s.strip() != title]
        location = next((s for s in rest if travel_minutes(s, None, tabelle) is not None or is_remote(s)), "")
        company = next((s for s in rest if s != location and len(s) < 80), "")
        job = Job(title=title, company=company or f"(über {platform(sender_domain)})", url=url, source=NAME,
                  location=location or default_location, remote=is_remote(context), description=context)
        if not location:
            job.flags.append("Ort nicht erkannt – Suchort des Alerts angenommen")
        jobs.append(job)
    return jobs


def parse_alert_text(text: str, sender_domain: str, role_keywords, default_location: str,
                     skipped: set | None = None, tabelle: dict | None = None) -> list[Job]:
    """Rückfall für Mails ohne HTML-Teil: Blöcke „Titel Firma Ort … Link“, getrennt durch Linien oder Leerzeilen."""
    jobs, seen = [], set()
    for block in re.split(r"\n\s*-{5,}\s*\n|\n\s*\n", text):
        link = next((u for u in PLAIN_LINK.findall(block)
                     if JOB_LINK.search(u) and not NOT_JOB.search(urlsplit(u).path)), None)
        lines = [ln.strip() for ln in PLAIN_LINK.sub("", block).splitlines()
                 if ln.strip() and not INTRO.match(ln.strip())]
        if not link or not lines:
            continue
        url = canonical_url(link)
        title = lines[0][:160]
        if not matches(title, role_keywords):
            if skipped is not None:
                skipped.add(url)
            continue
        if url in seen:
            continue
        seen.add(url)
        rest = lines[1:]
        location = next((s for s in rest if travel_minutes(s, None, tabelle) is not None or is_remote(s)), "")
        company = next((s for s in rest if s != location and len(s) < 80), "")
        job = Job(title=title, company=company or f"(über {platform(sender_domain)})", url=url, source=NAME,
                  location=location or default_location, remote=is_remote(block), description=" | ".join(lines))
        if not location:
            job.flags.append("Ort nicht erkannt – Suchort des Alerts angenommen")
        jobs.append(job)
    return jobs


def _decode(value: str) -> str:
    return str(make_header(decode_header(value or "")))


class MailAlertsSource:
    name = NAME

    def __init__(self, cfg: dict, role_keywords, today: date, default_location: str = "Köln",
                 fahrzeiten: dict | None = None):
        """fahrzeiten: ort.fahrzeiten (Orte im Umkreis des Wohnorts), um den Ort in der Alert-Mail zu erkennen."""
        self.cfg = cfg
        self.fahrzeiten = fahrzeiten or None
        self.role_keywords = list(role_keywords)
        self.today = today
        self.default_location = default_location

    @staticmethod
    def configured() -> bool:
        return bool(os.environ.get("IMAP_USER") and os.environ.get("IMAP_PASSWORD"))

    def fetch(self) -> SourceResult:
        result = SourceResult(self.name)
        if not self.configured():
            result.notes.append("nicht eingerichtet (IMAP_USER/IMAP_PASSWORD fehlen)")
            return result
        host = os.environ.get("IMAP_HOST") or "imap.mail.me.com"
        since = (self.today - timedelta(days=self.cfg["tage_zurueck"])).strftime("%d-%b-%Y")
        senders = [s.lower() for s in self.cfg["absender"]]
        with imaplib.IMAP4_SSL(host, int(os.environ.get("IMAP_PORT") or "993")) as imap:
            imap.login(os.environ["IMAP_USER"], os.environ["IMAP_PASSWORD"])
            imap.select(self.cfg.get("ordner", "INBOX"), readonly=True)
            _, data = imap.search(None, "SINCE", since)
            ids = data[0].split()
            mails, skipped = 0, set()
            for msg_id in ids:
                _, header_data = imap.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
                sender = parseaddr(_decode(header_data[0][1].decode("utf-8", "replace").partition(":")[2]))[1].lower()
                domain = sender_domain(sender)
                if not any(domain == s or domain.endswith("." + s) for s in senders):
                    continue
                _, msg_data = imap.fetch(msg_id, "(BODY.PEEK[])")
                msg = email.message_from_bytes(msg_data[0][1])
                mails += 1
                bodies = {part.get_content_type(): part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", "replace")
                    for part in msg.walk() if part.get_content_type() in ("text/html", "text/plain")}
                found = []
                if "text/html" in bodies:
                    found = parse_alert_html(bodies["text/html"], domain, self.role_keywords, self.default_location,
                                             skipped, self.fahrzeiten)
                if not found and "text/plain" in bodies:
                    found = parse_alert_text(bodies["text/plain"], domain, self.role_keywords,
                                             self.default_location, skipped, self.fahrzeiten)
                result.jobs += found
        note = f"{mails} Alert-Mail(s) gelesen"
        if skipped:
            note += (f"; {len(skipped)} Stelle(n) darin ohne passendes Rollen-Stichwort im Titel "
                     f"übersprungen – Alert-Suchbegriffe prüfen")
        result.notes.append(note)
        return result
