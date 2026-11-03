"""Lernvorschläge: Datei im Repo, Abgleich mit dem Master-CV, Auswahl nach Lücken, Übernehmen, Lücken-Seite."""
import shutil

import pytest
from ruamel.yaml import YAML

from jobmonitor import lernpfade as lp
from jobmonitor.config import ROOT, load_config
from jobmonitor.cv_data import covered_terms, load_cv_master
from jobmonitor.gui import App
from jobmonitor.models import Job
from jobmonitor.state import State
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

PFADE = ("Kubernetes:\n  - {art: zertifikat, name: KCNA, zusatz: Einstieg}\n"
         "  - {art: projekt, name: k3s im Homelab, zusatz: Cluster bauen, technologien: [Kubernetes, Linux]}\n"
         "Terraform:\n  - {art: projekt, name: Azure Landing Zone mit Terraform, zusatz: IaC}\n"
         "Kaputt:\n  - {art: kurs, name: Irgendwas}\n")


def test_repo_file_matches_fit_terms(cfg):
    pfade = lp.load(ROOT)
    assert pfade and set(pfade) <= set(cfg["fit"]["begriffe"])          # nur bekannte Begriffe
    for term, items in pfade.items():
        assert items and all(v["art"] in lp.SECTION for v in items), term
        for v in items:
            if v["art"] == "projekt":
                assert set(v.get("technologien") or [term]) <= set(cfg["fit"]["begriffe"]), v["name"]


def test_vorhanden():
    cv = {"zertifikate": [{"name": "Cisco CCNA", "status": "geplant"}],
          "projekte": [{"name": "Homelab mit Proxmox", "status": "in_arbeit"}]}
    assert lp.vorhanden(cv, {"name": "Cisco CCNA"}) == "geplant"
    assert lp.vorhanden(cv, {"name": "Homelab mit Proxmox"}) == "in_arbeit"
    assert lp.vorhanden(cv, {"name": "CCNA"}) == "geplant"                 # Teil des Namens genügt
    assert lp.vorhanden(cv, {"name": "LPIC-1"}) is None


def test_vorschlaege_follow_gaps(tmp_path):
    (tmp_path / lp.DATEI).write_text(PFADE, encoding="utf-8")
    rows = [{"term": "Englisch", "gewinn": {}}, {"term": "Kubernetes", "gewinn": {"gut": 3.9}},
            {"term": "SQL", "gewinn": {"gut": 2.0}}, {"term": "Terraform", "gewinn": {"gut": 3.0}}]
    out = lp.vorschlaege(rows, lp.load(tmp_path), {"zertifikate": [{"name": "KCNA", "status": "erreicht"}]})
    assert [b["term"] for b in out] == ["Kubernetes", "Terraform"]           # ohne Gewinn / ohne Pfad: weg
    assert [v["stand"] for v in out[0]["items"]] == ["erreicht", None] and out[0]["gewinn"] == 3.9
    assert len(lp.vorschlaege(rows, lp.load(tmp_path), {}, limit=1)) == 1


def test_uebernehmen_writes_planned_entries(root):  # noqa: F811
    (root / lp.DATEI).write_text(PFADE, encoding="utf-8")
    cfg = load_config(root / "config.yaml")
    before = covered_terms(load_cv_master(root)[0], cfg["fit"]["begriffe"])
    z = lp.uebernehmen(root, "Kubernetes", 0)
    p = lp.uebernehmen(root, "Kubernetes", 1)
    assert z == {"name": "KCNA", "zusatz": "Einstieg", "datum": "", "status": "geplant", "im_cv": False}
    assert p["technologien"] == ["Kubernetes", "Linux"] and p["beschreibung"] == "Cluster bauen"
    cv = YAML(typ="safe").load((root / "cv" / "cv_master.yaml").read_text(encoding="utf-8"))
    assert cv["zertifikate"][-1]["name"] == "KCNA" and cv["projekte"][-1]["name"] == "k3s im Homelab"
    assert (root / "cv" / "cv_master.yaml.bak").exists()
    assert covered_terms(load_cv_master(root)[0], cfg["fit"]["begriffe"]) == before   # geplant zählt nicht
    with pytest.raises(lp.LernpfadError, match="steht schon"):
        lp.uebernehmen(root, "Kubernetes", 0)
    with pytest.raises(lp.LernpfadError, match="nicht gefunden"):
        lp.uebernehmen(root, "Kubernetes", 7)
    with pytest.raises(lp.LernpfadError, match="Unbekannte Art"):
        lp.uebernehmen(root, "Kaputt", 0)


def test_luecken_page(root):  # noqa: F811
    shutil.copy(ROOT / lp.DATEI, root / lp.DATEI)
    state = State(root / "state" / "seen.sqlite")
    for i in range(3):
        job = Job(f"Werkstudent Cloud {i}", "Beispiel AG", f"https://x/{i}", "test")
        job.fit_anforderungen = {"Kubernetes": 1.0, "Azure": 1.0, "Linux": 1.0}
        state.save_job_detail(job, "2026-11-01")
    state.close()
    app = App(root, compile_pdf=False)
    html = app.luecken().decode()
    assert "Was du tun kannst" in html and "KCNA – Kubernetes and Cloud Native Associate" in html
    assert 'name="term" value="Kubernetes"' in html
    html = app.luecken_uebernehmen({"term": "Kubernetes", "index": "0"}).decode()
    assert "als geplant in deinen Master-CV übernommen" in html and "im Master-CV: geplant" in html
    assert "steht schon" in app.luecken_uebernehmen({"term": "Kubernetes", "index": "0"}).decode()
    assert "card err" in app.luecken_uebernehmen({"term": "Kubernetes", "index": "x"}).decode()
