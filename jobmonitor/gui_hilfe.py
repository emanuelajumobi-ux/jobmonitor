"""Seite „Anleitung“: aufgebaut nach Diátaxis (diataxis.fr) – vier Arten von Hilfe für vier Bedürfnisse:

- Schnellstart (Tutorial): einmal geführt von null zur ersten Bewerbung
- So geht's (Anleitungen): kurze Schritte für eine konkrete Aufgabe, als Frage formuliert
- Nachschlagen (Referenz): Seiten, Begriffe, Dateien – zum Nachsehen, nicht zum Lesen
- Hintergrund (Erklärung): wie Suche, Fit, KI und Datenschutz funktionieren

Dazu nach den Hilfe-Richtlinien von Microsoft und Apple: Suche oben, kurze überfliegbare Schritte, Links direkt zur
passenden Seite und von jeder Seite derselbe Weg hierher (Knopf „Hilfe zu dieser Seite“, siehe HILFE_ZU_SEITE).
"""
from __future__ import annotations

from html import escape

from . import feedback

# Seite der App (aktiver Menüpunkt) → passender Abschnitt der Anleitung
HILFE_ZU_SEITE = {"stellen": "seite-stellen", "traum": "seite-stellen", "bewerbungen": "seite-bewerbungen",
                  "eigene": "eigene-stelle", "rueckblick": "seite-rueckblick", "firmen": "seite-firmen",
                  "luecken": "seite-luecken", "bericht": "seite-bericht", "master": "seite-master",
                  "profil": "seite-profil", "unterlagen": "seite-unterlagen", "einstellungen": "seite-einstellungen"}

SCHNELLSTART = [
    ("Angaben eintragen", "Name und Kontakt unter <a href=\"/profil\">Profil</a> – sie stehen nur im Kopf deiner PDFs "
     "und bleiben auf diesem Rechner."),
    ("KI-Schlüssel hinterlegen (empfohlen)", "Unter <a href=\"/einstellungen#ki\">Einstellungen → KI</a> deinen eigenen "
     "Claude-Schlüssel eintragen. Ohne geht alles auch, nur mit mehr Tipparbeit."),
    ("Wohnort und Suche festlegen", "Unter <a href=\"/einstellungen\">Einstellungen</a> den Wohnort setzen und ein "
     "Suchprofil anlegen: kurz beschreiben, was du suchst, Karrierestufe wählen, „Mit KI ausfüllen“."),
    ("Lebenslauf anlegen", "Im <a href=\"/master\">Master-CV</a> Stationen, Ausbildung, Kenntnisse und Projekte eintragen "
     "– oder im Einrichtungs-Assistenten ein vorhandenes Lebenslauf-PDF übernehmen lassen."),
    ("Erste Suche starten", "Unter <a href=\"/einstellungen\">Einstellungen</a> einen Probelauf starten oder den "
     "täglichen Zeitplan einschalten. Die Treffer erscheinen unter <a href=\"/\">Stellen</a>, sortiert nach Fit."),
    ("Bewerben", "Bei einer passenden Stelle auf <b>Bewerbung</b>: Anschreiben schreiben (oder von der KI entwerfen "
     "lassen), Design wählen, <b>Speichern und Mappe bauen</b>, Prüfung vor dem Abschicken ansehen – dann selbst "
     "abschicken und den Status auf „beworben“ setzen."),
]

