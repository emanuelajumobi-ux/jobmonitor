import json
import re
from datetime import date

import responses

from jobmonitor.drafts import render, write_drafts
from jobmonitor.initiativ import find_initiativ_link
from jobmonitor.sources.ats import boards, sitemap, workday
from jobmonitor.sources.companies import CompaniesSource, detect_ats
from jobmonitor.sources.mail_alerts import canonical_url, parse_alert_html
from tests.conftest import fixture


# --- Initiativ-Erkennung ---
def test_initiative_is_not_initiativbewerbung():
    html = '<a href="/de/die-corporate-influencer-initiative">Unsere Initiative</a>'
    assert find_initiativ_link(html, "https://x") is None
    assert find_initiativ_link('<a href="/s">Jetzt initiativ bewerben</a>', "https://x") == "https://x/s"


# --- Sitemaps / SuccessFactors / Workday ---
def test_sitemap_candidates_adesso():
    locs = re.findall(r"<loc>([^<]+)", fixture("adesso_sitemap.xml"))
    cands = sitemap.candidate_urls(locs)
    assert cands and all(re.search(r"werkstud|thesis|bachelor", c, re.I) for c in cands)


def test_workday_internal_is_not_intern():
    locs = re.findall(r"<loc>([^<]+)", fixture("workday_sitemap.xml"))
    cands = sitemap.candidate_urls(locs)
    assert cands and not any("Internal" in c for c in cands)


@responses.activate
def test_sitemap_collect_follows_robots_sitemap(fetcher):
    responses.get("https://jobs.example.com/robots.txt", body="User-agent: *\nDisallow: /services/\n"
                  "Sitemap: https://jobs.example.com/sitemap.xml\n")
    responses.get("https://jobs.example.com/sitemap.xml", body=fixture("adesso_sitemap.xml"))
    cands, rss = sitemap.collect(fetcher, "https://jobs.example.com/", "adesso", "Firmen")
    assert cands and not rss


@responses.activate
def test_sitemap_rss_variant(fetcher):
    rss = ("<rss version='2.0'><channel><item><title>Werkstudent Cloud Security (Leverkusen, DE)</title>"
           "<link>https://jobs.bayer.com/job/1/</link><description>Azure</description></item>"
           "<item><title>Senior Manager (Reading, GB)</title><link>https://jobs.bayer.com/job/2/</link></item>"
           "</channel></rss>")
    responses.get("https://jobs.bayer.com/robots.txt", status=404)
    responses.get("https://jobs.bayer.com/sitemap.xml", body=rss)
    cands, jobs = sitemap.collect(fetcher, "https://jobs.bayer.com/", "Bayer", "Firmen")
    assert [j.title for j in jobs] == ["Werkstudent Cloud Security (Leverkusen, DE)"]


def test_workday_ids_and_parse():
    ats_id = "covestro.wd3.myworkdayjobs.com/de-DE/cov_external"
    assert workday.search_url(ats_id) == "https://covestro.wd3.myworkdayjobs.com/wday/cxs/covestro/cov_external/jobs"
    jobs = workday.parse({"jobPostings": [{"title": "Werkstudent IT", "externalPath": "/job/Leverkusen/x_JR-1",
                                           "locationsText": "Leverkusen"}]}, ats_id, "Covestro", "Firmen")
    assert jobs[0].url == "https://covestro.wd3.myworkdayjobs.com/de-DE/cov_external/job/Leverkusen/x_JR-1"


@responses.activate
def test_workday_without_approval_uses_sitemap(cfg, fetcher):
    responses.get("https://www.covestro.com/robots.txt", status=404)
    responses.get("https://www.covestro.com/", body="<html></html>")
    responses.get("https://covestro.wd3.myworkdayjobs.com/robots.txt", body="User-agent: *\nAllow: /\n")
    responses.get("https://covestro.wd3.myworkdayjobs.com/cov_external/siteMap.xml", body=fixture("workday_sitemap.xml"))
    responses.get(re.compile(r"https://covestro\.wd3\.myworkdayjobs\.com/cov_external/job/.*"),
                  body=fixture("inovex_detail.html"))
    doc = {"firmen": [{"name": "Covestro", "karriereseite_url": "https://www.covestro.com/", "ats": "workday",
                       "ats_id": "covestro.wd3.myworkdayjobs.com/de-DE/cov_external"}]}
    result = CompaniesSource(doc, cfg["sources"]["companies"], fetcher, date(2026, 10, 31)).fetch()
    assert result.jobs and not result.errors
    assert not any("/wday/cxs/" in c.request.url for c in responses.calls)  # keine inoffizielle API ohne Freigabe


@responses.activate
def test_http_403_goes_to_manual_check(cfg, fetcher):
    responses.get("https://www.rhenag.de/robots.txt", status=404)
    responses.get("https://www.rhenag.de/karriere/", status=403)
    doc = {"firmen": [{"name": "rhenag", "karriereseite_url": "https://www.rhenag.de/karriere/"}]}
    result = CompaniesSource(doc, cfg["sources"]["companies"], fetcher, date(2026, 10, 31)).fetch()
    assert not result.errors and "HTTP 403" in result.manual_check[0]


def test_detect_smartrecruiters_and_parse():
    html = '<a href="https://careers.smartrecruiters.com/SopraSteria1/0a19a7e0-1681-4e0f-815a-662bf5721b48-newsletter">'
    assert detect_ats(html, "https://careers.soprasteria.de") == ("smartrecruiters", "SopraSteria1")
    jobs = boards.parse_smartrecruiters(json.loads(fixture("smartrecruiters.json")), "Sopra Steria", "Firmen")
    assert len(jobs) == 3 and jobs[0].url.startswith("https://jobs.smartrecruiters.com/SopraSteria1/")


