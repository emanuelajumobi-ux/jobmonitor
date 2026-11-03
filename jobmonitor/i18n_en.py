"""Englische Texte der Oberfläche (i18n.py). Schlüssel: der deutsche Text, wie er auf der Seite steht (Leerraum
zusammengefasst). Fehlende Texte findet JOBMONITOR_I18N_SAMMELN=<datei> (siehe i18n.py)."""

TEXTE: dict[str, str] = {
    # --- Navigation, Grundgerüst ---
    "Übersicht": "Overview", "Stellen": "Jobs", "Bewerbungen": "Applications", "Eigene Stelle": "Own job ad",
    "Rückblick": "Review", "Recherche": "Research", "Firmen": "Companies", "Lücken-Auswertung": "Skill gaps",
    "Letzter Bericht": "Latest report", "Mein Profil": "My profile", "Master-CV": "Master CV", "Profil": "Profile",
    "Unterlagen": "Documents", "System": "System", "Einstellungen": "Settings", "Anleitung": "Guide",
    "Synchronisieren": "Sync", "Beenden": "Quit", "Bitte warten …": "Please wait …", "Job-Monitor": "Job-Monitor",
    "Hilfe zu dieser Seite": "Help for this page", "Bewerbung": "Application", "Bericht": "Report",
    "Dateien": "Files", "Start": "Start", "Beendet": "Closed", "Wird beendet …": "Closing …",
    "Synchronisiere mit GitHub.": "Syncing with GitHub.",
    "Synchronisiere mit GitHub …": "Syncing with GitHub …", "Du kannst dieses Fenster schließen.":
        "You can close this window.", "Traumprofil": "Dream profile", "Weiter": "Next", "Zurück": "Back",
    "Abbrechen": "Cancel", "Speichern": "Save", "Übernehmen": "Apply", "Bearbeiten": "Edit", "Ersetzen": "Replace",
    "Hinzufügen": "Add", "Hochladen": "Upload", "entfernen": "remove", "Entfernen": "Remove", "Verwerfen": "Discard",
    "Wechseln": "Switch", "Ausprobieren": "Try it", "Herunterladen": "Download", "Kopieren": "Copy",
    "Ignorieren": "Ignore", "Ausblenden": "Hide", "Ausschließen": "Exclude", "Merken": "Save for later",
    "Bewerben": "Apply", "Erinnern": "Remind", "einschalten": "turn on", "ausschalten": "turn off",
    "deaktivieren": "deactivate", "Noch nichts.": "Nothing yet.", "Noch keine Einträge.": "No entries yet.",
    "✓ erledigt": "✓ done", "offen": "open", "sonstige": "other", "Alle": "All", "Alle ›": "All ›",
    "Auswertung ›": "Analysis ›", "Oder": "Or", "oder": "or", "und": "and", "Uhr": "",
    "Deutsch": "German", "Englisch": "English", "English": "English",

    # --- Monate (Diagramme) ---
    "Mär": "Mar", "Mai": "May", "Okt": "Oct", "Dez": "Dec",

    # --- Stellenliste / Startseite ---
    "Heute bewerben": "Apply today", "Stellen filtern": "Filter jobs", "Stellen durchsuchen": "Search jobs",
    "Titel, Firma, Skill oder ID": "Title, company, skill or ID", "Nach Eckdaten filtern": "Filter by key facts",
    "bis 20 h/Woche": "up to 20 h/week", "Remote möglich": "Remote possible",
    "Abschlussarbeit möglich": "Thesis possible", "Nach Fit": "By fit", "Eckdaten": "Key facts",
    "Eckdaten laut Anzeige (von der KI gelesen)": "Key facts from the ad (read by the AI)",
    "Fit, Frist und Frische zusammen": "Fit, deadline and freshness combined",
    "frisch – früh bewerben lohnt sich": "fresh – applying early pays off", "Neue Version": "New version",
    "Zu wenig Angaben in der Anzeige": "Too little information in the ad",
    "Zu wenig Angaben in der Anzeige für einen Fit": "Too little information in the ad for a fit score",
    "keine Anforderungen erkannt": "no requirements detected", "Darauf vorbereiten": "Prepare for it",
    "Lebenslauf für diese Stelle": "CV for this job", "nur Cloud Security": "Cloud Security only",
    "Neue Stellen – Junior": "New jobs – Junior", "Neue Stellen – Werkstudent": "New jobs – Working student",
    "Keine neuen passenden Junior-Stellen seit dem letzten Lauf.":
        "No new matching junior jobs since the last run.",
    "Fit-Begriffe, die dein Lebenslauf belegt": "Fit terms your CV covers",
    "nicht belegt – anklicken zum Eintragen": "not covered – click to add", "Kann ich schon:": "I can already do:",
    "Habe ich:": "I have:", "gefordert in": "required in", "fehlt dir": "you are missing",
    "in den Lebenslauf": "into the CV", "Als geplant übernehmen": "Add as planned",
    "hat gerade passende Stellen – lieber direkt bewerben": "currently has matching jobs – better apply directly",
    "Erste Suche starten": "Start the first search", "Fertig – zur Stellenliste": "Done – to the job list",

    # --- Bewerbungsseite ---
    "Alles vorbereiten": "Prepare everything",
    "Anzeige sichern, Anschreiben mit KI entwerfen, Lebenslauf zuschneiden und die Mappe bauen – in einem Schritt. "
    "Danach liest du alles noch einmal; abgeschickt wird nichts.":
        "Save the ad, draft the cover letter with AI, tailor the CV and build the application PDF – in one step. "
        "Afterwards you read everything once more; nothing is sent.",
    "Anzeige sichern, Lebenslauf zuschneiden und die Mappe bauen – in einem Schritt. Danach liest du alles noch "
    "einmal; abgeschickt wird nichts.":
        "Save the ad, tailor the CV and build the application PDF – in one step. Afterwards you read everything "
        "once more; nothing is sent.",
    "KI bereitet die Bewerbung vor …": "AI is preparing the application …", "Anzeige": "Ad",
    "Noch keine PDFs gebaut.": "No PDFs built yet.", "Ordner im Finder zeigen": "Show folder in Finder",
    "Stelle auch ausblenden": "Also hide the job", "Bewerbung verwerfen": "Discard application",
    "Bewerbung verwerfen? Der Ordner mit Anschreiben und PDFs wandert in den Papierkorb.":
        "Discard application? The folder with cover letter and PDFs goes to the trash.",
    "Anrede (Ansprechperson nur, wenn die Firma sie selbst für Bewerbungen nennt)":
        "Salutation (contact person only if the company names them for applications)",
    "Empfänger unter dem Firmennamen (optional, z. B. Abteilung, Straße, PLZ Ort – eine Zeile je Zeile)":
        "Recipient below the company name (optional, e.g. department, street, postcode city – one per line)",
    "Text (Absätze durch Leerzeile trennen; Gruß und Name ergänzt das PDF)":
        "Text (separate paragraphs with a blank line; the PDF adds closing and name)",
    "Anlagen für die Mappe": "Attachments for the application PDF", "Unterlagen hochladen": "Upload documents",
    "(landen in cv/private/, gitignored).": "(stored in cv/private/, gitignored).",
    "Speichern und Mappe bauen": "Save and build application PDF", "Nur Anschreiben-PDF": "Cover letter PDF only",
    "Nur Lebenslauf": "CV only", "Nur speichern": "Save only", "Neuer Entwurf aus Vorlage": "New draft from template",
    "Text durch einen neuen Entwurf aus der Vorlage ersetzen?":
        "Replace the text with a new draft from the template?",
    "Entwurf mit KI": "Draft with AI",
    "Text durch einen KI-Entwurf ersetzen? Gesendet werden die Anzeige und dein Master-CV, keine persönlichen Daten.":
        "Replace the text with an AI draft? The ad and your master CV are sent, no personal data.",
    "KI schreibt das Anschreiben …": "AI is writing the cover letter …",
    "KI schneidet den Lebenslauf auf die Stelle zu …": "AI is tailoring the CV to the job …",
    "Anschreiben": "Cover letter", "Design": "Design",
    "alle Designs ansehen": "see all designs",
    "Einspaltig und schlicht (Harvard-Stil). Gilt für Lebenslauf und Anschreiben dieser Bewerbung; neu bauen, damit "
    "die PDFs es übernehmen.": "Single column and plain (Harvard style). Applies to CV and cover letter of this "
                               "application; rebuild so the PDFs pick it up.",
    "Klassisch": "Classic", "Modern": "Modern", "Kreativ": "Creative", "Kompakt": "Compact",
    "Akademisch": "Academic",
    "Klassisch – IT, Ingenieurwesen, Beratung, Finanzen, öffentlicher Dienst":
        "Classic – IT, engineering, consulting, finance, public sector",
    "Modern – IT, Startups, Marketing, Vertrieb": "Modern – IT, startups, marketing, sales",
    "Kreativ – Design, Medien, Kommunikation, Architektur": "Creative – design, media, communication, architecture",
    "Kompakt – Ausbildung, Pflege, Handwerk, Verwaltung, Handel":
        "Compact – apprenticeships, care, trades, administration, retail",
    "Akademisch – Abschlussarbeiten, Forschung, Promotion": "Academic – theses, research, PhD",
    "IT, Ingenieurwesen, Beratung, Finanzen, öffentlicher Dienst":
        "IT, engineering, consulting, finance, public sector",
    "IT, Startups, Marketing, Vertrieb": "IT, startups, marketing, sales",
    "Design, Medien, Kommunikation, Architektur": "Design, media, communication, architecture",
    "Ausbildung, Pflege, Handwerk, Verwaltung, Handel": "Apprenticeships, care, trades, administration, retail",
    "Abschlussarbeiten, Forschung, Promotion": "Theses, research, PhD",
    "Sprache der Bewerbung": "Language of the application",
    "Die Anzeige ist auf Englisch.": "The ad is in English.",
    "Internationale Firmen erwarten dann meist auch Lebenslauf und Anschreiben auf Englisch.":
        "International companies then usually expect CV and cover letter in English too.",
    "Für Englisch fehlt noch die englische Fassung deines Master-CV (cv/cv_master.en.yaml). Die KI übersetzt ihn "
    "einmal, danach kannst du ihn unter Dateien anpassen. Ohne Übersetzung nutzt der Lebenslauf die deutschen "
    "Inhalte.": "For English, the English version of your master CV (cv/cv_master.en.yaml) is still missing. The AI "
                "translates it once; afterwards you can adjust it under Files. Without a translation the CV uses "
                "the German content.",
    "Master-CV mit KI übersetzen": "Translate master CV with AI", "KI einrichten": "Set up AI",
    "KI übersetzt deinen Lebenslauf …": "AI is translating your CV …",
    "Inhalte aus cv/cv_master.en.yaml ·": "Content from cv/cv_master.en.yaml ·",
    "unter Dateien anpassen": "adjust under Files",
    ". Englische Lebensläufe ohne Foto und Geburtsdatum.": ". English CVs without photo and date of birth.",
    "Gesicherte Anzeige": "Saved job ad", "Anzeige sichern": "Save the ad", "Jetzt sichern": "Save now",
    "Anzeigen verschwinden oft, bevor das Gespräch stattfindet. Gesichert liegt der Text im Bewerbungsordner – für "
    "die Gesprächsvorbereitung und zum Nachlesen. „Alles vorbereiten“ und „Mappe bauen“ sichern ihn automatisch.":
        "Ads often disappear before the interview. Once saved, the text stays in the application folder – for "
        "interview preparation and to look things up. “Prepare everything” and “Build application PDF” save it "
        "automatically.",
    "Oder Text selbst einfügen (z. B. von LinkedIn, das die App nicht abruft)":
        "Or paste the text yourself (e.g. from LinkedIn, which the app does not fetch)",
    "Text speichern": "Save text", "Text ersetzen": "Replace text",
    "Neuen Anzeigentext einfügen, um den gesicherten zu ersetzen": "Paste a new ad text to replace the saved one",
    "Für Bewerbungsportale": "For application portals", "– Felder zum Kopieren": "– fields to copy",
    "Für Online-Formulare: Wert kopieren und im Portal einfügen. Lange Texte sind auf die gewählte Grenze gekürzt; "
    "du kannst sie hier noch anpassen, bevor du kopierst. Abgeschickt wird nichts.":
        "For online forms: copy a value and paste it into the portal. Long texts are shortened to the chosen limit; "
        "you can still adjust them here before copying. Nothing is sent.",
    "Zeichengrenze der Textfelder": "Character limit of text fields", "Vorname": "First name",
    "Nachname": "Last name", "E-Mail": "Email", "Telefon": "Phone", "Straße": "Street", "PLZ": "Postcode",
    "Ort": "City", "Studium / Abschluss": "Studies / degree", "Aktuelle Tätigkeit": "Current position",
    "Verfügbarkeit (ab wann, Stunden)": "Availability (from when, hours)", "Gehaltsvorstellung": "Salary expectation",
    "Sprachen": "Languages", "Kenntnisse": "Skills", "Kurzprofil": "Short profile",
    "Motivation (aus dem Anschreiben)": "Motivation (from the cover letter)",
    "Anschreiben als Text (für Textfelder statt PDF-Upload)": "Cover letter as text (for text fields instead of PDF upload)",
    "Mit KI kürzen": "Shorten with AI", "KI kürzt den Text …": "AI is shortening the text …",
    "· an der Satzgrenze gekürzt": "· shortened at a sentence boundary", "· mit KI gekürzt": "· shortened with AI",
    "mit KI gekürzt": "shortened with AI", "an der Satzgrenze gekürzt": "shortened at a sentence boundary",
    "Fehlt etwas (z. B. Gehaltsvorstellung)? Unter": "Something missing (e.g. salary expectation)? Add it under",
    "ergänzen.": ".", "Vor dem Abschicken": "Before sending",
    "Anschreiben mit KI prüfen": "Check cover letter with AI",
    "Anschreiben von der KI durchsehen lassen? Gesendet werden der Anschreiben-Text und die Anzeige, keine "
    "persönlichen Daten aus profile.yaml.": "Have the AI review the cover letter? The cover letter text and the ad "
                                            "are sent, no personal data from profile.yaml.",
    "KI liest dein Anschreiben …": "AI is reading your cover letter …",
    "Firma, Stelle und Anrede im Anschreiben passen zur Anzeige":
        "Company, job and salutation in the cover letter match the ad",
    "Rechtschreibung, Floskeln, Länge, Bezug zur Stelle": "Spelling, empty phrases, length, relation to the job",
    "Anzeige noch online?": "Ad still online?",
    "Noch keine Mappe gebaut („Speichern und Mappe bauen“)":
        "No application PDF built yet (“Save and build application PDF”)",
    "Selbst abschicken, dann": "Send it yourself, then", "den Status auf": "set the status to", "setzen.": ".",
    "Über das Portal oder per Mail selbst abschicken, dann in": "Send it yourself via the portal or by email, then in",
    "Anlage fehlt: Immatrikulationsbescheinigung (Unterlagen hochladen)":
        "Attachment missing: enrolment certificate (upload documents)",
    "Deine Bewerbungsordner": "Your application folders",
    "Gespeichert.": "Saved.", "Anzeigentext gespeichert.": "Ad text saved.",
    "Anzeige im Bewerbungsordner gesichert.": "Ad saved in the application folder.",
    "Bitte den Anzeigentext einfügen.": "Please paste the ad text.",
    "Neuer Entwurf aus der Vorlage.": "New draft from the template.",
    "Prüfung des Lebenslaufs": "CV check", "Prüfung des Anschreibens": "Cover letter check",
    "Warnung:": "Warning:", "Tipp:": "Tip:",

    # --- Bewerbungen ---
    "Deine Liste (applications.csv) · wird automatisch synchronisiert":
        "Your list (applications.csv) · synced automatically",
    "Filtern nach Firma, Notiz oder Status": "Filter by company, note or status", "Status:": "Status:",
    "Gespräche": "Interviews", "Nachfassen": "Follow up", "Antworten von Firmen": "Replies from companies",
    "Antwort bekommen": "Got a reply", "Als nachgefasst markieren": "Mark as followed up",
    "Mit KI formulieren": "Phrase with AI", "Firmenprofil": "Company profile", "Gespräch vorbereiten": "Prepare interview",
    "Bewerbungsliste": "Application list", "Beworben": "Applied", "beworben": "applied", "Zusage": "Offer",
    "Noch keine Bewerbungen.": "No applications yet.", "laut Postfach": "according to mailbox",
    "mit Antwort der Firma": "with reply from the company", "mit Termin": "with appointment",
    "In deine Liste übernommen": "Added to your list", "Nachfrage-Vorlage": "Follow-up template",

    # --- Rückblick ---
    "Stand deiner Bewerbungen": "Status of your applications", "Bewerbungen je Woche": "Applications per week",
    "Rücklauf": "Response rate", "Ø bis zur Antwort": "Avg. time to reply", "Letzte 8 Wochen": "Last 8 weeks",
    "seit Beginn": "since the start", "Woher deine Bewerbungen kommen": "Where your applications come from",
    "Woher passende Stellen kommen": "Where matching jobs come from",
    "Passende Stellen gefunden (8 Wochen)": "Matching jobs found (8 weeks)",
    "Wie deine Bewerbungsphase läuft – aus deiner Liste, den erkannten Antworten und den gefundenen Stellen.":
        "How your application phase is going – from your list, the detected replies and the jobs found.",
    "Noch keine Bewerbungen mit Datum. Setz den Status auf „beworben“, dann zählt sie hier.":
        "No applications with a date yet. Set the status to “applied” and it counts here.",
    "Vom Fund zur Zusage": "From find to offer", "Anteil der Stellen je Monat": "Share of jobs per month",
    "Gefragt im Verlauf": "Demand over time",

    # --- Lücken ---
    "Häufigste Lücken": "Most common gaps", "Begriff": "Term", "Begriffe": "Terms", "Ø-Fit-Gewinn": "Avg. fit gain",
    "Lernvorschläge": "Learning suggestions", "Lernplan": "Learning plan",
    "Lernplan mit KI erstellen": "Create learning plan with AI", "KI erstellt deinen Lernplan …":
        "AI is creating your learning plan …",
    "Aus deinen teuersten Lücken und deinem Master-CV.": "From your most costly gaps and your master CV.",
    "Was alle gefundenen Stellen verlangen (ohne ausgeblendete).": "What all jobs found require (excluding hidden).",
    "Fit-Begriffe": "Fit terms", "Eigener Begriff": "Own term",
    "Andere Schreibweisen (optional, mit Komma)": "Other spellings (optional, comma-separated)",
    "Alle Fit-Begriffe als Datei bearbeiten": "Edit all fit terms as a file",
    "Gerade keine neuen Vorschläge der KI.": "No new AI suggestions right now.",
    "Damit der Fit erkennt, was solche Anzeigen verlangen. Ob du es kannst, kommt weiter aus deinem Master-CV. Die "
    "Begriffe gelten für alle Stellen, sie machen den Fit nur genauer.":
        "So the fit recognises what such ads require. Whether you can do it still comes from your master CV. The "
        "terms apply to all jobs; they only make the fit more precise.",
    "Kannst du etwas schon, das hier fehlt? Ein Klick auf das Level trägt es als Kenntnis in deinen Master-CV ein "
    "(passende Kategorie, alter Stand bleibt als .bak). Bitte ehrlich – das Level fließt in den Fit ein.":
        "Can you already do something that is missing here? One click on the level adds it as a skill to your "
        "master CV (matching category, the old version stays as .bak). Please be honest – the level feeds into the "
        "fit.",
    "Vorschläge für die Lücken, die dich am meisten Fit kosten (aus lernpfade.yaml, frei erweiterbar). „Als geplant "
    "übernehmen“ trägt den Eintrag mit Status geplant in deinen Master-CV ein – er zählt erst für den Fit und "
    "erscheint erst im Lebenslauf, wenn du ihn auf in Arbeit/erreicht setzt. Prüfungsdetails vor dem Buchen beim "
    "Anbieter nachsehen.": "Suggestions for the gaps that cost you the most fit (from lernpfade.yaml, freely "
                           "extendable). “Add as planned” adds the entry with status planned to your master CV – it "
                           "only counts for the fit and appears in the CV once you set it to in progress/achieved. "
                           "Check exam details with the provider before booking.",
    ". Die Spalte „Ø-Fit-Gewinn“ zeigt, um wie viele Prozentpunkte dein Durchschnitt steigen würde, wenn du den "
    "Begriff mit diesem Level im Master-CV belegst (z. B. durch ein Projekt, ein Zertifikat oder Praxis).":
        ". The column “Avg. fit gain” shows by how many percentage points your average would rise if your master CV "
        "covered the term at this level (e.g. through a project, a certificate or practice).",

    # --- Eigene Stelle ---
    "Stellen, die der Monitor nicht gefunden hat: Text oder Link einfügen, Fit prüfen, Lebenslauf bauen.":
        "Jobs the monitor did not find: paste text or link, check fit, build CV.",
    "Firma (Pflicht)": "Company (required)",
    "Anzeigentext (einfach aus der Anzeige kopieren, erste Zeile = Titel)":
        "Ad text (just copy it from the ad, first line = title)",
    "… oder Link zur Anzeige (nur Firmen-Karriereseiten, nicht LinkedIn/StepStone/Indeed)":
        "… or link to the ad (company career pages only, not LinkedIn/StepStone/Indeed)",
    "Link für die Bewerbungsliste (optional, bei Text)": "Link for the application list (optional, with text)",
    "Fit prüfen und Lebenslauf erstellen": "Check fit and create CV",
    "Werkstudent Cloud (m/w/d) Deine Aufgaben: …": "Working student Cloud (m/f/d) Your tasks: …",
    "Allgemeiner Lebenslauf": "General CV",

    # --- Profil und Unterlagen ---
    "cv/profile.yaml · nur auf deinem Mac (gitignored, wird nie hochgeladen).":
        "cv/profile.yaml · only on your computer (gitignored, never uploaded).",
    "Kontakt und Briefkopf": "Contact and letterhead", "Name": "Name",
    "Straße und Hausnummer": "Street and house number", "Geburtsdatum": "Date of birth",
    "LinkedIn (optional)": "LinkedIn (optional)", "GitHub (optional)": "GitHub (optional)",
    "Studium für Anschreiben (optional, sonst aus dem Master-CV)":
        "Studies for cover letters (optional, otherwise from the master CV)",
    "Zeitraum für Anschreiben, z. B. „ab März 2027 mit 20 Stunden pro Woche“":
        "Availability for cover letters, e.g. “from March 2027, 20 hours per week”",
    "Gehaltsvorstellung für Bewerbungsportale (optional), z. B. „16 € pro Stunde“":
        "Salary expectation for application portals (optional), e.g. “€16 per hour”",
    "Was im Lebenslauf erscheint": "What appears in the CV", "Adresse": "Address", "Foto": "Photo",
    "· wird angezeigt": "· shown", "· ausgeblendet": "· hidden", "Noch kein Foto.": "No photo yet.",
    "Noch kein Foto. Hochladen unter": "No photo yet. Upload under", "Hochladen unter": "Upload under",
    "Änderungen verwerfen": "Discard changes",
    "Für die Bewerbungsmappe · alles bleibt lokal in cv/private/ (gitignored).":
        "For the application PDF · everything stays local in cv/private/ (gitignored).",
    "Notenübersicht": "Transcript of records", "Immatrikulationsbescheinigung": "Enrolment certificate",
    "Zeugnisse und Zertifikate": "References and certificates", "Bewerbungsfoto": "Application photo",
    "Noch nichts hochgeladen.": "Nothing uploaded yet.", "Ein PDF; ein neuer Upload ersetzt das alte.":
        "One PDF; a new upload replaces the old one.",
    "Mehrere PDFs möglich. Reihenfolge wie in der Mappe, automatisch: erst Zeugnisse, dann Zertifikate mit Nachweis "
    "aus dem Master-CV, neueste zuerst.": "Several PDFs possible. Order as in the application PDF, automatic: first "
                                         "references, then certificates with proof from the master CV, newest first.",
    "Foto hochladen": "Upload photo", "JPG oder PNG. Ob es im Lebenslauf erscheint, stellst du im":
        "JPG or PNG. Whether it appears in the CV is set in your", "ein.": ".", "im Master-CV verknüpft":
        "linked in the master CV", "oder Datei hierher ziehen": "or drag a file here",

    # --- Master-CV ---
    "cv/cv_master.yaml · nur Nicht-Persönliches (Kontaktdaten und Foto stehen in cv/profile.yaml).":
        "cv/cv_master.yaml · non-personal content only (contact details and photo are in cv/profile.yaml).",
    "Profiltext mit KI vorschlagen": "Suggest profile text with AI",
    "KI schlägt einen Profiltext vor …": "AI is suggesting a profile text …",
    "Aus deinen Einträgen; ersetzt den Text im Feld Profil, gespeichert wird erst mit Speichern":
        "From your entries; replaces the text in the Profile field, saved only with Save",
    "Designs für Lebenslauf und Anschreiben": "Designs for CV and cover letter",
    "Gleicher Inhalt, anderes Aussehen. Das Design wählst du je Suchprofil (Einstellungen) oder je Bewerbung. "
    "„Gestaltete“ Designs (Spalten, Farbflächen) lesen Bewerbungssysteme großer Firmen teils schlechter – die "
    "Prüfung vor dem Abschicken weist darauf hin.": "Same content, different look. You choose the design per search "
                                                     "profile (Settings) or per application. Applicant tracking "
                                                     "systems of large companies sometimes read “designed” layouts "
                                                     "(columns, colour areas) less well – the check before sending "
                                                     "points this out.",
    "· gut maschinenlesbar": "· machine-readable", "· gestaltet": "· designed",
    "Durchgestrichen = nicht belegt. Einträge mit Status „geplant“ zählen nicht. Kannst du einen durchgestrichenen "
    "Begriff schon? Anklicken, Level wählen – er landet in der passenden Kategorie unter Kenntnisse.":
        "Struck through = not covered. Entries with status “planned” do not count. Can you already do a struck-through "
        "term? Click it, choose a level – it lands in the matching category under Skills.",
    "Ausbildung": "Education", "Berufserfahrung": "Work experience", "Projekte": "Projects",
    "Zertifikate": "Certifications", "Interessen": "Interests", "Stationen": "Positions",
    "Grundkenntnisse": "Basic knowledge", "gut": "good", "sehr gut": "very good", "geplant": "planned",
    "in Arbeit": "in progress", "erreicht": "achieved", "Kategorie": "Category",

    # --- Firmen ---
    "Firmen und Hochschulbörsen": "Companies and university job boards", "Firma hinzufügen": "Add company",
    "Filtern nach Name, Kategorie, Branche oder Ort": "Filter by name, category, industry or city",
    "Name (Pflicht)": "Name (required)", "Branche (optional)": "Industry (optional)",
    "Standorte (mit Komma getrennt)": "Locations (comma-separated)", "Fokus (mit Komma getrennt)":
        "Focus (comma-separated)", "Karriereseite (Pflicht, am besten die Seite mit der Stellenliste)":
        "Career page (required, ideally the page with the job list)", "Besucht": "Visited",
    "noch nicht besucht": "not visited yet", "Manuell prüfen": "Check manually", "manuell prüfen": "check manually",
    "Selbst ansehen": "Look yourself", "Seite öffnen": "Open page", "Quellen beobachten": "Watch sources",
    "Initiativ-Bewerbungen": "Speculative applications", "Initiativ-Entwürfe": "Speculative drafts",
    "Initiativ-Seite": "Speculative application page", "Initiativ: ja": "Speculative: yes",
    "Initiativ: unbekannt": "Speculative: unknown", "Vorschläge aus deinen Treffern": "Suggestions from your matches",
    "Vorschläge für Firmen ohne passende Stelle": "Suggestions for companies without a matching job",
    "Quelle: wird erkannt": "Source: detected automatically", "Hochschulbörsen": "University job boards",
    "Firmen-Karriereseiten": "Company career pages", "Firmenseiten": "Company pages", "Quellen": "Sources",
    "Diese Seiten lassen sich nicht automatisch lesen.": "These pages cannot be read automatically.",
    "Diese Karriereseiten kann das Tool nicht automatisch lesen. Schau etwa alle 14 Tage selbst vorbei und klick "
    "danach auf „Besucht“.": "The tool cannot read these career pages automatically. Look yourself about every 14 days "
                             "and then click “Visited”.",
    "Liefern seit mehreren Läufen der Pipeline nichts mehr oder nur Fehler. Meist ist die Karriereseite umgezogen.":
        "Have returned nothing or only errors for several pipeline runs. Usually the career page has moved.",
    "Firmen, die in gefundenen Stellen vorkommen, aber noch nicht in deiner Liste stehen. Prüf die Karriereseite, "
    "bevor du hinzufügst.": "Companies that appear in jobs found but are not on your list yet. Check the career page "
                            "before adding.",
    "Firmen aus deinen Treffern schlägt die Seite außerdem vor.": "The page also suggests companies from your matches.",
    "Firmen in Reichweite, die Initiativbewerbungen annehmen (companies.yaml: initiativ.moeglich ja). Der Bericht nennt "
    "nur neu dazugekommene. Wichtige Kategorien zuerst, Firmen mit passenden Stellen am Ende.":
        "Companies within reach that accept speculative applications (companies.yaml: initiativ.moeglich yes). The "
        "report only lists new ones. Important categories first, companies with matching jobs at the end.",
    "Stellenquelle (ATS) und Initiativ-Seite erkennt die Pipeline beim nächsten Lauf selbst – mit robots.txt-Prüfung. "
    "Ansprechpersonen nur eintragen, wenn die Firma sie selbst für Bewerbungen nennt.":
        "The pipeline detects the job source (ATS) and speculative application page itself on the next run – with a "
        "robots.txt check. Only enter contact persons if the company names them for applications itself.",
    "Ändern oder löschen (z. B. neue Karriereseite, Warnhinweis, Initiativ-Status): als Datei bearbeiten. Vor dem "
    "Speichern wird geprüft; der alte Stand bleibt als .bak daneben.":
        "Change or delete (e.g. new career page, warning, speculative status): edit as a file. It is checked before "
        "saving; the old version stays next to it as .bak.",
    "Als Datei bearbeiten": "Edit as file", "Seite blockiert automatische Abrufe (HTTP 403)":
        "Page blocks automatic requests (HTTP 403)", "keine maschinenlesbaren Stellen gefunden":
        "no machine-readable jobs found", "Neue Firma": "New company", "z. B. IT-Beratung": "e.g. IT consulting",
    "https://firma.de/karriere/jobs": "https://company.com/careers/jobs",
    "https://firma.de/jobs/…": "https://company.com/jobs/…",

    # --- Bericht ---
    "Automatisch erzeugt. Es wurden keine Bewerbungen oder Mails an Firmen verschickt.":
        "Generated automatically. No applications or emails were sent to companies.",
    "Berichte": "Reports", "Ein Bericht je Suchtag.": "One report per search day.", "alle Quellen": "all sources",
    "Rohtreffer": "Raw hits", "Mail-Alerts": "Mail alerts", "Job-Alert-Mails": "Job alert emails",

    # --- Einstellungen ---
    "Suche: Rhythmus und Modus": "Search: rhythm and mode", "Aktiv suchen": "Search actively", "Ruhemodus": "Rest mode",
    "Angehalten": "Paused", "Suche": "Search", "Zeitplan": "Schedule", "Wohnort": "Home location",
    "Postfach verbinden": "Connect mailbox", "Mitteilungen": "Notifications", "Suchprofile": "Search profiles",
    "Neues Suchprofil": "New search profile", "Suchprofil": "Search profile", "Suchprofil ·": "Search profile ·",
    "Probelauf auf diesem Rechner": "Test run on this computer", "Probelauf starten": "Start test run",
    "Dateien bearbeiten": "Edit files", "Sicherung": "Backup", "Sicherung erstellen": "Create backup",
    "Noch keine Sicherung.": "No backup yet.", "App und Wartung": "App and maintenance",
    "Oberfläche": "Interface", "Sprache der Oberfläche": "Interface language",
    "Wenn du gerade keinen Job suchst: Ruhemodus. Gilt ab dem nächsten Lauf. Gefundene Stellen, Bewerbungen und "
    "Einstellungen bleiben erhalten.": "If you are not looking for a job right now: rest mode. Applies from the next "
                                       "run. Jobs found, applications and settings are kept.",
    "Einmal pro Woche suchen, damit die Firmenliste gepflegt bleibt und du früh siehst, wenn eine Quelle nicht mehr "
    "funktioniert. Kein Postfach, keine Mitteilungen.": "Search once a week so the company list stays maintained and "
                                                         "you notice early when a source stops working. No mailbox, "
                                                         "no notifications.",
    "Die Pipeline startet weiter jeden Morgen, hört aber sofort wieder auf. Nichts wird abgefragt. „Lauf jetzt "
    "starten“ sucht trotzdem einmal.": "The pipeline still starts every morning but stops right away. Nothing is "
                                      "queried. “Start run now” still searches once.",
    "Beim Zurückschalten auf „Aktiv“ zeigt die Startseite eine kurze Checkliste für den Neustart.":
        "When switching back to “Active”, the start page shows a short checklist for restarting.",
    "Täglich automatisch suchen (auf diesem Rechner)": "Search automatically every day (on this computer)",
    "Mac und Windows tragen die Suche in die Aufgabenplanung des Systems ein; verpasste Termine holt die App nach, "
    "sobald sie offen ist.": "Mac and Windows add the search to the system scheduler; the app catches up on missed "
                             "runs as soon as it is open.",
    "Läuft deine Suche über GitHub Actions, ist der lokale Zeitplan nicht nötig.":
        "If your search runs via GitHub Actions, the local schedule is not needed.",
    "Verpasste Termine (Rechner aus oder im Ruhezustand) holt die App nach, sobald sie läuft. Den Bericht findest du "
    "unter „Letzter Bericht“.": "The app catches up on missed runs (computer off or asleep) as soon as it runs. You "
                               "find the report under “Latest report”.",
    "Täglich suchen": "Search daily", "Täglich benachrichtigen": "Notify daily",
    "Aus: Die Suche läuft nur, wenn du sie startest.": "Off: the search only runs when you start it.",
    "Wohnort und Fahrzeit": "Home location and travel time", "z. B. Leipzig": "e.g. Leipzig",
    "z. B. München": "e.g. Munich", "Fahrzeiten mit KI erstellen": "Create travel times with AI",
    "KI schätzt die Fahrzeiten …": "AI is estimating travel times …",
    "Gesendet wird nur der Städtename. Die Minuten sind Schätzungen; ändert auch den Suchort der Bundesagentur.":
        "Only the city name is sent. The minutes are estimates; this also changes the search location of the "
        "Federal Employment Agency.",
    "Mit KI werden die Fahrzeiten in die Umgebung geschätzt; zählen tun Stellen bis zur eingestellten Fahrzeit und "
    "remote.": "With AI, travel times to the surrounding area are estimated; jobs up to the set travel time and remote "
               "jobs count.",
    "· eingebaute Tabelle für Köln und Umgebung.": "· built-in table for Cologne and surroundings.",
    "Mitteilung bei neuen Stellen": "Notification for new jobs", "Probe-Mitteilung senden": "Send test notification",
    "· keine Mitteilungen": "· no notifications",
    "Statt eines Berichts per Mail: eine Mitteilung von Job-Monitor auf diesem Mac, z. B. „3 neue Stellen · "
    "Werkstudent Cloud – adesso · Fit 85 %“. Dazu je eine eigene Mitteilung für sehr gut passende Stellen (ab Fit "
    "75 % oder Traumprofil) und für neue Antworten von Firmen. Ein Klick öffnet die App. Ohne Neues kommt nichts; "
    "schläft der Mac zur Uhrzeit, kommt sie beim Aufwachen.":
        "Instead of a report by email: a notification from Job-Monitor on this computer, e.g. “3 new jobs · Working "
        "student Cloud – adesso · Fit 85 %”. Plus a separate notification for very well matching jobs (fit 75 % or "
        "more, or dream profile) and for new replies from companies. One click opens the app. Without news nothing "
        "comes; if the computer is asleep at that time, it comes when it wakes up.",
    "E-Mail-Adresse": "Email address", "App-Passwort": "App password",
    "IMAP-Server (nur bei „Anderer Anbieter“)": "IMAP server (only for “Other provider”)",
    "Anderer Anbieter": "Other provider", "Verbinden und testen": "Connect and test", "Anbieter": "Provider",
    "Bericht per Mail": "Report by email", "Bericht täglich mailen": "Email the report daily",
    "schickt dir den Bericht an deine eigene Adresse.": "sends the report to your own address.",
    "Versand aus der GitHub-Pipeline": "Sending from the GitHub pipeline",
    "Erkennen von Eingangsbestätigung, Einladung, Absage im Postfach":
        "Detect acknowledgements, invitations and rejections in the mailbox",
    "Damit liest die App Job-Alerts (z. B. von StepStone oder LinkedIn) und erkennt Antworten von Firmen. Nur lesen, "
    "nie senden. Du brauchst ein": "With this, the app reads job alerts (e.g. from StepStone or LinkedIn) and detects "
                                   "replies from companies. Read only, never send. You need an",
    "deines Anbieters, nicht dein normales Passwort.": "from your provider, not your normal password.",
    "deines Anbieters eintragen (nicht dein normales Passwort).": "from your provider (not your normal password).",
    ". Outlook/Hotmail geht nicht (Microsoft erlaubt keine Passwort-Anmeldung mehr). Das Passwort liegt im "
    "Schlüsselbund des Rechners.": ". Outlook/Hotmail does not work (Microsoft no longer allows password sign-in). The "
                                   "password is stored in the computer's keychain.",
    "Outlook und Microsoft 365 erlauben keine Anmeldung per Passwort mehr – dort die Alerts an ein anderes Postfach "
    "weiterleiten.": "Outlook and Microsoft 365 no longer allow password sign-in – forward the alerts to another "
                     "mailbox there.",
    "App-Passwort anlegen:": "Create an app password:",
    "Einstellungen der Suche": "Search settings", "Quellen, Filter, Ausschlüsse, Fit-Begriffe, Ort, KI, Lebenslauf "
    "und Designs – alles, was die tägliche Suche steuert.": "Sources, filters, exclusions, fit terms, location, AI, CV "
                                                          "and designs – everything that controls the daily search.",
    "Bundesagentur, Hochschulbörsen, Arbeitnow, Firmenseiten, Job-Alert-Mails ein- und ausschalten":
        "Turn the Federal Employment Agency, university job boards, Arbeitnow, company pages and job alert emails on "
        "and off",
    "Filter und Ausschlüsse": "Filters and exclusions",
    "Mindest-Score, Fach-Wörter, Titel und Firmen, die rausfliegen":
        "Minimum score, subject words, titles and companies that are excluded",
    "Fit-Bewertung": "Fit rating", "Fit-Begriffe mit Synonymen und Gewichte der Kenntnis-Level":
        "Fit terms with synonyms and weights of the skill levels",
    "maximale Fahrzeit, Punkte je Entfernung, Remote": "maximum travel time, points per distance, remote",
    "Modell und Monatslimit für Aufrufe aus der Oberfläche": "Model and monthly limit for calls from the interface",
    "Lebenslauf und Designs": "CV and designs",
    "Vorlagen, Design, Akzentfarbe, Prüfungen von Lebenslauf und Anschreiben":
        "Templates, design, accent colour, checks of CV and cover letter",
    "Kennung der App und Pausen zwischen Abfragen derselben Seite":
        "App identifier and pauses between requests to the same page",
    "inoffizielle Schnittstellen – nur ändern, wenn du weißt, was du tust":
        "unofficial interfaces – only change if you know what you are doing",
    "aktiv / Ruhemodus / angehalten, Abstand zwischen den Läufen": "active / rest mode / paused, interval between runs",
    "ab wann eine stumme Quelle gemeldet wird": "when a silent source is reported",
    "ab welchem Fit eine eigene Mitteilung kommt": "from which fit a separate notification comes",
    "nach wie vielen Tagen Nachfassen vorgeschlagen wird": "after how many days a follow-up is suggested",
    "wie oft die Links deiner Bewerbungen geprüft werden": "how often the links of your applications are checked",
    "kleine Einstellungen der App": "small app settings",
    "automatische Anschreiben-Entwürfe für Initiativ-Vorschläge":
        "automatic cover letter drafts for speculative suggestions",
    "optionaler Reiter für besonders passende Stellen": "optional tab for particularly matching jobs",
    "Vorlauf und Uhrzeit für Fristen": "Lead time and time of day for deadlines",
    "lieber im Formular unter Einstellungen bearbeiten": "better edit in the form under Settings",
    "Alles, was du sonst im Terminal machen würdest.": "Everything you would otherwise do in the terminal.",
    "Pakete installieren/aktualisieren": "Install/update packages", "Alle Pakete installiert.":
        "All packages installed.", "App neu bauen": "Rebuild app", "Selbsttest": "Self-test",
    "Alte Lebenslauf-Dateien aufräumen": "Clean up old CV files",
    "Alle Dateien in cv/out in den Papierkorb verschieben? Bewerbungsordner bleiben.":
        "Move all files in cv/out to the trash? Application folders stay.",
    "Protokoll der App (letzte Zeilen)": "App log (last lines)",
    "Pipeline / Zeitplan": "Pipeline / schedule", "Freigaben": "Permissions",
    "Neue App laden und die alte ersetzen – deine Daten im Ordner Dokumente/Job-Monitor bleiben erhalten.":
        "Download the new app and replace the old one – your data in the Documents/Job-Monitor folder is kept.",
    "Beim ersten Start fragt das System wieder nach (Mac: Systemeinstellungen → Datenschutz & Sicherheit → „Trotzdem "
    "öffnen“).": "On first launch the system asks again (Mac: System Settings → Privacy & Security → “Open Anyway”).",
    "Fragt die Quellen ab und zeigt den Bericht, ohne etwas zu speichern oder eine Mail zu schicken. Alle Quellen "
    "dauern einige Minuten.": "Queries the sources and shows the report without saving anything or sending an email. "
                              "All sources take a few minutes.",
    "Sie wird beim Beenden oder mit „Synchronisieren“ hochgeladen und gilt ab dem nächsten Lauf.":
        "It is uploaded when quitting or with “Sync” and applies from the next run.",
    "Abgelegt unter Dokumente → Job-Monitor Sicherungen. Der KI-Schlüssel ist nicht enthalten.":
        "Stored under Documents → Job-Monitor Sicherungen. The AI key is not included.",
    "Passwort (empfohlen, mind. 8 Zeichen)": "Password (recommended, at least 8 characters)",
    "Passwort wiederholen": "Repeat password",
    "Das Passwort wird nirgends gespeichert – ohne es lässt sich das Image nicht öffnen.":
        "The password is not stored anywhere – without it the image cannot be opened.",
    "Job-Monitor unterstützen": "Support Job-Monitor",
    "Oberfläche der App. Stellenanzeigen, deine Texte und die Anleitung im Detail bleiben, wie sie sind.":
        "The app's interface. Job ads and your own texts stay as they are.",
    "Sprache der Oberfläche gespeichert.": "Interface language saved.", "Sprache": "Language", "Unterstützen": "Support",

    # --- KI (Einstellungen) ---
    "KI": "AI", "Claude (Anthropic)": "Claude (Anthropic)", "OpenAI (ChatGPT)": "OpenAI (ChatGPT)",
    "Google Gemini": "Google Gemini", "Mistral (EU)": "Mistral (EU)", "Ollama (lokal, kostenlos)":
        "Ollama (local, free)", "Claude einrichten": "Set up Claude",
    "Schritt-für-Schritt-Anleitung für Claude": "Step-by-step guide for Claude",
    "Empfohlen – die App ist auf Claude abgestimmt (Prompt-Caching, Ersatzmodell bei Ablehnung).":
        "Recommended – the app is tuned for Claude (prompt caching, fallback model on refusal).",
    "Abrechnung über dein OpenAI-Konto.": "Billed via your OpenAI account.",
    "Abrechnung über Google AI Studio.": "Billed via Google AI Studio.",
    "Anbieter mit Sitz in Frankreich.": "Provider based in France.",
    "Läuft auf deinem Rechner, nichts verlässt ihn. Braucht einen kräftigen Rechner; Ergebnisse sind meist schwächer "
    "als bei den großen Anbietern.": "Runs on your computer, nothing leaves it. Needs a powerful computer; results are "
                                     "usually weaker than with the big providers.",
    "Sicher speichern": "Save securely", "Schlüssel entfernen": "Remove key",
    "Schlüssel aus dem Schlüsselspeicher löschen?": "Delete the key from the keychain?",
    "Schlüssel sicher im Schlüsselspeicher deines Rechners hinterlegt.":
        "Key stored securely in your computer's keychain.",
    "Die Kosten laufen über dein Anthropic-Konto, nach Verbrauch. Die Karte zeigt den Verbrauch dieses Monats; für "
    "Aufrufe aus der Oberfläche gibt es ein Monatslimit.": "Costs go through your Anthropic account, based on usage. "
                                                           "The card shows this month's usage; calls from the "
                                                           "interface have a monthly limit.",
    "Zugang beim Anbieter; Kosten laufen über dein Konto dort, nach Verbrauch. Gesendet werden Anzeigentexte und dein "
    "Master-CV ohne persönliche Angaben – direkt an den Anbieter, nie an den Entwickler dieser App. Die KI verschickt "
    "nichts.": "Access with the provider; costs go through your account there, based on usage. Ad texts and your "
               "master CV without personal details are sent – directly to the provider, never to the developer of "
               "this app. The AI sends nothing.",
    "Die KI liest Anzeigen, schlägt Suchprofile vor, schneidet Lebensläufe zu (nur Auswahl und Reihenfolge, nichts "
    "Erfundenes), entwirft Anschreiben, Nachfragen und Danke-Mails und bereitet Gespräche vor. Sie verschickt nichts. "
    "Gesendet werden Anzeigentexte und dein Master-CV ohne persönliche Angaben – mit deinem eigenen Schlüssel direkt "
    "an Anthropic.": "The AI reads ads, suggests search profiles, tailors CVs (selection and order only, nothing "
                     "invented), drafts cover letters, follow-ups and thank-you emails and prepares interviews. It "
                     "sends nothing. Ad texts and your master CV without personal details are sent – with your own key "
                     "directly to Anthropic.",
    "Die tägliche Suche nutzt automatisch ein kleines, günstiges Modell; nur Anschreiben, Vorbereitung und "
    "Lebenslauf-Zuschnitt nutzen das stärkere. Das Monatslimit der Oberfläche steht in config.yaml unter":
        "The daily search automatically uses a small, cheap model; only cover letters, preparation and CV tailoring "
        "use the stronger one. The interface's monthly limit is in config.yaml under",
    "Entwurf mit KI (je Bewerbung)": "Draft with AI (per application)",
    "Mit KI formulieren (Bewerbungen)": "Phrase with AI (applications)", "Zu Einstellungen → KI": "To Settings → AI",
    "Einstellungen → KI": "Settings → AI", "Modell": "Model",

    # --- KI-Anleitung (Claude) ---
    "Bevor du anfängst: das Wichtigste in Kürze": "Before you start: the essentials",
    "Kein Abo, keine Überraschungen.": "No subscription, no surprises.",
    "Bei Anthropic kaufst du vorher Guthaben; verbraucht wird nur davon. Automatisches Nachladen gibt es nur, wenn du "
    "es selbst einschaltest (": "At Anthropic you buy credit in advance; only that is used. Automatic top-up only "
                                "happens if you turn it on yourself (",
    "). Fang klein an – für Suche, Anschreiben und Vorbereitung reicht ein kleiner Betrag lange.":
        "). Start small – a small amount lasts a long time for searching, cover letters and preparation.",
    "Die App bremst zusätzlich:": "The app also puts on the brakes:",
    "Für Aufrufe aus der Oberfläche gibt es ein Monatslimit, und unter Einstellungen siehst du jederzeit, wie viel "
    "verbraucht wurde.": "Calls from the interface have a monthly limit, and under Settings you can see at any time "
                         "how much has been used.",
    "Deine persönlichen Daten bleiben bei dir.": "Your personal data stays with you.",
    "Name, Adresse, Telefon, E-Mail und Foto werden nie gesendet – nur Anzeigentexte und der fachliche Teil deines "
    "Lebenslaufs. Laut Anthropic werden Daten aus der API standardmäßig nicht zum Training der Modelle verwendet.":
        "Name, address, phone, email and photo are never sent – only ad texts and the professional part of your CV. "
        "According to Anthropic, data from the API is not used to train the models by default.",
    "Der Entwickler dieser App bekommt nichts": "The developer of this app gets nothing",
    "– weder deinen Schlüssel noch deine Daten noch Geld. Alles läuft direkt zwischen deinem Rechner und Anthropic.":
        "– not your key, not your data, not money. Everything runs directly between your computer and Anthropic.",
    "Du kannst jederzeit aufhören:": "You can stop at any time:",
    "Schlüssel in der App entfernen, in der Anthropic Console löschen – fertig. Die App funktioniert auch ohne KI "
    "weiter.": "Remove the key in the app, delete it in the Anthropic Console – done. The app keeps working without AI.",
    "Schritt für Schritt": "Step by step", "Konto anlegen": "Create an account", "Öffne die": "Open the",
    "und registriere dich mit deiner E-Mail-Adresse. Das ist ein anderes Konto als ein Claude-Chat-Abo – ein Abo "
    "brauchst du nicht.": "and sign up with your email address. This is a different account from a Claude chat "
                         "subscription – you do not need a subscription.",
    "Guthaben aufladen": "Add credit", "In der Console unter": "In the Console under",
    "(Abrechnung) eine Zahlungsart hinterlegen und Guthaben kaufen. Ein kleiner Betrag genügt zum Ausprobieren. "
    "„Auto-reload“ (automatisch nachladen) lässt du aus. Gekauftes Guthaben wird nicht erstattet – darum lieber klein "
    "anfangen und bei Bedarf nachkaufen.": "add a payment method and buy credit. A small amount is enough to try it "
                                         "out. Leave “Auto-reload” off. Purchased credit is not refunded – so better "
                                         "start small and buy more when needed.",
    "Schlüssel erstellen": "Create a key", "Unter": "Under", ", als Namen z. B. „Job-Monitor“. Den Schlüssel (beginnt "
    "mit": ", name it e.g. “Job-Monitor”. Copy the key (starts with",
    ") gleich kopieren – er wird nur einmal angezeigt. Teile ihn mit niemandem.":
        ") right away – it is only shown once. Do not share it with anyone.",
    "In der App eintragen": "Enter it in the app", "In der App:": "In the app:",
    "als Anbieter „Claude“ wählen, den Schlüssel einfügen und": "choose “Claude” as provider, paste the key and",
    ". Er landet im Schlüsselbund deines Rechners (Windows: Anmeldeinformationsverwaltung), nicht in einer Datei.":
        ". It goes into your computer's keychain (Windows: Credential Manager), not into a file.",
    "Zum Beispiel unter Einstellungen ein Suchprofil mit „Felder mit KI ausfüllen“ anlegen oder bei einer Bewerbung "
    "„Entwurf mit KI“ klicken. Ab dann liest die tägliche Suche neue Anzeigen mit KI.":
        "For example, create a search profile under Settings with “Fill in fields with AI” or click “Draft with AI” "
        "for an application. From then on the daily search reads new ads with AI.",
    "Kosten im Blick behalten": "Keep an eye on costs",
    "Einstellungen → KI zeigt Aufrufe und Tokens dieses Monats (Tokens sind die Einheit, nach der abgerechnet wird – "
    "grob: Textmenge).": "Settings → AI shows calls and tokens of this month (tokens are the billing unit – roughly: "
                         "amount of text).",
    "Bei Anthropic:": "At Anthropic:", "siehst du die Kosten in Euro bzw. Dollar.": "you see the costs in dollars.",
    "Sparen:": "Saving:", "Die KI nutzt": "The AI uses", "Häufige Sorgen": "Common worries",
    "Was passiert, wenn das Guthaben leer ist?": "What happens when the credit runs out?",
    "Die KI-Knöpfe melden einen Fehler, die App läuft ohne KI weiter. Es entstehen keine Schulden.":
        "The AI buttons report an error, the app keeps running without AI. No debt is incurred.",
    "Kann jemand meinen Schlüssel sehen?": "Can anyone see my key?",
    "Er liegt im Schlüsselspeicher deines Rechners und wird nur an Anthropic geschickt. Wenn du unsicher bist: in "
    "der Console löschen und einen neuen erstellen.": "It is stored in your computer's keychain and only sent to "
                                                     "Anthropic. If you are unsure: delete it in the Console and "
                                                     "create a new one.",
    "Schreibt die KI meine Bewerbungen und schickt sie ab?": "Does the AI write my applications and send them?",
    "Nein. Sie macht Entwürfe; du liest, änderst und schickst selbst. Beim Lebenslauf sortiert sie nur deine eigenen "
    "Einträge – sie erfindet nichts.": "No. It makes drafts; you read, change and send them yourself. For the CV it "
                                      "only sorts your own entries – it invents nothing.",
    "Muss ich programmieren können?": "Do I need to know how to program?",
    "Nein. Du brauchst nur das Konto, Guthaben und den kopierten Schlüssel.":
        "No. You only need the account, credit and the copied key.",
    "Ich möchte lieber einen anderen Anbieter.": "I would prefer another provider.",
    "Unter Einstellungen → KI gehen auch OpenAI, Google Gemini, Mistral und Ollama (läuft kostenlos auf deinem "
    "Rechner). Die App ist aber auf Claude abgestimmt.": "Under Settings → AI you can also use OpenAI, Google Gemini, "
                                                         "Mistral and Ollama (runs for free on your computer). The app "
                                                         "is tuned for Claude, though.",
    "In etwa zehn Minuten – und du behältst jederzeit die Kontrolle über Kosten und Daten.":
        "In about ten minutes – and you stay in control of costs and data at all times.",
    "Die App hat keinen eigenen Zugang: Deine Daten gehen direkt an Anthropic, nie an den Entwickler.":
        "The app has no access of its own: your data goes directly to Anthropic, never to the developer.",
    "Anthropic-Hilfe": "Anthropic help",

    # --- Einrichtungs-Assistent ---
    "Willkommen bei Job-Monitor": "Welcome to Job-Monitor", "Einrichtungs-Assistent": "Setup assistant",
    "Einrichten": "Set up", "Los geht’s": "Let's go", "1. Deine Angaben": "1. Your details",
    "2. KI (optional)": "2. AI (optional)", "3. Wohnort": "3. Home location", "4. Was suchst du?": "4. What are you looking for?",
    "5. Lebenslauf": "5. CV", "6. Postfach (optional)": "6. Mailbox (optional)", "Angaben eintragen": "Enter details",
    "KI-Schlüssel hinterlegen (empfohlen)": "Add AI key (recommended)",
    "KI ist eingerichtet: Suchprofil und Lebenslauf füllt sie für dich aus.":
        "AI is set up: it fills in the search profile and CV for you.",
    "Wohnort und Suche festlegen": "Set home location and search", "Suchprofil anlegen": "Create search profile",
    "KI legt dein Suchprofil an …": "AI is creating your search profile …",
    "KI legt das Suchprofil an …": "AI is creating the search profile …", "Lebenslauf anlegen": "Create CV",
    "Lebenslauf übernehmen": "Import CV", "KI liest deinen Lebenslauf …": "AI is reading your CV …",
    "Was suchst du? In ein, zwei Sätzen": "What are you looking for? In one or two sentences",
    "z. B. Werkstudentenjob im Bereich Data Engineering oder KI, gern mit Python, in Köln oder remote":
        "e.g. working student job in data engineering or AI, ideally with Python, in Cologne or remote",
    "z. B. Werkstudent im Controlling oder Finanzbereich, gern mit Excel und SAP":
        "e.g. working student in controlling or finance, ideally with Excel and SAP",
    "Karrierestufe": "Career level", "Ausbildung / duales Studium": "Apprenticeship / dual study",
    "Werkstudent / Nebenjob im Studium": "Working student / part-time job while studying",
    "Berufseinstieg / Junior": "Entry level / junior", "Berufserfahren": "Experienced",
    "Werkstudent, Praktikum, Abschlussarbeit": "Working student, internship, thesis",
    "später in den Einstellungen anpassen": "adjust later in Settings",
    "Vor dem Senden entfernt die App Name, Adresse, Telefon, E-Mail, Links und Geburtsdatum aus dem Text.":
        "Before sending, the app removes name, address, phone, email, links and date of birth from the text.",
    "Vor dem Senden entfernt die App Name, Adresse, Telefon, E-Mail, Links und Geburtsdatum aus dem Text. Danach "
    "prüfst du alles im": "Before sending, the app removes name, address, phone, email, links and date of birth from "
                          "the text. Afterwards you check everything in the",
    "Stationen, Ausbildung, Kenntnisse und Projekte eintragen – oder im Einrichtungs-Assistenten ein vorhandenes "
    "Lebenslauf-PDF übernehmen lassen.": "Enter positions, education, skills and projects – or let the setup "
                                         "assistant import an existing CV PDF.",
    "Damit der Fit stimmt": "So the fit is right", "Name, Kontakt, Foto – nur lokal, nie an eine KI.":
        "Name, contact, photo – only local, never sent to an AI.",
    "Steht nur im Kopf deiner PDFs. Bleibt auf diesem Rechner, geht nie an eine KI.":
        "Only appears in the header of your PDFs. Stays on this computer, never goes to an AI.",
    "Danach liest die App Job-Alert-Mails (z. B. von LinkedIn oder StepStone) und erkennt Antworten von Firmen – sie "
    "liest nur, sie verschickt nie etwas an Firmen.": "Afterwards the app reads job alert emails (e.g. from LinkedIn "
                                                       "or StepStone) and detects replies from companies – it only "
                                                       "reads, it never sends anything to companies.",
    "Die KI schätzt die Fahrzeiten in die Umgebung (nur der Städtename wird gesendet).":
        "The AI estimates travel times to the surrounding area (only the city name is sent).",
    "Ausbildung, Praktikum, Werkstudent, Abschlussarbeit, Berufseinstieg oder Berufserfahren – füllt Rollen-Wörter und "
    "Stellenart aus und wählt ein passendes Design.": "Apprenticeship, internship, working student, thesis, entry "
                                                      "level or experienced – fills in role words and job type and "
                                                      "chooses a matching design.",

    # --- Suchprofile ---
    "Was du suchst: Rollen-Wörter im Titel, Suchbegriffe je Quelle, Fachgebiet, Karrierestufe und Design. Mehrere "
    "Profile gleichzeitig sind möglich.": "What you are looking for: role words in the title, search terms per "
                                         "source, subject area, career level and design. Several profiles at the "
                                         "same time are possible.",
    "Grunddaten": "Basic data", "Fachgebiet": "Subject area", "Eigenes Fachgebiet": "Own subject area",
    "Gemeinsam mit den anderen Profilen": "Shared with the other profiles",
    "Karrierestufe (Vorlage für Rollen-Wörter und Stellenart; passt zu jedem Fachgebiet)":
        "Career level (template for role words and job type; fits any subject area)",
    "Rollen-Wörter im Titel, je Zeile „wort: punkte“ (ohne Punkte: 25)":
        "Role words in the title, one per line “word: points” (without points: 25)",
    "Fach-Stichwörter, je Zeile „wort: punkte“ (ohne Punkte: 8; Titel zählt doppelt)":
        "Subject keywords, one per line “word: points” (without points: 8; title counts double)",
    "Suchbegriffe Bundesagentur, einer je Zeile": "Search terms Federal Employment Agency, one per line",
    "Suchbegriffe Stellenwerk, einer je Zeile": "Search terms Stellenwerk, one per line",
    "Stellenart (Bundesagentur)": "Job type (Federal Employment Agency)", "Alle Angebotsarten": "All offer types",
    "Zielrolle für Anschreiben": "Target role for cover letters", "Absicht („… und suche …“)":
        "Intention (“… and I am looking for …”)", "Ausblick (Schlusssatz)": "Outlook (closing sentence)",
    "Design für Lebenslauf und Anschreiben": "Design for CV and cover letter",
    "automatisch (nach Karrierestufe)": "automatic (by career level)",
    "Speichern. Höchstens vier Profile können gleichzeitig aktiv sein.":
        "Save. At most four profiles can be active at the same time.",
    "Aktiv (wird bei jedem Lauf abgefragt)": "Active (queried on every run)",
    "Felder mit KI ausfüllen": "Fill in fields with AI", "Mit KI ausfüllen": "Fill in with AI",
    "Gesendet: deine Beschreibung und dein Master-CV. Du prüfst alles, gespeichert wird erst mit „Speichern“.":
        "Sent: your description and your master CV. You check everything; it is only saved with “Save”.",
    "Für ein anderes Feld, z. B. Data Science oder Netzwerktechnik. Dann zählen nur diese Stichwörter, die "
    "IT-Prüfungen des gemeinsamen Fachgebiets entfallen.": "For another field, e.g. data science or network "
                                                          "engineering. Then only these keywords count; the IT checks "
                                                          "of the shared subject area are dropped.",
    "Für ein anderes Fach „eigenes Fachgebiet“ wählen, damit Fach-Wörter wie „Marketing“ nicht ausgeschlossen werden.":
        "For another subject choose “own subject area”, so that subject words like “Marketing” are not excluded.",
    "Cloud, Azure, IAM, DevOps, IT-Security … aus config.yaml (filter.fach). Richtig für Profile im selben Bereich.":
        "Cloud, Azure, IAM, DevOps, IT security … from config.yaml (filter.fach). Right for profiles in the same "
        "area.",
    "Tipp: Wörter so, wie sie in Anzeigentiteln stehen (eher „KI“ und „Data Engineering“ als „Machine Learning“). Bei "
    "der Bundesagentur kennt der Filter oft nur den Titel; mit einem Fach-Wort im Titel kommt eine Stelle sicher "
    "durch, sonst braucht es zwei starke Stichwörter (ab 8 Punkten) in der Beschreibung.":
        "Tip: words as they appear in ad titles (rather “AI” and “Data Engineering” than “Machine Learning”). For "
        "the Federal Employment Agency the filter often only knows the title; with a subject word in the title a job "
        "always gets through, otherwise it needs two strong keywords (8 points or more) in the description.",
    "Optional: Stellen, die besonders gut zu deinem Schwerpunkt passen, bekommen einen eigenen Reiter.":
        "Optional: jobs that particularly match your focus get their own tab.",
    "zurück zu den Einstellungen": "back to Settings", "Zusätzliche Fit-Begriffe (optional), je Zeile „Begriff: "
    "Synonym, Synonym“": "Additional fit terms (optional), one per line “term: synonym, synonym”",
    "Eine Stelle zählt nur, wenn eines davon im Titel steht. Mehr Punkte = weiter oben im Bericht.":
        "A job only counts if one of them is in the title. More points = higher in the report.",
    "„Berufserfahren“ schließt Stellen mit senior, lead oder leiter im Titel nicht mehr aus.":
        "“Experienced” no longer excludes jobs with senior, lead or head in the title.",
    "Feste Stelle (Berufseinstieg)": "Permanent position (entry level)",
    "eine Werkstudententätigkeit im Bereich …": "a working student position in …",
    "Langfristig möchte ich …": "In the long run I would like to …", "z. B. Werkstudent IT-Security":
        "e.g. working student IT security", "z. B. Praktikum Security": "e.g. internship security",
    "z. B. SAP": "e.g. SAP", "z. B. sap s/4hana, sap erp": "e.g. sap s/4hana, sap erp",

    # --- Dateien bearbeiten ---
    "Für Fortgeschrittene: alles, was es nicht als eigenes Formular gibt. Vor dem Speichern prüft die App die Datei; "
    "der alte Stand bleibt als Sicherung und lässt sich mit einem Klick zurückholen.":
        "For advanced users: everything that has no form of its own. The app checks the file before saving; the old "
        "version stays as a backup and can be restored with one click.",
    "Alle Einstellungen der Suche – das meiste hat ein eigenes Formular in den Einstellungen.":
        "All search settings – most have their own form in Settings.",
    "Prüfen und speichern": "Check and save", "Vorherige Fassung wiederherstellen": "Restore previous version",
    "Den Stand vor dem letzten Speichern zurückholen? Deine jetzige Fassung wird dabei zur Sicherung.":
        "Restore the version before the last save? Your current version becomes the backup.",
    "Im Text suchen": "Search in text", "Kurzhilfe zum Format": "Quick format help", "Einrückung": "Indentation",
    "ungespeichert": "unsaved", "Anschreiben-Vorlage": "Cover letter template",
    "Textbausteine für neue Anschreiben-Entwürfe. Platzhalter in {geschweiften Klammern} füllt die App aus; Text in "
    "[eckigen Klammern] schreibst du je Bewerbung selbst.": "Text blocks for new cover letter drafts. The app fills in "
                                                           "placeholders in {curly braces}; you write text in [square "
                                                           "brackets] yourself for each application.",
    "Vorlage für die Nachfrage, wenn eine Firma nicht antwortet. Die erste Zeile ist der Betreff.":
        "Template for the follow-up when a company does not reply. The first line is the subject.",
    "Zeilen mit # am Anfang werden ignoriert. Welche Platzhalter es gibt, steht in den Kommentarzeilen oben in der "
    "Datei.": "Lines starting with # are ignored. The available placeholders are listed in the comment lines at the "
              "top of the file.",
    "– Kommentar, wird ignoriert. Gut, um zu notieren, warum du etwas geändert hast.":
        "– comment, ignored. Good for noting why you changed something.",
    "– ein Eintrag. Nach dem Doppelpunkt ein Leerzeichen.": "– an entry. A space after the colon.",
    "– ein Listenpunkt; oder kurz": "– a list item; or short",
    "mit Leerzeichen zeigt, was wozu gehört (die Tab-Taste fügt hier zwei Leerzeichen ein).":
        "with spaces shows what belongs to what (the Tab key inserts two spaces here).",
    "Text mit Doppelpunkt oder # in Anführungszeichen setzen:": "Put text with a colon or # in quotes:",
    "– keine Vorlage –": "– no template –",

    # --- Anleitung (Hilfe) ---
    "Schnellstart": "Quick start", "So geht's": "How to", "Nachschlagen": "Reference", "Hintergrund": "Background",
    "Probleme lösen": "Troubleshooting", "Hilfe durchsuchen": "Search help",
    "Hilfe durchsuchen, z. B. Design, Postfach, Fit": "Search help, e.g. design, mailbox, fit",
    "Erst der Schnellstart, danach kurze Anleitungen für einzelne Aufgaben. Links führen direkt zur passenden Seite.":
        "First the quick start, then short guides for individual tasks. Links lead directly to the right page.",
    "Schnellstart: in sechs Schritten zur ersten Bewerbung": "Quick start: six steps to your first application",
    "Einmal von oben nach unten – danach kennst du die wichtigsten Seiten. Neu hier? Der":
        "Once from top to bottom – then you know the most important pages. New here? The",
    "führt durch die ersten vier Schritte.": "guides you through the first four steps.",
    "Seiten der App": "Pages of the app", "Dateien und Ordner": "Files and folders",
    "Nichts gefunden. Andere Wörter versuchen – oder unter Einstellungen → Protokoll nach einer Fehlermeldung sehen.":
        "Nothing found. Try other words – or look for an error message under Settings → Log.",
    "Wie bewerbe ich mich auf eine gefundene Stelle?": "How do I apply for a job I found?",
    "Wie bewerte ich eine Stelle, die ich selbst gefunden habe?": "How do I rate a job I found myself?",
    "Wie bereite ich mich auf ein Gespräch vor?": "How do I prepare for an interview?",
    "Wie fasse ich nach, wenn keine Antwort kommt?": "How do I follow up when no reply comes?",
    "Wie blende ich unpassende Stellen aus – und bringe dem Filter etwas bei?":
        "How do I hide unsuitable jobs – and teach the filter something?",
    "Wie zeige ich nur Stellen bis 20 Stunden, mit Remote oder Abschlussarbeit?":
        "How do I show only jobs up to 20 hours, with remote or thesis?",
    "Wie lege ich ein neues Suchprofil an (z. B. für ein anderes Fach)?":
        "How do I create a new search profile (e.g. for another subject)?",
    "Wie ändere ich meinen Wohnort?": "How do I change my home location?",
    "Wie trage ich eine Kenntnis schnell ein?": "How do I add a skill quickly?",
    "Wie übernehme ich meinen vorhandenen Lebenslauf?": "How do I import my existing CV?",
    "Wie ändere ich das Design von Lebenslauf und Anschreiben?": "How do I change the design of CV and cover letter?",
    "Wie füge ich eine Firma hinzu, deren Karriereseite ich beobachten will?":
        "How do I add a company whose career page I want to watch?",
    "Wie verbinde ich mein Postfach (Job-Alerts, Antworten, Bericht per Mail)?":
        "How do I connect my mailbox (job alerts, replies, report by email)?",
    "Wie richte ich die KI ein, und was kostet sie?": "How do I set up the AI, and what does it cost?",
    "Wie sucht die App jeden Tag von selbst?": "How does the app search every day by itself?",
    "Wie pausiere ich die Suche, wenn ich gerade nichts suche?": "How do I pause the search when I am not looking?",
    "Wie sichere ich meine Daten?": "How do I back up my data?", "Wie bekomme ich eine neue Version?":
        "How do I get a new version?", "Wo liegen meine Dateien?": "Where are my files?",
    "Wie die Suche funktioniert": "How the search works", "Wie der Fit entsteht": "How the fit is calculated",
    "Warum kein LinkedIn, StepStone oder Indeed?": "Why no LinkedIn, StepStone or Indeed?",
    "Was die KI macht – und was nicht": "What the AI does – and what it does not",
    "Es kommen kaum Treffer.": "There are hardly any matches.", "Der Fit wirkt zu niedrig.": "The fit seems too low.",
    "Eine Stelle fehlt, die ich auf LinkedIn gesehen habe.": "A job I saw on LinkedIn is missing.",
    "Das PDF ließ sich nicht bauen.": "The PDF could not be built.",
    "Meine Änderung kommt in der GitHub-Suche nicht an.": "My change does not reach the GitHub search.",
    "Was du tun kannst": "What you can do", "Bei der Stelle auf": "On the job, click",
    "Bei einer passenden Stelle auf": "On a matching job, click", "bei der Stelle auf": "on the job, click",
    "klicken – es entsteht ein Bewerbungsordner mit einem Anschreiben-Entwurf.":
        "– an application folder with a cover letter draft is created.",
    ": Anschreiben schreiben (oder von der KI entwerfen lassen), Design wählen,":
        ": write the cover letter (or let the AI draft it), choose a design,",
    ": Anschreiben, zugeschnittener Lebenslauf und Unterlagen als ein PDF.":
        ": cover letter, tailored CV and documents as one PDF.",
    ", Prüfung vor dem Abschicken ansehen – dann selbst abschicken und den Status auf „beworben“ setzen.":
        ", look at the check before sending – then send it yourself and set the status to “applied”.",
    ": Anzeigentext einfügen oder den Link zur Karriereseite angeben.":
        ": paste the ad text or enter the link to the career page.",
    "– die Stelle landet in deinen Bewerbungen.": "– the job lands in your applications.",
    "LinkedIn, StepStone und Indeed ruft die App nicht ab: dort den Text kopieren.":
        "The app does not fetch LinkedIn, StepStone and Indeed: copy the text there.",
    "unter „Gespräche“ den Termin eintragen und in den Kalender übernehmen (Mac: Kalender, Windows: Kalenderdatei).":
        "enter the appointment under “Interviews” and add it to the calendar (Mac: Calendar, Windows: calendar file).",
    ": kurze Zusammenfassung der Firma aus ihrer Webseite.": ": short summary of the company from its website.",
    ": wahrscheinliche Fragen und passende Beispiele aus deinem Lebenslauf; mit KI ausführlich.":
        ": likely questions and matching examples from your CV; detailed with AI.",
    "Nach dem Gespräch Notizen und Bauchgefühl festhalten; die KI entwirft eine Danke-Mail, die du selbst schickst.":
        "After the interview, note down your impressions; the AI drafts a thank-you email that you send yourself.",
    "Nach einigen Wochen ohne Antwort erscheint die Bewerbung in": "After a few weeks without a reply, the "
                                                                   "application appears in",
    "– mit einem Entwurf zum Kopieren (oder": "– with a draft to copy (or",
    "klicken (ein Klick auf „Rückgängig“ holt sie zurück).": "(one click on “Undo” brings it back).",
    "Danach kurz den Grund antippen, z. B. „anderes Fachgebiet“ – freiwillig.":
        "Then tap the reason, e.g. “other subject area” – optional.",
    "Häufen sich Wörter in abgelehnten Titeln, schlägt die Startseite sie als Ausschluss vor:":
        "If words pile up in rejected titles, the start page suggests them as exclusions:",
    "die Häkchen über der Liste setzen. Stellen ohne Angabe bleiben bei Stunden und Remote sichtbar.":
        "tick the boxes above the list. Jobs without information stay visible for hours and remote.",
    "Ohne Angabe in der Anzeige bleibt eine Stelle sichtbar (außer bei Abschlussarbeit).":
        "Without information in the ad, a job stays visible (except for thesis).",
    "Die Eckdaten liest die KI aus den Anzeigen; ohne KI fehlen sie meist.":
        "The AI reads the key facts from the ads; without AI they are usually missing.",
    "Kurz beschreiben, was du suchst, und": "Briefly describe what you are looking for, and",
    "– oder Karrierestufe wählen und die Suchbegriffe selbst eintragen.":
        "– or choose a career level and enter the search terms yourself.",
    ": Stadt eintragen.": ": enter the city.",
    "den Begriff anklicken und das Level wählen – er landet in der passenden Kategorie.":
        "click the term and choose the level – it lands in the matching category.",
    ") unter „Lebenslauf“ das PDF hochladen (KI nötig).": ") upload the PDF under “CV” (AI needed).",
    "Im Einrichtungs-Assistenten (": "In the setup assistant (",
    "Für ein ganzes Suchprofil:": "For a whole search profile:", "→ Suchprofil bearbeiten →":
        "→ edit search profile →", "Für eine einzelne Bewerbung: auf der Bewerbungsseite unter":
        "For a single application: on the application page under", "wählen und die Mappe neu bauen.":
        "choose and rebuild the application PDF.", "Alle Designs mit deinen Daten ansehen:":
        "See all designs with your data:", "Master-CV → Designs": "Master CV → Designs",
    "Bei großen Firmen mit Bewerbungsportal sind": "For large companies with an application portal,",
    "sicherer – die Prüfung vor dem Abschicken weist darauf hin.": "are safer – the check before sending points this out.",
    ": unten Name und Adresse der Karriereseite eintragen.": ": enter name and address of the career page below.",
    "Beim nächsten Lauf erkennt die App das Bewerbungssystem selbst. Lässt sich die Seite nicht lesen, steht sie unter "
    "„manuell prüfen“ und die App erinnert dich, selbst nachzusehen.":
        "On the next run, the app detects the application system itself. If the page cannot be read, it is listed "
        "under “check manually” and the app reminds you to look yourself.",
    ": Anbieter wählen, E-Mail-Adresse und ein": ": choose a provider, enter your email address and an",
    "Bequemer:": "More convenient:", "einen eigenen API-Schlüssel anlegen und unter": "create your own API key and enter it under",
    "eintragen.": ".", "– mit allem, was du vorher wissen willst (Kosten, Kontrolle, Datenschutz).":
        "– with everything you want to know beforehand (costs, control, privacy).",
    ": Uhrzeit wählen und": ": choose a time and", "einschalten.": "turn it on.",
    ": mit Passwort als verschlüsseltes Disk-Image (Mac) oder als ZIP-Datei.":
        ": with a password as an encrypted disk image (Mac) or as a ZIP file.",
    "Gibt es eine neue Version, steht oben auf der Startseite ein Hinweis mit": "If there is a new version, a note "
                                                                               "with a link appears at the top of the "
                                                                               "start page",
    "Siehe „Dateien und Ordner“ unter Nachschlagen.": "See “Files and folders” under Reference.",
    "Die App fragt öffentliche Quellen ab: die Jobsuche der Bundesagentur für Arbeit, Arbeitnow, Karriereseiten von "
    "Firmen (über ihre Bewerbungssysteme, strukturierte Daten oder Sitemaps), Hochschulbörsen und – mit verbundenem "
    "Postfach – Job-Alert-Mails. Jede Stelle durchläuft Filter (Rolle, Fach, Ort, Ausschlüsse), bekommt einen Score "
    "und einen Fit. Gemeldet wird jede Stelle nur einmal.":
        "The app queries public sources: the job search of the German Federal Employment Agency, Arbeitnow, company "
        "career pages (via their application systems, structured data or sitemaps), university job boards and – with "
        "a connected mailbox – job alert emails. Every job goes through filters (role, subject, location, "
        "exclusions) and gets a score and a fit. Each job is reported only once.",
    "Aus jeder Anzeige werden Anforderungen erkannt – per Stichwort und, mit KI, aus dem Text (auch Pflicht oder "
    "„wünschenswert“). Erfüllt ist, was dein Master-CV belegt; Grundkenntnisse zählen weniger als „gut“, Geplantes gar "
    "nicht. Fehlt dir etwas, das du kannst: im Master-CV eintragen.":
        "Requirements are detected from every ad – by keyword and, with AI, from the text (also mandatory or “nice to "
        "have”). Met is what your master CV covers; basic knowledge counts less than “good”, planned items not at all. "
        "If something you can do is missing: add it to your master CV.",
    "Diese Börsen verbieten das automatische Auslesen. Die App hält sich an robots.txt, fragt sparsam ab und nutzt "
    "keine Logins oder Tricks gegen Sperren. Ihre Stellen kommen trotzdem an: über deine Job-Alert-Mails, zu denen die "
    "App die Originalanzeige bei der Firma sucht.":
        "These job boards prohibit automatic reading. The app respects robots.txt, queries sparingly and uses no "
        "logins or tricks against blocks. Their jobs still arrive: via your job alert emails, for which the app looks "
        "up the original ad at the company.",
    "Name, Adresse, Telefon, E-Mail und Foto liegen nur in cv/profile.yaml auf diesem Rechner. Zugangsdaten "
    "(KI-Schlüssel, Mail-App-Passwort) liegen im Schlüsselbund bzw. in der Windows-Anmeldeinformationsverwaltung. "
    "Bewerbungen und Mails an Firmen schickst immer du selbst.":
        "Name, address, phone, email and photo are only in cv/profile.yaml on this computer. Credentials (AI key, "
        "mail app password) are in the keychain or the Windows Credential Manager. You always send applications and "
        "emails to companies yourself.",
    "Suchbegriffe im Suchprofil prüfen (eher so, wie Firmen Stellen betiteln), Wohnort und Fahrzeit prüfen, eigenes "
    "Fachgebiet wählen, wenn du nicht in der IT suchst. Ein Probelauf zeigt, was jede Quelle liefert.":
        "Check the search terms in the search profile (rather the way companies title jobs), check home location and "
        "travel time, choose your own subject area if you are not looking in IT. A test run shows what each source "
        "delivers.",
    "Er zählt nur, was im Master-CV belegt ist. Fehlende Kenntnisse in der Lücken-Auswertung mit einem Klick "
    "eintragen; Status „geplant“ zählt nicht.": "It only counts what your master CV covers. Add missing skills with "
                                               "one click under Skill gaps; status “planned” does not count.",
    "LinkedIn wird nicht abgefragt. Richte dort einen Job-Alert ein und verbinde dein Postfach – oder füge die Stelle "
    "unter „Eigene Stelle“ ein.": "LinkedIn is not queried. Set up a job alert there and connect your mailbox – or "
                                 "add the job under “Own job ad”.",
    "Unter Einstellungen → Protokoll steht der Grund. Ohne LaTeX baut die App die PDFs über HTML; dafür braucht "
    "Windows den Browser Edge (vorinstalliert).": "Settings → Log shows the reason. Without LaTeX the app builds the "
                                                 "PDFs via HTML; on Windows this needs the Edge browser (preinstalled).",
    "Gefundene Stellen nach Fit, mit Reitern je Suchprofil, Eckdaten-Filter, Suchfeld. Je Zeile: Bewerbung, Lebenslauf, "
    "Frist eintragen (Glocke), merken (Lesezeichen), ausblenden (×). Oben: „Heute bewerben“, Hinweise auf neue "
    "Versionen und Vorschläge aus deinen Ablehnungen.": "Jobs found by fit, with tabs per search profile, key fact "
                                                        "filters, search field. Per row: application, CV, enter "
                                                        "deadline (bell), save for later (bookmark), hide (×). At the "
                                                        "top: “Apply today”, notes about new versions and suggestions "
                                                        "from your rejections.",
    "Deine Liste mit Status, dazu Gespräche (Termin, Vorbereitung, Firmenprofil, Nachbereitung), erkannte Antworten "
    "von Firmen, Nachfassen und ab zwei Zusagen der Angebotsvergleich.": "Your list with status, plus interviews "
                                                                         "(appointment, preparation, company profile, "
                                                                         "follow-up notes), detected replies from "
                                                                         "companies, follow-ups and, from two offers, "
                                                                         "the offer comparison.",
    "Für Anzeigen, die der Monitor nicht gefunden hat. Fit prüfen, Lebenslauf bauen und in deine Bewerbungen "
    "übernehmen.": "For ads the monitor did not find. Check fit, build CV and add to your applications.",
    "Bewerbungen je Woche, Rücklauf, Zeit bis zur Antwort, woher passende Stellen kommen und was zum Gespräch führt "
    "(nach Fit, Art und Quelle).": "Applications per week, response rate, time to reply, where matching jobs come from "
                                   "and what leads to interviews (by fit, type and source).",
    "Welche Karriereseiten die Suche liest, Initiativ-Möglichkeiten und Warnhinweise je Firma.":
        "Which career pages the search reads, speculative application options and warnings per company.",
    "Beobachtete Karriereseiten, Seiten zum manuellen Prüfen, Quellen, die nichts mehr liefern, Firmen-Vorschläge und "
    "Initiativ-Möglichkeiten.": "Watched career pages, pages to check manually, sources that no longer deliver, company "
                                "suggestions and speculative application options.",
    "Welche Anforderungen am häufigsten fehlen und wie stark dein Fit stiege; Lernvorschläge und Lernplan (KI), "
    "gefragte Kenntnisse im Verlauf, Fit-Begriffe ergänzen.": "Which requirements are missing most often and how much "
                                                             "your fit would rise; learning suggestions and learning "
                                                             "plan (AI), skills in demand over time, add fit terms.",
    "Der Bericht der letzten Suche: neue Stellen, Status der Quellen, Hinweise.":
        "The report of the latest search: new jobs, status of the sources, notes.",
    "Die eine Quelle für alle Lebensläufe. Je Stelle sortiert die App passende Inhalte nach vorn – erfunden wird nichts.":
        "The single source for all CVs. For each job the app moves matching content to the front – nothing is invented.",
    "Name, Kontakt, Foto und was davon im PDF erscheint. Bleibt auf diesem Rechner.":
        "Name, contact, photo and what of it appears in the PDF. Stays on this computer.",
    "Zeugnisse, Nachweise und Foto für die Bewerbungsmappe.": "References, certificates and photo for the application PDF.",
    "Suche aktiv/Ruhe/aus, Zeitplan, Wohnort, Postfach, KI, Suchprofile, Probelauf, Dateien bearbeiten, Sicherung, "
    "Updates und Protokoll.": "Search active/rest/off, schedule, home location, mailbox, AI, search profiles, test run, "
                              "edit files, backup, updates and log.",
    "Dein Datenordner (installierte App). Beim Ersetzen der App bleibt er erhalten.":
        "Your data folder (installed app). It is kept when the app is replaced.",
    "Dein Master-CV (Seite Master-CV).": "Your master CV (Master CV page).",
    "Deine Bewerbungsliste (Seite Bewerbungen).": "Your application list (Applications page).",
    "Bestimmt, welche Stellen inhaltlich passen und wie hoch ihr Score ist.":
        "Determines which jobs match in content and how high their score is.",
    "Beobachtete Firmen und Hochschulbörsen (Seite Firmen).": "Watched companies and university job boards (Companies page).",
    "Hochgeladene Unterlagen und Foto.": "Uploaded documents and photo.",
    "Ein Ordner je Bewerbung mit Anschreiben, Lebenslauf und Mappe.":
        "One folder per application with cover letter, CV and application PDF.",
    "Zertifikate, Kurse und kleine Projekte, die die Lücken-Auswertung je fehlender Kenntnis vorschlägt.":
        "Certificates, courses and small projects that Skill gaps suggests per missing skill.",
    "Die tägliche Suche – entweder als GitHub Action oder über den Zeitplan auf diesem Rechner.":
        "The daily search – either as a GitHub Action or via the schedule on this computer.",
    "Die Liste der Kenntnisse, nach denen der Fit zählt, mit Synonymen. Neue schlägt die KI vor.":
        "The list of skills the fit counts, with synonyms. The AI suggests new ones.",
    "Wie viel Prozent der Anforderungen einer Anzeige dein Master-CV belegt, gewichtet nach Level. „Zu wenig Angaben“: "
    "Die Anzeige nennt zu wenige Anforderungen für eine faire Zahl.": "What percentage of an ad's requirements your "
                                                                       "master CV covers, weighted by level. “Too "
                                                                       "little information”: the ad names too few "
                                                                       "requirements for a fair number.",
    "Software großer Firmen, die Lebensläufe automatisch einliest. Einspaltige Designs werden dort am zuverlässigsten "
    "erkannt.": "Software used by large companies that reads CVs automatically. Single-column designs are recognised "
                "most reliably there.",
    "Am schnellsten:": "Fastest:",
    "– sichert die Anzeige, entwirft das Anschreiben (mit KI), schneidet den Lebenslauf zu und baut die Mappe in einem "
    "Schritt. Danach alles lesen und anpassen.": "– saves the ad, drafts the cover letter (with AI), tailors the CV and "
                                                "builds the application PDF in one step. Then read and adjust "
                                                "everything.",
    "Wie fülle ich ein Bewerbungsportal schneller aus?": "How do I fill in an application portal faster?",
    "Auf der Bewerbungsseite unter": "On the application page under",
    "stehen Name, Kontakt, Studium, Verfügbarkeit, Gehaltsvorstellung, Kurzprofil, Motivation und das Anschreiben als "
    "Text – je mit": "you find name, contact, studies, availability, salary expectation, short profile, motivation and "
                     "the cover letter as text – each with",
    "Lange Texte kürzt die App auf die Zeichengrenze des Portals (300 bis 2000 Zeichen), an der Satzgrenze oder mit":
        "The app shortens long texts to the portal's character limit (300 to 2000 characters), at a sentence boundary "
        "or with",
    "Die Gehaltsvorstellung trägst du einmal im": "You enter the salary expectation once in your",
    "ein. Abgeschickt wird nichts – du fügst ein und sendest selbst.":
        ". Nothing is sent – you paste and submit yourself.",
    "Wie bewerbe ich mich auf Englisch?": "How do I apply in English?",
    "„Englisch“ wählen. Ist die Anzeige auf Englisch, schlägt die App das selbst vor.":
        "choose “Englisch”. If the ad is in English, the app suggests it itself.",
    "Einmalig": "Once:",
    ": Die englische Fassung liegt danach in cv/cv_master.en.yaml und lässt sich unter":
        ": the English version is then in cv/cv_master.en.yaml and can be adjusted under",
    "anpassen.": ".",
    "Lebenslauf und Anschreiben bekommen englische Überschriften, Datum und Grußformel; englische Lebensläufe kommen "
    "ohne Foto und Geburtsdatum aus.": "CV and cover letter get English headings, date and closing; English CVs come "
                                      "without photo and date of birth.",
    "schreibt das Anschreiben auf Englisch.": "writes the cover letter in English.",
    "Wie stelle ich die App auf Englisch um? (How do I switch the app to English?)": "How do I switch the app to English?",
    "Einstellungen → Sprache · Language": "Settings → Sprache · Language",
    ": „English“ wählen. Beim ersten Start übernimmt die App die Sprache des Systems.":
        ": choose “English”. On first launch the app uses the system language.",
    "Stellenanzeigen, deine eigenen Texte und Teile der Anleitung bleiben deutsch.":
        "Job ads and your own texts stay as they are.",
    "Bewerbungsportale": "Application portals", "Auf Englisch": "In English",
    "Bewerbungssystem (ATS)": "Applicant tracking system (ATS)", "Fit": "Fit", "Score": "Score",
    "Initiativ bewerben": "Speculative application", "Rückgängig": "Undo", "Abschlussarbeit": "Thesis",
    "Werkstudent": "Working student", "Praktikum": "Internship", "Junior": "Junior",
    "Datenbank für ein eigenes Tool": "Database for your own tool",
    "Gespräch": "Interview", "Postfach": "Mailbox", "Lebenslauf": "CV", "Bundesagentur": "Federal Employment Agency",
    "Stellenwerk": "Stellenwerk", "Inhalt": "Content", "Platzhalter": "Placeholder",
    "Ein Klick öffnet die App.": "One click opens the app.", "Optional:": "Optional:", "Nov": "Nov",
    "(einmal pro Woche, ohne Mitteilungen) oder": "(once a week, without notifications) or",
    ", sortiert nach Fit.": ", sorted by fit.", "Abfragen": "Query", "Alle Einträge": "All entries",
    "Alle Angebotsarten · gemeinsames Fachgebiet": "All offer types · shared subject area",
    "Feste Stelle (Berufseinstieg) · gemeinsames Fachgebiet": "Permanent position (entry level) · shared subject area",
    "Danach im": "Then in the", "Design wählen": "Choose design", "Designs ansehen": "View designs",
    "Die Karte": "The card", "Einstellungen → Neues Suchprofil": "Settings → New search profile",
    "Einstellungen → Postfach": "Settings → Mailbox", "Einstellungen → Sicherung": "Settings → Backup",
    "Einstellungen → Suche": "Settings → Search", "Einstellungen → Wohnort": "Settings → Home location",
    "Einstellungen → Zeitplan": "Settings → Schedule", "Erinnerungen": "Reminders",
    "Gilt ab dem nächsten Lauf; gespeicherte Stellen werden danach nach und nach neu bewertet.":
        "Applies from the next run; saved jobs are then gradually re-rated.",
    "In der": "In the", "Karriereseite eintragen": "Enter career page", "Master-CV bearbeiten": "Edit master CV",
    "Initiativ: ja (Standort außerhalb der Reichweite oder ohne Link – nicht unter „Initiativ bewerben“)":
        "Speculative: yes (location out of reach or without link – not under “Speculative application”)",
    "Name und Kontakt unter": "Name and contact under", "Notizen (optional)": "Notes (optional)",
    "Stunden, Vergütung, Remote, Start und ob eine Abschlussarbeit möglich ist – von der KI aus der Anzeige gelesen.":
        "Hours, pay, remote, start and whether a thesis is possible – read from the ad by the AI.",
    "Suche aktiv/Ruhe/aus": "Search active/rest/off", "Text in": "Text in", "Was gesucht wird": "What is searched for",
    "Täglich suchen, Postfach auf Antworten prüfen, Anzeigen auf „noch online“ prüfen, Mitteilungen.":
        "Search daily, check the mailbox for replies, check ads are “still online”, notifications.",
    "[eckigen Klammern]": "[square brackets]", "alles prüfen und speichern.": "check and save everything.",
    "companies.yaml · Änderungen werden beim Beenden hochgeladen und gelten ab dem nächsten Lauf der Pipeline.":
        "companies.yaml · changes are uploaded when quitting and apply from the next pipeline run.",
    "das Aussehen wählen (Klassisch, Modern, Kreativ, Kompakt, Akademisch).":
        "choose the look (Classic, Modern, Creative, Compact, Academic).",
    "dein Stand": "your status", "deinen eigenen": "your own",
    "deinen eigenen Claude-Schlüssel eintragen. Ohne geht alles auch, nur mit mehr Tipparbeit.":
        "enter your own Claude key. Everything also works without it, just with more typing.",
    "durchgehen (Platzhalter, Firmenname, Größe, Anlagen, Frist).":
        "go through it (placeholders, company name, size, attachments, deadline).",
    "einen Probelauf starten oder den täglichen Zeitplan einschalten. Die Treffer erscheinen unter":
        "start a test run or turn on the daily schedule. The matches appear under",
    "nutzen.": "use.", "oder oben im": "or at the top of the", "selbst ausfüllen oder": "fill in yourself or",
    "spenden": "donate", "robots.txt verbietet das Auslesen (robots.txt verbietet":
        "robots.txt prohibits reading (robots.txt prohibits",
    "Alle fachlichen Inhalte deines Lebenslaufs (ohne Persönliches): Stationen, Ausbildung, Kenntnisse, Zertifikate, "
    "Projekte. Daraus entstehen alle Lebensläufe. Unten: die Designs.":
        "All professional content of your CV (nothing personal): positions, education, skills, certificates, "
        "projects. All CVs are built from it. Below: the designs.",
    "den Wohnort setzen und ein Suchprofil anlegen: kurz beschreiben, was du suchst, Karrierestufe wählen, „Mit KI "
    "ausfüllen“.": "set your home location and create a search profile: briefly describe what you are looking for, "
                   "choose a career level, “Fill in with AI”.",
    "· Quellen, Filter, Ausschlüsse, Fit-Begriffe, Ort, KI, Lebenslauf und Designs – alles, was die tägliche Suche "
    "steuert. Bequemer:": "· sources, filters, exclusions, fit terms, location, AI, CV and designs – everything that "
                         "controls the daily search. More convenient:",
    "· Textbausteine für neue Anschreiben-Entwürfe. Platzhalter in {geschweiften Klammern} füllt die App aus; Text in "
    "[eckigen Klammern] schreibst du je Bewerbung selbst. Bequemer:":
        "· text blocks for new cover letter drafts. The app fills in placeholders in {curly braces}; you write text in "
        "[square brackets] yourself for each application. More convenient:",
    "Stellen passen zu über 75 %.": "jobs match over 75 %.",
    "Stellen passen zu über 75 %. Am häufigsten fehlt dir": "jobs match over 75 %. Most often you are missing",
}