# (Anker, Frage, Schritte als HTML-Liste oder Absatz, Suchwörter)
AUFGABEN = [
    ("stelle-bewerben", "Wie bewerbe ich mich auf eine gefundene Stelle?", [
        "Unter <a href=\"/\">Stellen</a> bei der Stelle auf <b>Bewerbung</b> klicken – es entsteht ein Bewerbungsordner mit "
        "einem Anschreiben-Entwurf.",
        "Am schnellsten: <b>Alles vorbereiten</b> – sichert die Anzeige, entwirft das Anschreiben (mit KI), schneidet "
        "den Lebenslauf zu und baut die Mappe in einem Schritt. Danach alles lesen und anpassen.",
        "Text in <b>[eckigen Klammern]</b> selbst ausfüllen oder <b>Entwurf mit KI</b> nutzen.",
        "Unter <b>Design</b> das Aussehen wählen (Klassisch, Modern, Kreativ, Kompakt, Akademisch).",
        "<b>Speichern und Mappe bauen</b>: Anschreiben, zugeschnittener Lebenslauf und Unterlagen als ein PDF.",
        "Die Karte <b>Vor dem Abschicken</b> durchgehen (Platzhalter, Firmenname, Größe, Anlagen, Frist).",
        "Über das Portal oder per Mail selbst abschicken, dann in <a href=\"/bewerbungen\">Bewerbungen</a> den Status auf "
        "<b>beworben</b> setzen."], "anschreiben mappe pdf lebenslauf bewerben abschicken"),
    ("portal", "Wie fülle ich ein Bewerbungsportal schneller aus?", [
        "Auf der Bewerbungsseite unter <b>Für Bewerbungsportale</b> stehen Name, Kontakt, Studium, Verfügbarkeit, "
        "Gehaltsvorstellung, Kurzprofil, Motivation und das Anschreiben als Text – je mit <b>Kopieren</b>.",
        "Lange Texte kürzt die App auf die Zeichengrenze des Portals (300 bis 2000 Zeichen), an der Satzgrenze oder "
        "mit <b>Mit KI kürzen</b>.",
        "Die Gehaltsvorstellung trägst du einmal im <a href=\"/profil\">Profil</a> ein. Abgeschickt wird nichts – du "
        "fügst ein und sendest selbst."], "portal formular kopieren workday successfactors gehalt kurzprofil"),
    ("englisch", "Wie bewerbe ich mich auf Englisch?", [
        "Auf der Bewerbungsseite unter <b>Sprache der Bewerbung</b> „Englisch“ wählen. Ist die Anzeige auf Englisch, "
        "schlägt die App das selbst vor.",
        "Einmalig <b>Master-CV mit KI übersetzen</b>: Die englische Fassung liegt danach in cv/cv_master.en.yaml und "
        "lässt sich unter <a href=\"/einstellungen#dateien\">Dateien bearbeiten</a> anpassen.",
        "Lebenslauf und Anschreiben bekommen englische Überschriften, Datum und Grußformel; englische Lebensläufe "
        "kommen ohne Foto und Geburtsdatum aus. <b>Entwurf mit KI</b> schreibt das Anschreiben auf Englisch."],
     "englisch english international cover letter cv übersetzen"),
    ("sprache", "Wie stelle ich die App auf Englisch um? (How do I switch the app to English?)", [
        "<a href=\"/einstellungen#sprache\">Einstellungen → Sprache · Language</a>: „English“ wählen. Beim ersten Start "
        "übernimmt die App die Sprache des Systems.",
        "Stellenanzeigen, deine eigenen Texte und Teile der Anleitung bleiben deutsch."],
     "sprache language english englisch oberfläche"),
    ("design-waehlen", "Wie ändere ich das Design von Lebenslauf und Anschreiben?", [
        "Alle Designs mit deinen Daten ansehen: <a href=\"/master#designs\">Master-CV → Designs</a>.",
        "Für ein ganzes Suchprofil: <a href=\"/einstellungen\">Einstellungen</a> → Suchprofil bearbeiten → <b>Design</b>.",
        "Für eine einzelne Bewerbung: auf der Bewerbungsseite unter <b>Design</b> wählen und die Mappe neu bauen.",
        "Bei großen Firmen mit Bewerbungsportal sind <b>Klassisch</b>, <b>Kompakt</b> oder <b>Akademisch</b> sicherer – "
        "die Prüfung vor dem Abschicken weist darauf hin."], "design vorlage layout farbe aussehen modern kreativ"),
    ("stelle-ausblenden", "Wie blende ich unpassende Stellen aus – und bringe dem Filter etwas bei?", [
        "Bei der Stelle auf <b>×</b> klicken (ein Klick auf „Rückgängig“ holt sie zurück).",
        "Danach kurz den Grund antippen, z. B. „anderes Fachgebiet“ – freiwillig.",
        "Häufen sich Wörter in abgelehnten Titeln, schlägt die Startseite sie als Ausschluss vor: <b>Ausschließen</b> "
        "übernimmt sie ab dem nächsten Lauf."], "ausblenden passt nicht filter ausschluss lernen"),
    ("eckdaten-filtern", "Wie zeige ich nur Stellen bis 20 Stunden, mit Remote oder Abschlussarbeit?", [
        "Unter <a href=\"/\">Stellen</a> die Häkchen über der Liste setzen. Stellen ohne Angabe bleiben bei Stunden und "
        "Remote sichtbar.",
        "Die Eckdaten liest die KI aus den Anzeigen; ohne KI fehlen sie meist."], "stunden remote abschlussarbeit eckdaten filter"),
    ("suchprofil", "Wie lege ich ein neues Suchprofil an (z. B. für ein anderes Fach)?", [
        "<a href=\"/einstellungen/suchprofil\">Einstellungen → Neues Suchprofil</a>.",
        "Kurz beschreiben, was du suchst, und <b>Felder mit KI ausfüllen</b> – oder Karrierestufe wählen und die "
        "Suchbegriffe selbst eintragen.",
        "Für ein anderes Fach „eigenes Fachgebiet“ wählen, damit Fach-Wörter wie „Marketing“ nicht ausgeschlossen werden.",
        "Speichern. Höchstens vier Profile können gleichzeitig aktiv sein."], "suchprofil fach richtung karrierestufe neu"),
    ("wohnort", "Wie ändere ich meinen Wohnort?", [
        "<a href=\"/einstellungen#wohnort\">Einstellungen → Wohnort</a>: Stadt eintragen.",
        "Mit KI werden die Fahrzeiten in die Umgebung geschätzt; zählen tun Stellen bis zur eingestellten Fahrzeit und "
        "remote."], "wohnort stadt umkreis fahrzeit"),
    ("taeglich", "Wie sucht die App jeden Tag von selbst?", [
        "<a href=\"/einstellungen#zeitplan\">Einstellungen → Zeitplan</a>: Uhrzeit wählen und <b>Täglich suchen</b>.",
        "Mac und Windows tragen die Suche in die Aufgabenplanung des Systems ein; verpasste Termine holt die App nach, "
        "sobald sie offen ist.",
        "Läuft deine Suche über GitHub Actions, ist der lokale Zeitplan nicht nötig."], "zeitplan täglich automatisch"),
    ("pausieren", "Wie pausiere ich die Suche, wenn ich gerade nichts suche?", [
        "<a href=\"/einstellungen\">Einstellungen → Suche</a>: <b>Ruhemodus</b> (einmal pro Woche, ohne Mitteilungen) oder "
        "<b>Angehalten</b>.",
        "Beim Zurückschalten auf „Aktiv“ zeigt die Startseite eine kurze Checkliste für den Neustart."], "pause ruhe anhalten"),
    ("postfach", "Wie verbinde ich mein Postfach (Job-Alerts, Antworten, Bericht per Mail)?", [
        "<a href=\"/einstellungen\">Einstellungen → Postfach</a>: Anbieter wählen, E-Mail-Adresse und ein "
        "<b>App-Passwort</b> deines Anbieters eintragen (nicht dein normales Passwort).",
        "Danach liest die App Job-Alert-Mails (z. B. von LinkedIn oder StepStone) und erkennt Antworten von Firmen – sie "
        "liest nur, sie verschickt nie etwas an Firmen.",
        "Optional: <b>Bericht täglich mailen</b> schickt dir den Bericht an deine eigene Adresse.",
        "Outlook und Microsoft 365 erlauben keine Anmeldung per Passwort mehr – dort die Alerts an ein anderes Postfach "
        "weiterleiten."], "postfach mail imap alert linkedin antwort bericht"),
    ("ki-schluessel", "Wie richte ich die KI ein, und was kostet sie?", [
        "In der <a href=\"https://console.anthropic.com\" target=\"_blank\" rel=\"noopener\">Anthropic Console</a> einen "
        "eigenen API-Schlüssel anlegen und unter <a href=\"/einstellungen#ki\">Einstellungen → KI</a> eintragen.",
        "Die Kosten laufen über dein Anthropic-Konto, nach Verbrauch. Die Karte zeigt den Verbrauch dieses Monats; für "
        "Aufrufe aus der Oberfläche gibt es ein Monatslimit.",
        "Die App hat keinen eigenen Zugang: Deine Daten gehen direkt an Anthropic, nie an den Entwickler."],
     "ki schlüssel kosten claude anthropic api"),
    ("lebenslauf-import", "Wie übernehme ich meinen vorhandenen Lebenslauf?", [
        "Im Einrichtungs-Assistenten (<a href=\"/einrichten\">Einrichten</a>) unter „Lebenslauf“ das PDF hochladen (KI nötig).",
        "Vor dem Senden entfernt die App Name, Adresse, Telefon, E-Mail, Links und Geburtsdatum aus dem Text.",
        "Danach im <a href=\"/master\">Master-CV</a> alles prüfen und speichern."], "lebenslauf import pdf übernehmen"),
    ("kenntnis-eintragen", "Wie trage ich eine Kenntnis schnell ein?", [
        "In der <a href=\"/luecken\">Lücken-Auswertung</a> oder oben im <a href=\"/master\">Master-CV</a> den Begriff "
        "anklicken und das Level wählen – er landet in der passenden Kategorie."], "kenntnis fit begriff eintragen level"),
    ("gespraech", "Wie bereite ich mich auf ein Gespräch vor?", [
        "In <a href=\"/bewerbungen\">Bewerbungen</a> unter „Gespräche“ den Termin eintragen und in den Kalender übernehmen "
        "(Mac: Kalender, Windows: Kalenderdatei).",
        "<b>Darauf vorbereiten</b>: wahrscheinliche Fragen und passende Beispiele aus deinem Lebenslauf; mit KI ausführlich.",
        "<b>Firmenprofil</b>: kurze Zusammenfassung der Firma aus ihrer Webseite.",
        "Nach dem Gespräch Notizen und Bauchgefühl festhalten; die KI entwirft eine Danke-Mail, die du selbst schickst."],
     "gespräch interview vorbereitung termin danke"),
    ("nachfassen", "Wie fasse ich nach, wenn keine Antwort kommt?", [
        "Nach einigen Wochen ohne Antwort erscheint die Bewerbung in <a href=\"/bewerbungen\">Bewerbungen</a> unter "
        "<b>Nachfassen</b> – mit einem Entwurf zum Kopieren (oder <b>Mit KI formulieren</b>).",
        "Selbst abschicken, dann <b>Als nachgefasst markieren</b>."], "nachfassen nachfrage keine antwort"),
    ("eigene-stelle", "Wie bewerte ich eine Stelle, die ich selbst gefunden habe?", [
        "<a href=\"/eigene\">Eigene Stelle</a>: Anzeigentext einfügen oder den Link zur Karriereseite angeben.",
        "<b>Fit prüfen und Lebenslauf erstellen</b> – die Stelle landet in deinen Bewerbungen.",
        "LinkedIn, StepStone und Indeed ruft die App nicht ab: dort den Text kopieren."], "eigene stelle link text"),
    ("firma-hinzufuegen", "Wie füge ich eine Firma hinzu, deren Karriereseite ich beobachten will?", [
        "<a href=\"/firmen\">Firmen</a>: unten Name und Adresse der Karriereseite eintragen.",
        "Beim nächsten Lauf erkennt die App das Bewerbungssystem selbst. Lässt sich die Seite nicht lesen, steht sie unter "
        "„manuell prüfen“ und die App erinnert dich, selbst nachzusehen.",
        "Firmen aus deinen Treffern schlägt die Seite außerdem vor.",
        "<b>Passende Firmen finden</b>: Die KI erstellt eine Liste von Arbeitgebern in deiner Nähe, die zu Lebenslauf "
        "und Suchprofilen passen – Karriereseite mit <b>Prüfen</b> öffnen, dann <b>Hinzufügen</b>."],
     "firma karriereseite hinzufügen finden liste arbeitgeber"),
    ("sicherung", "Wie sichere ich meine Daten?", [
        "<a href=\"/einstellungen\">Einstellungen → Sicherung</a>: mit Passwort als verschlüsseltes Disk-Image (Mac) oder "
        "als ZIP-Datei.",
        "Abgelegt unter Dokumente → Job-Monitor Sicherungen. Der KI-Schlüssel ist nicht enthalten."], "sicherung backup"),
    ("update", "Wie bekomme ich eine neue Version?", [
        "Gibt es eine neue Version, steht oben auf der Startseite ein Hinweis mit <b>Herunterladen</b>.",
        "Neue App laden und die alte ersetzen – deine Daten im Ordner Dokumente/Job-Monitor bleiben erhalten.",
        "Beim ersten Start fragt das System wieder nach (Mac: Systemeinstellungen → Datenschutz & Sicherheit → „Trotzdem "
        "öffnen“)."], "update version neu herunterladen"),
]

