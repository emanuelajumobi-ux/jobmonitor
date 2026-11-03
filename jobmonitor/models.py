from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field


def normalize(text: str) -> str:
    """Kleinbuchstaben, ohne Gender-Suffixe, Sonderzeichen und Mehrfach-Leerzeichen."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"\((?:m|w|d|f|x|all gender|gn)[^)]*\)", " ", text)
    text = re.sub(r"[*:/](?:in|innen)\b", "", text)
    text = re.sub(r"[^a-z0-9äöüß]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Job:
    title: str
    company: str
    url: str
    source: str
    location: str = ""
    remote: bool = False
    description: str = ""
    kind: str = ""          # z. B. Stellentyp der Hochschulbörse oder BA-Angebotsart
    posted: str = ""
    external_id: str = ""
    distance_km: float | None = None
    # Wird beim Bewerten gesetzt
    score: int = 0
    reason: str = ""
    flags: list[str] = field(default_factory=list)
    # Fit-Rating gegen cv_master.yaml (None = nicht bewertet oder zu wenig Angaben)
    fit: int | None = None
    fit_passt: list[str] = field(default_factory=list)
    fit_fehlt: list[str] = field(default_factory=list)
    fit_anforderungen: dict[str, float] = field(default_factory=dict)
    frist: str | None = None          # Bewerbungsfrist (ISO-Datum), aus dem Anzeigentext erkannt
    traum: int = 0                    # Traumprofil: 0 nein, 1 passend (⭐), 2 stark (⭐⭐)
    traum_grund: str = ""
    profil: str = "werkstudent"       # Suchprofil aus config.yaml (profile:), z. B. werkstudent oder junior
    eckdaten: dict = field(default_factory=dict)   # von der KI gelesen: stunden, verguetung, remote, start, abschlussarbeit

    @property
    def key(self) -> str:
        """Dedupe-Schlüssel: gleiche Stelle aus verschiedenen Quellen ergibt denselben Schlüssel."""
        company = normalize(self.company)
        company = re.sub(r"\b(gmbh|ag|se|kg|co|mbh|ohg|e v|group|deutschland)\b", "", company)
        return f"{normalize(self.title)}|{re.sub(r'\s+', ' ', company).strip()}"

    @property
    def short_id(self) -> str:
        """Kurze, stabile ID für den Bericht und `make cv JOB=<id>`."""
        return hashlib.sha1(self.key.encode("utf-8")).hexdigest()[:8]


@dataclass
class SourceResult:
    name: str
    jobs: list[Job] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    manual_check: list[str] = field(default_factory=list)   # "Firma: Grund"
    notes: list[str] = field(default_factory=list)
    # Fehler einzelner Einträge (z. B. eine Firma nicht erreichbar): die Quelle selbst läuft, gewarnt wird je Eintrag
    teilfehler: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.errors or self.teilfehler) and not self.jobs
