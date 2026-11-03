"""Eigene Suchprofile: anlegen, bearbeiten, löschen (gui_suchprofile.py), eigenes Fachgebiet und Fit-Begriffe je
Profil (scoring.py, config.py) sowie die Grenzen für sparsame Abfragen (suchprofil.py)."""
import pytest

from jobmonitor import gui_suchprofile as gsp
from jobmonitor import gui_wartung as gw
from jobmonitor import scoring, suchprofil
from jobmonitor.config import load_config
from jobmonitor.gui import App
from jobmonitor.gui_sync import SyncResult
from jobmonitor.models import Job
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

DATA = {"name": "Data", "enabled": "1", "art": "studium", "rollen": "werkstudent: 30\npraktikum",
        "such_bundesagentur": "Werkstudent Data Science\nWerkstudent Machine Learning", "such_stellenwerk": "",
        "fachgebiet": "eigen", "fach": "data science: 14\nmachine learning: 12\npython\nsql: 6",
        "fit_begriffe": "Pandas: pandas dataframe\nMachine Learning: ml, scikit-learn"}


def job(title, desc=""):
    return Job(title=title, company="Firma", location="Köln", url="https://x.de/1", source="Test", description=desc)


def test_eigenes_fachgebiet_im_scoring():
    cfg = load_config()
    cfg["profile"]["data"] = {"name": "Data", "rollen": {"werkstudent": 30}, "fach": {"data science": 14,
                              "machine learning": 12, "python": 8}, "suchbegriffe": {"bundesagentur": ["x"]}}
    data = suchprofil.get(cfg, "data")
    ds = job("Werkstudent Data Science (m/w/d)", "Machine Learning mit Python")
    assert scoring.evaluate(job(ds.title, ds.description), cfg, data.rollen, fach=data.fach) is not None
    # gemeinsames Fachgebiet (Cloud, Security …) kennt Data Science nicht
    assert scoring.evaluate(job(ds.title, ds.description), cfg, data.rollen) is None
    # Ohne Fach-Wort im Titel braucht es zwei starke Stichwörter in der Beschreibung (auch beim eigenen Fachgebiet)
    assert scoring.evaluate(job("Werkstudent Marketing", "etwas Python"), cfg, data.rollen, fach=data.fach) is None
    best = scoring.evaluate_profiles(job(ds.title, ds.description), cfg, suchprofil.alle(cfg))
    assert best.profil == "data"


def test_fit_begriffe_und_grenzen(tmp_path):
    text = (load_config.__globals__["ROOT"] / "config.yaml").read_text(encoding="utf-8")
    text = text.replace("profile:\n", "profile:\n  data:\n    name: Data\n    rollen: {werkstudent: 30}\n"
                        "    fit_begriffe:\n      Pandas: [pandas dataframe]\n      Azure: [nicht doppelt]\n", 1)
    (tmp_path / "config.yaml").write_text(text, encoding="utf-8")
    cfg = load_config(tmp_path / "config.yaml")
    assert cfg["fit"]["begriffe"]["Pandas"] == ["pandas dataframe"]
    assert cfg["fit"]["begriffe"]["Azure"] == ["microsoft azure"]                 # Vorhandenes bleibt
    viele = {f"p{i}": {"rollen": {"x": 1}, "suchbegriffe": {"bundesagentur": [f"b{j}" for j in range(20)]}}
             for i in range(6)}
    cfg = {"profile": viele, "sources": {"bundesagentur": {"bundesweit_remote": True, "max_details": 25},
                                         "stellenwerk": {"max_detail_pages": 20}}}
    aktiv = suchprofil.aktive(cfg)
    assert len(aktiv) == suchprofil.MAX_AKTIV and len(aktiv[0].begriffe("bundesagentur")) == suchprofil.MAX_BEGRIFFE
    assert suchprofil.anfragen(cfg, 2) == {"bundesagentur": 4 * (15 * 2 + 25), "stellenwerk": 0}


