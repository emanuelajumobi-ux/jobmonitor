"""schema.org JobPosting aus JSON-LD sowie Kandidaten-Links für Detailseiten."""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ...location import is_remote
from ...models import Job

ROLE_SLUG = re.compile(r"werkstud|working-student|thesis|bachelor|abschlussarbeit|praktik|praxis|student|internship|"
                       r"(?<![a-z])intern(?![a-z])", re.IGNORECASE)
# Grober IT-Bezug im URL-Slug, um Detailseiten zu priorisieren
TECH_SLUG = re.compile(r"cloud|azure|devops|security|sicherheit|it-|-it|iam|identity|infrastru|platform|informatik|"
                       r"cyber|netzwerk|network|digital|automati|software|data|daten|sap", re.IGNORECASE)
JOB_PATH = re.compile(r"karriere|career|jobs?/|stellen", re.IGNORECASE)


def _walk(node):
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        if "@graph" in node:
            yield from _walk(node["@graph"])


def _is_posting(node: dict) -> bool:
    t = node.get("@type")
    return t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t)


def _text(html: str) -> str:
    return BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)


def _locations(node: dict) -> list[str]:
    locs = node.get("jobLocation") or []
    out = []
    for loc in locs if isinstance(locs, list) else [locs]:
        addr = (loc or {}).get("address") or {}
        if isinstance(addr, dict):
            out.append(addr.get("addressLocality") or addr.get("addressRegion") or "")
        elif isinstance(addr, str):
            out.append(addr)
    return [o for o in out if o]


def parse_postings(html: str, page_url: str, company: str, source: str) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "", strict=False)
        except json.JSONDecodeError:
            continue
        for node in _walk(data):
            if not _is_posting(node):
                continue
            location = ", ".join(_locations(node))
            desc = _text(node.get("description", ""))
            telecommute = "TELECOMMUTE" in json.dumps(node.get("jobLocationType", "")).upper()
            jobs.append(Job(
                title=_text(node.get("title", "")), company=company, source=source,
                url=node.get("url") or page_url, location=location,
                remote=telecommute or is_remote(location, desc), description=desc,
                kind=json.dumps(node.get("employmentType", ""), ensure_ascii=False),
                posted=str(node.get("datePosted", ""))[:10],
            ))
    return jobs


def microdata_locations(html: str) -> list[str]:
    """schema.org-Microdata (z. B. SuccessFactors): itemprop="addressLocality"."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for el in soup.find_all(attrs={"itemprop": "addressLocality"}):
        value = (el.get("content") or el.get_text(" ", strip=True)).strip()
        if value and value not in out:
            out.append(value)
    return out


def page_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    og = soup.find("meta", property="og:title")
    return og["content"] if og and og.get("content") else (soup.title.string if soup.title else "")


def role_re(patterns: list[str]) -> re.Pattern:
    """Mehrere Rollen-Muster (z. B. je Suchprofil) zu einem verbinden."""
    return re.compile("|".join(f"(?:{p})" for p in patterns) or ROLE_SLUG.pattern, re.IGNORECASE)


def job_links(html: str, page_url: str, role_pattern: re.Pattern = ROLE_SLUG) -> tuple[list[str], list[str]]:
    """(Links mit Rollen-Stichwort im Pfad, alle Stellen-Links) unterhalb der Listenseite.

    Nur Unterseiten der Listen-URL zählen, damit Navigationslinks wie /karriere/berufseinstieg/werkstudierende/
    nicht als Stelle gelten.
    """
    soup = BeautifulSoup(html, "lxml")
    host = urlsplit(page_url).netloc
    base_path = urlsplit(page_url).path.rstrip("/")
    role, all_jobs = [], []
    for a in soup.find_all("a", href=True):
        url = urljoin(page_url, a["href"]).split("#")[0].split("?")[0]
        parts = urlsplit(url)
        if parts.netloc != host or not parts.path.startswith(base_path + "/") or parts.path.rstrip("/") == base_path:
            continue
        if not JOB_PATH.search(parts.path):
            continue
        if re.search(r"initiativ|faq|benefit|bewerbungsprozess", parts.path, re.IGNORECASE):
            continue
        if url not in all_jobs:
            all_jobs.append(url)
            slug = [s for s in parts.path.split("/") if s][-1]
            if role_pattern.search(slug):
                role.append(url)
    return role, all_jobs
