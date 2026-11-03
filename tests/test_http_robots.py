"""robots.txt nach RFC 9309: Platzhalter, Gruppen je User-Agent, längste Regel gewinnt."""
from jobmonitor.http import Robots

UA = "job-monitor/0.1 (privates Jobsuche-Skript eines Studenten)"


def test_platzhalter_wie_bei_reply():
    r = Robots(["User-agent: *", "Disallow: /*/search", "Disallow: /*/about/careers/*/job-search",
                "Sitemap: https://www.reply.com/sitemap.xml"])
    assert not r.can_fetch(UA, "https://www.reply.com/de/about/careers/de/job-search?country=de&role=career_starter")
    assert r.can_fetch(UA, "https://www.reply.com/de/about/careers/de")
    assert not r.can_fetch(UA, "https://www.reply.com/de/search")
    assert r.site_maps() == ["https://www.reply.com/sitemap.xml"]


def test_eigene_gruppe_laengste_regel_und_ende():
    r = Robots(["User-agent: *", "Disallow: /", "", "User-agent: job-monitor", "Allow: /jobs$", "Disallow: /jobs",
                "Allow: /karriere/*.html", "Disallow: /karriere/"])
    assert r.can_fetch(UA, "https://x/jobs") and not r.can_fetch(UA, "https://x/jobs/1")
    assert r.can_fetch(UA, "https://x/karriere/a.html") and not r.can_fetch(UA, "https://x/karriere/a")
    assert r.can_fetch(UA, "https://x/sonst")                       # eigene Gruppe ersetzt die *-Gruppe
    assert not Robots(["User-agent: *", "Disallow: /"]).can_fetch(UA, "https://x/a")
    assert Robots(["User-agent: *", "Disallow:"]).can_fetch(UA, "https://x/a")


def test_gleichstand_allow_und_kommentare():
    r = Robots(["User-agent: *  # alle", "Disallow: /a", "Allow: /a", "Disallow: /p?q=1  # Suche"])
    assert r.can_fetch(UA, "https://x/a/b") and not r.can_fetch(UA, "https://x/p?q=1")
