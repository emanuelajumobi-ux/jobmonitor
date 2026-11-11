# Neuigkeiten

Was sich je Version geändert hat. Der Abschnitt der jeweiligen Version erscheint beim Veröffentlichen auf der
Download-Seite und in der App beim Hinweis „Version … ist da“ unter „Was ist neu“.

## Unveröffentlicht

- **Suchprofil-Seite repariert:** Ein Fehler im Skript der Seite legte den Zähler der Suchbegriffe, die Schätzung der Abrufe und die Vorlagen der Karrierestufe lahm. Wählst du jetzt eine Karrierestufe, werden die Rollen-Wörter wieder vorbelegt.
- **Tägliche Suche überlebt das Verschieben der App:** Der Zeitplan merkte sich den Ort der App. Nach dem Verschieben (von „Downloads“ nach „Programme“, vom ZIP-Ordner zum Installer) lief die tägliche Suche still nie mehr. Jetzt erneuert die App den Zeitplan beim Start von selbst.
- **Anschreiben-Entwürfe für jedes Fach:** Die Entwürfe für Initiativbewerbungen nannten fest IT-Schwerpunkte (Cloud, Azure, Entra ID). Jetzt stehen dort deine eigenen Kenntnisse aus dem Master-CV, und die Zielrolle kommt aus deinem aktiven Suchprofil.
- **Fehlerseite statt leerer Seite:** Passiert ein unerwarteter Fehler, zeigt die App eine verständliche Seite mit dem Grund und dem Weg zurück.
- **Robuster bei beschädigten Dateien:** Eine beschädigte Datenbank, eine leere Firmenliste oder ein von Hand falsch bearbeiteter Lebenslauf legen nicht mehr alle Seiten lahm. Die App sagt, was nicht stimmt.
- **Tote Firmenseiten kosten keine Zeit mehr:** Antwortet eine Karriereseite nicht, versucht die Suche es einmal und überspringt sie dann, statt mehrfach je 25 Sekunden zu warten. Im Bericht steht ein kurzer Grund.
- **Mitteilungen (Mac):** Die Karte „Mitteilung bei neuen Stellen“ erscheint nur noch mit GitHub-Suche. Ohne GitHub meldet die tägliche Suche neue Stellen selbst. Der Befehl dahinter funktioniert jetzt auch in der installierten App.

## 1.4.4

- **Suche bricht nicht mehr am Ende ab:** Hattest du im Einrichtungs-Assistenten deine Adresse eingetragen, stürzte die Suche beim Anlegen der Anschreiben-Entwürfe ab – und alle gefundenen Stellen gingen verloren. Das ist behoben. Außerdem kann ein Fehler bei den Entwürfen die Suche nicht mehr abbrechen.
- **„database is locked“ endgültig behoben:** Die Suche hielt die Datenbank während der ganzen Abfrage gesperrt. Lief zur selben Zeit noch eine zweite Suche (etwa aus der App vor einem Update), scheiterte sie. Jetzt wird jeder Schreibvorgang sofort abgeschlossen.
- **Gemini sparsamer:** Mit dem kostenlosen Gemini fragt die App höchstens etwa alle 6,5 Sekunden, wartet bei der Minutengrenze so lange, wie Google angibt, und hört bei aufgebrauchtem Tageskontingent sofort auf (es ist ab 9 Uhr morgens wieder frei). Pro Suche bewertet sie weniger Stellen ausführlich, die übrigen folgen in den nächsten Suchen.

## 1.4.3

- **Suche bricht nicht mehr ab, wenn zwei gleichzeitig starten:** Nach einem Update konnte die Suche der alten Version noch im Hintergrund laufen, während die neue Version schon die nächste startete. Beide schrieben in dieselbe Datenbank, und eine scheiterte mit „database is locked“. Jetzt läuft immer nur eine Suche, eine zweite wird übersprungen.
- **Laufende Suche sichtbar:** Läuft noch eine Suche aus der vorigen Sitzung, zeigt die Stellenliste das an und lädt neu, sobald sie fertig ist.

## 1.4.2

