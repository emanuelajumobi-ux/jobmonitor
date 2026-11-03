"""Demo-Modus: Beispieldaten in eigenem Ordner, Umschalten und zurück, eigene Daten bleiben unberührt."""
from jobmonitor import demo, erststart
from jobmonitor.gui import App


def test_demo_anlegen(tmp_path):
    ziel = demo.anlegen(tmp_path / "demo")
    app = App(ziel, compile_pdf=False)
    jobs = app.jobs()
    assert len(jobs) == len(demo.STELLEN) and all(j["url"].startswith("https://example.com/") for j in jobs)
    assert max(j["fit"] or 0 for j in jobs) >= 75                     # Fit aus dem Beispiel-Lebenslauf
    html = app.index().decode()
    assert "Werkstudent IT-Support" in html and "Noch kein Wohnort" not in html


def test_umschalten_und_zurueck(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "ORDNER", tmp_path / "demo")
    eigen = tmp_path / "eigen"
    erststart.vorbereiten(eigen)
    app = App(eigen, compile_pdf=False)
    assert "Demo ansehen" in app.einrichten().decode()
    html = app.demo_starten().decode()
    assert app.root == tmp_path / "demo" and "Demo beenden" in html and "Beispiel Logistik" in html
    assert "In der Demo nicht verfügbar" in app.einstellungen_post({"aktion": "pipeline"}).decode()
    assert "nichts synchronisiert" in app.sync_card()
    html = app.demo_beenden().decode()
    assert app.root == eigen and app.echt is None and "demo-banner" not in html
    assert not (eigen / "cv" / "cv_master.yaml").exists()                # eigene Daten unberührt
