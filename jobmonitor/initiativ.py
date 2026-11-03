"""Erkennt Initiativbewerbung / Talentpool-Links auf Karriereseiten."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# "initiativ(?!e)": Initiativbewerbung ja, aber nicht "Initiative(n)" / "initiatives"
INITIATIV_RE = re.compile(r"initiativ(?!e)|spontan|talent[\s_-]?pool|talent[\s_-]?community|talent[\s_-]?netzwerk",
                          re.IGNORECASE)


# Initiativ-Wege nur für andere Zielgruppen (Führungskräfte, Azubis …) zählen nicht
OTHER_AUDIENCE = re.compile(r"f(ü|ue)hrungskr|ausbildung|azubi|sch(ü|ue)ler|professional|senior", re.IGNORECASE)


def find_initiativ_link(html: str, page_url: str) -> str | None:
    """Bester Link, dessen Text oder URL auf eine Initiativbewerbung hinweist.

    Text-Treffer gehen vor URL-Treffern. Links nur für Führungskräfte/Azubis werden ignoriert.
    """
    soup = BeautifulSoup(html, "lxml")
    candidates = []
    for pos, a in enumerate(soup.find_all("a", href=True)):
        href = a["href"]
        if href.startswith(("javascript:", "#")):
            continue
        text = a.get_text(" ", strip=True)
        by_text = bool(INITIATIV_RE.search(text))
        if (by_text or INITIATIV_RE.search(href)) and not OTHER_AUDIENCE.search(f"{text} {href}"):
            candidates.append((not by_text, pos, urljoin(page_url, href)))
    return min(candidates)[2] if candidates else None


def update_entry(entry: dict, link: str | None, today: str) -> bool:
    """Aktualisiert entry['initiativ']; gibt True zurück, wenn die Möglichkeit neu entdeckt wurde.

    Ein fehlender Link ist kein Beweis für "nein" – manuell gesetzte Werte bleiben stehen.
    """
    info = entry.get("initiativ")
    if info is None:
        info = entry["initiativ"] = {"moeglich": "unbekannt", "url": None, "zuletzt_geprueft": None}
    newly = False
    if link:
        newly = info.get("moeglich") != "ja"
        info["moeglich"] = "ja"
        info["url"] = link
    info["zuletzt_geprueft"] = today
    return newly
