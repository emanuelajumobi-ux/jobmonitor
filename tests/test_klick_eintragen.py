"""Per Klick eintragen: Kenntnis in den Master-CV (Lücken-Auswertung, Fit-Begriffe im Master-CV), Fit-Begriffe in
config.yaml (KI-Vorschläge, eigene) und die eine Initiativ-Liste für Bericht und Firmen-Seite."""
import json
from collections import Counter
from datetime import date

import pytest

from jobmonitor import fit_begriffe as fb
from jobmonitor import gui_master as gm
from jobmonitor.config import ROOT, load_companies, load_config
from jobmonitor.gui import App
from jobmonitor.gui_sync import SyncResult
from jobmonitor.initiativ_liste import kandidaten
from jobmonitor.models import normalize
from jobmonitor.report import InitiativTip, Report
from jobmonitor.state import State
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

CV = {"kenntnisse": [{"kategorie": "Microsoft und IT-Betrieb", "eintraege": [{"name": "Intune", "level": "gut"}]},
                     {"kategorie": "Automatisierung und DevOps", "eintraege": [{"name": "Git", "level": "gut"}]},
                     {"kategorie": "Netzwerke", "eintraege": [{"name": "Wireshark", "level": "gut"}]}],
      "sprachen": [{"sprache": "Deutsch", "niveau": "Muttersprache"}]}


def test_kenntnis_eintragen():
    data = json.loads(json.dumps(CV))
    assert gm.kenntnis_eintragen(data, "MS Office", "gut", ["excel", "powerpoint"]) == ("Microsoft und IT-Betrieb", True)
    assert gm.kenntnis_eintragen(data, "Kubernetes", "Grundkenntnisse", ["k8s"]) == ("Automatisierung und DevOps", True)
    assert gm.kenntnis_eintragen(data, "Firewall", "gut", []) == ("Netzwerke", True)
    assert gm.kenntnis_eintragen(data, "SAP", "gut", []) == ("Weitere Kenntnisse", True)
    assert data["kenntnisse"][-1] == {"kategorie": "Weitere Kenntnisse", "eintraege": [{"name": "SAP", "level": "gut"}]}
    assert gm.kenntnis_eintragen(data, "ms office", "sehr gut", []) == ("Microsoft und IT-Betrieb", False)
    assert data["kenntnisse"][0]["eintraege"][1] == {"name": "MS Office", "level": "sehr gut"}   # Level angepasst
    assert gm.kenntnis_eintragen(data, "Deutsch", "gut", []) == ("Sprachen", False)          # steht schon da
    assert gm.kenntnis_eintragen(data, "Englisch", "sehr gut", []) == ("Sprachen", True)
    assert data["sprachen"][-1] == {"sprache": "Englisch", "niveau": "sehr gut (C1)"}
    with pytest.raises(Exception):
        gm.kenntnis_eintragen(data, "X", "Profi", [])


def test_kenntnis_aus_der_lueckenauswertung(root):  # noqa: F811
    app = App(root, compile_pdf=False)
    html = app.luecken_kenntnis({"term": "Kubernetes", "level": "Grundkenntnisse"}).decode()
    assert "„Kubernetes“ (Grundkenntnisse) unter" in html and "in deinen Master-CV eingetragen" in html
    eintraege = [e["name"] for k in gm.load(root)["kenntnisse"] for e in k.get("eintraege") or []]
    assert "Kubernetes" in eintraege and (root / "cv" / "cv_master.yaml.bak").is_file()
    assert "Unbekannter Begriff" in app.luecken_kenntnis({"term": "Quatsch", "level": "gut"}).decode()


def test_kenntnis_im_master_cv(root):  # noqa: F811
    app = App(root, compile_pdf=False)
    html = app.master().decode()
    assert 'data-term="AWS"' in html and 'value="kenntnis:gut"' in html and 'id="kenntnis-term"' in html
    data = gm.load(root)
    data["profil"] = "Neu formuliert, noch nicht gespeichert."
    html = app.master_save({"aktion": "kenntnis:gut", "term": "AWS", "data": json.dumps(data)}).decode()
    assert "„AWS“ (gut) unter" in html and "eingetragen und gespeichert" in html
    neu = gm.load(root)
    assert neu["profil"] == "Neu formuliert, noch nicht gespeichert."      # offene Änderungen mitgespeichert
    assert any(e["name"] == "AWS" for k in neu["kenntnisse"] for e in k.get("eintraege") or [])