def test_formular_pruefen(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    key, daten = gsp.aus_formular(DATA, cfg)
    assert key == "data" and daten["angebotsart"] == 34 and daten["rollen"] == {"werkstudent": 30, "praktikum": 25}
    assert daten["fach"]["python"] == gsp.FACH_STANDARD and daten["fit_begriffe"]["Machine Learning"] == ["ml",
                                                                                                         "scikit-learn"]
    assert gsp.schluessel("Prüfung & Ölbau", {}) == "pruefung_oelbau"
    fehler = {**DATA, "name": "Junior", "rollen": "", "such_bundesagentur": "\n".join(f"b{i}" for i in range(16)),
              "fach": "eins", "art": "arbeit"}
    with pytest.raises(gsp.SuchprofilError) as e:
        gsp.aus_formular(fehler, cfg)
    msg = str(e.value)
    assert "„Junior“ gibt es schon" in msg and "Mindestens ein Rollen-Wort" in msg and "Höchstens 15" in msg
    assert "mindestens 3 Fach-Stichwörter" in msg
    with pytest.raises(gsp.SuchprofilError, match="Zahl"):
        gsp.aus_formular({**DATA, "rollen": "werkstudent: viel"}, cfg)
    voll = {**cfg, "profile": {f"p{i}": {"name": f"P{i}"} for i in range(4)}}
    with pytest.raises(gsp.SuchprofilError, match="Höchstens 4 Suchprofile"):
        gsp.aus_formular(DATA, voll)
    assert gsp.aus_formular({**DATA, "enabled": ""}, voll)[1]["enabled"] is False     # ausgeschaltet geht


def test_speichern_bearbeiten_loeschen(root):  # noqa: F811
    vorher = (root / "config.yaml").read_text(encoding="utf-8")
    cfg = load_config(root / "config.yaml")
    gsp.speichern(root, *gsp.aus_formular(DATA, cfg))
    nachher = (root / "config.yaml").read_text(encoding="utf-8")
    start, ende = nachher.index("  data:\n"), nachher.index("\n# Inoffizielle")
    assert nachher[:start] == vorher[:start]                               # alles davor unverändert
    assert nachher[ende:] == vorher[vorher.index("\n# Inoffizielle"):]     # alles danach unverändert
    cfg = load_config(root / "config.yaml")
    data = suchprofil.get(cfg, "data")
    assert data.name == "Data" and data.fach["data science"] == 14 and data.angebotsart == 34
    assert "Pandas" in cfg["fit"]["begriffe"]
    # Werkstudent bearbeiten: Kommentar in den Suchbegriffen und Felder außerhalb des Formulars bleiben
    form = {**gsp._profil_formdaten(cfg["profile"]["werkstudent"]), "zielrolle": "Werkstudent Cloud Security"}
    form["enabled"] = "1"
    gsp.speichern(root, *gsp.aus_formular({**form, "key": "werkstudent"}, cfg))
    text = (root / "config.yaml").read_text(encoding="utf-8")
    assert "# Traumprofil Cloud Security (gezielt)" in text and "zielrolle: Werkstudent Cloud Security" in text
    cfg = load_config(root / "config.yaml")
    assert cfg["profile"]["werkstudent"]["ats_suchbegriffe"][0] == "Werkstudent"
    assert cfg["profile"]["junior"]["slug_begriffe"][0] == "junior"         # Nachbar unberührt
    assert gsp.loeschen(root, "data", cfg) == "Data"
    assert "data" not in load_config(root / "config.yaml")["profile"]
    with pytest.raises(gsp.SuchprofilError):
        gsp.loeschen(root, "werkstudent", cfg)


def test_einschalten_mit_grenze(root):  # noqa: F811
    cfg = load_config(root / "config.yaml")
    for i in range(2):
        gsp.speichern(root, *gsp.aus_formular({**DATA, "name": f"Data {i}"}, load_config(root / "config.yaml")))
    gsp.speichern(root, *gsp.aus_formular({**DATA, "name": "Fünftes", "enabled": ""},
                                           load_config(root / "config.yaml")))
    assert len(suchprofil.aktive(load_config(root / "config.yaml"))) == 4
    with pytest.raises(gw.WartungError, match="Höchstens 4"):
        gw.profil_setzen(root, "fuenftes", True)
    gw.profil_setzen(root, "junior", False)
    gw.profil_setzen(root, "fuenftes", True)
    assert suchprofil.get(load_config(root / "config.yaml"), "fuenftes").enabled
    assert cfg                                                              # (Ausgangsstand nur zum Lesen)


def test_seiten_in_der_app(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr("jobmonitor.gui.sync", lambda r: SyncResult(True, "Synchronisiert."))
    app = App(root, compile_pdf=False)
    html = app.einstellungen().decode()
    assert "Neues Suchprofil" in html and "/einstellungen/suchprofil?key=junior" in html and "Aktiv: 2 von" in html
    assert "Abrufe bei der Bundesagentur" in html
    html = app.suchprofil().decode()
    assert "<h1>Neues Suchprofil</h1>" in html and "Eigenes Fachgebiet" in html and "Löschen" not in html
    assert "Löschen" in app.suchprofil("junior").decode() and "Löschen" not in app.suchprofil("werkstudent").decode()
    html = app.suchprofil_post({**DATA, "name": ""}).decode()
    assert "Bitte einen Namen angeben" in html and "Werkstudent Data Science" in html     # Eingabe bleibt
    html = app.suchprofil_post(DATA).decode()
    assert "Suchprofil „Data“ gespeichert. Synchronisiert." in html and "<h1>Einstellungen</h1>" in html
    assert "eigenes Fachgebiet" in html
    html = app.suchprofil_post({"key": "data", "aktion": "loeschen"}).decode()
    assert "Suchprofil „Data“ gelöscht" in html
    assert "Unbekanntes Suchprofil" in app.suchprofil("gibtsnicht").decode()


def test_unveraendert_speichern_aendert_nichts(root):  # noqa: F811
    vorher = (root / "config.yaml").read_text(encoding="utf-8")
    for key in ("werkstudent", "junior"):
        cfg = load_config(root / "config.yaml")
        form = {**gsp._profil_formdaten(cfg["profile"][key]), "key": key, "enabled": "1"}
        gsp.speichern(root, *gsp.aus_formular(form, cfg))
    assert (root / "config.yaml").read_text(encoding="utf-8") == vorher