# Kurze Namen der wichtigsten Aufgaben fürs Inhaltsverzeichnis
NAV_AUFGABEN = [("stelle-bewerben", "Bewerben"), ("design-waehlen", "Design wählen"), ("suchprofil", "Suchprofil anlegen"),
                ("postfach", "Postfach verbinden"), ("ki-schluessel", "KI einrichten"), ("taeglich", "Täglich suchen"),
                ("gespraech", "Gespräch vorbereiten"), ("portal", "Bewerbungsportale"), ("englisch", "Auf Englisch"),
                ("update", "Neue Version")]

SEITEN = [
    ("seite-stellen", "Stellen", "/", "Gefundene Stellen nach Fit, mit Reitern je Suchprofil, Eckdaten-Filter, Suchfeld. "
     "Je Zeile: Bewerbung, Lebenslauf, Frist eintragen (Glocke), merken (Lesezeichen), ausblenden (×). Oben: „Heute "
     "bewerben“, Hinweise auf neue Versionen und Vorschläge aus deinen Ablehnungen."),
    ("seite-bewerbungen", "Bewerbungen", "/bewerbungen", "Deine Liste mit Status, dazu Gespräche (Termin, Vorbereitung, "
     "Firmenprofil, Nachbereitung), erkannte Antworten von Firmen, Nachfassen und ab zwei Zusagen der Angebotsvergleich."),
    ("seite-eigene", "Eigene Stelle", "/eigene", "Stellen, die der Monitor nicht gefunden hat: Text oder Link einfügen, Fit "
     "prüfen, Lebenslauf bauen."),
    ("seite-rueckblick", "Rückblick", "/rueckblick", "Bewerbungen je Woche, Rücklauf, Zeit bis zur Antwort, woher passende "
     "Stellen kommen und was zum Gespräch führt (nach Fit, Art und Quelle)."),
    ("seite-firmen", "Firmen", "/firmen", "Beobachtete Karriereseiten, Seiten zum manuellen Prüfen, Quellen, die nichts "
     "mehr liefern, Firmen-Vorschläge und Initiativ-Möglichkeiten."),
    ("seite-luecken", "Lücken-Auswertung", "/luecken", "Welche Anforderungen am häufigsten fehlen und wie stark dein Fit "
     "stiege; Lernvorschläge und Lernplan (KI), gefragte Kenntnisse im Verlauf, Fit-Begriffe ergänzen."),
    ("seite-bericht", "Letzter Bericht", "/bericht", "Der Bericht der letzten Suche: neue Stellen, Status der Quellen, "
     "Hinweise."),
    ("seite-master", "Master-CV", "/master", "Alle fachlichen Inhalte deines Lebenslaufs (ohne Persönliches): Stationen, "
     "Ausbildung, Kenntnisse, Zertifikate, Projekte. Daraus entstehen alle Lebensläufe. Unten: die Designs."),
    ("seite-profil", "Profil", "/profil", "Name, Kontakt, Foto und was davon im PDF erscheint. Bleibt auf diesem Rechner."),
    ("seite-unterlagen", "Unterlagen", "/unterlagen", "Zeugnisse, Nachweise und Foto für die Bewerbungsmappe."),
    ("seite-einstellungen", "Einstellungen", "/einstellungen", "Suche aktiv/Ruhe/aus, Zeitplan, Wohnort, Postfach, KI, "
     "Suchprofile, Probelauf, Dateien bearbeiten, Sicherung, Updates und Protokoll."),
]

