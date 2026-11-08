"""Persistenter Zustand in SQLite: gemeldete Stellen, bekannte Rohdaten-Einträge, letzter Lauf."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    key TEXT PRIMARY KEY, title TEXT, company TEXT, url TEXT, source TEXT, score INTEGER, first_seen TEXT
);
CREATE TABLE IF NOT EXISTS seen_urls (url TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS crawled (source TEXT, item_id TEXT, first_seen TEXT, PRIMARY KEY (source, item_id));
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS job_detail (
    id TEXT PRIMARY KEY, key TEXT, title TEXT, company TEXT, url TEXT, anforderungen_json TEXT, fit INTEGER,
    first_seen TEXT
);
CREATE TABLE IF NOT EXISTS quellen_verlauf (
    datum TEXT, art TEXT, name TEXT, rohtreffer INTEGER, status TEXT, PRIMARY KEY (datum, art, name)
);
"""


class State:
    def __init__(self, path: Path | str, readonly: bool = False):
        """readonly: für Oberfläche und `make cv` – die Datei gehört der Pipeline und wird von ihr committet;
        lokale Änderungen würden beim Synchronisieren mit ihr kollidieren."""
        self.readonly = readonly
        if readonly:
            if not Path(path).exists():
                self.db = sqlite3.connect(":memory:")
                self.db.executescript(SCHEMA)
            else:
                self.db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, timeout=30)   # liest die App gerade, kurz warten statt abbrechen
            self.db.executescript(SCHEMA)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(job_detail)")}
        if "frist" not in columns and not readonly:   # ältere Datenbanken ohne Frist-Spalte
            self.db.execute("ALTER TABLE job_detail ADD COLUMN frist TEXT")
            columns.add("frist")
        self._frist = "frist" if "frist" in columns else "NULL"
        # Suchprofil (werkstudent, junior …); ältere Datenbanken ohne Spalte → NULL = erstes Profil
        seen_columns = {row[1] for row in self.db.execute("PRAGMA table_info(seen)")}
        if not readonly:
            for table, cols in (("seen", seen_columns), ("job_detail", columns)):
                if "profil" not in cols:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN profil TEXT")
                    cols.add("profil")
        self._profil = "profil" if "profil" in columns else "NULL"
        # Eckdaten (Stunden, Vergütung, Remote, Start) von der KI; ältere Datenbanken ohne Spalte → leer
        if "eckdaten_json" not in columns and not readonly:
            self.db.execute("ALTER TABLE job_detail ADD COLUMN eckdaten_json TEXT")
            columns.add("eckdaten_json")
        self._eckdaten = "eckdaten_json" if "eckdaten_json" in columns else "NULL"

    def close(self) -> None:
        if not self.readonly:
            self.db.commit()
        self.db.close()

    # --- Zeitplan ---
    def last_success(self) -> datetime | None:
        row = self.db.execute("SELECT v FROM meta WHERE k='last_success'").fetchone()
        return datetime.fromisoformat(row[0]) if row else None

    def get_meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def set_last_success(self, when: datetime) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES ('last_success', ?)", (when.isoformat(),))

    def is_due(self, now: datetime, interval_days: int, tolerance_hours: int = 0) -> bool:
        """Fällig, wenn der letzte erfolgreiche Lauf mindestens interval_days Kalendertage (Ortszeit) her ist.

        Nach Kalendertagen, nicht nach Stunden: Ein Hand-Lauf am Abend blockiert sonst den Cron am nächsten Morgen.
        tolerance_hours wird nicht mehr gebraucht und nur noch aus Kompatibilität angenommen."""
        last = self.last_success()
        if last is None:
            return True
        if now.tzinfo and last.tzinfo:
            last = last.astimezone(now.tzinfo)
        return (now.date() - last.date()).days >= interval_days

    # --- gemeldete Stellen ---
    def is_new(self, job: Job) -> bool:
        if self.db.execute("SELECT 1 FROM seen WHERE key=?", (job.key,)).fetchone():
            return False
        return not (job.url and self.db.execute("SELECT 1 FROM seen_urls WHERE url=?", (job.url,)).fetchone())

    def mark_reported(self, job: Job, today: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO seen (key, title, company, url, source, score, first_seen, profil) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (job.key, job.title, job.company, job.url, job.source, job.score, today, job.profil))
        if job.url:
            self.db.execute("INSERT OR IGNORE INTO seen_urls VALUES (?)", (job.url,))

    # --- Anforderungen je Stelle (für den lokalen Lebenslauf-Zuschnitt, nichts Persönliches) ---
    def update_detail(self, id_: str, anforderungen: dict[str, float], fit: int | None,
                      eckdaten: dict | None = None) -> None:
        """Anforderungen, Fit und (falls gelesen) Eckdaten einer gespeicherten Stelle ersetzen (Nachbewertung)."""
        self.db.execute("UPDATE job_detail SET anforderungen_json=?, fit=? WHERE id=?",
                        (json.dumps(anforderungen, ensure_ascii=False), fit, id_))
        if eckdaten is not None:
            self.db.execute("UPDATE job_detail SET eckdaten_json=? WHERE id=?",
                            (json.dumps(eckdaten, ensure_ascii=False), id_))

    def save_job_detail(self, job: Job, today: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO job_detail (id, key, title, company, url, anforderungen_json, fit, "
                        "first_seen, frist, profil, eckdaten_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (job.short_id, job.key, job.title, job.company, job.url,
                         json.dumps(job.fit_anforderungen, ensure_ascii=False), job.fit, today, job.frist, job.profil,
                         json.dumps(job.eckdaten, ensure_ascii=False) if job.eckdaten else None))

    def job_detail(self, job_id: str) -> dict | None:
        row = self.db.execute(f"SELECT id, title, company, url, anforderungen_json, fit, {self._frist}, {self._profil}, "
                              f"{self._eckdaten} FROM job_detail WHERE id LIKE ?", (job_id.strip() + "%",)).fetchall()
        if len(row) != 1:
            return None
        id_, title, company, url, reqs, fit, frist, profil, eck = row[0]
        return {"id": id_, "title": title, "company": company, "url": url,
                "anforderungen": json.loads(reqs or "{}"), "fit": fit, "frist": frist, "profil": profil,
                "eckdaten": json.loads(eck or "{}")}

    def job_details(self, limit: int = 200) -> list[dict]:
        """Gespeicherte Stellen, neueste zuerst (für die Oberfläche)."""
        rows = self.db.execute(f"SELECT id, title, company, url, anforderungen_json, fit, first_seen, {self._frist}, "
                               f"{self._profil}, {self._eckdaten} FROM job_detail ORDER BY first_seen DESC, fit DESC "
                               f"LIMIT ?", (limit,)).fetchall()
        return [{"id": id_, "title": title, "company": company, "url": url, "anforderungen": json.loads(reqs or "{}"),
                 "fit": fit, "first_seen": first_seen, "frist": frist, "profil": profil,
                 "eckdaten": json.loads(eck or "{}")}
                for id_, title, company, url, reqs, fit, first_seen, frist, profil, eck in rows]

    # --- Verlauf je Quelle und Firma (Warnung, wenn etwas dauerhaft nichts mehr liefert) ---
    def record_source(self, datum: str, art: str, name: str, rohtreffer: int, status: str) -> None:
        """art: "quelle" oder "firma". Ein Eintrag pro Tag; ein zweiter Lauf am selben Tag ersetzt ihn."""
        self.db.execute("INSERT OR REPLACE INTO quellen_verlauf VALUES (?,?,?,?,?)",
                        (datum, art, name, rohtreffer, status))

    def source_history(self, runs: int = 12) -> dict[tuple[str, str], list[tuple[str, int, str]]]:
        """(art, name) → [(datum, rohtreffer, status)], neueste zuerst, je höchstens `runs` Einträge."""
        try:
            rows = self.db.execute("SELECT art, name, datum, rohtreffer, status FROM quellen_verlauf "
                                   "ORDER BY datum DESC").fetchall()
        except sqlite3.OperationalError:   # alte Datenbank ohne Tabelle, read-only geöffnet
            return {}
        history: dict[tuple[str, str], list[tuple[str, int, str]]] = {}
        for art, name, datum, roh, status in rows:
            entries = history.setdefault((art, name), [])
            if len(entries) < runs:
                entries.append((datum, roh, status))
        return history

    # --- Rohdaten (z. B. Hochschulbörse, für Pagination-Stopp) ---
    def is_crawled(self, source: str, item_id: str) -> bool:
        return bool(self.db.execute("SELECT 1 FROM crawled WHERE source=? AND item_id=?",
                                    (source, item_id)).fetchone())

    def mark_crawled(self, source: str, item_id: str, today: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO crawled VALUES (?,?,?)", (source, item_id, today))

    def has_crawled_any(self, source: str) -> bool:
        return bool(self.db.execute("SELECT 1 FROM crawled WHERE source=? LIMIT 1", (source,)).fetchone())
