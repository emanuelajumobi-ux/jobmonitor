"""KI in der Pipeline: Anmeldung per WIF (llm.py), Anforderungen erkennen (fit.mit_ki), Antworten einordnen
(antworten.ki_einordnen) und die Übernahme eines erkannten Termins in der App. Die Claude-API wird nie aufgerufen."""
import json
import os
import time
from collections import Counter
from types import SimpleNamespace

import pytest

from jobmonitor import antworten as aw
from jobmonitor import fit, llm, runner, tracking
from jobmonitor.config import load_config
from jobmonitor.gui import App
from jobmonitor.models import Job
from tests.test_bewerbung import root  # noqa: F401  (Fixture)

BEGRIFFE = {"Azure": ["microsoft azure"], "Terraform": [], "Python": [], "Englisch": ["english"]}


@pytest.fixture
def ohne_ki_env(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
                "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ANTHROPIC_IDENTITY_TOKEN_FILE"):
        monkeypatch.delenv(var, raising=False)


def test_anmeldung_wif(tmp_path, monkeypatch, ohne_ki_env):
    assert not llm.verfuegbar()
    monkeypatch.setenv("ANTHROPIC_FEDERATION_RULE_ID", "")                    # leere Repo-Variable: aus
    monkeypatch.setenv("ANTHROPIC_ORGANIZATION_ID", "org")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://gh/token?x=1")
    assert not llm.verfuegbar()
    monkeypatch.setenv("ANTHROPIC_FEDERATION_RULE_ID", "fdrl_1")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "req")
    monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN_FILE", str(tmp_path / "jwt"))
    assert llm.foederation() and llm.verfuegbar()
    abrufe = []

    def get(url, params, timeout, headers):
        abrufe.append((url, params, headers))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"value": f"jwt{len(abrufe)}"})
    llm._github_token_auffrischen(get)
    assert (tmp_path / "jwt").read_text() == "jwt1" and oct((tmp_path / "jwt").stat().st_mode)[-3:] == "600"
    assert abrufe[0] == ("https://gh/token?x=1", {"audience": "https://api.anthropic.com"},
                         {"Authorization": "Bearer req"})
    llm._github_token_auffrischen(get)                                         # frisch: nicht neu holen
    assert len(abrufe) == 1
    alt = time.time() - llm.TOKEN_ALTER - 5
    os.utime(tmp_path / "jwt", (alt, alt))
    llm._github_token_auffrischen(get)
    assert (tmp_path / "jwt").read_text() == "jwt2"


def test_haiku_ohne_fallback(monkeypatch):
    aufrufe = []

    class Messages:
        def create(self, **kw):
            aufrufe.append(kw)
            return SimpleNamespace(stop_reason="end_turn", usage=None,
                                   content=[SimpleNamespace(type="text", text="ok")])
    monkeypatch.setattr(llm, "_client", lambda key: SimpleNamespace(beta=SimpleNamespace(messages=Messages())))
    assert llm._ask("claude-haiku-5-5", "x") == "ok" and llm._ask("claude-opus-5-5", "x") == "ok"
    assert "fallbacks" not in aufrufe[0] and aufrufe[1]["fallbacks"] == "default"
    assert llm.json_aus('Hier:\n```json\n{"a": 1}\n```') == {"a": 1} and llm.json_aus("kein json") is None


def stelle(beschreibung="x" * 400):
    return Job(title="Werkstudent Cloud", company="A", url="https://a/1", source="T", description=beschreibung)


def test_ki_anforderungen():
    antwort = json.dumps({"anforderungen": [
        {"begriff": "azure", "bekannt": True, "pflicht": True},
        {"begriff": "Terraform", "bekannt": True, "pflicht": False},
        {"begriff": "Kubernetes", "bekannt": False, "pflicht": True},
        {"begriff": ""}, "Unsinn"]})
    prompts = []

    def ask(model, prompt, **kw):
        prompts.append(prompt + "\n" + kw["system"])
        return f"```json\n{antwort}\n```"
    bekannt, weitere, eck = fit.ki_anforderungen(stelle("Erfahrung mit Microsofts Cloud. " * 20), BEGRIFFE, "m", ask)
    assert bekannt == {"Azure": 1.0, "Terraform": 0.5} and weitere == ["Kubernetes"] and eck == {}
    assert "Microsofts Cloud" in prompts[0] and "- Azure (auch: microsoft azure)" in prompts[0]
    assert fit.ki_anforderungen(stelle(), BEGRIFFE, "m", lambda *a, **k: "keine Ahnung") is None


def test_mit_ki_ergaenzt_stichwortsuche():
    cfg = {"begriffe": BEGRIFFE, "optional_marker": ["von vorteil"], "min_anforderungen": 2,
           "ki": {"enabled": True, "max_stellen": 1}}
    cv = {"kenntnisse": [{"name": "Azure", "level": "sehr gut"}, {"name": "Python", "level": "gut"}]}
    a = stelle("Du arbeitest mit Python. Terraform ist Pflicht. " * 10)
    fit.rate_all([a], cv, cfg)
    assert set(a.fit_anforderungen) == {"Python", "Terraform"}
    antwort = json.dumps({"anforderungen": [{"begriff": "Azure", "pflicht": True},
                                            {"begriff": "Terraform", "pflicht": False},
                                            {"begriff": "Kubernetes", "pflicht": True}]})
    zu_kurz, zweite = stelle("kurz"), stelle()
    vorschlaege = fit.mit_ki([zu_kurz, a, zweite], cv, cfg, ask=lambda *x, **k: antwort)
    assert a.fit_anforderungen == {"Python": 1.0, "Terraform": 0.5, "Azure": 1.0}        # KI ergänzt und gewichtet
    assert a.fit_passt[:1] == ["Azure"] and "Terraform" in a.fit_fehlt
    assert vorschlaege == Counter({"Kubernetes": 1}) and not zweite.fit_anforderungen  # max_stellen: 1
    assert fit.mit_ki([a], cv, {**cfg, "ki": {"enabled": False}}, ask=lambda *x, **k: antwort) == Counter()