BEGRIFFE = [
    ("Fit", "Wie viel Prozent der Anforderungen einer Anzeige dein Master-CV belegt, gewichtet nach Level. „Zu wenig "
     "Angaben“: Die Anzeige nennt zu wenige Anforderungen für eine faire Zahl."),
    ("Suchprofil", "Was du suchst: Rollen-Wörter im Titel, Suchbegriffe je Quelle, Fachgebiet, Karrierestufe und Design. "
     "Mehrere Profile gleichzeitig sind möglich."),
    ("Karrierestufe", "Ausbildung, Praktikum, Werkstudent, Abschlussarbeit, Berufseinstieg oder Berufserfahren – füllt "
     "Rollen-Wörter und Stellenart aus und wählt ein passendes Design."),
    ("Master-CV", "Die eine Quelle für alle Lebensläufe. Je Stelle sortiert die App passende Inhalte nach vorn – erfunden "
     "wird nichts."),
    ("Eckdaten", "Stunden, Vergütung, Remote, Start und ob eine Abschlussarbeit möglich ist – von der KI aus der Anzeige "
     "gelesen."),
    ("Fit-Begriffe", "Die Liste der Kenntnisse, nach denen der Fit zählt, mit Synonymen. Neue schlägt die KI vor."),
    ("Traumprofil", "Optional: Stellen, die besonders gut zu deinem Schwerpunkt passen, bekommen einen eigenen Reiter."),
    ("Pipeline / Zeitplan", "Die tägliche Suche – entweder als GitHub Action oder über den Zeitplan auf diesem Rechner."),
    ("Bewerbungssystem (ATS)", "Software großer Firmen, die Lebensläufe automatisch einliest. Einspaltige Designs werden dort "
     "am zuverlässigsten erkannt."),
]

