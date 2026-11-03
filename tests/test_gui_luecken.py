import pytest

from jobmonitor import gui_luecken as gl
from jobmonitor.config import load_config


@pytest.fixture
def fit_cfg():
    return load_config()["fit"]


def details(*reqs):
    return [{"title": f"Job {i}", "company": "X", "url": f"https://x/{i}", "anforderungen": r}
            for i, r in enumerate(reqs)]


def test_most_valuable_gap_first(fit_cfg):
    jobs = details({"Azure": 1.0, "Terraform": 1.0, "Git": 1.0},
                   {"Azure": 1.0, "Terraform": 1.0, "Linux": 1.0},
                   {"Kubernetes": 0.5, "Git": 1.0, "Linux": 1.0})
    covered = {"Azure": 0.85, "Git": 0.85, "Linux": 0.6}
    base, rows = gl.analyse(jobs, covered, fit_cfg)
    assert rows[0]["term"] == "Terraform" and rows[0]["gefordert"] == 2 and rows[0]["stand"] is None
    assert rows[0]["gewinn"]["Grundkenntnisse"] > 0 and rows[0]["gewinn"]["gut"] > rows[0]["gewinn"]["Grundkenntnisse"]
    linux = next(r for r in rows if r["term"] == "Linux")
    assert "Grundkenntnisse" not in linux["gewinn"] and linux["gewinn"]["gut"] > 0     # schon Grundkenntnisse
    kube = next(r for r in rows if r["term"] == "Kubernetes")
    assert kube["gefordert"] == 0 and kube["optional"] == 1
    html = gl.render(base, rows, 3)
    assert "Terraform" in html and "fehlt" in html and "+1 optional" in html


def test_too_few_requirements_are_ignored(fit_cfg):
    base, rows = gl.analyse(details({"Azure": 1.0}), {}, fit_cfg)
    assert base is None and rows == []
    assert "zu wenige" in gl.render(base, rows, 0)
