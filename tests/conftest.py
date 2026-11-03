from pathlib import Path

import pytest

from jobmonitor.config import load_config
from jobmonitor.http import Fetcher

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str, mode: str = "r"):
    """Gespeicherte Seite oder API-Antwort. Im öffentlichen Repo fehlen gespeicherte Fremdseiten (Urheberrecht) –
    Tests, die sie brauchen, werden dort übersprungen."""
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"Testdatei {name} fehlt (im öffentlichen Repo nicht enthalten)")
    return path.read_bytes() if mode == "rb" else path.read_text(encoding="utf-8")


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def fetcher():
    return Fetcher("job-monitor-test", min_delay=0, timeout=5, retries=0, sleep=lambda s: None)


@pytest.fixture(autouse=True)
def ohne_echte_ki(monkeypatch):
    """Tests rufen nie die echte Claude-API auf: kein Schlüssel aus Umgebung oder Schlüsselbund, keine WIF-Variablen,
    und jeder Aufruf, der trotzdem durchrutscht, schlägt laut fehl. Tests, die KI brauchen, setzen ki.schluessel
    bzw. llm._ask selbst."""
    from jobmonitor import i18n, ki, llm
    monkeypatch.setattr(i18n, "systemsprache", lambda run=None: "de")   # erster Start in Tests immer deutsch
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
                "ACTIONS_ID_TOKEN_REQUEST_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(llm, "ANBIETER", "claude")              # gewählter KI-Anbieter gilt nur je Test
    monkeypatch.setattr(llm, "MODELLE", {})
    monkeypatch.delenv("KI_API_KEY", raising=False)
    monkeypatch.setattr(ki, "schluessel", lambda run=None: None)
    monkeypatch.setattr(ki, "herkunft", lambda run=None: "")

    def kein_client(api_key):
        raise AssertionError("Test hätte die echte Claude-API aufgerufen")
    monkeypatch.setattr(llm, "_client", kein_client)