DATEIEN = [
    ("Dokumente/Job-Monitor", "Dein Datenordner (installierte App). Beim Ersetzen der App bleibt er erhalten."),
    ("config.yaml", "Alle Einstellungen der Suche – das meiste hat ein eigenes Formular in den Einstellungen."),
    ("companies.yaml", "Beobachtete Firmen und Hochschulbörsen (Seite Firmen)."),
    ("cv/cv_master.yaml", "Dein Master-CV (Seite Master-CV)."),
    ("cv/profile.yaml", "Name, Kontakt, Foto – nur lokal, nie an eine KI."),
    ("cv/bewerbungen/", "Ein Ordner je Bewerbung mit Anschreiben, Lebenslauf und Mappe."),
    ("cv/private/", "Hochgeladene Unterlagen und Foto."),
    ("applications.csv", "Deine Bewerbungsliste (Seite Bewerbungen)."),
    ("reports/", "Ein Bericht je Suchtag."),
]

HINTERGRUND = [
    ("wie-suche", "Wie die Suche funktioniert", "Die App fragt öffentliche Quellen ab: die Jobsuche der Bundesagentur für "
     "Arbeit, Arbeitnow, Karriereseiten von Firmen (über ihre Bewerbungssysteme, strukturierte Daten oder Sitemaps), "
     "Hochschulbörsen und – mit verbundenem Postfach – Job-Alert-Mails. Jede Stelle durchläuft Filter (Rolle, Fach, Ort, "
     "Ausschlüsse), bekommt einen Score und einen Fit. Gemeldet wird jede Stelle nur einmal."),
    ("fair", "Warum kein LinkedIn, StepStone oder Indeed?", "Diese Börsen verbieten das automatische Auslesen. Die App hält "
     "sich an robots.txt, fragt sparsam ab und nutzt keine Logins oder Tricks gegen Sperren. Ihre Stellen kommen trotzdem an: "
     "über deine Job-Alert-Mails, zu denen die App die Originalanzeige bei der Firma sucht."),
    ("fit-erklaert", "Wie der Fit entsteht", "Aus jeder Anzeige werden Anforderungen erkannt – per Stichwort und, mit KI, "
     "aus dem Text (auch Pflicht oder „wünschenswert“). Erfüllt ist, was dein Master-CV belegt; Grundkenntnisse zählen "
     "weniger als „gut“, Geplantes gar nicht. Fehlt dir etwas, das du kannst: im Master-CV eintragen."),
    ("ki-erklaert", "Was die KI macht – und was nicht", "Die KI liest Anzeigen, schlägt Suchprofile vor, schneidet "
     "Lebensläufe zu (nur Auswahl und Reihenfolge, nichts Erfundenes), entwirft Anschreiben, Nachfragen und Danke-Mails und "
     "bereitet Gespräche vor. Sie verschickt nichts. Gesendet werden Anzeigentexte und dein Master-CV ohne persönliche "
     "Angaben – mit deinem eigenen Schlüssel direkt an Anthropic."),
    ("datenschutz", "Datenschutz", "Name, Adresse, Telefon, E-Mail und Foto liegen nur in cv/profile.yaml auf diesem "
     "Rechner. Zugangsdaten (KI-Schlüssel, Mail-App-Passwort) liegen im Schlüsselbund bzw. in der Windows-"
     "Anmeldeinformationsverwaltung. Bewerbungen und Mails an Firmen schickst immer du selbst."),
]

