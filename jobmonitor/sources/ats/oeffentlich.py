"""Öffentliche Stellenlisten großer Bewerbersysteme, die ohne JavaScript lesbar sind (geprüft und freigegeben am
02.11.2026, robots.txt wird bei jedem Abruf geprüft):

- d.vinci:         /jobPublication/list.json – Datenquelle der Stellen-Widgets auf Firmenseiten (z. B. Generali)
- SuccessFactors:  Suchseite des Career Site Builders (/search/?q=…), HTML-Tabelle (z. B. Zurich); RSS ist per
                   robots.txt gesperrt und wird nicht genutzt
- Phenom:          Suchergebnisseite (/search-results?keywords=…) mit eingebetteter Stellenliste (z. B. DHL)
- eingebettet:     Stellenliste als JSON in einem data-…-props-Attribut der Karriereseite (z. B. REWE digital)
- Sitemap:         Stellen-Sitemap, die die robots.txt nennt; Detailseiten mit JSON-LD (z. B. WDR) – in companies.py

In companies.yaml: ats + ats_id (siehe Kommentar dort). Gespeichert wird nichts davon außer den gefundenen Stellen.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from urllib.parse import quote_plus, urljoin, urlsplit

from bs4 import BeautifulSoup

from ...location import is_remote
from ...models import Job


def _text(fragment: str) -> str:
    return BeautifulSoup(html_lib.unescape(fragment or ""), "lxml").get_text(" ", strip=True)


# --- d.vinci ---
def dvinci_url(host: str) -> str:
    return f"https://{host}/jobPublication/list.json"


def parse_dvinci(data: list, company: str, source: str) -> list[Job]:
    jobs = []
    for item in data or []:
        opening = item.get("jobOpening") or {}
        orte = [loc.get("name", "") for loc in opening.get("locations") or [] if loc.get("name")]
        text = " ".join(_text(item.get(k) or "") for k in ("introduction", "tasks", "profile", "benefits"))
        jobs.append(Job(
            title=opening.get("name") or item.get("position") or "", company=company, source=source,
            url=item.get("jobPublicationURL") or "", location=", ".join(orte), remote=is_remote(", ".join(orte), text),
            description=text[:8000], kind=", ".join(t.get("name", "") for t in opening.get("targetGroups") or []
                                                     if isinstance(t, dict)),
            posted=(opening.get("createdDate") or "")[:10], external_id=str(item.get("id", "")),
        ))
    return jobs


# --- SuccessFactors Career Site Builder ---
def successfactors_url(search_base: str, term: str) -> str:
    """search_base z. B. https://www.careers.zurich.com/search/?locationsearch=Deutschland&locale=de_DE"""
    sep = "&" if "?" in search_base else "?"
    return f"{search_base}{sep}q={quote_plus(term)}"


def parse_successfactors(page: str, base: str) -> list[tuple[str, str, str]]:
    """(Titel, Link, Ort) aus der Ergebnistabelle (tr.data-row)."""
    soup = BeautifulSoup(page, "lxml")
    out, seen = [], set()
    for row in soup.select("tr.data-row"):
        a = row.select_one("a.jobTitle-link")
        if not a or not a.get("href"):
            continue
        url = urljoin(base, a["href"])
        if url in seen:
            continue
        seen.add(url)
        ort = row.select_one("span.jobLocation")
        out.append((a.get_text(" ", strip=True), url, re.sub(r"\s+", " ", ort.get_text(" ", strip=True)) if ort else ""))
    return out


# --- Phenom ---
def phenom_url(base: str, term: str) -> str:
    """base z. B. https://careers.dhl.com/eu/de"""
    return f"{base.rstrip('/')}/search-results?keywords={quote_plus(term)}"


def _eingebettete_liste(page: str, key: str = '"jobs":[') -> list[dict]:
    i = page.find(key)
    if i < 0:
        return []
    try:
        data, _ = json.JSONDecoder().raw_decode(page[i + len(key) - 1:])
    except ValueError:
        return []
    return [d for d in data if isinstance(d, dict)]


def _slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")


def parse_phenom(page: str, base: str, company: str, source: str) -> list[Job]:
    jobs = []
    for item in _eingebettete_liste(page):
        title = item.get("title") or ""
        if not title or not item.get("jobId"):
            continue
        orte = item.get("multi_location") or [item.get("cityStateCountry") or item.get("city") or ""]
        teaser = item.get("descriptionTeaser") or ""
        skills = ", ".join(item.get("ml_skills") or [])
        jobs.append(Job(
            title=title, company=company, source=source,
            url=f"{base.rstrip('/')}/job/{item['jobId']}/{_slug(title)}",
            location="; ".join(o for o in orte if o), remote=is_remote(" ".join(orte), teaser),
            description=f"{teaser}\n{skills}".strip(), kind=item.get("type") or item.get("careerLevel") or "",
            posted=(item.get("postedDate") or "")[:10], external_id=str(item.get("jobId")),
        ))
    return jobs


# --- Stellenliste eingebettet in der Karriereseite (data-…-props-value='{"jobs":[…]}') ---
def parse_eingebettet(page: str, page_url: str, company: str, source: str) -> list[Job]:
    jobs, seen = [], set()
    for m in re.finditer(r'data-[\w-]*props-value="([^"]*&quot;jobs&quot;[^"]*)"', page):
        try:
            data = json.loads(html_lib.unescape(m.group(1)))
        except ValueError:
            continue
        for item in data.get("jobs") or []:
            url = urljoin(page_url, item.get("url") or "")
            if not item.get("title") or not url or url in seen:
                continue
            seen.add(url)
            ort = item.get("location") or item.get("city") or ""
            text = _text(item.get("description") or "")
            jobs.append(Job(
                title=item["title"], company=company, source=source, url=url, location=ort,
                remote=is_remote(ort, text), description=text[:8000], external_id=str(item.get("externalId") or ""),
            ))
    return jobs


# --- Stellen-Sitemap (Detailseiten werden in companies.py mit JSON-LD gelesen) ---
def sitemap_links(xml: str, host_of: str) -> list[str]:
    """Adressen aus <loc>, nur vom selben Host wie die Sitemap."""
    host = urlsplit(host_of).netloc
    return [html_lib.unescape(u) for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
            if urlsplit(html_lib.unescape(u)).netloc == host]
