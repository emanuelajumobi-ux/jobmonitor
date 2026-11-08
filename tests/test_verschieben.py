"""macOS: App aus Downloads nach Programme verschieben."""
import sys
from pathlib import Path

from jobmonitor import selbstupdate, verschieben as vs


def test_verschieben_ersetzt_alte_und_entfernt_markierung(tmp_path, monkeypatch):
    quelle = tmp_path / "Downloads" / "Job-Monitor.app"
    (quelle / "Contents").mkdir(parents=True)
    ziel_ordner = tmp_path / "Applications"
    (ziel_ordner / "Job-Monitor.app").mkdir(parents=True)                # ältere Version liegt schon da
    weg = []
    monkeypatch.setattr(vs, "_papierkorb", lambda p: (weg.append(p.name), __import__("shutil").rmtree(p)))
    aufrufe = []
    neu = vs.verschieben(quelle, ziel_ordner, run=lambda cmd, **k: aufrufe.append(cmd))
    assert neu == ziel_ordner / "Job-Monitor.app" and (neu / "Contents").is_dir() and not quelle.exists()
    assert weg == ["Job-Monitor.app"] and aufrufe[0][:3] == ["xattr", "-dr", "com.apple.quarantine"]


def test_zielordner_ohne_rechte_eigener_programme_ordner(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    gesperrt = tmp_path / "gesperrt"
    gesperrt.mkdir()
    gesperrt.chmod(0o555)
    try:
        assert vs.zielordner(gesperrt) == tmp_path / "Applications"
    finally:
        gesperrt.chmod(0o755)
    assert vs.zielordner(tmp_path) == tmp_path


def test_hinweis_nur_wenn_aus_downloads(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(selbstupdate, "programm",
                        lambda *a, **k: Path("/private/var/folders/x/AppTranslocation/A/d/Job-Monitor.app"))
    assert 'action="/verschieben"' in vs.karte("t")
    monkeypatch.setattr(selbstupdate, "programm", lambda *a, **k: Path("/Applications/Job-Monitor.app"))
    assert vs.karte("t") == ""


def test_original_bei_normalem_ort():
    if sys.platform != "darwin":
        return
    assert vs.original(Path("/System/Applications/Calculator.app")) == Path("/System/Applications/Calculator.app")
