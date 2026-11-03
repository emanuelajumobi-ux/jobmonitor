"""Andere KI-Anbieter (OpenAI-kompatibel: OpenAI, Gemini, Mistral, Ollama) und die Claude-Anleitung."""
import json

import pytest

from jobmonitor import gui_ki, ki, ki_anbieter, llm
from jobmonitor.config import load_config
from jobmonitor.gui import App
from tests.test_bewerbung import root  # noqa: F401  (Fixture)


class Antwort:
    def __init__(self, status, daten):
        self.status_code, self._d, self.text = status, daten, json.dumps(daten)

    def json(self):
        return self._d


def test_modelle_und_vorschlag():
    get = lambda url, headers, timeout: Antwort(200, {"data": [  # noqa: E731
        {"id": "gpt-x-mini"}, {"id": "gpt-x"}, {"id": "text-embedding-3"}, {"id": "whisper-1"}, {"id": "gpt-x-pro"}]})
    ids = ki_anbieter.modelle("openai", "sk-test", get)
    assert ids == ["gpt-x", "gpt-x-mini", "gpt-x-pro"]                       # Embeddings & Audio aussortiert
    assert ki_anbieter.vorschlag(ids) == {"schnell": "gpt-x-mini", "gut": "gpt-x-pro"}
    with pytest.raises(ki_anbieter.AnbieterError, match="abgelehnt"):
        ki_anbieter.modelle("openai", "falsch", lambda url, headers, timeout: Antwort(401, {}))
    gemini = lambda url, headers, timeout: Antwort(200, {"data": [{"id": "models/gemini-x-flash"}]})  # noqa: E731
    assert ki_anbieter.modelle("gemini", "k", gemini) == ["gemini-x-flash"]


def test_fragen_kompatibel(monkeypatch):
    gesendet = []

    def post(url, json, headers, timeout):
        gesendet.append((url, json, headers))
        return Antwort(200, {"choices": [{"message": {"content": " Hallo "}, "finish_reason": "stop"}],
                             "usage": {"prompt_tokens": 12, "completion_tokens": 3}})
    usage = []
    assert ki_anbieter.fragen("mistral", "k", "m-small", "Frage", "System", 500, usage, post) == "Hallo"
    url, body, headers = gesendet[0]
    assert url == "https://api.mistral.ai/v1/chat/completions" and body["max_tokens"] == 500
    assert body["messages"][0] == {"role": "system", "content": "System"} and headers["Authorization"] == "Bearer k"
    assert usage == [(12, 3)]
    ki_anbieter.fragen("openai", "k", "x", "F", post=post)
    assert "max_completion_tokens" in gesendet[1][1]
    ki_anbieter.fragen("ollama", None, "llama", "F", post=post)
    assert gesendet[2][0].startswith("http://localhost:11434/v1") and gesendet[2][2] == {}


def test_llm_leitet_um(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(ki_anbieter, "fragen", lambda a, s, m, p, sys_, mt, u, post=None:
                        aufrufe.append((a, s, m)) or u.append((5, 1)) or "ok")
    llm.einstellen({"ki": {"anbieter": "gemini", "modelle": {"gemini": {"schnell": "g-flash", "gut": "g-pro"}}}})
    monkeypatch.setenv("KI_API_KEY", "key")
    assert llm.verfuegbar()
    assert llm._ask("claude-haiku-5-5", "x") == "ok" and llm._ask("claude-opus-5-5", "x", api_key="k2") == "ok"
    assert aufrufe == [("gemini", "key", "g-flash"), ("gemini", "k2", "g-pro")]
    llm.einstellen({"ki": {"anbieter": "gemini"}})
    assert not llm.verfuegbar() and llm._ask("claude-haiku-5-5", "x") is None       # ohne Modelle: nichts


def test_config_text():
    text = "run:\n  modus: aktiv\nki:\n  model: claude-opus-5-5\n  max_aufrufe_monat: 60\ncv:\n  x: 1\n"
    neu = gui_ki.config_text(text, "openai", {"schnell": "a-mini", "gut": "a"})
    cfg = load_config.__globals__["YAML"](typ="safe").load(neu)
    assert cfg["ki"]["anbieter"] == "openai" and cfg["ki"]["modelle"]["openai"] == {"schnell": "a-mini", "gut": "a"}
    assert cfg["ki"]["max_aufrufe_monat"] == 60 and cfg["cv"] == {"x": 1}
    zurueck = gui_ki.config_text(neu, "claude")                        # Wechsel zurück: Modelle bleiben gemerkt
    cfg = load_config.__globals__["YAML"](typ="safe").load(zurueck)
    assert cfg["ki"]["anbieter"] == "claude" and cfg["ki"]["modelle"]["openai"]["gut"] == "a"
    assert zurueck.count("anbieter:") == 1
    with pytest.raises(ki_anbieter.AnbieterError):
        gui_ki.config_text(text, "openai", {"schnell": "a b; rm", "gut": "x"})


def test_einstellungen_anbieter_wechseln(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr("jobmonitor.gui_wartung.pipeline_laeufe", lambda r: ([], ""))
    monkeypatch.setattr(ki_anbieter, "modelle", lambda a, s, get=None: ["m-large", "m-small"])
    app = App(root, compile_pdf=False)
    html = app.einstellungen().decode()
    assert 'name="anbieter"' in html and "Ollama (lokal, kostenlos)" in html and 'href="/ki-anleitung"' in html
    html = app.einstellungen_post({"aktion": "ki_anbieter", "anbieter": "ollama"}).decode()
    assert "Anbieter: Ollama" in html and load_config(root / "config.yaml")["ki"]["anbieter"] == "ollama"
    monkeypatch.setattr(ki, "schluessel", lambda run=None: "lokal")
    html = app.einstellungen_post({"aktion": "ki_modelle_laden"}).decode()
    assert "2 Modelle geladen" in html and "<option selected>m-small</option>" in html
    html = app.einstellungen_post({"aktion": "ki_modelle", "schnell": "m-small", "gut": "m-large"}).decode()
    assert "Modelle übernommen" in html
    assert load_config(root / "config.yaml")["ki"]["modelle"]["ollama"] == {"schnell": "m-small", "gut": "m-large"}


def test_claude_anleitung(root):  # noqa: F811
    html = App(root, compile_pdf=False).ki_anleitung().decode()
    for text in ("Kein Abo", "nicht zum", "bekommt nichts", "Auto-reload", "Create Key", "jederzeit aufhören"):
        assert text in html