- **Ladehinweise jetzt wirklich sichtbar:** Im App-Fenster auf dem Mac blieb der Hinweis „Bitte warten“ bzw. „KI arbeitet …“ oft unsichtbar, weil das Fenster nach einem Klick nichts mehr neu zeichnet. Jetzt erscheint der Hinweis zuerst, erst dann geht die Aktion los – bei KI-Aktionen mit Erklärung, sonst als kleines „Bitte warten …“.
- **Fortschrittsbalken für die Suche:** Die Stellenliste zeigt, welche Quelle gerade abgefragt wird und wie weit die Suche ist. Ist sie fertig, lädt die Liste von selbst neu. Scheitert sie, steht dort, was schiefging.
- **Erste Suche geht nicht mehr verloren:** Schließt du Job-Monitor, während eine Suche läuft, fragt die App vorher nach. Wurde die erste Suche abgebrochen, holt die App sie beim nächsten Start nach.
- **Wohnort wird immer gespeichert:** Kann die KI die Fahrzeiten gerade nicht schätzen (z. B. weil das kostenlose Gemini-Kontingent aufgebraucht ist), speichert die App den Wohnort trotzdem und sagt, was fehlt.
- **Kleinigkeiten:** Keine irreführende Fehlermeldung mehr am Ende eines Probelaufs (Mac). „Andere Modelle wählen“ zeigt einen Ladehinweis.

## 1.4.1

- **Mac: leichter installieren:** Für den Mac gibt es jetzt eine DMG-Datei. Öffnen, Job-Monitor auf „Programme“ ziehen, fertig. Hat sich die App direkt aus „Downloads“ geöffnet, zeigt sie oben „In Programme verschieben“ an und startet nach einem Klick von dort neu.
- **Windows: richtiger Installer:** Statt ZIP-Datei gibt es jetzt `Job-Monitor-Windows-Setup.exe`. Doppelklick, „Weiter“, fertig – ohne Admin-Rechte, mit Eintrag im Startmenü, optional auf dem Desktop, und deinstallierbar wie jedes Programm unter Einstellungen → Apps. Deine Daten bleiben dabei immer erhalten.
- **Mac: Update mit einem Klick auch ohne Schreibrechte:** Darf dein Benutzer den Ordner „Programme“ nicht ändern, fragt macOS beim Update nach dem Passwort eines Administrators, statt nur die Download-Seite zu öffnen. Geht ein Update gar nicht mit einem Klick, sagt die App, warum und was zu tun ist.

## 1.4.0

- **Einstellungen neu geordnet:** Statt einer langen Liste gibt es sechs Gruppen: Allgemein, Suche, KI und Postfach, Deine Daten, App und ganz unten abgesetzt Zurücksetzen. Oben springst du mit einer festen Leiste zu jeder Gruppe, und ein Suchfeld findet einzelne Einstellungen, zum Beispiel „Sicherung“ oder „Postfach“.
- **Updates schneller sichtbar:** Die App sucht jetzt bei jedem Start nach einer neuen Version, nicht mehr nur einmal am Tag. Bleibt sie länger offen, schaut sie alle drei Stunden nach. Unter Einstellungen → App gibt es außerdem „Jetzt nach Updates suchen“.

## 1.3.9

- **Kurzer Rundgang:** Nach der Einrichtung zeigt dir ein Rundgang in acht Schritten die wichtigsten Bereiche der App. Neu starten kannst du ihn jederzeit unter Anleitung.
- **Erste Suche startet sofort:** Mit „Fertig – erste Suche starten“ läuft die erste Suche gleich los, nicht erst am nächsten Morgen. Die Stellenliste zeigt, dass sie läuft, und lädt sich von selbst neu, sobald sie fertig ist.
- **Firmenliste mit KI füllen:** Im Einrichtungs-Assistenten schlägt die KI mit einem Klick passende Arbeitgeber in deiner Gegend vor und trägt sie ein. Einzelne schaltest du später unter „Firmen“ wieder ab.
- **Einstellungen springen nicht mehr nach oben:** Während im Hintergrund eine Suche läuft, aktualisiert sich nur noch deren Ausgabe, nicht mehr die ganze Seite.
- **Passende Begriffe für jedes Fach:** Auf der Master-CV-Seite stehen nur noch Begriffe, die dein Lebenslauf belegt oder die deine gefundenen Stellen verlangen. Neue Nutzer bekommen außerdem Begriffe aus Wirtschaft und Verwaltung dazu, zum Beispiel SAP, Power BI, Controlling, Marketing und Vertrieb.
- **Gemini schneller eingerichtet:** Die App probiert die Gemini-Modelle jetzt gleichzeitig statt nacheinander aus.
- **Kleinigkeiten:** Bei Berufserfahrung und Projekten ist das Feld „Technologien und Werkzeuge“ als optional gekennzeichnet.

## 1.3.8

