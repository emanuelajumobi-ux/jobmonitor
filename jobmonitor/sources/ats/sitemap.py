"""Fallback über Sitemaps: Stellen-URLs mit Rollen-Stichwort finden (z. B. SuccessFactors-Karriereseiten).

Manche Seiten liefern unter /sitemap.xml einen RSS-Feed mit allen Stellen; der wird direkt gelesen.
Gepackte Sitemaps (.xml.gz, z. B. Henkel) werden entpackt, Text-Sitemaps (eine URL je Zeile, z. B. q.beyond) gelesen.
"""
from __future__ import annotations

import gzip
import logging
import re
from urllib.parse import urlsplit
from xml.etree import ElementTree

from ...http import Fetcher
from ...models import Job
from .boards import parse_rss
from .jsonld import JOB_PATH, ROLE_SLUG

log = logging.getLogger(__name__)
MAX_SITEMAPS = 5


def _tag(el) -> str:
    return el.tag.split("}")[-1]


def candidate_urls(locs: list[str], role: re.Pattern = ROLE_SLUG) -> list[str]:
    """Stellen-URLs, deren Pfad ein Rollen-Stichwort enthält."""
    out = []
    for loc in locs:
        path = urlsplit(loc).path
        if JOB_PATH.search(path) and role.search(path) and loc not in out:
            out.append(loc)
    return out


def collect(fetcher: Fetcher, page_url: str, company: str, source: str,
            sitemap_urls: list[str] | None = None, role: re.Pattern = ROLE_SLUG) -> tuple[list[str], list[Job]]:
    """(Kandidaten-URLs aus urlset-Sitemaps, fertige Jobs aus RSS-Sitemaps)."""
    parts = urlsplit(page_url)
    queue = list(sitemap_urls or fetcher.sitemaps(page_url) or [f"{parts.scheme}://{parts.netloc}/sitemap.xml"])
    seen, locs, rss_jobs = set(), [], []
    while queue and len(seen) < MAX_SITEMAPS:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            body = fetcher.get(url).content
            if body[:2] == b"\x1f\x8b":            # gzip (requests entpackt nur bei Content-Encoding)
                body = gzip.decompress(body)[:50_000_000]
            if not body.lstrip()[:1] == b"<":       # Text-Sitemap: eine URL je Zeile
                locs += [z.strip() for z in body.decode("utf-8", "replace").splitlines()
                         if z.strip().startswith("http")]
                continue
            root = ElementTree.fromstring(body.lstrip(b"\xef\xbb\xbf \r\n\t"))
        except Exception as exc:
            log.info("Sitemap %s nicht lesbar: %s", url, exc)
            continue
        if _tag(root) == "rss":
            rss_jobs += [j for j in parse_rss(body.decode("utf-8", "replace"), company, source)
                         if role.search(j.title)]
        elif _tag(root) == "sitemapindex":
            children = [el.text.strip() for el in root.iter() if _tag(el) == "loc" and el.text]
            # Stellen-Sitemaps zuerst
            children.sort(key=lambda u: not re.search(r"job|stellen|career|karriere|position", u, re.I))
            queue += children
        else:
            locs += [el.text.strip() for el in root.iter() if _tag(el) == "loc" and el.text]
    return candidate_urls(locs, role), rss_jobs
