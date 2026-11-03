"""Workday: die Karriereseiten-Suche (CXS-JSON), die auch die öffentliche Seite im Browser nutzt.

Inoffiziell – deshalb nur aktiv, wenn in config.yaml `ats_freigabe.workday: true` steht.
ats_id hat die Form "firma.wd3.myworkdayjobs.com/de-DE/site" (Sprachteil optional).
"""
from __future__ import annotations

import re

from ...location import is_remote
from ...models import Job

SEARCH_TERMS = ["Werkstudent", "Working Student", "Thesis", "Praktikum", "Internship"]


def split_id(ats_id: str) -> tuple[str, str, str]:
    m = re.match(r"(?P<host>(?P<tenant>[a-z0-9-]+)\.wd\d+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?(?P<site>[A-Za-z0-9_-]+)",
                 ats_id)
    if not m:
        raise ValueError(f"Workday-ID nicht erkannt: {ats_id}")
    return m["host"], m["tenant"], m["site"]


def search_url(ats_id: str) -> str:
    host, tenant, site = split_id(ats_id)
    return f"https://{host}/wday/cxs/{tenant}/{site}/jobs"


def payload(term: str) -> dict:
    return {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term}


def parse(data: dict, ats_id: str, company: str, source: str) -> list[Job]:
    host, _, site = split_id(ats_id)
    jobs = []
    for item in data.get("jobPostings", []):
        location = item.get("locationsText", "")
        jobs.append(Job(
            title=item.get("title", ""), company=company, source=source,
            url=f"https://{host}/de-DE/{site}{item.get('externalPath', '')}",
            location=location, remote=is_remote(location, item.get("remoteType") or ""),
            posted=item.get("postedOn", ""), external_id=(item.get("bulletFields") or [""])[0],
        ))
    return jobs
