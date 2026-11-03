"""Öffentliche Listen großer Bewerbersysteme (sources/ats/oeffentlich.py) und ihre Anbindung in companies.py.
Beispiele nach der echten Struktur (geprüft am 02.11.2026), stark gekürzt."""
import html
import json
import re
from datetime import date

import responses

from jobmonitor.config import load_config
from jobmonitor.sources.ats import oeffentlich as oe
from jobmonitor.sources.companies import CompaniesSource
from jobmonitor.state import State

DVINCI = [{"id": 1, "jobPublicationURL": "https://g.dvinci-hr.com/de/jobs/1/werkstudent-it-security",
           "introduction": "<p>Bei uns …</p>", "tasks": "<ul><li>Azure-Umgebungen absichern</li></ul>",
           "profile": "<p>Studium Informatik, Terraform</p>",
           "jobOpening": {"name": "Werkstudent IT-Security (m/w/d)", "createdDate": "2026-10-20T08:00:00",
                          "locations": [{"name": "Köln"}, {"name": "München"}], "targetGroups": [{"name": "Studierende"}]}}]
CSB = """<table><tr class="data-row"><td><span class="jobTitle"><a href="/job/Koeln-Werkstudent-IT/793/"
class="jobTitle-link">Werkstudent IT Security (m/w/d)</a></span><span class="jobLocation"> Köln, DE </span></td></tr>
<tr class="data-row"><td><a class="jobTitle-link" href="/job/Koeln-Werkstudent-IT/793/">Werkstudent IT Security (m/w/d)</a>
</td></tr><tr class="data-row"><td><a class="jobTitle-link" href="/job/Bonn-Underwriter/12/">Underwriter (m/w/d)</a>
<span class="jobLocation">Bonn, DE</span></td></tr></table>"""
PHENOM = ('<script>phApp.ddo = {"eagerLoadRefineSearch":{"status":200,"hits":1,"data":{"jobs":[{"title":'
          '"Werkstudent (m/w/d) Cloud","jobId":"AV-1","city":"Köln","multi_location":["Köln, NRW, Germany"],'
          '"descriptionTeaser":"Du unterstützt unser Azure-Team","ml_skills":["azure","terraform"],'
          '"postedDate":"2026-10-01T10:00:00.000+0000"}],"aggregations":[]}}};</script>')
REWE_JOBS = {"jobs": [{"externalId": "985451", "title": "Werkstudent Fullstack Software Developer (m/w/d)",
                       "location": "51149 Köln", "url": "https://karriere.rewe-group.com/rewe_digital/job/1",
                       "description": "&lt;p&gt;Du entwickelst mit Kotlin und AWS&lt;/p&gt;"}]}
REWE = f'<div data-symfony--ux-react--react-props-value="{html.escape(json.dumps(REWE_JOBS))}"></div>'
WDR_SITEMAP = """<urlset><url><loc>https://bewerbung.wdr.de/index.php?ac=jobad&amp;id=1</loc></url>
<url><loc>https://bewerbung.wdr.de/index.php?ac=jobad&amp;id=2</loc></url>
<url><loc>https://fremd.de/x</loc></url></urlset>"""


def detail(title):
    posting = {"@context": "https://schema.org", "@type": "JobPosting", "title": title, "description": "IT-Sicherheit",
               "jobLocation": {"@type": "Place", "address": {"addressLocality": "Köln"}}}
    return f'<html><script type="application/ld+json">{json.dumps(posting)}</script></html>'


def test_parser():
    job = oe.parse_dvinci(DVINCI, "Generali", "Q")[0]
    assert job.title == "Werkstudent IT-Security (m/w/d)" and job.location == "Köln, München"
    assert "Azure-Umgebungen absichern" in job.description and "Terraform" in job.description
    assert job.url.endswith("/werkstudent-it-security") and job.posted == "2026-10-20"
    rows = oe.parse_successfactors(CSB, "https://www.careers.zurich.com/search/")
    assert rows == [("Werkstudent IT Security (m/w/d)", "https://www.careers.zurich.com/job/Koeln-Werkstudent-IT/793/",
                     "Köln, DE"), ("Underwriter (m/w/d)", "https://www.careers.zurich.com/job/Bonn-Underwriter/12/", "Bonn, DE")]
    assert oe.successfactors_url("https://x/search/?locale=de_DE", "Working Student") == \
        "https://x/search/?locale=de_DE&q=Working+Student"
    job = oe.parse_phenom(PHENOM, "https://careers.dhl.com/eu/de", "DHL", "Q")[0]
    assert job.url == "https://careers.dhl.com/eu/de/job/AV-1/Werkstudent-m-w-d-Cloud"
    assert "Azure-Team" in job.description and "terraform" in job.description and job.location == "Köln, NRW, Germany"
    job = oe.parse_eingebettet(REWE, "https://www.rewe-digital.com/de/jobs", "REWE digital", "Q")[0]
    assert job.title.startswith("Werkstudent Fullstack") and "Kotlin" in job.description and job.location == "51149 Köln"
    assert oe.sitemap_links(WDR_SITEMAP, "https://bewerbung.wdr.de/sitemap.xml") == [
        "https://bewerbung.wdr.de/index.php?ac=jobad&id=1", "https://bewerbung.wdr.de/index.php?ac=jobad&id=2"]