FRAGEN = [
    ("Eine Stelle fehlt, die ich auf LinkedIn gesehen habe.", "LinkedIn wird nicht abgefragt. Richte dort einen Job-Alert "
     "ein und verbinde dein Postfach – oder füge die Stelle unter „Eigene Stelle“ ein."),
    ("Der Fit wirkt zu niedrig.", "Er zählt nur, was im Master-CV belegt ist. Fehlende Kenntnisse in der Lücken-Auswertung "
     "mit einem Klick eintragen; Status „geplant“ zählt nicht."),
    ("Es kommen kaum Treffer.", "Suchbegriffe im Suchprofil prüfen (eher so, wie Firmen Stellen betiteln), Wohnort und "
     "Fahrzeit prüfen, eigenes Fachgebiet wählen, wenn du nicht in der IT suchst. Ein Probelauf zeigt, was jede Quelle "
     "liefert."),
    ("Das PDF ließ sich nicht bauen.", "Unter Einstellungen → Protokoll steht der Grund. Ohne LaTeX baut die App die PDFs "
     "über HTML; dafür braucht Windows den Browser Edge (vorinstalliert)."),
    ("Meine Änderung kommt in der GitHub-Suche nicht an.", "Sie wird beim Beenden oder mit „Synchronisieren“ hochgeladen und "
     "gilt ab dem nächsten Lauf."),
    ("Wo liegen meine Dateien?", "Siehe „Dateien und Ordner“ unter Nachschlagen."),
]


def _eintrag(anker: str, titel: str, inhalt: str, such: str, klasse: str = "card") -> str:
    return (f'<section id="{anker}" class="{klasse} hilfe-eintrag" data-such="{escape((titel + " " + such).lower())}">'
            f'<h3>{escape(titel)}</h3>{inhalt}</section>')


