"""Seite „Letzter Bericht“ im Stil der App (gui_bericht.py) – gelesen aus dem Markdown von report.py."""
from datetime import date

from jobmonitor import gui_bericht as gbe
from jobmonitor import gui_layout as layout
from jobmonitor.models import Job, SourceResult
from jobmonitor.report import InitiativTip, Report


def bericht_text():
    job = Job("Werkstudent Cloud Security (m/w/d)", "adesso", "https://x/1", "Firmen-Karriereseiten",
              location="Köln", remote=True, score=88, reason="Werkstudent mit Bezug zu cloud", fit=82,
              fit_passt=["Azure", "Terraform"], fit_fehlt=["Kubernetes"], frist="2026-11-20")
    ohne = Job("Werkstudent IT", "Firma B", "https://x/2", "Bundesagentur für Arbeit", score=50, reason="x")
    results = [SourceResult("Bundesagentur für Arbeit", jobs=[ohne]),
               SourceResult("Firmen-Karriereseiten", jobs=[job], errors=["Zurich: 404"],
                            manual_check=["WDR: keine maschinenlesbaren Stellen gefunden – https://karriere.wdr.de/"])]
    tip = InitiativTip("RheinEnergie", "https://r/init", "Energieversorger mit Bezug zu OT-Security", True)
    return Report(date(2026, 11, 2), results, [job, ohne], [tip], [], "", "Traumprofil", {"werkstudent": "Werkstudent"},
                  []).render()


def test_parse_and_render():
    b = gbe.parse(bericht_text())
    assert b.datum == "02.11.2026" and [q.status for q in b.quellen] == ["ok", "warn"]
    assert b.quellen[1].fehler == ["Zurich: 404"] and len(b.manuell) == 1
    stellen = b.gruppen[0].stellen
    assert stellen[0].fit == 82 and stellen[0].passt == "Azure, Terraform" and stellen[0].fehlt == "Kubernetes"
    assert stellen[0].frist and stellen[1].fit is None
    html = gbe.render(b, ["2026-11-02", "2026-11-01"], "2026-11-02")
    assert "Bericht vom 02.11.2026" in html and "2 neue Stellen" in html and "1 mit Problemen" in html
    assert 'class="dot warn"' in html and "RheinEnergie" in html and 'href="https://karriere.wdr.de/"' in html
    assert not gbe.EMOJI.search(html)          # keine Emojis wie in der Mail


def test_unknown_format_falls_back():
    assert gbe.parse("# Alt\n") is None


def test_logo_is_radar():
    assert 'class="logo"' in layout.LOGO and "#5EEAD4" in layout.LOGO