- **Rückgängig mit ⌘Z / Strg+Z:** In Textfeldern nimmt ⌘Z die letzte Eingabe zurück (⇧⌘Z stellt sie wieder her). Außerhalb von Feldern nimmt es die letzte Aktion zurück, etwa eine gerade ausgeblendete Stelle.
- **Ausgeblendete Stellen zurückholen oder löschen:** Im Reiter „Ausgeblendet“ holt das Auge eine Stelle zurück, der Papierkorb löscht sie endgültig. Mit „Alle endgültig löschen“ räumst du die ganze Liste auf einmal auf.
- **Einrichtung übersichtlicher:** Solange die Einrichtung läuft, steht „Einrichtung fortsetzen“ farbig ganz oben in der Seitenleiste. Die Seite selbst hat einen eigenen Kopf mit Fortschrittsbalken. Ist alles erledigt, verschwindet der Eintrag. Später öffnest du den Assistenten unter Einstellungen → Neu einrichten.
- **KI direkt im Assistenten:** Den Schlüssel trägst du jetzt direkt im Einrichtungs-Assistenten ein, prüfst ihn und kannst ihn dort auch wieder entfernen. Bei Gemini übernimmt die App die passenden Modelle von selbst.
- **Klare KI-Fehlermeldungen:** Statt „Die KI hat nicht geantwortet“ steht jetzt der Grund da, zum Beispiel kein Internet, Kontingent erschöpft, Schlüssel abgelehnt oder Modell nicht verfügbar. Ist das kostenlose Gemini-Kontingent einer Minute voll, versucht die App es nach 15 Sekunden noch einmal.
- **Postfach leichter verbinden:** Wählst du deinen Anbieter, steht vorher da, was eingeschaltet sein muss. Bei Gmail ist das die Bestätigung in zwei Schritten. Knöpfe führen direkt zur richtigen Seite, um sie einzuschalten und das App-Passwort anzulegen.
- **Sichtbarer Ladehinweis:** Während die KI arbeitet, zum Beispiel beim Fit-Prüfen einer eigenen Stelle, ist der Hinweis jetzt auch im dunklen Design deutlich zu sehen. Das Update hat einen eigenen Ladehinweis ohne KI-Text.
- **Aufgeräumter:** Tags unter dem Jobtitel überlappen nicht mehr mit der Bewertung. Der Knopf „Beenden“ ist aus der Seitenleiste verschwunden: Schließen oder ⌘Q beendet die App.

## 1.3.7

- **Einrichtung geht nicht mehr verloren:** Öffnest du im Einrichtungs-Assistenten die KI-Anleitung, führt dich oben und unten ein Knopf zurück. Solange die Einrichtung nicht abgeschlossen ist, zeigt jede Seite oben „Weiter einrichten“.
- **Gemini-Anleitung ausführlicher:** Schritt für Schritt durch Google AI Studio – auch, was zu tun ist, wenn sich zuerst ein Chat-Fenster öffnet, und wo genau der Schlüssel steht.
- **Neu einrichten:** Unter Einstellungen → Neu einrichten setzt du Job-Monitor zurück, als wäre die App frisch installiert – auf Wunsch mit Sicherung der alten Daten und ohne die KI-Schlüssel. Wie du die App vollständig entfernst, steht im README.
- **Windows: App über die Suche finden:** Job-Monitor legt beim Start einen Eintrag im Startmenü an. Hast du den Ordner verschoben oder neu entpackt, zeigt der Eintrag automatisch auf den neuen Ort.

## 1.3.6

- **Du siehst sofort, wo du gelandet bist:** Führt ein Link an eine bestimmte Stelle einer Seite (zum Beispiel „Weiterempfehlen“ in der Seitenleiste), steht das Ziel jetzt mittig im Fenster und leuchtet kurz farbig auf.
- **Einstellungen schneller:** Die Liste der letzten GitHub-Läufe lädt jetzt im Hintergrund und hält den nächsten Klick nicht mehr auf. Außerdem liest die App ihre Einstellungen nur noch einmal statt mehrfach pro Seite.
- **Ohne KI klarer:** Ist keine KI eingerichtet, sind alle KI-Funktionen sichtbar, aber ausgegraut. Ein Klick darauf erklärt kurz, wo du die KI einrichtest (mit Google Gemini auch kostenlos).

## 1.3.5

