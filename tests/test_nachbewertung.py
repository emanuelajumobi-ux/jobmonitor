"""Einmalige Nachbewertung gespeicherter Stellen mit KI-Anforderungen (nachbewertung.py). Keine echte API."""
import base64
import json
import re

import responses

from jobmonitor import nachbewertung as nb
from jobmonitor.config import load_config
from jobmonitor.http import Fetcher
from jobmonitor.models import Job
from jobmonitor.state import State

TEXT = "Du betreust unsere Microsoft-Cloud. Erfahrung mit Terraform ist Pflicht. " * 8
CV = {"kenntnisse": [{"name": "Azure", "level": "sehr gut"}, {"name": "Terraform", "level": "gut"}]}


def gespeichert(state, title, url, reqs):
    job = Job(title=title, company="Firma", url=url, source="T")
    job.fit_anforderungen, job.fit = reqs, 0
    state.save_job_detail(job, "2026-10-20")
    return job.short_id


@responses.activate
def test_nachbewerten(tmp_path):
    cfg = load_config()
    posting = {"@context": "https://schema.org", "@type": "JobPosting", "title": "Werkstudent Cloud",
               "description": TEXT, "hiringOrganization": {"name": "Firma"}}
    responses.get("https://firma.de/robots.txt", body="")
    responses.get("https://firma.de/job/1", body=f'<script type="application/ld+json">{json.dumps(posting)}</script>')
    responses.get("https://firma.de/job/weg", status=404)
    b64 = base64.b64encode(b"10001-123-S").decode()
    responses.get(re.compile(rf".*/jobdetails/{re.escape(b64)}"), json={"stellenangebotsBeschreibung": TEXT})
    state = State(tmp_path / "s.sqlite")
    firma = gespeichert(state, "Werkstudent Cloud", "https://firma.de/job/1", {"Linux": 1.0})
    agentur = gespeichert(state, "Werkstudent IT", "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-123-S", {})
    weg = gespeichert(state, "Werkstudent Alt", "https://firma.de/job/weg", {"Azure": 1.0})
    linkedin = gespeichert(state, "Werkstudent LI", "https://www.linkedin.com/jobs/view/1", {})
    aufrufe = []

    def ask(model, prompt, **kw):
        aufrufe.append(prompt)
        return json.dumps({"anforderungen": [{"begriff": "Azure", "pflicht": True},
                                             {"begriff": "Terraform", "pflicht": True},
                                             {"begriff": "Bicep", "pflicht": False}]})
    out = nb.nachbewerten(state, CV, cfg, Fetcher("test", 0, 5, 0), ask)
    assert (out["geprueft"], out["aktualisiert"], out["ohne_text"]) == (4, 2, 2)
    assert out["vorschlaege"] == {"Bicep": 2}
    details = {d["id"]: d for d in state.job_details()}
    assert details[firma]["anforderungen"] == {"Linux": 1.0, "Azure": 1.0, "Terraform": 1.0}
    assert details[firma]["fit"] == 62                    # (Azure 1,0 + Terraform „gut“ 0,85) von 3 Anforderungen
    assert details[agentur]["anforderungen"] == {"Terraform": 1.0, "Azure": 1.0}
    assert details[agentur]["fit"] is None                                 # unter min_anforderungen (3)
    assert details[weg]["anforderungen"] == {"Azure": 1.0}                 # Anzeige weg: bleibt wie sie war
    assert not any("linkedin" in c.request.url for c in responses.calls)   # nie LinkedIn & Co.
    assert "Microsoft-Cloud" in aufrufe[0]
    # Zweiter Aufruf: alles erledigt, keine neuen Abrufe und keine KI
    vorher = len(responses.calls)
    out = nb.nachbewerten(state, CV, cfg, Fetcher("test", 0, 5, 0), ask)
    assert out["geprueft"] == 0 and len(responses.calls) == vorher and len(aufrufe) == 2
    assert linkedin in nb.erledigt(state)


@responses.activate
def test_ki_weg_wird_spaeter_nachgeholt(tmp_path):
    cfg = load_config()
    b64 = base64.b64encode(b"1-2-S").decode()
    responses.get(re.compile(rf".*/jobdetails/{re.escape(b64)}"), json={"stellenangebotsBeschreibung": TEXT})
    state = State(tmp_path / "s.sqlite")
    sid = gespeichert(state, "Werkstudent IT", "https://www.arbeitsagentur.de/jobsuche/jobdetail/1-2-S", {})
    out = nb.nachbewerten(state, CV, cfg, Fetcher("test", 0, 5, 0), lambda *a, **k: None)
    assert out["aktualisiert"] == 0 and sid not in nb.erledigt(state)       # beim nächsten Mal erneut