def render() -> str:
    start = "".join(f'<li><b>{escape(t)}</b><span>{html}</span></li>' for t, html in SCHNELLSTART)
    aufgaben = "".join(_eintrag(a, frage, "<ol>" + "".join(f"<li>{s}</li>" for s in schritte) + "</ol>", such)
                       for a, frage, schritte, such in AUFGABEN)
    seiten = "".join(f'<tr id="{a}" class="hilfe-eintrag" data-such="{escape((n + " " + t).lower())}">'
                     f'<td><a href="{href}">{escape(n)}</a></td><td>{escape(t)}</td></tr>' for a, n, href, t in SEITEN)
    begriffe = "".join(f'<div class="hilfe-eintrag" data-such="{escape((b + " " + t).lower())}"><dt>{escape(b)}</dt>'
                       f'<dd>{escape(t)}</dd></div>' for b, t in BEGRIFFE)
    dateien = "".join(f'<tr class="hilfe-eintrag" data-such="{escape((d + " " + t).lower())}"><td><code>{escape(d)}</code>'
                      f'</td><td>{escape(t)}</td></tr>' for d, t in DATEIEN)
    hintergrund = "".join(_eintrag(a, t, f"<p>{escape(text)}</p>", text) for a, t, text in HINTERGRUND)
    fragen = "".join(f'<div class="hilfe-eintrag" data-such="{escape((f + " " + a).lower())}"><dt>{escape(f)}</dt>'
                     f'<dd>{escape(a)}</dd></div>' for f, a in FRAGEN)
    nav = "".join(f'<a href="#{a}">{escape(t)}</a>' for a, t in (
        ("schnellstart", "Schnellstart"), ("so-gehts", "So geht's"), ("nachschlagen", "Nachschlagen"),
        ("hintergrund", "Hintergrund"), ("fragen", "Probleme lösen")))
    nav += '<div class="hilfe-sub">' + "".join(f'<a href="#{a}">{escape(t)}</a>' for a, t in NAV_AUFGABEN) + '</div>'
    return f"""<div class="page-head"><div><h1>Anleitung</h1><p class="sub">Erst der Schnellstart, danach kurze Anleitungen
für einzelne Aufgaben. Links führen direkt zur passenden Seite.</p></div></div>
<label class="search hilfe-suche">{_lupe()}<input id="hilfe-suche" type="search"
placeholder="Hilfe durchsuchen, z. B. Design, Postfach, Fit" aria-label="Hilfe durchsuchen"></label><p id="hilfe-treffer" class="muted" hidden></p>
<div class="help"><nav aria-label="Inhalt">{nav}</nav><div>
<section id="schnellstart" class="card hilfe-gruppe"><h2>Schnellstart: in sechs Schritten zur ersten Bewerbung</h2>
<p class="muted">Einmal von oben nach unten – danach kennst du die wichtigsten Seiten. Neu hier? Der
<a href="/einrichten">Einrichtungs-Assistent</a> führt durch die ersten vier Schritte.</p><ol class="schritte">{start}</ol>
</section>
<h2 id="so-gehts" class="hilfe-gruppe">So geht's</h2><div class="aufgaben">{aufgaben}</div>
<h2 id="nachschlagen" class="hilfe-gruppe">Nachschlagen</h2>
<div class="card"><h3>Seiten der App</h3><table class="hilfe-tabelle">{seiten}</table></div>
<div class="card" id="begriffe"><h3>Begriffe</h3><dl>{begriffe}</dl></div>
<div class="card" id="dateien"><h3>Dateien und Ordner</h3><table class="hilfe-tabelle">{dateien}</table></div>
<h2 id="hintergrund" class="hilfe-gruppe">Hintergrund</h2>{hintergrund}
<h2 id="fragen" class="hilfe-gruppe">Probleme lösen</h2><div class="card"><dl>{fragen}</dl></div>
{feedback.karte()}
<p class="muted" id="hilfe-nichts" hidden>Nichts gefunden. Andere Wörter versuchen – oder unter Einstellungen →
Protokoll nach einer Fehlermeldung sehen.</p>
</div></div>{JS}"""


def _lupe() -> str:
    return ('<svg class="ic" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/>'
            '<path d="m21 21-4.3-4.3"/></svg>')


def knopf(active: str) -> str:
    """„Hilfe zu dieser Seite“ – auf jeder Seite an derselben Stelle (unten rechts)."""
    anker = HILFE_ZU_SEITE.get(active)
    if not anker:
        return ""
    return (f'<a class="hilfe-knopf" href="/hilfe#{anker}" title="Hilfe zu dieser Seite" aria-label="Hilfe zu dieser '
            f'Seite">?</a>')


