"""Karrierestufe Minijob / Aushilfe: Vorlage, Suche der Bundesagentur mit arbeitszeit=mj, Formular, Filter, Design."""
from jobmonitor import designs, gui, suchprofil
from jobmonitor import gui_suchprofile as gsp
from jobmonitor.config import load_config
from jobmonitor.sources.bundesagentur import BundesagenturSource
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


def test_vorlage_und_formular():
    assert suchprofil.STUFEN["minijob"]["art"] == "minijob" and "aushilfe" in suchprofil.STUFEN["minijob"]["rollen"]
    cfg = load_config()
    form = {"name": "Aushilfe Verkauf", "enabled": "", "art": "minijob", "stufe": "minijob",
            "rollen": "minijob: 30\naushilfe: 28", "such_bundesagentur": "Minijob Verkauf", "such_stellenwerk": "",
            "fachgebiet": "eigen", "fach": "verkauf: 10\nkasse: 8\neinzelhandel: 8"}
    key, daten = gsp.aus_formular(form, cfg)
    assert daten["arbeitszeit"] == "mj" and daten["angebotsart"] == 1 and daten["stufe"] == "minijob"
    assert gsp._profil_formdaten(daten)["art"] == "minijob"
    p = suchprofil._from_dict(key, daten)
    assert p.arbeitszeit == "mj" and suchprofil.stufe_von(p) == "minijob"
    assert designs.fuer_profil({**cfg, "profile": {key: daten}}, key) == "kompakt"
    assert 'data-eck="v"' in gui.eck_filter(["minijob"]) and 'data-eck="h"' not in gui.eck_filter(["minijob"])


def test_ba_suche_mit_minijob(cfg):
    gesendet = []
    quelle = BundesagenturSource({**cfg["sources"]["bundesagentur"], "wo": "", "bundesweit_remote": False,
                                  "suchbegriffe": ["Minijob Verkauf"], "angebotsart": 1, "arbeitszeit": "mj"}, None)
    quelle._search = lambda params: gesendet.append(params) or {}
    quelle.fetch()
    assert gesendet and gesendet[0]["arbeitszeit"] == "mj" and gesendet[0]["angebotsart"] == 1
