"""Rückmeldungen nach 1.3.7: KI im Assistenten, klare KI-Fehler, Update-Ladebild, Gmail-Hinweis."""
import html

from jobmonitor import erststart, ki, ki_anbieter, mailzugang, updates
from jobmonitor.gui import App


class Antwort:
    def __init__(self, status, daten=None, text=""):
        self.status_code, self._daten, self.text = status, daten or {}, text

    def json(self):
        return self._daten


def test_gruende_statt_hat_nicht_geantwortet():
    for status, wort in (("netz", "Internetverbindung"), (429, "Kontingent"), (403, "lehnt den Schlüssel ab"),
                         (404, "Modelle vom Anbieter laden"), (503, "überlastet"), ("keine_modelle", "keine Modelle")):
        ki_anbieter.LETZTER_FEHLER.clear()
        ki_anbieter.LETZTER_FEHLER["status"] = status
        assert wort in ki_anbieter.grund("gemini")
    ki_anbieter.LETZTER_FEHLER.clear()
    assert ki_anbieter.grund("gemini") == ""


def test_gemini_429_wird_einmal_wiederholt():
    antworten = [Antwort(429), Antwort(200, {"choices": [{"message": {"content": "ok"}}]})]
    pausen = []
    text = ki_anbieter.fragen("gemini", "k", "gemini-2.5-flash", "hi", post=lambda *a, **k: antworten.pop(0),
                              warten=pausen.append)
    assert text == "ok" and pausen == [15]


def test_ki_im_assistenten_eintragen_und_austragen(tmp_path, monkeypatch):
    erststart.vorbereiten(tmp_path)
    app = App(tmp_path, compile_pdf=False)
    gespeichert = {}
    monkeypatch.setattr(ki, "schluessel_speichern", lambda s: gespeichert.update(s=s))
    monkeypatch.setattr(ki, "schluessel", lambda: gespeichert.get("s"))
    monkeypatch.setattr(ki, "schluessel_loeschen", lambda: gespeichert.clear())
    monkeypatch.setattr(ki, "herkunft", lambda *a, **k: "schluesselbund" if gespeichert else "")
    monkeypatch.setattr(ki_anbieter, "modelle", lambda *a, **k: ["gemini-2.5-flash", "gemini-2.5-flash-lite"])
    monkeypatch.setattr(ki_anbieter, "gemini_pruefen", lambda *a, **k: {})
    app.einrichten({"aktion": "ki_anbieter", "anbieter": "gemini"})
    seite = app.einrichten({"aktion": "ki_schluessel", "schluessel": "AIza-test"}).decode()
    assert "startklar" in seite and gespeichert["s"] == "AIza-test"
    assert "Schlüssel entfernen" in seite and 'action="/einrichten"' in seite      # austragen ohne Seitenwechsel
    seite = app.einrichten({"aktion": "ki_entfernen"}).decode()
    assert "entfernt" in seite and not gespeichert
    assert '<a class="einrichtung active" href="/einrichten">' in seite                # Reiter ganz oben, hervorgehoben
    assert 'class="einrichtung-kopf"' in seite and 'role="progressbar"' in seite        # Seite sieht anders aus


def test_reiter_verschwindet_nach_der_einrichtung(tmp_path):
    erststart.vorbereiten(tmp_path)
    app = App(tmp_path, compile_pdf=False)
    assert 'class="einrichtung"' in app.einstellungen().decode()
    (tmp_path / "cv" / "cv_master.yaml").write_text("x: 1\n", encoding="utf-8")   # alter Stand = eingerichtet
    seite = app.einstellungen().decode()
    assert 'class="einrichtung' not in seite and "Einrichtungs-Assistent öffnen" in seite


def test_update_hat_eigenes_ladebild():
    h = updates.hinweis({"version": "9.9", "url": ""}, "t", True)
    assert "data-laden=" in h and "data-ki" not in h


def test_gmail_hinweis_2fa_und_direktlink(tmp_path):
    h = mailzugang.formular(tmp_path, "t", html.escape)
    assert "myaccount.google.com/apppasswords" in h
    assert 'class="btn ghost small" href="https://myaccount.google.com/signinoptions/twosv"' in h   # als Knopf