def _source(entries, state=None):
    cfg = load_config()
    from jobmonitor.http import Fetcher
    fetcher = Fetcher("test-agent", 0, 5, 0)
    return CompaniesSource({"firmen": entries}, cfg["sources"]["companies"], fetcher, date(2026, 11, 2),
                           ats_terms=["Werkstudent", "Junior"], state=state)


@responses.activate
def test_anbindung_in_companies(tmp_path):
    responses.get(re.compile(r"https://[^/]+/robots\.txt"), body="User-agent: *\nAllow: /\n")
    for host in ("www.generali.de", "www.careers.zurich.com", "careers.dhl.com", "www.rewe-digital.com", "karriere.wdr.de"):
        responses.get(re.compile(rf"https://{re.escape(host)}/(?!search|job|eu/de/search).*"), body="<html>Karriere</html>")
    responses.get("https://g.dvinci-hr.com/jobPublication/list.json", json=DVINCI)
    responses.get(re.compile(r"https://www\.careers\.zurich\.com/search/\?.*"), body=CSB)
    responses.get("https://www.careers.zurich.com/job/Koeln-Werkstudent-IT/793/", body=detail("Werkstudent IT Security"))
    responses.get(re.compile(r"https://careers\.dhl\.com/eu/de/search-results\?.*"), body=PHENOM)
    responses.get("https://www.rewe-digital.com/de/jobs", body=REWE)
    responses.get("https://bewerbung.wdr.de/sitemap.xml", body=WDR_SITEMAP)
    responses.get("https://bewerbung.wdr.de/index.php?ac=jobad&id=1", body=detail("Werkstudent Redaktion IT"))
    responses.get("https://bewerbung.wdr.de/index.php?ac=jobad&id=2", body=detail("Duales Studium BWL"))
    entries = [
        {"name": "Generali", "karriereseite_url": "https://www.generali.de/karriere", "ats": "dvinci",
         "ats_id": "g.dvinci-hr.com"},
        {"name": "Zurich", "karriereseite_url": "https://www.careers.zurich.com/start", "ats": "successfactors",
         "ats_id": "https://www.careers.zurich.com/search/?locationsearch=Deutschland&locale=de_DE"},
        {"name": "DHL Group", "karriereseite_url": "https://careers.dhl.com/eu/de", "ats": "phenom",
         "ats_id": "https://careers.dhl.com/eu/de"},
        {"name": "REWE digital", "karriereseite_url": "https://www.rewe-digital.com/de/jobs", "ats": "eingebettet"},
        {"name": "WDR", "karriereseite_url": "https://karriere.wdr.de/", "ats": "sitemap",
         "ats_id": "https://bewerbung.wdr.de/sitemap.xml"},
    ]
    state = State(tmp_path / "s.sqlite")
    result = _source(entries, state).fetch()
    titel = {j.company: sorted(x.title for x in result.jobs if x.company == j.company) for j in result.jobs}
    assert titel["Generali"] == ["Werkstudent IT-Security (m/w/d)"]
    assert titel["Zurich"] == ["Werkstudent IT Security"]                 # Underwriter: kein Rollen-Stichwort
    assert titel["DHL Group"] == ["Werkstudent (m/w/d) Cloud"]
    assert titel["REWE digital"] == ["Werkstudent Fullstack Software Developer (m/w/d)"]
    assert titel["WDR"] == ["Duales Studium BWL", "Werkstudent Redaktion IT"]
    assert not result.manual_check and not result.teilfehler
    zurich = next(j for j in result.jobs if j.company == "Zurich")
    assert zurich.location == "Köln"                                     # aus JSON-LD der Detailseite
    # Zweiter Lauf: WDR-Detailseiten kommen aus dem Zwischenspeicher, Rohtreffer bleiben gleich
    vorher = sum(1 for c in responses.calls if "ac=jobad" in c.request.url)
    result = _source(entries[4:], state).fetch()
    assert sorted(j.title for j in result.jobs) == ["Duales Studium BWL", "Werkstudent Redaktion IT"]
    assert sum(1 for c in responses.calls if "ac=jobad" in c.request.url) == vorher