# Muster: {} steht für einen beliebigen Teil (wird, wenn möglich, selbst übersetzt), {n} für eine Zahl
MUSTER: list[tuple[str, str]] = [
    ("{n} Stellen", "{} jobs"), ("({n} Stelle(n))", "({} job(s))"), ("{n} % der Stellen", "{} % of jobs"),
    ("{n} von {n} erfüllt", "{} of {} met"), ("{n} von {n}", "{} of {}"), ("{n} Zeichen", "{} characters"),
    ("Anzeige öffnen · ID {}", "Open ad · ID {}"), ("gefunden {}", "found {}"), ("Bewerbung: {}", "Application: {}"),
    ("Grundkenntnisse: +{} · gut: +{}", "basic: +{} · good: +{}"), ("gut: +{}", "good: +{}"),
    ("(bis +{} Ø-Fit)", "(up to +{} avg. fit)"), ("Gewicht {}", "weight {}"),
    ("{} · Fit {n} % · frisch – früh bewerben lohnt sich", "{} · Fit {} % · fresh – applying early pays off"),
    ("· Fit {n} % · passt: {} · fehlt: {}", "· Fit {} % · matches: {} · missing: {}"),
    ("· Fit {n} % · passt: {}", "· Fit {} % · matches: {}"), ("Quelle: {}", "Source: {}"),
    ("Vorschau {}", "Preview {}"), ("{} entfernen?", "Remove {}?"), ("Bericht vom {}", "Report from {}"),
    ("Noch {n} Platzhalter in [eckigen Klammern] – bitte vor dem Abschicken ersetzen.",
     "{} placeholders left in [square brackets] – please replace them before sending."),
    ("Noch {n} Platzhalter: {}", "{} placeholders left: {}"), ("{n} Punkt(e) offen.", "{} item(s) open."),
    ("Beste offene Stelle: {} ({n} %)", "Best open job: {} ({} %)"),
    ("Erinnerung für den nächsten Besuch ({})", "Reminder for the next visit ({})"),
    ("{n} Seite(n) gelesen", "{} page(s) read"), ("Initiativ bewerben ({n})", "Speculative applications ({})"),
    ("Alle Firmen ({n})", "All companies ({})"), ("Initiativ möglich ({n} neu)", "Speculative possible ({} new)"),
    ("Diesen Monat aus der Oberfläche: {} von höchstens {} Aufrufen · {} Eingabe- und {} Ausgabe-Tokens.",
     "This month from the interface: {} of at most {} calls · {} input and {} output tokens."),
    ("Pipeline (GitHub, per WIF) diesen Monat: {} Aufrufe · {} Eingabe-Tokens (davon {} günstig aus dem Cache) · {} "
     "Ausgabe-Tokens.", "Pipeline (GitHub, via WIF) this month: {} calls · {} input tokens ({} of them cheap from "
                        "the cache) · {} output tokens."),
    ("Version {} (Entwicklungsordner – Updates per Synchronisieren).", "Version {} (development folder – updates via "
                                                                      "Sync)."),
    ("Version {}", "Version {}"),
    ("Stellen zählen, wenn sie höchstens {n} Minuten mit Bahn/ÖPNV entfernt sind. Jetzt:",
     "Jobs count if they are at most {} minutes away by public transport. Now:"),
    ("Gilt ab dem nächsten Lauf der Pipeline. Aktiv: {n} von höchstens {n}. Pro Lauf bis zu {n} Abrufe bei der "
     "Bundesagentur und {n} bei Stellenwerk (Suchen plus nachgeladene Anzeigentexte).",
     "Applies from the next pipeline run. Active: {} of at most {}. Per run up to {} requests to the Federal "
     "Employment Agency and {} to Stellenwerk (searches plus loaded ad texts)."),
    ("In fünf Schritten zur ersten Suche, dazu optional KI und Postfach. Noch {n} Schritt(e) offen.",
     "Five steps to the first search, plus optional AI and mailbox. {} step(s) left."),
    ("Die {n} häufigsten Anforderungen der letzten {n} Monate. Erst {n} Monat(e) mit genug Stellen – ein Trend zeigt "
     "sich ab etwa drei Monaten.", "The {} most common requirements of the last {} months. Only {} month(s) with "
                                  "enough jobs so far – a trend shows from about three months."),
    ("Die {n} häufigsten Anforderungen der letzten {n} Monate.", "The {} most common requirements of the last {} "
                                                                 "months."),
    ("Sichert, was nur auf diesem Mac liegt ({n} Dateien): persönliche Angaben, Zeugnisse und Zertifikate, "
     "Bewerbungsordner, KI-Vorbereitungen – dazu Master-CV und Einstellungen. Mit Passwort als verschlüsseltes "
     "Disk-Image (AES-256), ohne als ZIP. Nicht enthalten: der API-Schlüssel (Schlüsselbund). Ablage: Dokumente → "
     "Job-Monitor Sicherungen.", "Backs up what only exists on this computer ({} files): personal details, references "
                                 "and certificates, application folders, AI preparations – plus master CV and "
                                 "settings. With a password as an encrypted disk image (AES-256), without as a ZIP. Not "
                                 "included: the API key (keychain). Location: Documents → Job-Monitor Sicherungen."),
    ("Ø-Fit über {n} Stellen mit genug Angaben:", "Avg. fit over {} jobs with enough information:"),
    ("– Stand {}, bleibt auch, wenn die Anzeige offline geht", "– as of {}, stays even if the ad goes offline"),
    ("läuft wieder (geprüft beim Lauf am {})", "working again (checked on the run of {})"),
    ("{n} neue Stelle · {}", "{} new job · {}"), ("{n} neue Stellen · {}", "{} new jobs · {}"),
    ("{n} Quellen, alle ohne Fehler · {}", "{} sources, all without errors · {}"),
    ("{n} Seiten zum selbst Ansehen", "{} pages to look at yourself"),
    ("{n} (+{n} optional)", "{} (+{} optional)"), ("Sprache: {}.{}", "Language: {}.{}"),
    ("Alles vorbereitet: {}", "Everything prepared: {}"),
    ("({n} Stellen).", "({} jobs)."), ("(in {n} Stellen).", "(in {} jobs)."),
    ("Bundesagentur für Arbeit ({})", "Federal Employment Agency ({})"),
    ("{} · Quelle: {} (KI-Einschätzung {n})", "{} · Source: {} (AI estimate {})"),
    ("{n} Firmen in Reichweite nehmen Initiativbewerbungen an. Die ganze Liste (mit Hinweis, wo es gerade passende "
     "Stellen gibt) steht in der App unter Firmen → Initiativ bewerben.",
     "{} companies within reach accept speculative applications. The full list (with a note where there are matching "
     "jobs right now) is in the app under Companies → Speculative application."),
    ("{n} Alert-Mail(s) gelesen; {n} Stelle(n) darin ohne passendes Rollen-Stichwort im Titel übersprungen – "
     "Alert-Suchbegriffe prüfen", "{} alert email(s) read; {} job(s) in them skipped without a matching role keyword "
                                 "in the title – check the alert search terms"),
    ("Stellen passen zu über 75 %, eine ist {}. Am häufigsten fehlt dir",
     "jobs match over 75 %, one is {}. Most often you are missing"),
    ("Stellen passen zu über 75 %, {n} sind {}. Am häufigsten fehlt dir",
     "jobs match over 75 %, {} are {}. Most often you are missing"),
    ("Stellen passen zu über 75 %, eine ist {}.", "jobs match over 75 %, one is {}."),
    ("Stellen passen zu über 75 %, {n} sind {}.", "jobs match over 75 %, {} are {}."), ("Design „{}“ gewählt. {}", "Design “{}” chosen. {}"),
    ("Gespeichert: {}", "Saved: {}"), ("Gespeichert und erstellt: {}", "Saved and created: {}"),
]

# Texte in den Skripten der Seite (wörtlich ersetzt)
SKRIPT: dict[str, str] = {
    "'Kopiert'": "'Copied'",
    "die KI arbeitet, meist 10 bis 40 Sekunden. Fenster bitte offen lassen.":
        "the AI is working, usually 10 to 40 seconds. Please keep the window open.",
    "'oder Datei hierher ziehen'": "'or drag a file here'",
    "'Diese Datei passt hier nicht (erwartet: '": "'This file does not fit here (expected: '",
    "' Zeichen'": "' characters'",
}