MAIL = {"datum": "2026-11-02", "betreff": "Ihre Bewerbung bei INFODAS", "text": "Wir möchten Sie gern am "
        "Donnerstag, 12.11., um 14 Uhr kennenlernen. Bitte bestätigen Sie den Termin."}


def test_antwort_einordnen():
    a = aw.Antwort("https://x/1", "INFODAS", "2026-11-02", "nachricht", "infodas.de")
    vorher = a.schluessel
    prompts = []

    def ask(model, prompt, **kw):
        prompts.append(prompt)
        return '{"art": "einladung", "termin": "2026-11-12T14:00"}'
    assert aw.ki_einordnen(a, MAIL, "m", ask)
    assert (a.art, a.termin, a.roh) == ("einladung", "2026-11-12T14:00", "nachricht")
    assert a.schluessel == vorher                                # gleicher Schlüssel: nächster Lauf erkennt sie wieder
    assert "MAILDATUM: 2026-11-02" in prompts[0] and "12.11., um 14 Uhr" in prompts[0]
    b = aw.Antwort("https://x/2", "B", "2026-11-02", "einladung", "b.de")
    assert aw.ki_einordnen(b, MAIL, "m", lambda *x, **k: '{"art": "einladung", "termin": "irgendwann"}')
    assert b.termin == "" and b.roh == ""
    assert not aw.ki_einordnen(b, MAIL, "m", lambda *x, **k: '{"art": "vielleicht"}')
    assert aw._ablage(b) == {"link": "https://x/2", "firma": "B", "datum": "2026-11-02", "art": "einladung",
                             "absender": "b.de"}


def test_runner_ordnet_nur_neue_ein(root, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    alt = aw.Antwort("https://x/1", "A", "2026-10-30", "nachricht", "a.de")
    aw.speichern(root, [alt])
    gesehen = {}

    def postfach(rows, doc, cfg, today, ausschluss, bekannt, einordnen):
        gesehen["bekannt"] = bekannt
        neu = [aw.Antwort(f"https://x/{i}", "B", "2026-11-02", "nachricht", "b.de") for i in range(3)]
        for a in neu:
            einordnen(a, MAIL)
        return [alt] + neu
    eingeordnet = []
    monkeypatch.setattr(aw, "postfach", postfach)
    monkeypatch.setattr(aw, "ki_einordnen", lambda a, mail, model: eingeordnet.append((a.link, model)))
    cfg = load_config(root / "config.yaml")
    cfg["antworten"]["ki_max_je_lauf"] = 2
    neu = runner.antworten_suchen([], {}, cfg, None, runner.Options(root=root))
    assert alt.schluessel in gesehen["bekannt"] and len(neu) == 3
    assert eingeordnet == [("https://x/0", "claude-haiku-5-5"), ("https://x/1", "claude-haiku-5-5")]   # Limit 2


def test_termin_aus_mail_in_der_app(root, monkeypatch):  # noqa: F811
    tracking.save(root / "applications.csv", [{"firma": "INFODAS", "typ": "Stelle", "status": "beworben",
                                                "datum": "2026-10-20", "link": "https://x/1", "notizen": "Werkstudent"}])
    a = aw.Antwort("https://x/1", "INFODAS", "2026-11-02", "einladung", "infodas.de", "2026-11-12T14:00", "nachricht")
    aw.speichern(root, [a])
    app = App(root, compile_pdf=False)
    html = app.bewerbungen().decode()
    assert "Termin laut Mail: 12.11.2026, 14:00 Uhr" in html
    html = app.antwort({"schluessel": a.schluessel, "aktion": "uebernehmen"}).decode()
    assert "Gesprächstermin 12.11. um 14:00 Uhr eingetragen" in html
    assert tracking.load(root / "applications.csv")[0]["termin"] == "2026-11-12T14:00"
    # Ohne Übernahme: Gespräch mit vorausgefülltem Termin
    tracking.save(root / "applications.csv", [{"firma": "INFODAS", "typ": "Stelle", "status": "Antwort",
                                                "datum": "2026-10-20", "link": "https://x/1", "notizen": "Werkstudent"}])
    html = app.bewerbungen().decode()
    assert 'value="2026-11-12T14:00"' in html and "Termin laut Mail – bitte bestätigen" in html


def test_abgelehnte_anmeldung_bricht_nichts_ab(monkeypatch):
    from anthropic.lib.credentials._workload import WorkloadIdentityError

    class Messages:
        def create(self, **kw):
            raise WorkloadIdentityError("Token exchange failed (HTTP 401) Ensure your federation rule …")
    monkeypatch.setattr(llm, "_client", lambda key: SimpleNamespace(beta=SimpleNamespace(messages=Messages())))
    assert llm._ask("claude-haiku-5-5", "x") is None
