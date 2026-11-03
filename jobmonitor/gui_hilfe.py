"""Seite „Anleitung“: was die App kann und wie man es benutzt, nach Aufgaben geordnet.

Kurz und aufgabenorientiert: je Abschnitt, wofür er da ist, die üblichen Schritte und wo die Daten liegen.
Hält sich an die Grundsätze der App: nichts wird automatisch verschickt, persönliche Daten bleiben lokal.
"""
from __future__ import annotations

from html import escape

# (Anker, Titel, HTML-Inhalt). Links zeigen auf die Seiten der App, damit man direkt loslegen kann.
ABSCHNITTE = [
    ("start", "Überblick", """
<p>Job-Monitor sucht jeden Morgen nach Stellen, die zu deinen Suchprofilen passen (Fachrichtung, Karrierestufe,
Wohnort), bewertet sie gegen deinen Lebenslauf und hilft dir bei der Bewerbung. Die Suche läuft entweder auf
diesem Rechner (Einstellungen → Zeitplan) oder auf GitHub (die <b>Pipeline</b>); diese App ist dein Arbeitsplatz.</p>
<ul>
<li><b>Beim Öffnen</b> holt die App die neuesten Ergebnisse von GitHub; <b>beim Beenden</b> lädt sie deine Änderungen
hoch (Bewerbungen, Master-CV, Firmen, Einstellungen). Zwischendurch geht das mit <b>Synchronisieren</b> unten links.</li>
<li><b>Es wird nie etwas verschickt.</b> Bewerbungen, Anschreiben und Nachfragen sind Entwürfe; abschicken tust du selbst.</li>
<li><b>Persönliches bleibt auf dem Mac:</b> Name, Adresse, Foto (<code>cv/profile.yaml</code>) und hochgeladene Unterlagen
(<code>cv/private/</code>) kommen nie ins Repo.</li>
</ul>"""),
    ("stellen", "Stellen ansehen und auswählen", """
<p><a href="/">Stellen</a> zeigt alles, was die Pipeline gefunden hat, sortiert nach <b>Fit</b>: wie gut dein
Master-CV die Anforderungen der Anzeige abdeckt.</p>
<ul>
<li><b>Der Satz oben</b> fasst zusammen, wie viele Stellen gut passen und was dir am häufigsten fehlt. Der Knopf rechts
öffnet direkt die Bewerbung zur besten offenen Stelle.</li>
<li><b>Die Kästchen je Stelle</b> sind ihre erkannten Anforderungen: gefüllt = erfüllt, umrandet = fehlt. Fährst du mit
der Maus darüber, steht da welche.</li>
<li><b>Reiter:</b> Alle, je Suchprofil (Werkstudent, Junior), Cloud Security (Stellen, bei denen Cloud und Security
zusammenkommen) und Ausgeblendet.</li>
<li><b>Je Zeile:</b> Titel öffnet die Anzeige · <b>Bewerbung</b> · Dokument-Symbol = Lebenslauf für diese Stelle ·
Lesezeichen = merken (landet bei Bewerbungen) · × = ausblenden (mit „Rückgängig“) · Glocke = Frist in
Apple-Erinnerungen eintragen.</li>
<li><b>„Zu wenig Angaben“</b> heißt: die Anzeige nennt kaum Anforderungen, ein Fit wäre geraten. Lies sie selbst.</li>
</ul>"""),
    ("bewerben", "Bewerbung vorbereiten", """
<ol>
<li>Bei der Stelle auf <b>Bewerbung</b>. Es entsteht ein Ordner unter <code>cv/bewerbungen/</code> mit einem
Anschreiben-Entwurf aus deinen Textbausteinen.</li>
<li>Text in <b>[eckigen Klammern]</b> selbst ausfüllen (z. B. warum genau diese Firma). Die Seite warnt, solange
welche übrig sind.</li>
<li><b>Speichern und Mappe bauen</b> erzeugt Anschreiben, zugeschnittenen Lebenslauf und die ganze Mappe mit deinen
Unterlagen als ein PDF. Darunter erscheinen die <b>Prüfungen</b>: Länge, Layout, Firmenname, Anrede, Frist.</li>
<li>Abschicken über das Portal oder per Mail der Firma. Danach in <a href="/bewerbungen">Bewerbungen</a> den Status auf
<b>beworben</b> setzen.</li>
</ol>
<p><b>Antworten von Firmen:</b> Die Pipeline schaut jeden Morgen im Postfach nach Antworten auf deine offenen
Bewerbungen (Eingangsbestätigung, Einladung, Absage, Zusage) – nur lesen, gespeichert werden Firma, Datum und Art. In
<a href="/bewerbungen">Bewerbungen</a> erscheint dann ein Vorschlag; mit einem Klick setzt du den Status. Wo eine
Antwort kam, entfällt das Nachfassen.</p>
<p><b>Gespräche:</b> Kommt eine Einladung, trägst du in <a href="/bewerbungen">Bewerbungen</a> unter „Gespräche“ den
Termin ein. Ein Klick legt ihn im Kalender an (Hinweis einen Tag und eine Stunde vorher); darunter steht, worauf du
dich vorbereiten solltest – aus den Anforderungen der Anzeige und deinem Master-CV.</p>
<p><b>Nicht mehr online:</b> Die Pipeline prüft die Links deiner Liste alle paar Tage. Ist eine Anzeige weg (404 oder
„Stelle besetzt“), steht das an der Stelle – bevor du eine Mappe für eine Stelle baust, die es nicht mehr gibt.</p>
<p><a href="/rueckblick">Rückblick</a> zeigt Bewerbungen je Woche, Rücklaufquote, Zeit bis zur Antwort und woher die
passenden Stellen kommen.</p>
<p>Nach 21 Tagen ohne Antwort erscheint dort <b>Nachfassen</b> mit einem fertigen Entwurf zum Kopieren; danach
„Als nachgefasst markieren“. Nicht passende Bewerbungen verwirfst du auf der Bewerbungsseite (der Ordner geht in den
Papierkorb).</p>"""),
    ("eigene", "Selbst gefundene Stellen", """
<p>Für Anzeigen, die der Monitor nicht kennt: <a href="/eigene">Eigene Stelle</a>. Anzeigentext einfügen oder den Link
zur Karriereseite angeben, Firma eintragen, <b>Fit prüfen und Lebenslauf erstellen</b>. Die Stelle landet in deinen
Bewerbungen. LinkedIn, StepStone und Indeed werden bewusst nicht abgerufen: dort den Text kopieren.</p>"""),
    ("lebenslauf", "Lebenslauf, Profil und Unterlagen", """
<ul>
<li><a href="/master">Master-CV</a>: alles Fachliche (Stationen, Ausbildung, Kenntnisse, Zertifikate, Projekte). Jeder
Eintrag ist ein umrandeter Block mit seinem Namen oben; Pfeile sortieren, × löscht. Erst <b>Speichern</b> übernimmt
die Änderungen. Oben siehst du, welche Fit-Begriffe dein Lebenslauf belegt.</li>
<li><b>Zertifikate mit Nachweis:</b> beim Zertifikat unter „Nachweis“ das PDF wählen und <b>Hochladen</b>. Es landet
bei den <a href="/unterlagen">Unterlagen</a> unter „Zeugnisse und Zertifikate“ und kommt damit automatisch in jede
Mappe; danach <b>Speichern</b>, damit die Verknüpfung bleibt. Die Reihenfolge ordnet die App selbst: erst Zeugnisse,
dann Zertifikate nach ihrem Datum, neueste zuerst.</li>
<li><b>Status</b> geplant / in Arbeit / erreicht: Geplantes zählt nicht für den Fit und erscheint nicht im Lebenslauf.
Der Schalter „im Lebenslauf zeigen“ blendet einzelne Einträge aus: gefüllt = wird angezeigt, Umriss = ausgeblendet
(der Eintrag wird dann blass und gestrichelt).</li>
<li><a href="/profil">Profil</a>: Name, Kontakt, Foto, ab wann du verfügbar bist. Bleibt nur auf dem Mac.</li>
<li><a href="/unterlagen">Unterlagen</a>: Notenübersicht, Immatrikulation, Zeugnisse und Foto für die Mappe (nur PDF
bzw. JPG/PNG, bis 20 MB).</li>
<li><b>Allgemeiner Lebenslauf</b> (oben auf der Stellen-Seite) baut die Fassung ohne Zuschnitt. Nach jedem Bau prüft
die App Länge, Layout und Inhalt und zeigt Hinweise.</li>
</ul>"""),
    ("luecken", "Lücken schließen", """
<p><a href="/luecken">Lücken-Auswertung</a> zeigt, welche Anforderungen in deinen Stellen am häufigsten vorkommen und um
wie viel dein durchschnittlicher Fit stiege, wenn du sie belegst. Oben stehen passende Zertifikate und kleine
Projekte; <b>Als geplant übernehmen</b> trägt sie in deinen Master-CV ein. Die Vorschläge stehen in
<code>lernpfade.yaml</code> und lassen sich unter Einstellungen bearbeiten.</p>"""),
    ("firmen", "Firmen", """
<ul>
<li><a href="/firmen">Firmen</a> listet alle Karriereseiten, die die Pipeline abfragt. Neue Firma unten eintragen; die
Stellenquelle erkennt die Pipeline beim nächsten Lauf selbst.</li>
<li><b>Manuell prüfen:</b> Seiten, die sich nicht automatisch lesen lassen. Ab und zu selbst ansehen und auf
<b>Besucht</b> klicken; nach 14 Tagen erinnert die App. <b>Erinnern</b> trägt den nächsten Besuch in Apple-Erinnerungen
ein.</li>
<li><b>Quellen beobachten:</b> Firmen oder Quellen, die seit mehreren Läufen nur Fehler oder nichts mehr liefern –
meist ist die Karriereseite umgezogen. Dann die Adresse prüfen.</li>
<li><b>Vorschläge:</b> Firmen aus deinen Treffern, die noch nicht in der Liste stehen.</li>
</ul>"""),
    ("einstellungen", "Einstellungen und Wartung", """
<p><a href="/einstellungen">Einstellungen</a> ersetzt das Terminal:</p>
<ul>
<li><b>Pipeline auf GitHub:</b> letzte Läufe ansehen, einen Lauf sofort starten.</li>
<li><b>Mitteilung bei neuen Stellen:</b> täglich zur gewählten Uhrzeit eine Mitteilung auf dem Mac, wenn die Pipeline
neue Stellen gefunden hat; ein Klick öffnet die App. Mit dem Schalter ein- und ausschalten. Beim ersten Mal fragt macOS,
ob Job-Monitor Mitteilungen senden darf.</li>
<li><b>Probelauf:</b> Quellen abfragen, ohne etwas zu speichern – gut zum Testen einer neuen Firma.</li>
<li><b>Suchprofile</b> an- und ausschalten (z. B. Junior nach dem Abschluss).</li>
<li><b>Dateien bearbeiten:</b> <code>config.yaml</code>, Lernvorschläge und die Textvorlagen; vor dem Speichern wird geprüft.</li>
<li><b>App neu bauen</b>, Pakete aktualisieren, Selbsttest, alte Lebenslauf-Dateien aufräumen, Protokoll ansehen.</li>
</ul>"""),
    ("fragen", "Häufige Fragen", """
<dl>
<dt>Warum sehe ich meine Änderung nicht in der Pipeline?</dt>
<dd>Sie wird erst beim Beenden oder mit „Synchronisieren“ hochgeladen und gilt ab dem nächsten Lauf.</dd>
<dt>Eine Stelle fehlt, die ich auf LinkedIn gesehen habe.</dt>
<dd>LinkedIn, StepStone und Indeed werden nicht abgefragt. Ihre Job-Alert-Mails werden aber gelesen: Steht im Titel
„Werkstudent“, „Junior“ o. ä., sucht die App die Originalanzeige auf der Firmenseite oder bei der Bundesagentur und
bewertet die Stelle mit deren vollem Text. Findet sie keine, steht die Stelle unter „Zu wenig Angaben“ – dann den Text
als eigene Stelle einfügen.</dd>
<dt>Der Fit wirkt zu niedrig.</dt>
<dd>Der Fit zählt nur, was im Master-CV belegt ist, mit dem Level (Grundkenntnisse zählen weniger). Fehlt ein Begriff,
den du kannst, trag ihn im Master-CV ein.</dd>
<dt>Wo liegen meine Dateien?</dt>
<dd>Lebensläufe in <code>cv/out/</code>, Bewerbungen in <code>cv/bewerbungen/</code>, Unterlagen in
<code>cv/private/</code> – alles lokal und nicht im Repo.</dd>
</dl>"""),
]

