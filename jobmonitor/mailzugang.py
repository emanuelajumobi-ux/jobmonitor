"""Postfach verbinden (Einrichtungs-Assistent, Schritt „Postfach“): Job-Alerts lesen und Antworten von Firmen
erkennen – für jeden Anbieter mit IMAP, nicht nur iCloud.

Gespeichert: Anbieter, Server und Benutzername lokal in .gui_mail.json, das App-Passwort im Schlüsselbund (macOS)
bzw. in der Anmeldeinformationsverwaltung (Windows, Paket keyring) – nie in einer Datei. Lokale Läufe
(__main__) setzen daraus IMAP_HOST, IMAP_USER und IMAP_PASSWORD, wenn sie nicht schon gesetzt sind (GitHub-Secrets
oder .env haben Vorrang). Die App liest nur, sie verschickt nie Mails.
Outlook.com und Microsoft 365 erlauben die Anmeldung mit Passwort per IMAP nicht mehr (nur OAuth) – nicht unterstützt.
"""
from __future__ import annotations

import imaplib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DATEI = ".gui_mail.json"
DIENST = "job-monitor-imap"
# Schlüssel → (Name, IMAP-Server, Anleitung für das App-Passwort)
ANBIETER = {
    "icloud": ("iCloud", "imap.mail.me.com", "https://support.apple.com/de-de/102654"),
    "gmail": ("Gmail", "imap.gmail.com", "https://support.google.com/accounts/answer/185833?hl=de"),
    "gmx": ("GMX", "imap.gmx.net", "https://hilfe.gmx.net/pop-imap/einschalten.html"),
    "webde": ("WEB.DE", "imap.web.de", "https://hilfe.web.de/pop-imap/einschalten.html"),
    "tonline": ("T-Online", "secureimap.t-online.de", "https://www.telekom.de/hilfe/e-mail-passwort"),
    "yahoo": ("Yahoo", "imap.mail.yahoo.com", "https://de.hilfe.yahoo.com/kb/SLN15241.html"),
    "posteo": ("Posteo", "posteo.de", "https://posteo.de/hilfe"),
    "anderer": ("Anderer Anbieter", "", ""),
}
# Direkt zur Seite, auf der man das App-Passwort anlegt, und was vorher eingeschaltet sein muss
DIREKT = {
    "gmail": ("https://myaccount.google.com/apppasswords",
              "Google zeigt die Seite nur, wenn die <b>Bestätigung in zwei Schritten</b> (2FA) eingeschaltet ist.",
              "https://myaccount.google.com/signinoptions/twosv"),
    "icloud": ("https://account.apple.com/account/manage",
               "Apple verlangt die <b>Zwei-Faktor-Authentifizierung</b> für deinen Account (meist schon an). Dort unter "
               "„Anmeldung und Sicherheit“ → „App-spezifische Passwörter“.", ""),
    "yahoo": ("https://login.yahoo.com/account/security",
              "Yahoo verlangt die <b>Bestätigung in zwei Schritten</b>. Dort unter „App-Passwort generieren“.",
              "https://login.yahoo.com/account/security"),
    "gmx": ("https://hilfe.gmx.net/pop-imap/einschalten.html",
            "Bei GMX muss <b>IMAP eingeschaltet</b> sein (E-Mail → Einstellungen → POP3/IMAP Abruf). Hast du die "
            "Zwei-Faktor-Authentifizierung an, brauchst du zusätzlich ein App-Passwort.", ""),
    "webde": ("https://hilfe.web.de/pop-imap/einschalten.html",
              "Bei WEB.DE muss <b>IMAP eingeschaltet</b> sein (E-Mail → Einstellungen → POP3/IMAP Abruf). Hast du die "
              "Zwei-Faktor-Authentifizierung an, brauchst du zusätzlich ein App-Passwort.", ""),
}


def _direkt_html(esc) -> str:
    """Pro Anbieter ein Kasten: Voraussetzung (z. B. 2FA bei Gmail) und ein Knopf direkt zur Einrichtung."""
    teile = []
    for k, (url, vorher, zwei) in DIREKT.items():
        # 2FA einschalten als eigener Knopf (Schritt 1) – als Textlink war er im Hinweis kaum zu erkennen
        zwei_html = (f'<a class="btn ghost small" href="{esc(zwei)}" target="_blank" rel="noopener">1. Bestätigung '
                     f'in zwei Schritten einschalten ↗</a> ' if zwei and zwei != url else "")
        teile.append(f'<div class="card info mail-direkt" data-mail="{k}" hidden><p style="margin:0 0 8px">'
                     f'<b>Vorher:</b> {vorher}</p><div class="row" style="gap:8px;flex-wrap:wrap;align-items:center">'
                     f'{zwei_html}<a class="btn small" href="{esc(url)}" target="_blank" '
                     f'rel="noopener">{"2. " if zwei_html else ""}{"App-Passwort jetzt anlegen" if k in ("gmail", "icloud", "yahoo") else "So schaltest du IMAP ein"} ↗'
                     f'</a><span class="muted">öffnet die Seite des Anbieters, danach das Passwort hier einfügen</span>'
                     f'</div></div>')
    return "".join(teile) + ('<script>(() => { const s = document.getElementById("anbieter"); if (!s) return;'
                             ' const zeigen = () => document.querySelectorAll(".mail-direkt").forEach(d =>'
                             ' d.hidden = d.dataset.mail !== s.value); s.addEventListener("change", zeigen); zeigen();'
                             ' })();</script>')


