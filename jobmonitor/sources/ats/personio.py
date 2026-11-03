"""Personio: öffentlicher XML-Feed unter https://{firma}.jobs.personio.de/xml"""
from __future__ import annotations

from xml.etree import ElementTree

from bs4 import BeautifulSoup

from ...location import is_remote
from ...models import Job


def feed_url(ats_id: str) -> str:
    return f"https://{ats_id}.jobs.personio.de/xml?language=de"


def parse(xml: str, ats_id: str, company: str, source: str) -> list[Job]:
    root = ElementTree.fromstring(xml)
    jobs = []
    for pos in root.iter("position"):
        get = lambda tag: (pos.findtext(tag) or "").strip()  # noqa: E731
        offices = [get("office")] + [(o.text or "").strip() for o in pos.iter("additionalOffice")]
        desc_html = " ".join((d.findtext("value") or "") for d in pos.iter("jobDescription"))
        desc = BeautifulSoup(desc_html, "lxml").get_text(" ", strip=True)
        location = ", ".join(o for o in offices if o)
        jobs.append(Job(
            title=get("name"), company=company, source=source,
            url=f"https://{ats_id}.jobs.personio.de/job/{get('id')}",
            location=location, remote=is_remote(location, get("name"), desc),
            description=f"{get('department')} {get('employmentType')} {get('schedule')} {desc}",
            kind=f"{get('recruitingCategory')} {get('employmentType')}",
            posted=get("createdAt")[:10], external_id=get("id"),
        ))
    return jobs