def test_fit_begriffe_vorschlaege(tmp_path):
    state = State(tmp_path / "s.sqlite")
    fb.merken(state, Counter({"Deutsch": 2, "Java": 1}))
    fb.merken(state, Counter({"Deutsch": 3}))
    gespeichert = Counter(json.loads(state.get_meta(fb.META)))
    assert gespeichert == Counter({"Deutsch": 5, "Java": 1})
    bericht = fb.aus_bericht("- KI fand Anforderungen ohne Fit-Begriff: Deutsch (2×), C# (1×), Power BI (1×) – in …")
    assert bericht == Counter({"Deutsch": 2, "C#": 1, "Power BI": 1})
    begriffe = {"Azure": ["microsoft azure"], "Power BI": []}
    assert fb.offen(gespeichert, bericht, begriffe, {"java"}) == [("Deutsch", 5), ("C#", 1)]


def test_fit_begriff_hinzufuegen(root, monkeypatch):  # noqa: F811
    vorher = (root / "config.yaml").read_text(encoding="utf-8")
    fb.hinzufuegen(root, "Deutsch", ["deutschkenntnisse", " German "], load_config(root / "config.yaml")["fit"]["begriffe"])
    fb.hinzufuegen(root, "C#", [], load_config(root / "config.yaml")["fit"]["begriffe"])
    cfg = load_config(root / "config.yaml")
    assert cfg["fit"]["begriffe"]["Deutsch"] == ["deutschkenntnisse", "german"] and cfg["fit"]["begriffe"]["C#"] == []
    nachher = (root / "config.yaml").read_text(encoding="utf-8")
    assert nachher.replace("    Deutsch: [deutschkenntnisse, german]\n    C#: []\n", "") == vorher   # Rest unverändert
    with pytest.raises(fb.BegriffError, match="gibt es schon"):
        fb.hinzufuegen(root, "microsoft azure", [], cfg["fit"]["begriffe"])
    # In der App: Vorschlag aus dem Bericht übernehmen bzw. ausblenden
    (root / "reports").mkdir()
    (root / "reports" / "2026-11-02.md").write_text("# Job-Monitor\n- KI fand Anforderungen ohne Fit-Begriff: "
                                                     "Jira (2×), Power BI (1×) – in der App …\n", encoding="utf-8")
    monkeypatch.setattr("jobmonitor.gui.sync", lambda r: SyncResult(True, "ok"))
    app = App(root, compile_pdf=False)
    html = app.luecken().decode()
    assert 'id="fitbegriffe"' in html and "<b>Jira</b>" in html and "<b>Power BI</b>" in html
    html = app.fitbegriffe({"aktion": "uebernehmen", "term": "Jira"}).decode()
    assert "„Jira“ ist jetzt ein Fit-Begriff. Zu GitHub hochgeladen." in html and "<b>Jira</b>" not in html
    html = app.fitbegriffe({"aktion": "ignorieren", "term": "Power BI"}).decode()
    assert "ausgeblendet" in html and "<b>Power BI</b>" not in html
    html = app.fitbegriffe({"aktion": "neu", "term": "SAP", "synonyme": "sap s/4hana, sap erp"}).decode()
    assert load_config(root / "config.yaml")["fit"]["begriffe"]["SAP"] == ["sap s/4hana", "sap erp"]
    assert "gibt es schon" in app.fitbegriffe({"aktion": "neu", "term": "SAP"}).decode()


def test_eine_initiativ_liste():
    cfg = load_config()
    doc = load_companies(ROOT / "companies.yaml")
    alle = kandidaten(doc, None, set(), cfg)
    ja = [f["name"] for f in doc["firmen"] if (f.get("initiativ") or {}).get("moeglich") == "ja"
          and (f.get("initiativ") or {}).get("url") and f.get("aktiv") is not False]
    assert {t.firma for t, _ in alle} <= set(ja) and alle
    name = alle[0][0].firma
    mit_stellen = kandidaten(doc, None, {normalize(name)}, cfg)
    assert mit_stellen[-1] == (alle[0][0], True)                 # bleibt drin, aber markiert und hinten
    tips = [InitiativTip("A", "https://a", "warum", False), InitiativTip("B", "https://b", "warum", True)]
    text = "\n".join(Report(date(2026, 11, 3), [], [], tips[:1], initiativ_alle=tips)._initiativ())
    assert "## Initiativ möglich (1 neu)" in text and "2 Firmen in Reichweite" in text and "**B** 🆕" in text
    assert "**A**" not in text


def test_initiativ_auf_der_firmenseite(root):  # noqa: F811
    import shutil
    shutil.copy(ROOT / "companies.yaml", root / "companies.yaml")
    html = App(root, compile_pdf=False).firmen().decode()
    assert "Initiativ bewerben (" in html and "Initiativ-Seite" in html
