"""Einstellungen → KI: Anbieter wählen (Claude empfohlen, OpenAI, Gemini, Mistral, Ollama), Schlüssel hinterlegen,
Modelle vom Anbieter laden und übernehmen – dazu die Seite /ki-anleitung, die Schritt für Schritt durch die Einrichtung
von Claude führt und erklärt, warum man dabei die Kontrolle behält.

Gespeichert: Anbieter und Modelle in config.yaml → ki (anbieter, modelle.<anbieter>.schnell/gut), der Schlüssel im
Schlüsselbund bzw. in der Windows-Anmeldeinformationsverwaltung (ki.py).
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path

from .ki_anbieter import ANBIETER, AnbieterError, aus_config, gueltig, vorschlag

MODELL = re.compile(r"^[\w.:/@+-]{1,120}$")


def esc(v) -> str:
    return escape(str(v if v is not None else ""))


def _zahl(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def config_text(text: str, anbieter: str, modelle: dict[str, str] | None = None) -> str:
    """config.yaml mit ki.anbieter (und ki.modelle.<anbieter>), der Rest bleibt unverändert."""
    anbieter = gueltig(anbieter)
    m = re.search(r"^ki:[^\n]*\n", text, re.M)
    if not m:
        text = text.rstrip("\n") + "\n\nki:\n"
        m = re.search(r"^ki:[^\n]*\n", text, re.M)
    ende_m = re.compile(r"^[^\s#\n]", re.M).search(text, m.end())
    ende = ende_m.start() if ende_m else len(text)
    block = text[m.end():ende]
    block = re.sub(r"^  anbieter:[^\n]*\n", "", block, flags=re.M)
    alte = {}
    mm = re.search(r"^  modelle:[^\n]*\n((?:    [^\n]*\n)*)", block, re.M)
    if mm:
        aktuell = None
        for zeile in mm.group(1).splitlines():
            if zeile.startswith("    ") and not zeile.startswith("      ") and zeile.strip().endswith(":"):
                aktuell = zeile.strip()[:-1]
                alte[aktuell] = {}
            elif aktuell and ":" in zeile:
                k, v = zeile.strip().split(":", 1)
                alte[aktuell][k.strip()] = v.strip().strip('"')
        block = block[:mm.start()] + block[mm.end():]
    if modelle is not None:
        for wert in modelle.values():
            if not MODELL.match(wert):
                raise AnbieterError("Ungültiger Modellname.")
        alte[anbieter] = dict(modelle)
    neu = f"  anbieter: {anbieter}            # claude | openai | gemini | mistral | ollama (Einstellungen → KI)\n"
    if alte:
        neu += "  modelle:                    # je Anbieter: schnell = tägliche Suche, gut = Anschreiben & Co.\n"
        for a, werte in alte.items():
            neu += f"    {a}:\n" + "".join(f'      {k}: "{v}"\n' for k, v in werte.items())
    return text[:m.end()] + neu + block + text[ende:]


def speichern(root: Path, anbieter: str, modelle: dict[str, str] | None = None) -> None:
    from .gui_wartung import speichern as datei_speichern
    path = root / "config.yaml"
    datei_speichern(root, "config.yaml", config_text(path.read_text(encoding="utf-8"), anbieter, modelle))


def wahl_html() -> str:
    """Zwei Wege zur KI nebeneinander – in Einstellungen → KI und im Einrichtungs-Assistenten."""
    return ('<div class="ki-wahl"><div class="ki-weg empfohlen"><b>Claude</b> <span class="chip">empfohlen</span>'
            '<p class="muted">Die besten Ergebnisse – die App ist darauf abgestimmt. Bezahlt wird nach Verbrauch aus '
            'vorher gekauftem Guthaben, kein Abo; ein kleiner Betrag reicht lange.</p>'
            '<a class="btn small" href="/ki-anleitung">Anleitung für Claude</a></div>'
            '<div class="ki-weg"><b>Google Gemini</b> <span class="chip einladung">kostenlos</span>'
            '<p class="muted">Ohne Kreditkarte, mit Tagesgrenzen. Gut zum Ausprobieren – die Ergebnisse sind etwas '
            'schwächer als mit Claude.</p><a class="btn ghost small" href="/ki-anleitung?anbieter=gemini">Anleitung '
            'für Gemini</a></div></div>')


WAHL_CSS = """
.ki-wahl { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px; margin:12px 0; }
.ki-weg { border:1px solid var(--line); border-radius:12px; padding:14px; display:flex; flex-direction:column; gap:6px;
  align-items:flex-start; }