# Knopf „Hilfe zu dieser Seite“ (gui.App.page hängt ihn und dieses CSS an jede Seite mit Hilfe-Abschnitt)
KNOPF_CSS = """
.hilfe-knopf { position:fixed; right:22px; bottom:22px; width:38px; height:38px; border-radius:50%; display:grid;
  place-items:center; background:var(--surface); color:var(--text); border:1px solid var(--line); font-weight:600;
  text-decoration:none; box-shadow:0 2px 10px rgba(0,0,0,.12); z-index:20; }
.hilfe-knopf:hover { background:var(--accent); color:var(--on-accent); }
@media print { .hilfe-knopf { display:none; } }
"""

JS = """<script>
(() => {
  const feld = document.getElementById('hilfe-suche');
  if (!feld) return;
  const eintraege = [...document.querySelectorAll('.hilfe-eintrag')];
  const gruppen = [...document.querySelectorAll('.hilfe-gruppe, .help .card:not(.hilfe-eintrag)')];
  const info = document.getElementById('hilfe-treffer'), nichts = document.getElementById('hilfe-nichts');
  feld.addEventListener('input', () => {
    const woerter = feld.value.toLowerCase().split(/\\s+/).filter(Boolean);
    let n = 0;
    eintraege.forEach(e => { const ja = woerter.every(w => e.dataset.such.includes(w)); e.hidden = !ja; n += ja; });
    const suche = woerter.length > 0;
    gruppen.forEach(g => g.hidden = suche && !g.querySelector('.hilfe-eintrag:not([hidden])')
                                    && !g.classList.contains('hilfe-eintrag'));
    document.getElementById('schnellstart').hidden = suche;
    info.hidden = !suche; info.textContent = n + (n === 1 ? ' Treffer' : ' Treffer');
    nichts.hidden = !suche || n > 0;
  });
  // Sprung zu einem Abschnitt (z. B. vom Knopf „?“): kurz hervorheben
  const ziel = location.hash && document.querySelector(location.hash);
  if (ziel) { ziel.classList.add('hilfe-ziel'); setTimeout(() => ziel.classList.remove('hilfe-ziel'), 2400); }
})();
</script>"""

CSS = """
.help { display:grid; grid-template-columns:210px minmax(0,1fr); gap:32px; align-items:start; }
.help nav { position:sticky; top:20px; display:grid; gap:2px; }
.help nav a { color:var(--muted); text-decoration:none; padding:5px 10px; border-radius:8px; font-size:13.5px; }
.help nav a:hover { background:var(--surface-2); color:var(--text); }
.help .hilfe-sub { display:grid; gap:1px; margin:6px 0 0 8px; padding-left:8px; border-left:1px solid var(--line); }
.help .hilfe-sub a { font-size:12.5px; padding:3px 8px; }
.hilfe-suche { display:block; max-width:520px; margin:0 0 18px; }
.help section, .help h2, .help tr, .help .card { scroll-margin-top:16px; }
.help h2.hilfe-gruppe { margin:28px 0 12px; font-size:20px; }
.help h3 { margin:0 0 10px; font-size:16px; }
.help p, .help li, .help dd, .help td { max-width:72ch; line-height:22px; }
.help ol { padding-left:22px; margin:0; } .help li { margin:5px 0; }
.schritte { counter-reset:s; list-style:none; padding:0 !important; display:grid; gap:10px; margin-top:12px !important; }
.schritte li { display:grid; grid-template-columns:28px 1fr; column-gap:10px; margin:0; }
.schritte li::before { counter-increment:s; content:counter(s); grid-row:span 2; width:26px; height:26px; border-radius:50%;
  background:var(--accent-soft); color:var(--accent); display:grid; place-items:center; font-weight:600; font-size:13px; }
.schritte li span { color:var(--muted); }
.aufgaben { display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:14px; }
.aufgaben .card { margin:0; }
.hilfe-tabelle { width:100%; border-collapse:collapse; } .hilfe-tabelle td { padding:7px 12px 7px 0; vertical-align:top;
  border-top:1px solid var(--line); } .hilfe-tabelle td:first-child { white-space:nowrap; font-weight:500; }
.help dt { font-weight:600; margin-top:12px; } .help dd { margin:4px 0 0; color:var(--muted); }
.help code { font-size:12.5px; background:var(--surface-2); padding:1px 6px; border-radius:6px; }
.hilfe-ziel { outline:2px solid var(--accent); outline-offset:4px; border-radius:var(--radius); transition:outline-color 1s; }
@media (max-width:860px) { .help { grid-template-columns:1fr; } .help nav { position:static; } }
"""
