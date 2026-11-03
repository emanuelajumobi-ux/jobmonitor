import subprocess

import pytest

from jobmonitor.gui_sync import sync

CSV = "firma,typ,status,datum,link,notizen\nA,Stelle,neu,2026-10-01,https://a,\nB,Stelle,neu,2026-10-02,https://b,\n"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repos(tmp_path, monkeypatch):
    for var, val in (("GIT_AUTHOR_NAME", "Test"), ("GIT_AUTHOR_EMAIL", "t@example.com"),
                     ("GIT_COMMITTER_NAME", "Test"), ("GIT_COMMITTER_EMAIL", "t@example.com")):
        monkeypatch.setenv(var, val)
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(remote), str(seed))
    (seed / "applications.csv").write_text(CSV, encoding="utf-8")
    (seed / "cv").mkdir()
    (seed / "cv" / "cv_master.yaml").write_text("profil: alt\n", encoding="utf-8")
    git(seed, "add", ".")
    git(seed, "commit", "-q", "-m", "start")
    git(seed, "push", "-q", "origin", "HEAD:main")
    mac, pipeline = tmp_path / "mac", tmp_path / "pipeline"
    git(tmp_path, "clone", "-q", str(remote), str(mac))
    git(tmp_path, "clone", "-q", str(remote), str(pipeline))
    return remote, mac, pipeline


def test_sync_merges_local_edits_with_pipeline_commits(repos):
    _, mac, pipeline = repos
    # Pipeline hängt eine neue Stelle an und lädt hoch
    (pipeline / "applications.csv").write_text(CSV + "C,Stelle,neu,2026-10-03,https://c,\n", encoding="utf-8")
    (pipeline / "reports").mkdir()
    (pipeline / "reports" / "r.md").write_text("Bericht", encoding="utf-8")
    git(pipeline, "add", ".")
    git(pipeline, "commit", "-q", "-m", "Lauf")
    git(pipeline, "push", "-q")
    # Auf dem Mac: Status geändert, Master-CV geändert, eine fremde Datei angelegt
    (mac / "applications.csv").write_text(CSV.replace("A,Stelle,neu", "A,Stelle,beworben"), encoding="utf-8")
    (mac / "cv" / "cv_master.yaml").write_text("profil: neu\n", encoding="utf-8")
    (mac / "notiz.txt").write_text("privat", encoding="utf-8")

    result = sync(mac)
    assert result.ok, result.log
    assert "Bewerbungen und Master-CV" in git(mac, "log", "-1", "--format=%s")
    text = (mac / "applications.csv").read_text(encoding="utf-8")
    assert "A,Stelle,beworben" in text and "https://c" in text and (mac / "reports" / "r.md").exists()
    assert "notiz.txt" not in git(mac, "ls-files")                       # fremde Dateien nie committen
    git(pipeline, "pull", "-q")
    assert "A,Stelle,beworben" in (pipeline / "applications.csv").read_text(encoding="utf-8")   # hochgeladen
    assert sync(mac).message == "Alles aktuell."


def test_conflict_keeps_local_commit(repos):
    _, mac, pipeline = repos
    (pipeline / "cv" / "cv_master.yaml").write_text("profil: pipeline\n", encoding="utf-8")
    git(pipeline, "commit", "-q", "-am", "x")
    git(pipeline, "push", "-q")
    (mac / "cv" / "cv_master.yaml").write_text("profil: mac\n", encoding="utf-8")
    result = sync(mac)
    assert not result.ok and "lokal gesichert" in result.message
    assert (mac / "cv" / "cv_master.yaml").read_text(encoding="utf-8") == "profil: mac\n"
    assert not (mac / ".git" / "rebase-merge").exists()                  # kein halber Rebase zurückgelassen


def test_without_git(tmp_path):
    assert sync(tmp_path).ok and "übersprungen" in sync(tmp_path).message
