"""Greenhouse und Lever: öffentliche JSON-Job-Board-APIs."""
from __future__ import annotations

from bs4 import BeautifulSoup

from ...location import is_remote
from ...models import Job


def greenhouse_url(ats_id: str) -> str:
    return f"https://boards-api.greenhouse.io/v1/boards/{ats_id}/jobs?content=true"


def parse_greenhouse(data: dict, company: str, source: str) -> list[Job]:
    jobs = []
    for item in data.get("jobs", []):
        location = (item.get("location") or {}).get("name", "")
        desc = BeautifulSoup(item.get("content") or "", "lxml").get_text(" ", strip=True)
        jobs.append(Job(
            title=item.get("title", ""), company=company, source=source, url=item.get("absolute_url", ""),
            location=location, remote=is_remote(location, desc), description=desc,
            posted=(item.get("updated_at") or "")[:10], external_id=str(item.get("id", "")),
        ))
    return jobs


def lever_url(ats_id: str) -> str:
    return f"https://api.lever.co/v0/postings/{ats_id}?mode=json"


def parse_lever(data: list, company: str, source: str) -> list[Job]:
    jobs = []
    for item in data:
        cats = item.get("categories") or {}
        location = ", ".join(filter(None, [cats.get("location")] + (cats.get("allLocations") or [])))
        desc = item.get("descriptionPlain") or ""
        jobs.append(Job(
            title=item.get("text", ""), company=company, source=source, url=item.get("hostedUrl", ""),
            location=location, remote=is_remote(location, item.get("workplaceType") or "", desc),
            description=desc, kind=cats.get("commitment") or "", external_id=item.get("id", ""),
        ))
    return jobs


def recruitee_url(ats_id: str) -> str:
    return f"https://{ats_id}.recruitee.com/api/offers/"


def parse_recruitee(data: dict, company: str, source: str) -> list[Job]:
    jobs = []
    for item in data.get("offers", []):
        location = item.get("location") or item.get("city") or ""
        desc = BeautifulSoup((item.get("description") or "") + (item.get("requirements") or ""), "lxml").get_text(" ", strip=True)
        jobs.append(Job(
            title=item.get("title", ""), company=company, source=source, url=item.get("careers_url", ""),
            location=location, remote=bool(item.get("remote")) or is_remote(location, desc), description=desc,
            kind=item.get("employment_type_code") or "", posted=(item.get("published_at") or "")[:10],
            external_id=str(item.get("id", "")),
        ))
    return jobs


def teamtailor_url(ats_id: str) -> str:
    return f"https://{ats_id}.teamtailor.com/jobs.rss"


def parse_rss(xml: str, company: str, source: str) -> list[Job]:
    """Allgemeiner RSS-2.0-Parser (Teamtailor, SuccessFactors-Feeds u. a.)."""
    from xml.etree import ElementTree

    jobs = []
    for item in ElementTree.fromstring(xml.encode() if isinstance(xml, str) else xml).iter("item"):
        title = (item.findtext("title") or "").strip()
        desc = BeautifulSoup(item.findtext("description") or "", "lxml").get_text(" ", strip=True)
        loc_el = next((el for el in item if el.tag.split("}")[-1] in ("location", "city")), None)
        location = (loc_el.text or "").strip() if loc_el is not None else ""
        jobs.append(Job(
            title=title, company=company, source=source, url=(item.findtext("link") or "").strip(),
            location=location, remote=is_remote(title, location, desc), description=desc,
            posted=(item.findtext("pubDate") or "").strip(),
        ))
    return jobs


def smartrecruiters_url(ats_id: str) -> str:
    return f"https://api.smartrecruiters.com/v1/companies/{ats_id}/postings?country=de&limit=100"


def parse_smartrecruiters(data: dict, company: str, source: str) -> list[Job]:
    jobs = []
    for item in data.get("content", []):
        loc = item.get("location") or {}
        jobs.append(Job(
            title=item.get("name", ""), company=company, source=source,
            url=f"https://jobs.smartrecruiters.com/{(item.get('company') or {}).get('identifier', '')}/{item.get('id', '')}",
            location=loc.get("city", ""), remote=bool(loc.get("remote")),
            description=" ".join(str((item.get(k) or {}).get("label", "")) for k in ("function", "department",
                                                                                   "typeOfEmployment")),
            kind=(item.get("typeOfEmployment") or {}).get("label", ""), posted=(item.get("releasedDate") or "")[:10],
            external_id=str(item.get("id", "")),
        ))
    return jobs