.ki-weg.empfohlen { border-color:var(--accent); }
.ki-weg p { margin:0 0 4px; }
"""


def karte(token: str, cfg: dict, herkunft: str, nutzung: dict, limit: int, pipeline: str = "",
          liste: list[str] | None = None) -> str:
    anbieter, modelle = aus_config(cfg)
    a = ANBIETER[anbieter]
    form = lambda aktion, inhalt, extra="": (  # noqa: E731
        f'<form method="post" action="/einstellungen" class="row" style="gap:8px;align-items:end{extra}">'
        f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="aktion" value="{aktion}">'
        f'{inhalt}</form>')
    wahl = "".join(f'<option value="{k}"{" selected" if k == anbieter else ""}>{esc(v["name"])}</option>'
                   for k, v in ANBIETER.items())
    kopf = form("ki_anbieter", f'<div><label for="ki_anbieter">Anbieter</label><select id="ki_anbieter" '
                               f'name="anbieter" style="width:auto">{wahl}</select></div>'
                               f'<button class="ghost small">Wechseln</button>')
    if a.get("ohne_schluessel"):
        schluessel = (f'<p class="ok">Kein Schlüssel nötig – Ollama läuft auf diesem Rechner. '
                      f'<a href="{a["schluessel_url"]}" target="_blank" rel="noopener">Ollama installieren</a></p>')
    elif herkunft == ".env":
        schluessel = '<p class="ok">Schlüssel aus der Datei .env aktiv.</p>'
    elif herkunft:
        schluessel = ('<p class="ok">Schlüssel sicher im Schlüsselspeicher deines Rechners hinterlegt.</p>'
                      + form("ki_entfernen", '<button class="ghost small" onclick="return confirm(\'Schlüssel aus dem '
                                             'Schlüsselspeicher löschen?\')">Schlüssel entfernen</button>'))
    else:
        platzhalter = "sk-ant-…" if anbieter == "claude" else "Schlüssel einfügen"
        schluessel = form("ki_schluessel", f'<div style="flex:1;min-width:240px"><label for="ki_key">API-Schlüssel '
                                           f'(<a href="{a["schluessel_url"]}" target="_blank" rel="noopener">hier '
                                           f'anlegen</a>)</label><input id="ki_key" type="password" name="schluessel" '
                                           f'autocomplete="off" spellcheck="false" placeholder="{platzhalter}" '
                                           f'required></div><button data-ki="Schlüssel und Modelle werden geprüft …">Sicher speichern</button>')
    if anbieter == "claude":
        modell_html = ""
    elif liste:
        v = {**vorschlag(liste, anbieter), **{k: w for k, w in modelle.items() if w in liste}}
        opts = lambda wahl_: "".join(f'<option{" selected" if m == wahl_ else ""}>{esc(m)}</option>'  # noqa: E731
                                     for m in liste)
        modell_html = form("ki_modelle", f'<div><label>Schnelles Modell (tägliche Suche)</label><select name="schnell" '
                                         f'style="width:auto">{opts(v["schnell"])}</select></div><div><label>Gutes '
                                         f'Modell (Anschreiben, Vorbereitung)</label><select name="gut" '
                                         f'style="width:auto">{opts(v["gut"])}</select></div><button>Übernehmen</button>',
                           ";flex-wrap:wrap;margin-top:10px")
    elif modelle.get("schnell"):
        modell_html = (f'<p class="muted" style="margin-top:8px">Modelle: schnell <code>{esc(modelle.get("schnell"))}'
                       f'</code> · gut <code>{esc(modelle.get("gut"))}</code></p>'
                       + form("ki_modelle_laden", '<button class="ghost small">Andere Modelle wählen</button>'))
    elif herkunft or a.get("ohne_schluessel"):
        modell_html = (f'<p class="muted" style="margin-top:8px">Noch keine Modelle gewählt.</p>'
                       + form("ki_modelle_laden", '<button class="small" data-ki="Modelle werden geprüft …">Modelle vom Anbieter '
                                               'laden</button>'))
    else:
        modell_html = ""
    anleitung = ('' if not herkunft else
                 '<p class="muted" style="margin-top:10px">Anleitungen: <a href="/ki-anleitung">Claude</a> · '
                 '<a href="/ki-anleitung?anbieter=gemini">Google Gemini (kostenlos)</a></p>')
    return f"""<div class="card" id="ki"><h2>KI</h2>
