import json
import shutil

import pytest
from ruamel.yaml import YAML

from jobmonitor import gui_master as gm
from jobmonitor.config import ROOT
from jobmonitor.cv_data import CvDataError
from jobmonitor.gui import App
from tests.conftest import FIXTURES

HEADER = "# cv_master.yaml: Kopfkommentar\n# zweite Zeile\n\n"


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    text = HEADER + (FIXTURES / "cv_master_example.yaml").read_text(encoding="utf-8")
    (tmp_path / "cv" / "cv_master.yaml").write_text(text, encoding="utf-8")
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    return tmp_path


def test_roundtrip_keeps_data_and_header(root):
    data = gm.load(root)
    path = gm.save(root, gm.parse(json.dumps(data)))
    text = path.read_text(encoding="utf-8")
    assert text.startswith(HEADER) and YAML(typ="safe").load(text) == data
    assert (root / "cv" / "cv_master.yaml.bak").read_text(encoding="utf-8").startswith(HEADER)


def test_repo_cv_master_roundtrips(tmp_path, monkeypatch):
    if not (ROOT / "cv" / "cv_master.yaml").exists():
        pytest.skip("keine cv/cv_master.yaml")
    monkeypatch.delenv("CV_MASTER_YAML", raising=False)
    (tmp_path / "cv").mkdir()
    shutil.copy(ROOT / "cv" / "cv_master.yaml", tmp_path / "cv" / "cv_master.yaml")
    data = gm.load(tmp_path)
    gm.save(tmp_path, gm.parse(json.dumps(data)))
    assert gm.load(tmp_path) == data


def test_parse_cleans_empty_entries():
    data = gm.parse(json.dumps({
        "stationen": [{"rolle": " Werkstudent ", "aufgaben": ["A", "", " B "], "bis": ""}],
        "kenntnisse": [{"kategorie": "Cloud", "eintraege": [{"name": "Azure", "level": "gut"}, {"level": "gut"}]}],
        "sprachen": [{"sprache": "", "niveau": ""}], "interessen": ["Klettern", ""]}))
    assert data["stationen"] == [{"rolle": "Werkstudent", "aufgaben": ["A", "B"], "bis": ""}]
    assert data["kenntnisse"][0]["eintraege"] == [{"name": "Azure", "level": "gut"}]
    assert data["sprachen"] == [] and data["interessen"] == ["Klettern"]


@pytest.mark.parametrize("data, match", [
    ({"profil": "Mail an max@example.com"}, "E-Mail"),
    ({"projekte": [{"name": "", "beschreibung": "x"}]}, "Feld „name“ fehlt"),
    ("kaputt", "unlesbar"),
])
def test_parse_rejects(data, match):
    with pytest.raises(CvDataError, match=match):
        gm.parse(data if isinstance(data, str) else json.dumps(data))


def test_page_and_save_via_app(root):
    app = App(root, compile_pdf=False)
    html = app.master().decode()
    assert 'id="schema"' in html and "Azure Landing Zone" in html and app.token in html
    data = gm.load(root)
    data["kenntnisse"][0]["eintraege"].append({"name": "Kubernetes", "level": "Grundkenntnisse"})
    html = app.master_save({"aktion": "speichern", "data": json.dumps(data)}).decode()
    assert "Gespeichert" in html
    assert {"name": "Kubernetes", "level": "Grundkenntnisse"} in gm.load(root)["kenntnisse"][0]["eintraege"]


def test_error_keeps_unsaved_input(root):
    app = App(root, compile_pdf=False)
    before = (root / "cv" / "cv_master.yaml").read_text(encoding="utf-8")
    data = {**gm.load(root), "profil": "Ruf an: +49 221 1234567 – NEUER TEXT"}
    html = app.master_save({"aktion": "speichern", "data": json.dumps(data)}).decode()
    assert "Nicht gespeichert" in html and "Telefonnummer" in html and "NEUER TEXT" in html
    assert "1234567" not in html.split("Nicht gespeichert")[1].split("</div>")[0]   # Wert nicht in der Meldung
    assert (root / "cv" / "cv_master.yaml").read_text(encoding="utf-8") == before


def test_script_tags_in_data_are_neutralised(root):
    app = App(root, compile_pdf=False)
    html = app.master({"profil": "</script><script>alert(1)</script>"}).decode()
    assert "</script><script>alert(1)" not in html
