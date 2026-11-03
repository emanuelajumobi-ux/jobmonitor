"""Demo-Modus: die App mit erfundenen Beispieldaten ansehen, bevor man etwas einrichtet.

Legt einen eigenen Datenordner im temporären Verzeichnis an (Person „Alex Beispiel“, Stellen bei Beispielfirmen mit
example.com-Adressen, ein paar Bewerbungen). Die eigenen Daten werden nicht angefasst: Die Oberfläche schaltet nur
für die Dauer der Demo auf diesen Ordner um (App.demo_starten / demo_beenden). Synchronisieren und Suchen sind in der
Demo aus.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path

ORDNER = Path(tempfile.gettempdir()) / "job-monitor-demo"

CV = """# Beispiel-Lebenslauf der Demo (erfunden)
profil: Student der Wirtschaftsinformatik mit Praxis im IT-Support und ersten Projekten mit Python, SQL und Azure.
stationen:
  - rolle: Werkstudent IT-Support
    organisation: Beispiel Logistik GmbH
    von: "04/2025"
    bis: ""
    aufgaben: [Anwender-Support im Ticketsystem, Benutzerverwaltung in Active Directory, Einrichtung von Notebooks]
    technologien: [Active Directory, Microsoft 365, Windows, IT-Support]
ausbildung:
  - abschluss: Wirtschaftsinformatik (B. Sc.)
    institution: Beispiel-Hochschule Leipzig
    von: "10/2023"
    bis: "voraussichtlich 09/2027"
kenntnisse:
  - kategorie: Programmierung und Daten
    eintraege:
      - {name: Python, level: gut}
      - {name: SQL, level: gut}
      - {name: Git, level: Grundkenntnisse}
  - kategorie: Systeme
    eintraege:
      - {name: Windows, level: gut}
      - {name: Linux, level: Grundkenntnisse}
      - {name: Azure, level: Grundkenntnisse}
zertifikate:
  - {name: AZ-900 Microsoft Azure Fundamentals, datum: "03/2026", status: erreicht, im_cv: true}
projekte:
  - name: Auswertung von Lieferzeiten
    beschreibung: Python-Skript, das Lieferdaten aus einer SQL-Datenbank auswertet und als Bericht ausgibt.
    technologien: [Python, SQL]
sprachen:
  - {sprache: Deutsch, niveau: Muttersprache}
  - {sprache: Englisch, niveau: C1}