- **Weiterempfehlen:** In der Seitenleiste steht jetzt „Weiterempfehlen“ (führt zu Einstellungen → Weiterempfehlen). Die Knöpfe kopieren den Link oder öffnen WhatsApp, LinkedIn oder dein Mailprogramm mit einem fertigen Text und dem Link zur neuen Website – abschicken tust du selbst, die App verschickt nichts. Nach der ersten fertigen Mappe (einmalig), bei der ersten Einladung und bei einer Zusage steht der Vorschlag zusätzlich in der Glückwunsch-Karte.
- **Neue Website:** [emanuelajumobi-ux.github.io/jobmonitor](https://emanuelajumobi-ux.github.io/jobmonitor/) mit Download für Mac und Windows, Beispielen und Installationshilfe.

## 1.3.4

- **Minijobs und Aushilfen:** neue Karrierestufe „Minijob / Aushilfe“ im Einrichtungs-Assistenten und bei den Suchprofilen. Die Suche bei der Bundesagentur liefert dann nur Minijobs, Rollen-Wörter wie „Aushilfe“ oder „geringfügig“ sind vorbelegt, über der Stellenliste stehen passende Filter, und Lebenslauf und Anschreiben nutzen das tabellarische Design „Kompakt“.

## 1.3.3

- **Gemini im Alltag getestet und robuster:** Beim Einrichten prüft die App kurz, welche Gemini-Modelle mit deinem Schlüssel wirklich antworten (neue sind oft überlastet, ältere für neue Nutzer abgeschaltet, „Pro“ ist nicht kostenlos) und wählt diese. Ist ein Modell gerade überlastet, versucht die App es nach kurzer Pause erneut und weicht notfalls auf das zweite Modell aus – das gilt für alle Anbieter außer Claude.

## 1.3.2

- **KI leichter einrichten:** Im Einrichtungs-Assistenten und unter Einstellungen → KI stehen Claude (empfohlen) und Google Gemini (kostenlos) jetzt nebeneinander zur Wahl – mit kurzer Einordnung und direktem Weg zur jeweiligen Anleitung.

## 1.3.1

- **Kostenlos mit Google Gemini:** neue Schritt-für-Schritt-Anleitung (Einstellungen → KI) – ohne Kreditkarte, mit Tagesgrenzen. Ehrlich dazu: Die Ergebnisse sind etwas schwächer als mit Claude.
- **Google Gemini zuverlässiger:** Die Modellliste kommt notfalls über Googles eigene Schnittstelle, und die App schlägt Flash-Modelle vor, die im kostenlosen Kontingent enthalten sind.

## 1.3.0

- **Übungsgespräch:** Unter Bewerbungen → Gespräche (oder auf der Bewerbungsseite) spielt die KI das Vorstellungsgespräch für die konkrete Stelle durch – fünf Fragen, nach jeder Antwort eine kurze Rückmeldung, am Ende eine Zusammenfassung. Auf Wunsch auf Englisch.
- **Neue KI-Helfer:** „Was dein Lebenslauf noch belegt“ und „Lebenslauf-Check“ im Master-CV, „Fit erklärt“ und Antworten auf Freitextfragen aus Bewerbungsportalen auf der Bewerbungsseite, Hinweise an Stellen, die nicht halten, was der Titel verspricht (z. B. „verlangt Berufserfahrung“), und „Muster aus Absagen“ im Rückblick.
- **Günstiger:** Ältere Stellen liest die tägliche Suche jetzt gesammelt über die Batch-Schnittstelle von Anthropic nach – zum halben Preis.
- **Genauerer Fit:** Mit KI entscheidet die KI, was eine Anzeige wirklich verlangt – Stichwort-Treffer wie „Richtlinien“ (wegen „Dokumentation“) oder „Hardware“ (wegen „Clients“) fallen weg, und Anforderungen außerhalb der Begriffsliste (z. B. Java, React, SAP) zählen mit und werden direkt mit deinem Lebenslauf abgeglichen. Ohne KI: aufgeräumte Begriffsliste mit weniger Fehltreffern und neuen Begriffen für Softwareentwicklung. Gespeicherte Stellen werden nach und nach neu bewertet.
- **Eigene Stelle mit KI:** Ist ein KI-Schlüssel hinterlegt, liest die KI auch bei selbst eingefügten Anzeigen die Anforderungen (Pflicht oder Wunsch, Sprachen, Eckdaten) – wie bei den gefundenen Stellen.
- **Windows: schnellerer, sichtbarer Start.** Beim Doppelklick erscheint sofort ein Startbild, bis das Fenster da ist. Die Programmdateien werden nur noch geprüft, wenn Windows sie nach dem Herunterladen neu markiert hat.

## 1.2.2

- **Windows: App-Fenster öffnet sich wieder.** Nach dem Herunterladen markiert Windows die Programmdateien als „aus dem Internet“; dadurch ließ sich das Fenster nicht öffnen. Die App hebt diese Markierung für ihre eigenen Dateien jetzt beim Start auf.
- **Windows: kein Fehler mehr, wenn Git nicht installiert ist** (Synchronisieren wird dann übersprungen).

## 1.2.1

- **Windows: Start abgesichert.** Lässt sich das App-Fenster nicht öffnen (z. B. fehlt die Microsoft-Komponente WebView2), öffnet die App die Oberfläche im Browser, statt still abzubrechen. Andere Fehler beim Start zeigt Windows jetzt als Meldung mit dem Ort der Protokolldatei.

## 1.2.0

- **Passende Firmen finden:** Auf der Seite Firmen stellt die KI eine Liste von Arbeitgebern in deiner Nähe zusammen, die zu Lebenslauf und Suchprofilen passen – auch ohne aktuelle Ausschreibung. Karriereseite prüfen, mit einem Klick hinzufügen.
- **Hell oder dunkel:** unter Einstellungen → Darstellung, unabhängig vom System. Im App-Fenster passt sich auch die Seitenleiste an.
- **Designs groß ansehen:** Ein Klick auf eine Vorschau unter Master-CV → Designs zeigt den ganzen Lebenslauf mit deinen Daten; die Vorschau hat jetzt denselben Seitenrand wie das PDF.
- **Unterstützen:** gut sichtbar unten in der Seitenleiste; ein einmaliger Glückwunsch bei deiner ersten Einladung zum Gespräch.
- **Demo ansehen:** im Einrichtungs-Assistenten die App erst einmal mit erfundenen Beispieldaten ausprobieren – deine eigenen Daten bleiben unberührt.
- **Feedback:** „Fehler melden“ und „Idee vorschlagen“ unter Einstellungen und in der Anleitung (vorausgefülltes GitHub-Issue, ohne persönliche Daten).
- **Filter je Suchprofil:** Über der Stellenliste stehen die Filter, die zur Karrierestufe passen – z. B. „bis 20 h/Woche“ und „Abschlussarbeit möglich“ für Werkstudenten, „Vollzeit“ und „Vergütung angegeben“ für den Berufseinstieg, „Teilzeit möglich“ für Berufserfahrene.
- **Update mit einem Klick:** Beim Hinweis auf eine neue Version lädt „Jetzt aktualisieren“ sie herunter, prüft sie und startet die App neu – deine Daten bleiben. (Ab der nächsten Version nach dieser.)
- **Kein fester Wohnort mehr:** Ohne festgelegten Wohnort nimmt die App nicht mehr stillschweigend Köln an, sondern zählt nur Remote-Stellen und erinnert dich auf der Startseite.

## 1.1.0

- **Alles vorbereiten:** Ein Klick sichert die Anzeige, entwirft das Anschreiben (mit KI), schneidet den Lebenslauf zu und baut die Bewerbungsmappe. Danach liest du alles noch einmal – abgeschickt wird nichts.
- **Kopierhilfe für Bewerbungsportale:** Name, Kontakt, Studium, Verfügbarkeit, Gehaltsvorstellung, Kurzprofil, Motivation und das Anschreiben als Text – je mit Kopieren-Knopf, lange Texte auf die Zeichengrenze des Portals gekürzt (auf Wunsch mit KI).
- **Bewerbung auf Englisch:** Sprache je Bewerbung; die App erkennt englische Anzeigen und schlägt Englisch vor. Die KI übersetzt deinen Master-CV einmal; Lebenslauf und Anschreiben bekommen englische Überschriften, Datum und Grußformel (ohne Foto und Geburtsdatum).
- **Anzeige sichern:** Der Anzeigentext wird im Bewerbungsordner gespeichert und ist auch noch da, wenn die Anzeige offline geht. Text von LinkedIn & Co. lässt sich selbst einfügen.
- **Ziehen und Ablegen:** Zeugnisse, Lebenslauf-PDF und Foto einfach ins Fenster ziehen.
- **Oberfläche auf Englisch:** Einstellungen → Sprache · Language; beim ersten Start in der Sprache des Systems.
- **KI-Anbieter frei wählbar:** neben Claude auch OpenAI, Google Gemini, Mistral und Ollama (kostenlos auf dem eigenen Rechner), mit Schritt-für-Schritt-Anleitung für Claude.
- **Gehaltsvorstellung** im Profil (für Bewerbungsportale).

## 1.0.1

- Erste öffentliche Version für alle Fachrichtungen: Einrichtungs-Assistent, tägliche Suche auf dem eigenen Rechner, PDFs ohne LaTeX, automatische Hinweise auf neue Versionen.