CSS = """
.help { display:grid; grid-template-columns:200px minmax(0,1fr); gap:32px; align-items:start; }
.help nav { position:sticky; top:20px; display:grid; gap:2px; }
.help nav a { color:var(--muted); text-decoration:none; padding:5px 10px; border-radius:8px; font-size:13.5px; }
.help nav a:hover { background:var(--surface-2); color:var(--text); }
.help section { scroll-margin-top:16px; }
.help .card p, .help .card li, .help dd { max-width:70ch; line-height:22px; }
.help dt { font-weight:600; margin-top:12px; } .help dd { margin:4px 0 0; color:var(--muted); }
.help code { font-size:12.5px; background:var(--surface-2); padding:1px 6px; border-radius:6px; }
.help ol, .help ul { padding-left:20px; } .help li { margin:6px 0; }
@media (max-width:860px) { .help { grid-template-columns:1fr; } .help nav { position:static; } }
"""


def render() -> str:
    toc = "".join(f'<a href="#{a}">{escape(t)}</a>' for a, t, _ in ABSCHNITTE)
    sections = "".join(f'<section id="{a}" class="card"><h2>{escape(t)}</h2>{html}</section>'
                       for a, t, html in ABSCHNITTE)
    return (f'<div class="page-head"><div><h1>Anleitung</h1><p class="sub">Was die App kann und wie du sie benutzt. '
            f'Links führen direkt zur jeweiligen Seite.</p></div></div>'
            f'<div class="help"><nav aria-label="Inhalt">{toc}</nav><div>{sections}</div></div>')