interessen: [Fotografie, Fußball]
"""

PROFIL = """name: Alex Beispiel
adresse: {strasse: Musterstraße 1, plz: "04109", ort: Leipzig}
telefon: "+49 341 0000000"
email: alex@example.com
links: {linkedin: "", github: ""}
zeitraum: ab sofort mit 20 Stunden pro Woche
anzeigen: {adresse: true, geburtsdatum: false, foto: false}
"""

# (Titel, Firma, Anforderungen, Tage alt, Eckdaten)
STELLEN = [
    ("Werkstudent IT-Support (m/w/d)", "Beispiel Logistik GmbH", {"IT-Support": 1.0, "Windows": 1.0,
     "Active Directory": 1.0, "Microsoft 365": 0.5, "Englisch": 1.0}, 0, {"stunden": 20, "remote": False}),
    ("Werkstudent Data Analytics", "Muster Energie AG", {"Python": 1.0, "SQL": 1.0, "Git": 0.5, "Englisch": 1.0},
     0, {"stunden": 16, "remote": True}),
    ("Werkstudent Cloud Operations", "Beispiel Cloud GmbH", {"Azure": 1.0, "Linux": 1.0, "Terraform": 1.0,
     "Docker": 1.0, "Python": 0.5}, 1, {"stunden": 20, "remote": True}),
    ("Praktikum IT-Sicherheit", "Muster Versicherung AG", {"Informationssicherheit": 1.0, "ISO 27001": 1.0,
     "Windows": 1.0, "MS Office": 1.0}, 2, {"abschlussarbeit": True}),
    ("Werkstudent Softwareentwicklung Python", "Beispiel Software GmbH", {"Python": 1.0, "Git": 1.0, "SQL": 0.5,
     "Docker": 0.5, "CI/CD": 0.5}, 3, {"stunden": 18}),
    ("Werkstudent Datenbanken", "Muster Handel GmbH", {"SQL": 1.0, "Python": 0.5, "Datenmigration": 1.0}, 5, {}),
    ("Werkstudent Netzwerkadministration", "Beispiel Stadtwerke", {"Netzwerk": 1.0, "Linux": 1.0, "Windows": 1.0,
     "Monitoring": 0.5}, 6, {"stunden": 20}),
]

BEWERBUNGEN = [  # (Firma, Status, Tage her, Index in STELLEN oder None)
    ("Muster Energie AG", "beworben", 4, 1),
    ("Beispiel Software GmbH", "Antwort", 12, 4),
    ("Muster Handel GmbH", "Absage", 20, 5),
]


def _url(i: int) -> str:
    return f"https://example.com/stellen/demo-{i + 1}"


def anlegen(ziel: Path | None = None, heute: date | None = None) -> Path:
    """Demo-Ordner frisch anlegen und zurückgeben."""
    from . import erststart, tracking, wohnort
    from .models import Job
    from .state import State
    ziel = ziel or ORDNER
    heute = heute or date.today()
    if ziel.exists():
        shutil.rmtree(ziel)
    erststart.vorbereiten(ziel)
    (ziel / "cv" / "cv_master.yaml").write_text(CV, encoding="utf-8")
    (ziel / "cv" / "profile.yaml").write_text(PROFIL, encoding="utf-8")
    wohnort.speichern(ziel, "Leipzig", {"leipzig": 0, "halle": 35, "markkleeberg": 20, "taucha": 25})
    (ziel / ".gui_eingerichtet.json").write_text(json.dumps({"fertig": True, "demo": True}), encoding="utf-8")
    state = State(ziel / "state" / "seen.sqlite")
    for i, (titel, firma, anf, alt, eck) in enumerate(STELLEN):
        job = Job(titel, firma, _url(i), "Demo", "Leipzig")
        job.fit_anforderungen, job.eckdaten = anf, eck
        state.save_job_detail(job, (heute - timedelta(days=alt)).isoformat())
    state.close()
    rows = [{"firma": firma, "typ": "Stelle", "status": status, "datum": (heute - timedelta(days=tage)).isoformat(),
             "link": _url(i) if i is not None else "", "notizen": STELLEN[i][0] if i is not None else "",
             "termin": ((heute + timedelta(days=3)).isoformat() + "T10:00") if status == "Antwort" else ""}
            for firma, status, tage, i in BEWERBUNGEN]
    tracking.save(ziel / "applications.csv", rows)
    return ziel


def banner(token: str) -> str:
    return (f'<div class="card info row demo-banner" style="justify-content:space-between"><p><b>Demo</b> – erfundene '
            f'Beispieldaten, nichts davon ist echt. Suchen und Synchronisieren sind aus.</p><form method="post" '
            f'action="/demo"><input type="hidden" name="token" value="{token}"><button name="aktion" value="ende" '
            f'class="small">Demo beenden</button></form></div>')


def einstieg(token: str) -> str:
    """Karte im Einrichtungs-Assistenten: erst einmal ansehen."""
    return (f'<div class="card"><h2>Erst einmal ansehen?</h2><p class="muted">Die Demo zeigt die App mit erfundenen '
            f'Beispieldaten – Stellen, Fit, Bewerbungen, Lebenslauf-Designs. Deine eigenen Daten bleiben unberührt; '
            f'„Demo beenden“ führt zurück hierher.</p><form method="post" action="/demo"><input type="hidden" '
            f'name="token" value="{token}"><button name="aktion" value="start" class="ghost">Demo ansehen</button>'
            f'</form></div>')
