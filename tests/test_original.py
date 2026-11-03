"""Originalanzeige zu Stellen aus Job-Alert-Mails (original.py, runner.originale_suchen)."""
from jobmonitor import original
from jobmonitor.config import load_config
from jobmonitor.models import Job, SourceResult
from jobmonitor.runner import originale_suchen
from jobmonitor.sources.mail_alerts import NAME as ALERT
from jobmonitor import suchprofil


def alert(title, company, location="Köln"):
    return Job(title=title, company=company, url="https://www.linkedin.com/jobs/view/1", source=ALERT,
               location=location, description=f"{title} | {company} | {location}",
               flags=["Ort nicht erkannt – Suchort des Alerts angenommen"])


def test_matching():
    assert original.gleiche_firma("adesso SE", "adesso")
    assert original.gleiche_firma("Deutsche Post und DHL", "Deutsche Post und DHL Group")
    assert not original.gleiche_firma("EY", "CGI Deutschland")
    assert original.gleiche_firma("Deutsche Post und DHL", "DHL AG Zentrale")
    assert original.gleiche_firma("EY", "EY Consulting GmbH") and original.gleiche_firma("NRW.BANK", "NRW.BANK AdöR")
    assert not original.gleiche_firma("Deutsche Bank", "Deutsche Telekom")
    assert not original.gleiche_firma("IT Consulting Köln GmbH", "Bechtle IT Consulting")
    assert original.titel_aehnlich("Werkstudent Cloud Security (m/w/d)", "Werkstudent*in Cloud Security (w/m/d)") == 1
    assert original.titel_aehnlich("Werkstudent Cloud", "Werkstudent Vertrieb") < original.TITEL_AEHNLICH
    assert original.titel_aehnlich("Consultant Cyber Security (m/w/d) in Köln",
                                   "Cyber Security Engineer (m/w/d)") < original.TITEL_AEHNLICH
    assert original.titel_aehnlich("Werkstudent Cloud Security in Köln", "Werkstudent Cloud Security") >= 0.6
    assert original._suchtitel("Werkstudent IT-Security (m/w/d) – Köln") == "Werkstudent IT-Security"
    assert original._suchtitel("Testmanager/-in (m/w/d) bei der Sparkasse KölnBonn") == "Testmanager/-in"


class FakeBA:
    cfg = {"wo": "Köln", "umkreis_km": 50}

    def __init__(self, items):
        self.items, self.calls = items, []

    def _search(self, params):
        self.calls.append(params)
        return {"ergebnisliste": self.items}


def test_from_run_then_ba_then_none():
    firmenseite = Job(title="Werkstudent Cloud Security (w/m/d)", company="adesso SE",
                      url="https://jobs.adesso-group.com/job/1", source="Firmen-Karriereseiten",
                      description="Azure, Terraform, Kubernetes " * 20)
    ba = FakeBA([{"titel": "Werkstudent IT-Security (m/w/d)", "arbeitgeber": "Sparkasse KölnBonn",
                  "referenznummer": "123-456", "stellenlokationen": [{"adresse": {"ort": "Köln"}}]}])
    alerts = [alert("Werkstudent Cloud Security (m/w/d)", "adesso"),
              alert("Werkstudent IT-Security", "Sparkasse KölnBonn"),
              alert("Werkstudent Marketing", "Unbekannt AG"),
              alert("Werkstudent Cloud", "(über LinkedIn)")]
    out, n = original.ergaenzen(alerts, [firmenseite], ba, {"max_ba_anfragen": 5})
    assert n == 2
    assert out[0].url == firmenseite.url and "Terraform" in out[0].description
    assert out[0].source == f"Firmen-Karriereseiten + {ALERT}"
    assert any("Originalanzeige gefunden" in f for f in out[0].flags)
    assert not any(f.startswith("Ort nicht erkannt") for f in out[0].flags)
    assert out[1].external_id == "123-456" and out[1].source.startswith("Bundesagentur für Arbeit")
    assert out[2] is alerts[2] and out[3] is alerts[3]
    assert len(ba.calls) == 2   # erster Fund kam ohne Anfrage, „(über LinkedIn)“ wird nicht gesucht
    assert ba.calls[0]["was"] == "Werkstudent IT-Security"


def test_ba_limit_and_disabled():
    ba = FakeBA([])
    alerts = [alert(f"Werkstudent Cloud {i}", f"Firma {i}") for i in range(4)]
    assert original.ergaenzen(alerts, [], ba, {"max_ba_anfragen": 2})[1] == 0 and len(ba.calls) == 2
    assert original.ergaenzen(alerts, [], ba, {"enabled": False}) == (alerts, 0)


def test_runner_reevaluates_and_notes():
    cfg = load_config()
    profile = suchprofil.aktive(cfg)
    firmenseite = Job(title="Werkstudent Cloud Security (w/m/d)", company="adesso SE",
                      url="https://jobs.adesso-group.com/job/1", source="Firmen-Karriereseiten", location="Köln",
                      description="Azure Cloud Security Terraform")
    a = alert("Werkstudent Cloud Security (m/w/d)", "adesso")
    results = [SourceResult("Firmen-Karriereseiten", jobs=[firmenseite]), SourceResult(ALERT, jobs=[a])]
    from jobmonitor.scoring import evaluate_profiles
    evaluated = [m for r in results for j in r.jobs if (m := evaluate_profiles(j, cfg, profile))]
    src_cfg = {**cfg["sources"], "bundesagentur": {**cfg["sources"]["bundesagentur"], "enabled": False}}
    out = originale_suchen(evaluated, results, [], src_cfg, None, cfg, profile)
    assert {j.url for j in out} == {firmenseite.url}
    assert "Originalanzeige zu 1 von 1" in results[1].notes[-1]
