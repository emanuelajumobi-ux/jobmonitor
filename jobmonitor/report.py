"""Markdown-Bericht."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import fristen, traumjob
from .fit import eckdaten_text
from .models import Job, SourceResult

# Quellen, die um einen Rücklink bitten (Bedingungen von Arbeitnow und Adzuna)
QUELL_LINKS = {"Arbeitnow": "https://www.arbeitnow.com", "Adzuna": "https://www.adzuna.de"}


def fit_line(job: Job) -> str:
    if job.fit is None:
        return "Fit: zu wenig Angaben in der Anzeige" if job.fit_anforderungen else "Fit: –"
    parts = [f"Fit {job.fit} %"]
    if job.fit_passt:
        parts.append("passt: " + ", ".join(job.fit_passt[:6]))
    if job.fit_fehlt:
        parts.append("fehlt: " + ", ".join(job.fit_fehlt[:6]))
    return " · ".join(parts)


@dataclass
class InitiativTip:
    firma: str
    url: str
    warum: str
    neu: bool


@dataclass
class Report:
    day: date
    results: list[SourceResult]
    jobs: list[Job]
    initiativ: list[InitiativTip] = field(default_factory=list)
    follow_ups: list[dict] = field(default_factory=list)
    fit_hinweis: str = ""
    traum_name: str = "Cloud Security"
    profile: dict[str, str] = field(default_factory=dict)   # aktive Suchprofile: Schlüssel → Name, in Reihenfolge
    gesundheit: list = field(default_factory=list)          # quellen_verlauf.Warnung: liefert dauerhaft nichts
    antworten: list = field(default_factory=list)           # antworten.Antwort: neu erkannte Antworten von Firmen
    offline: list = field(default_factory=list)             # Einträge aus applications.csv, deren Anzeige weg ist
    initiativ_alle: list[InitiativTip] | None = None        # alle Firmen mit Initiativ-Möglichkeit (initiativ_liste)

    def _initiativ(self) -> list[str]:
        """Nur, was neu dazukam – die vollständige Liste steht in der App unter Firmen → Initiativ bewerben (dieselbe
        Auswahl, siehe initiativ_liste). Ohne `initiativ_alle` (ältere Aufrufe): wie früher alle Vorschläge."""
        if self.initiativ_alle is None:
            tips, kopf = self.initiativ, f"## Initiativ möglich ({len(self.initiativ)})"
        else:
            tips = [t for t in self.initiativ_alle if t.neu]
            kopf = f"## Initiativ möglich ({len(tips)} neu)"
        out = [kopf, ""]
        if self.initiativ_alle is not None:
            out += [f"{len(self.initiativ_alle)} Firmen in Reichweite nehmen Initiativbewerbungen an. Die ganze Liste "
                    f"(mit Hinweis, wo es gerade passende Stellen gibt) steht in der App unter Firmen → Initiativ "
                    f"bewerben." + (" Neu dazugekommen:" if tips else ""), ""]
        elif not tips:
            out += ["Keine Vorschläge (alle Firmen mit offener Initiativbewerbung haben gerade Treffer oder sind "
                    "unbekannt).", ""]
        for tip in tips:
            neu = " 🆕" if tip.neu else ""
            out += [f"- **{tip.firma}**{neu}: [Initiativbewerbung]({tip.url}) – {tip.warum}"]
        return out + [""]

    @property
    def mehrere_profile(self) -> bool:
        return len(self.profile) > 1

    def by_profil(self) -> list[tuple[str, list[Job]]]:
        """(Profilname, Stellen) je aktivem Profil; Stellen unbekannter Profile landen beim ersten."""
        keys = list(self.profile) or [""]
        groups: dict[str, list[Job]] = {k: [] for k in keys}
        for job in self.jobs:
            groups[job.profil if job.profil in groups else keys[0]].append(job)
        return [(self.profile.get(k, k), groups[k]) for k in keys]

    @property
    def failed_sources(self) -> list[str]:
        return [r.name for r in self.results if r.failed]

    def subject(self, prefix: str) -> str:
        warn = f" – ⚠ {len(self.failed_sources)} Quelle(n) ausgefallen" if self.failed_sources else ""
        if self.gesundheit:
            warn += f" – 🔎 {len(self.gesundheit)} Quelle(n) beobachten"
        if self.antworten:
            warn += f" – ✉️ {len(self.antworten)} Antwort(en) von Firmen"
        traum = sum(1 for j in self.jobs if j.traum)
        star = f" – ⭐ {traum}× {self.traum_name}" if traum else ""
        teile = f" ({', '.join(f'{name}: {len(jobs)}' for name, jobs in self.by_profil())})" \
            if self.mehrere_profile and self.jobs else ""
        return f"{prefix} {self.day:%d.%m.%Y}: {len(self.jobs)} neue Stelle(n){teile}{star}{warn}"

    def render(self) -> str:
        out = [f"# Job-Monitor – {self.day:%d.%m.%Y}", ""]
        out += self._status()
        traum = sorted((j for j in self.jobs if j.traum), key=lambda j: (-j.traum, -j.score))
        if traum:
            out += [f"## ⭐ {self.traum_name} ({len(traum)})", ""]
            for job in traum:
                fit_txt = f" · Fit {job.fit} %" if job.fit is not None else ""
                profil = f" · {self.profile.get(job.profil, job.profil)}" if self.mehrere_profile else ""
                out.append(f"- {traumjob.stars(job.traum)} [{job.title}]({job.url}) – **{job.company}**"
                           f"{fit_txt}{profil} · {job.traum_grund} · ID `{job.short_id}`")
            out.append("")
        if self.mehrere_profile:
            for name, jobs in self.by_profil():
                out += [f"## Neue Stellen – {name} ({len(jobs)})", ""]
                if not jobs:
                    out += [f"Keine neuen passenden {name}-Stellen seit dem letzten Lauf.", ""]
                for job in jobs:
                    out += self._job(job)
        else:
            out += [f"## Neue Stellen ({len(self.jobs)})", ""]
            if not self.jobs:
                out += ["Keine neuen passenden Stellen seit dem letzten Lauf.", ""]
            for job in self.jobs:
                out += self._job(job)
        out += self._initiativ()
        if self.antworten:
            out += [f"## Antworten von Firmen ({len(self.antworten)})", ""]
            for a in self.antworten:
                vorschlag = f" → Status „{a.status}“ vorgeschlagen" if a.status else ""
                out.append(f"- **{a.firma}**: {a.label} am {a.datum[8:10]}.{a.datum[5:7]}.{vorschlag}")
            out.append("")
        if self.offline:
            out += [f"## Nicht mehr online ({len(self.offline)})", ""]
            for r in self.offline:
                titel = (r.get("notizen") or "").splitlines()[0] if r.get("notizen") else ""
                out.append(f"- **{r.get('firma')}**: [{titel or 'Anzeige'}]({r.get('link')}) ist nicht mehr erreichbar "
                           f"(Status in deiner Liste: {r.get('status')})")
            out.append("")
        if self.follow_ups:
            out += ["## Nachfassen", ""]
            for r in self.follow_ups:
                out.append(f"- {r['firma']} ({r['typ']}), beworben am {r['datum']} – seit {r['tage']} Tagen keine Antwort. {r.get('link', '')}")
            out.append("")
        out += ["---", "_Automatisch erzeugt. Es wurden keine Bewerbungen oder Mails an Firmen verschickt._", ""]
        return "\n".join(out)

    def _job(self, job: Job) -> list[str]:
        ort = job.location or "–"
        if job.remote and "remote" not in ort.lower():
            ort += " · Remote möglich"
        flags = f" _({', '.join(job.flags)})_" if job.flags else ""
        return [
            f"### {job.score} · {traumjob.stars(job.traum) + ' ' if job.traum else ''}[{job.title}]({job.url})",
            f"**{job.company}** · {ort} · Quelle: {job.source}{flags}  ",
            f"{job.reason}  ",
            f"{fit_line(job)} · ID `{job.short_id}`"
            + (f" · **{fristen.label(job.frist, self.day)}**" if job.frist else "")
            + ("  " if job.eckdaten else ""),
            *([f"Eckdaten: {' · '.join(eckdaten_text(job.eckdaten))}"] if eckdaten_text(job.eckdaten or {}) else []),
            *([f"⚠ {' · '.join(job.eckdaten['hinweise'])}"] if (job.eckdaten or {}).get("hinweise") else []),
            "",
        ]

    def _status(self) -> list[str]:
        out = ["## Status der Quellen", ""]
        for r in self.results:
            if not (r.jobs or r.errors or r.notes or r.teilfehler):
                continue  # reine Hinweisliste (z. B. Hochschulen ohne Anbindung)
            icon = "❌" if r.failed else ("⚠️" if r.errors else "✅")
            notes = f" ({'; '.join(r.notes)})" if r.notes else ""
            name = next((f"[{r.name}]({url})" for start, url in QUELL_LINKS.items() if r.name.startswith(start)),
                        r.name)   # Rücklink, um den Arbeitnow und Adzuna bitten
            out.append(f"- {icon} **{name}**: {len(r.jobs)} Rohtreffer{notes}")
            for err in r.errors[:8]:
                out.append(f"  - Fehler: {err}")
            if len(r.errors) > 8:
                out.append(f"  - … und {len(r.errors) - 8} weitere Fehler")
            for err in r.teilfehler[:8]:   # einzelne Firma: Quelle bleibt ✅, Warnung steht bei der Firma
                out.append(f"  - Nicht erreichbar: {err}")
        if self.fit_hinweis:
            out.append(f"- {self.fit_hinweis}")
        if self.gesundheit:
            out += ["", "**Quellen beobachten** (liefern seit mehreren Läufen nichts oder nur Fehler):", ""]
            out += [f"- {'Firma' if w.art == 'firma' else 'Quelle'} **{w.name}**: {w.text}" for w in self.gesundheit]
        manual = [m for r in self.results for m in r.manual_check]
        if manual:
            out += ["", "**Manuell prüfen:**", ""] + [f"- {m}" for m in manual]
        out.append("")
        return out