def test_recruitee_and_teamtailor():
    jobs = boards.parse_recruitee({"offers": [{"title": "Werkstudent DevOps", "city": "Köln", "remote": True,
                                               "careers_url": "https://x.recruitee.com/o/1"}]}, "X", "Firmen")
    assert jobs[0].remote and jobs[0].location == "Köln"
    rss = "<rss><channel><item><title>Working Student Cloud</title><link>https://x.teamtailor.com/jobs/1</link>" \
          "<description>&lt;p&gt;Remote&lt;/p&gt;</description></item></channel></rss>"
    jobs = boards.parse_rss(rss, "X", "Firmen")
    assert jobs[0].remote and jobs[0].url.endswith("/jobs/1")


# --- Job-Alert-Mails ---
ALERT = """<html><body><table>
<tr><td><a href="https://www.linkedin.com/jobs/view/4012345678/?trk=eml-jobs&refId=abc">Werkstudent Cloud Engineering (m/w/d)</a></td></tr>
<tr><td>Beispiel GmbH</td></tr><tr><td>Köln, Nordrhein-Westfalen</td></tr>
</table><table>
<tr><td><a href="https://www.linkedin.com/jobs/view/4099999999/?trk=x">Senior Sales Manager</a> | Firma | Berlin</td></tr>
</table><a href="https://www.linkedin.com/comm/settings">Einstellungen für Job-Alerts verwalten</a></body></html>"""


def test_parse_alert_html(cfg):
    jobs = parse_alert_html(ALERT, "linkedin.com", cfg["profile"]["werkstudent"]["rollen"], "Köln")
    assert len(jobs) == 1
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/4012345678"
    assert jobs[0].title.startswith("Werkstudent Cloud")


def test_canonical_url_keeps_indeed_id():
    assert canonical_url("https://de.indeed.com/rc/clk?jk=abc123&from=alert&tk=x") == \
        "https://de.indeed.com/rc/clk?jk=abc123"


# --- Anschreiben-Entwürfe ---
ENTRY = {"name": "q.beyond", "branche": "Cloud- und Managed-Service-Provider", "standorte": ["Köln"],
         "fokus": ["Azure", "Cloud Operations"]}


def test_draft_without_profile_uses_placeholders(tmp_path):
    text = render(ENTRY, {}, {"zielrolle": "Werkstudent Cloud"}, date(2026, 10, 31))
    assert "[Dein Name]" in text and "q.beyond" in text and "Azure" in text
    assert "Sehr geehrte Damen und Herren" in text


def test_write_drafts_uses_local_profile(tmp_path):
    (tmp_path / "profile.yaml").write_text("name: Max Muster\nzeitraum: April 2027\n", encoding="utf-8")
    paths = write_drafts([ENTRY], tmp_path, {"llm": False}, date(2026, 10, 31))
    text = paths[0].read_text(encoding="utf-8")
    assert paths[0].name == "2026-10-31-q-beyond.md"
    assert "Max Muster" in text and "April 2027" in text
    assert write_drafts([ENTRY], tmp_path, {"llm": False}, date(2026, 10, 31)) == []  # nicht überschreiben


def test_initiativ_prefers_general_over_fuehrungskraft():
    html = ('<a href="/jobs/1/initiativbewerbung-als-fuehrungskraft/">Initiativbewerbung als Führungskraft</a>'
            '<a href="/jobs/2/initiativbewerbung/">Initiativbewerbung</a>')
    assert find_initiativ_link(html, "https://x") == "https://x/jobs/2/initiativbewerbung/"
    assert find_initiativ_link(html.split("<a href=\"/jobs/2")[0], "https://x") is None


def test_sender_behind_apple_relay():
    from jobmonitor.sources.mail_alerts import sender_domain
    assert sender_domain("no-reply_at_indeed_com_bdhdzfbcbj_c63567cd@privaterelay.appleid.com") == "indeed.com"
    assert sender_domain("info_at_mail_stepstone_de_abcdefgh_0a1b2c3d@privaterelay.appleid.com") == "mail.stepstone.de"
    assert sender_domain("jobalerts-noreply@linkedin.com") == "linkedin.com"


ALERT_TEXT = """Ihre Jobbenachrichtigung für Werkstudent Cloud
Werkstudent Cloud Security (m/w/d)
Beispiel AG
Köln
Jobangebot ansehen: https://www.linkedin.com/comm/jobs/view/111/?trackingId=abc&trk=x
---------------------------------------------------------
IT Security Architect (m/w/d)
Andere GmbH
Bonn
Jobangebot ansehen: https://www.linkedin.com/comm/jobs/view/222/?trackingId=def
---------------------------------------------------------
Alle Jobs auf LinkedIn anzeigen: https://www.linkedin.com/comm/jobs/search-results/?keywords=x
"""


def test_parse_alert_text_and_skipped(cfg):
    from jobmonitor.sources.mail_alerts import parse_alert_text
    skipped = set()
    jobs = parse_alert_text(ALERT_TEXT, "linkedin.com", cfg["profile"]["werkstudent"]["rollen"], "Köln", skipped)
    assert [j.title for j in jobs] == ["Werkstudent Cloud Security (m/w/d)"]
    assert jobs[0].url == "https://www.linkedin.com/comm/jobs/view/111" and jobs[0].company == "Beispiel AG"
    assert jobs[0].location == "Köln"
    assert skipped == {"https://www.linkedin.com/comm/jobs/view/222"}           # Vollzeitstelle übersprungen