# Versand des täglichen Berichts an dich selbst (gleiches App-Passwort, Port 587 mit STARTTLS)
SMTP = {"icloud": "smtp.mail.me.com", "gmail": "smtp.gmail.com", "gmx": "mail.gmx.net", "webde": "smtp.web.de",
        "tonline": "securesmtp.t-online.de", "yahoo": "smtp.mail.yahoo.com", "posteo": "posteo.de"}
NICHT_UNTERSTUETZT = re.compile(r"@(outlook|hotmail|live|msn)\.", re.I)
HOST = re.compile(r"^[a-z0-9.-]{3,80}$", re.I)


class MailError(Exception):
    pass


def laden(root: Path) -> dict:
    try:
        data = json.loads((root / DATEI).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# --- Passwort im Systemspeicher ---
def _keyring():
    try:
        import keyring
        return keyring
    except ImportError:
        return None


def passwort(benutzer: str, run=subprocess.run) -> str | None:
    if sys.platform == "darwin":
        try:
            proc = run(["security", "find-generic-password", "-s", DIENST, "-a", benutzer, "-w"],
                       capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return (proc.stdout.strip() or None) if proc.returncode == 0 else None
    tresor = _keyring()
    try:
        return tresor.get_password(DIENST, benutzer) if tresor else None
    except Exception:
        return None


def _passwort_speichern(benutzer: str, wert: str, run=subprocess.run) -> None:
    if sys.platform == "darwin":
        proc = run(["security", "add-generic-password", "-U", "-s", DIENST, "-a", benutzer, "-w", wert],
                   capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            raise MailError("Passwort nicht im Schlüsselbund gespeichert.")
        return
    tresor = _keyring()
    if tresor is None:
        raise MailError("Kein Schlüsselspeicher auf diesem System – IMAP_PASSWORD bitte in die Datei .env.")
    tresor.set_password(DIENST, benutzer, wert)


# --- Verbinden ---
def pruefen(host: str, benutzer: str, wert: str, imap=imaplib.IMAP4_SSL) -> None:
    """Anmelden und Posteingang öffnen; nur lesend."""
    try:
        verbindung = imap(host, 993, timeout=20)
    except (OSError, imaplib.IMAP4.error) as exc:
        raise MailError(f"Server {host} nicht erreichbar ({exc.__class__.__name__}).") from None
    try:
        verbindung.login(benutzer, wert)
        status, _ = verbindung.select("INBOX", readonly=True)
        if status != "OK":
            raise MailError("Posteingang nicht lesbar.")
    except imaplib.IMAP4.error:
        raise MailError("Anmeldung abgelehnt – App-Passwort prüfen (nicht das normale Passwort) und ob IMAP beim "
                        "Anbieter eingeschaltet ist.") from None
    finally:
        try:
            verbindung.logout()
        except Exception:
            pass


def verbinden(root: Path, anbieter: str, benutzer: str, wert: str, host: str = "", imap=imaplib.IMAP4_SSL,
              run=subprocess.run) -> str:
    benutzer, wert = (benutzer or "").strip(), (wert or "").strip()
    if anbieter not in ANBIETER:
        raise MailError("Bitte einen Anbieter wählen.")
    if NICHT_UNTERSTUETZT.search(benutzer):
        raise MailError("Outlook, Hotmail und Microsoft 365 lassen keine Anmeldung per Passwort mehr zu – "
                        "bitte eine Weiterleitung der Job-Alerts an ein anderes Postfach einrichten.")
    if not benutzer or "@" not in benutzer or not wert:
        raise MailError("Bitte E-Mail-Adresse und App-Passwort angeben.")
    host = (ANBIETER[anbieter][1] or host or "").strip()
    if not HOST.match(host):
        raise MailError("Bitte den IMAP-Server angeben (steht in der Hilfe deines Anbieters, z. B. imap.example.de).")
    pruefen(host, benutzer, wert, imap)
    _passwort_speichern(benutzer, wert, run)
    (root / DATEI).write_text(json.dumps({"anbieter": anbieter, "host": host, "benutzer": benutzer}),
                              encoding="utf-8")
    return f"Postfach {benutzer} verbunden ({ANBIETER[anbieter][0]}). Gelesen wird nur, verschickt wird nichts."


def trennen(root: Path, run=subprocess.run) -> None:
    data = laden(root)
    if data.get("benutzer") and sys.platform == "darwin":
        run(["security", "delete-generic-password", "-s", DIENST, "-a", data["benutzer"]], capture_output=True)
    (root / DATEI).unlink(missing_ok=True)


def smtp_host(data: dict) -> str:
    """SMTP-Server zum verbundenen Postfach: bekannter Anbieter, sonst imap.… → smtp.…"""
    if data.get("anbieter") in SMTP:
        return SMTP[data["anbieter"]]
    host = str(data.get("host") or "")
    return "smtp." + host[5:] if host.startswith("imap.") else host


def bericht_schalten(root: Path, an: bool) -> str:
    data = laden(root)
    if not data.get("benutzer"):
        raise MailError("Erst ein Postfach verbinden.")
    data["bericht"] = bool(an)
    (root / DATEI).write_text(json.dumps(data), encoding="utf-8")
    return (f"Der tägliche Bericht geht ab dem nächsten Lauf an {data['benutzer']} (nur an dich, nie an Firmen)."
            if an else "Kein Bericht per Mail mehr; er steht weiter in der App unter „Letzter Bericht“.")


def umgebung_setzen(root: Path, run=subprocess.run) -> bool:
    """Für lokale Läufe: IMAP-Zugang (und mit „Bericht per Mail“ den Versand an dich selbst) aus .gui_mail.json und
    Schlüsselbund, falls nicht schon gesetzt (GitHub-Secrets und .env haben Vorrang)."""
    if os.environ.get("IMAP_USER"):
        return False
    data = laden(root)
    wert = passwort(data["benutzer"], run) if data.get("benutzer") else None
    if not wert:
        return False
    os.environ.update({"IMAP_HOST": data["host"], "IMAP_USER": data["benutzer"], "IMAP_PASSWORD": wert})
    if data.get("bericht") and not os.environ.get("SMTP_USER") and smtp_host(data):
        os.environ.update({"SMTP_HOST": smtp_host(data), "SMTP_PORT": "587", "SMTP_USER": data["benutzer"],
                           "SMTP_PASSWORD": wert, "MAIL_FROM": data["benutzer"], "MAIL_TO": data["benutzer"],
                           "JOBMONITOR_BERICHT_MAIL": "1"})
    return True


def formular(root: Path, token: str, esc, ziel: str = "/einrichten") -> str:
    """Formular „Postfach verbinden“ (Assistent und Einstellungen)."""
    data = laden(root)
    if data.get("benutzer"):
        bericht = bool(data.get("bericht"))
        return (f'<p class="ok">Verbunden: {esc(data["benutzer"])} ({esc(ANBIETER.get(data.get("anbieter"), ("",))[0])})'
                f'</p><p>{"Der tägliche Bericht kommt per Mail an dich." if bericht else "Den täglichen Bericht kannst du dir auch per Mail schicken lassen (nur an dich)."}</p>'
                f'<form method="post" action="{ziel}" class="row" style="gap:8px"><input type="hidden" name="token" '
                f'value="{token}"><button name="aktion" value="{"mail_bericht_aus" if bericht else "mail_bericht_an"}" '
                f'class="{"ghost " if bericht else ""}small">{"Bericht nicht mehr mailen" if bericht else "Bericht täglich mailen"}'
                f'</button><button name="aktion" value="mail_trennen" class="ghost small">Trennen</button></form>')
    wahl = "".join(f'<option value="{k}">{esc(n)}</option>' for k, (n, _, _) in ANBIETER.items())
    hilfe = "".join(f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(n)}</a> · '
                    for k, (n, _, u) in ANBIETER.items() if u).rstrip(" · ")
    return (f'<p>Damit liest die App Job-Alerts (z. B. von StepStone oder LinkedIn) und erkennt Antworten von Firmen. '
            f'Nur lesen, nie senden. Du brauchst ein <b>App-Passwort</b> deines Anbieters, nicht dein normales '
            f'Passwort.</p><form method="post" action="{ziel}"><input type="hidden" name="token" value="{token}">'
            f'<input type="hidden" name="aktion" value="mail"><div class="grid2">'
            f'<div><label for="anbieter">Anbieter</label><select id="anbieter" name="anbieter">{wahl}</select></div>'
            f'<div class="mail-direkt-platz" style="grid-column:1/-1">{_direkt_html(esc)}</div>'
            f'<div><label for="host">IMAP-Server (nur bei „Anderer Anbieter“)</label><input id="host" name="host" '
            f'placeholder="imap.example.de"></div>'
            f'<div><label for="benutzer">E-Mail-Adresse</label><input id="benutzer" name="benutzer" type="email"></div>'
            f'<div><label for="passwort">App-Passwort</label><input id="passwort" name="passwort" type="password" '
            f'autocomplete="off"></div></div><div class="row" style="margin-top:10px"><button class="small">Verbinden '
            f'und testen</button></div></form><p class="muted">App-Passwort anlegen: {hilfe}. Outlook/Hotmail geht '
            f'nicht (Microsoft erlaubt keine Passwort-Anmeldung mehr). Das Passwort liegt im Schlüsselbund des '
            f'Rechners.</p>')