<p class="muted">Die KI nutzt <b>deinen eigenen</b> Zugang beim Anbieter; Kosten laufen über dein Konto dort, nach
Verbrauch. Gesendet werden Anzeigentexte und dein Master-CV ohne persönliche Angaben – direkt an den Anbieter, nie an
den Entwickler dieser App. Die KI verschickt nichts.</p>
{"" if herkunft else wahl_html()}
{kopf}<p class="muted">{esc(a["hinweis"])}</p>{schluessel}{modell_html}{anleitung}
<p class="muted" style="margin-top:8px">Diesen Monat aus der Oberfläche: {nutzung["aufrufe"]} von höchstens {limit}
Aufrufen · {_zahl(nutzung["eingabe"])} Eingabe- und {_zahl(nutzung["ausgabe"])} Ausgabe-Tokens.</p>{pipeline}</div>"""


ANLEITUNG = """<div class="page-head"><div><h1>Claude einrichten</h1><p class="sub">In etwa zehn Minuten – und du behältst
jederzeit die Kontrolle über Kosten und Daten.</p></div><div class="row"><a class="btn ghost small" href="/einstellungen#ki">
Zu Einstellungen → KI</a></div></div>
<div class="ki-anleitung">
<div class="card beruhigung"><h2>Bevor du anfängst: das Wichtigste in Kürze</h2><ul>
<li><b>Kein Abo, keine Überraschungen.</b> Bei Anthropic kaufst du vorher Guthaben; verbraucht wird nur davon.
Automatisches Nachladen gibt es nur, wenn du es selbst einschaltest (<a href="https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-api-usage"
target="_blank" rel="noopener">Anthropic-Hilfe</a>). Fang klein an – für Suche, Anschreiben und Vorbereitung reicht
ein kleiner Betrag lange.</li>
<li><b>Die App bremst zusätzlich:</b> Für Aufrufe aus der Oberfläche gibt es ein Monatslimit, und unter Einstellungen
siehst du jederzeit, wie viel verbraucht wurde.</li>
<li><b>Deine persönlichen Daten bleiben bei dir.</b> Name, Adresse, Telefon, E-Mail und Foto werden nie gesendet – nur
Anzeigentexte und der fachliche Teil deines Lebenslaufs. Laut Anthropic werden Daten aus der API standardmäßig nicht zum
Training der Modelle verwendet.</li>
<li><b>Der Entwickler dieser App bekommt nichts</b> – weder deinen Schlüssel noch deine Daten noch Geld. Alles läuft
direkt zwischen deinem Rechner und Anthropic.</li>
<li><b>Du kannst jederzeit aufhören:</b> Schlüssel in der App entfernen, in der Anthropic Console löschen – fertig.
Die App funktioniert auch ohne KI weiter.</li>
</ul></div>
<div class="card"><h2>Schritt für Schritt</h2><ol class="schritte">
<li><b>Konto anlegen</b><span>Öffne die <a href="https://console.anthropic.com" target="_blank" rel="noopener">Anthropic
Console</a> und registriere dich mit deiner E-Mail-Adresse. Das ist ein anderes Konto als ein Claude-Chat-Abo – ein
Abo brauchst du nicht.</span></li>
<li><b>Guthaben aufladen</b><span>In der Console unter <b>Billing</b> (Abrechnung) eine Zahlungsart hinterlegen und
Guthaben kaufen. Ein kleiner Betrag genügt zum Ausprobieren. „Auto-reload“ (automatisch nachladen) lässt du aus.
Gekauftes Guthaben wird nicht erstattet – darum lieber klein anfangen und bei Bedarf nachkaufen.</span></li>
<li><b>Schlüssel erstellen</b><span>Unter <b>API Keys</b> auf <b>Create Key</b>, als Namen z. B. „Job-Monitor“. Den
Schlüssel (beginnt mit <code>sk-ant-</code>) gleich kopieren – er wird nur einmal angezeigt. Teile ihn mit niemandem.</span></li>
<li><b>In der App eintragen</b><span>In <a href="/einstellungen#ki">Einstellungen → KI</a> als Anbieter „Claude“ wählen,
den Schlüssel einfügen und <b>Sicher speichern</b>. Er landet im Schlüsselbund deines Rechners (Windows:
Anmeldeinformationsverwaltung), nicht in einer Datei.</span></li>
<li><b>Ausprobieren</b><span>Zum Beispiel unter Einstellungen ein Suchprofil mit „Felder mit KI ausfüllen“ anlegen oder bei
einer Bewerbung „Entwurf mit KI“ klicken. Ab dann liest die tägliche Suche neue Anzeigen mit KI.</span></li>
</ol></div>
<div class="card"><h2>Kosten im Blick behalten</h2><ul>
<li><b>In der App:</b> Einstellungen → KI zeigt Aufrufe und Tokens dieses Monats (Tokens sind die Einheit, nach der
abgerechnet wird – grob: Textmenge).</li>
<li><b>Bei Anthropic:</b> In der Console unter <b>Usage</b> siehst du die Kosten in Euro bzw. Dollar.</li>
<li><b>Sparen:</b> Die tägliche Suche nutzt automatisch ein kleines, günstiges Modell; nur Anschreiben, Vorbereitung und
Lebenslauf-Zuschnitt nutzen das stärkere. Das Monatslimit der Oberfläche steht in config.yaml unter
<code>ki.max_aufrufe_monat</code>.</li></ul></div>
<div class="card"><h2>Häufige Sorgen</h2><dl>
<dt>Muss ich programmieren können?</dt><dd>Nein. Du brauchst nur das Konto, Guthaben und den kopierten Schlüssel.</dd>
<dt>Kann jemand meinen Schlüssel sehen?</dt><dd>Er liegt im Schlüsselspeicher deines Rechners und wird nur an Anthropic
geschickt. Wenn du unsicher bist: in der Console löschen und einen neuen erstellen.</dd>
<dt>Was passiert, wenn das Guthaben leer ist?</dt><dd>Die KI-Knöpfe melden einen Fehler, die App läuft ohne KI weiter.
Es entstehen keine Schulden.</dd>
<dt>Schreibt die KI meine Bewerbungen und schickt sie ab?</dt><dd>Nein. Sie macht Entwürfe; du liest, änderst und
schickst selbst. Beim Lebenslauf sortiert sie nur deine eigenen Einträge – sie erfindet nichts.</dd>
<dt>Ich möchte lieber einen anderen Anbieter.</dt><dd>Unter Einstellungen → KI gehen auch OpenAI, Google Gemini, Mistral
und Ollama (läuft kostenlos auf deinem Rechner). Die App ist aber auf Claude abgestimmt.</dd>
<dt>Gibt es das auch kostenlos?</dt><dd>Ja, mit Google Gemini – ohne Kreditkarte, mit Tagesgrenzen und etwas schwächeren
Ergebnissen: <a href="/ki-anleitung?anbieter=gemini">Anleitung für Google Gemini</a>.</dd>
</dl></div></div>"""

ANLEITUNG_GEMINI = """<div class="page-head"><div><h1>Google Gemini einrichten – kostenlos</h1><p class="sub">In etwa fünf
Minuten, ohne Kreditkarte. Ideal zum Ausprobieren der KI-Funktionen.</p></div><div class="row"><a class="btn ghost small"
href="/einstellungen#ki">Zu Einstellungen → KI</a></div></div>
<div class="ki-anleitung">
<div class="card beruhigung"><h2>Das Wichtigste in Kürze</h2><ul>
<li><b>Kostenlos.</b> Google bietet für die Gemini-Schnittstelle ein kostenloses Kontingent an. Du brauchst nur ein
Google-Konto – keine Kreditkarte, kein Abo, keine Rechnung.</li>
<li><b>Mit Tagesgrenzen.</b> Das kostenlose Kontingent erlaubt nur eine begrenzte Zahl Anfragen pro Minute und pro Tag;
wie viele, zeigt dir Google in AI Studio unter „Rate limits“. Ist es aufgebraucht, melden die KI-Knöpfe einen Fehler und
die App arbeitet ohne KI weiter – am nächsten Tag (gegen 9 Uhr) geht es wieder. Es entstehen nie Kosten, solange du
keine Zahlungsart hinterlegst.</li>
<li><b>Ehrlich gesagt: Claude ist besser.</b> Die App ist auf Claude abgestimmt. Mit Gemini funktionieren alle
KI-Funktionen, aber Anschreiben, Gesprächsvorbereitung und Lebenslauf-Zuschnitt fallen meist etwas weniger treffend
aus, und die stärksten Gemini-Modelle („Pro“) sind im kostenlosen Kontingent in der Regel nicht enthalten. Zum
Kennenlernen und für die meisten Aufgaben reicht Gemini gut – wer viel bewirbt, fährt mit
<a href="/ki-anleitung">Claude</a> besser.</li>
<li><b>Datenschutz:</b> Name, Adresse, Telefon, E-Mail und Foto sendet die App nie – nur Anzeigentexte und den fachlichen
Teil deines Lebenslaufs. Beim kostenlosen Kontingent darf Google Eingaben laut seinen Bedingungen grundsätzlich auch
zur Verbesserung seiner Produkte nutzen (auch durch menschliche Prüfer, losgelöst von deinem Konto). Für Nutzer in der
EU, der Schweiz und Großbritannien gelten laut Google die strengeren Regeln der bezahlten Nutzung – lies die
<a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noopener">aktuellen Bedingungen</a> im Zweifel
selbst nach.</li>
<li><b>Der Entwickler dieser App bekommt nichts</b> – weder deinen Schlüssel noch deine Daten. Alles läuft direkt
zwischen deinem Rechner und Google.</li>
</ul></div>
<div class="card"><h2>Schritt für Schritt</h2><ol class="schritte">
<li><b>Google AI Studio öffnen</b><span>Öffne <a href="https://aistudio.google.com/apikey" target="_blank"
rel="noopener">Google AI Studio</a> und melde dich mit deinem Google-Konto an. Beim ersten Mal bestätigst du die
Nutzungsbedingungen.</span></li>
<li><b>Schlüssel erstellen</b><span>Auf <b>Create API key</b> bzw. „API-Schlüssel erstellen“ klicken. Den Schlüssel
(beginnt meist mit <code>AIza</code>) kopieren und mit niemandem teilen. Eine Zahlungsart musst du dafür nicht
hinterlegen – lass das aus, dann bleibt es garantiert kostenlos.</span></li>
<li><b>In der App eintragen</b><span>In <a href="/einstellungen#ki">Einstellungen → KI</a> als Anbieter
„Google Gemini“ wählen und <b>Wechseln</b>, den Schlüssel einfügen und <b>Sicher speichern</b>. Er landet im
Schlüsselbund deines Rechners (Windows: Anmeldeinformationsverwaltung), nicht in einer Datei.</span></li>
<li><b>Modelle übernehmen</b><span>Die App lädt die verfügbaren Modelle und schlägt zwei aus der „Flash“-Reihe vor: ein
leichtes für die tägliche Suche und ein stärkeres für Anschreiben und Vorbereitung. Mit <b>Übernehmen</b> bestätigen –
ändern kannst du das jederzeit.</span></li>
<li><b>Ausprobieren</b><span>Zum Beispiel bei einer Bewerbung „Entwurf mit KI“ oder „Gespräch üben“ klicken.</span></li>
</ol></div>
<div class="card"><h2>Häufige Fragen</h2><dl>
<dt>Kostet mich das wirklich nichts?</dt><dd>Ja, solange du in Google AI Studio bzw. Google Cloud keine Zahlungsart
hinterlegst. Dann gibt es nur das kostenlose Kontingent – ist es aufgebraucht, wartet die KI bis zum nächsten Tag.</dd>
<dt>Warum funktioniert die KI plötzlich nicht mehr?</dt><dd>Meist ist das Tages- oder Minutenkontingent erschöpft. Kurz
warten bzw. am nächsten Tag weitermachen. In AI Studio unter „Rate limits“ siehst du deinen Stand.</dd>
<dt>Kann ich später zu Claude wechseln?</dt><dd>Jederzeit unter Einstellungen → KI. Die App merkt sich jeden Schlüssel
getrennt; du kannst also auch hin und her wechseln.</dd>
<dt>Schreibt die KI meine Bewerbungen und schickt sie ab?</dt><dd>Nein. Sie macht Entwürfe; du liest, änderst und
schickst selbst.</dd>
</dl></div></div>"""

CSS = """
.ki-anleitung .card { max-width:860px; } .ki-anleitung li, .ki-anleitung dd { line-height:22px; max-width:72ch; }
.ki-anleitung ul { padding-left:20px; } .ki-anleitung li { margin:7px 0; }
.beruhigung { border-left:3px solid var(--ok); }
.ki-anleitung dt { font-weight:600; margin-top:12px; } .ki-anleitung dd { margin:4px 0 0; color:var(--muted); }
.ki-anleitung code { font-size:12.5px; background:var(--surface-2); padding:1px 6px; border-radius:6px; }
.schritte { counter-reset:s; list-style:none; padding:0; display:grid; gap:12px; }
.schritte li { display:grid; grid-template-columns:28px 1fr; column-gap:10px; margin:0; }
.schritte li::before { counter-increment:s; content:counter(s); grid-row:span 2; width:26px; height:26px; border-radius:50%;
  background:var(--accent-soft); color:var(--accent); display:grid; place-items:center; font-weight:600; font-size:13px; }
.schritte li span { color:var(--muted); }
"""
