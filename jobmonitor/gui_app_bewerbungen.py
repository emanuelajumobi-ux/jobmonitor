"""Seite „Bewerbungen“ der Oberfläche: Liste, Gespräche (Termin, Vorbereitung, Firmenprofil, Nachbereitung),
Antworten, Nachfassen und Rückblick. Teil von gui.App (Mixin); Seitenrahmen, Token und Stellenliste kommen von dort.
"""
from __future__ import annotations

import html
from datetime import date, datetime

from . import anki, antworten, anzeigen_check, kalender, ki, nachfassen, spenden, tracking
from . import bewerbung as bw
from . import gui_bewerbung as gbw
from . import gui_bewerbungen as gb
from . import gui_gespraech as ggs
from . import gui_layout as layout
from . import gui_rueckblick as grb
from .config import load_companies, load_config
from .cv_data import CvDataError, load_cv_master
from .eigene_stelle import fetcher_from
from .state import State


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


class BewerbungenSeiten:
    def bewerbungen(self, message: str = "", show_hidden: bool = False, offen_link: str = "") -> bytes:
        cfg = load_config(self.root / "config.yaml")
        rows = tracking.load(self.root / "applications.csv")
        alle = antworten.laden(self.root)
        follow = tracking.follow_ups(rows, date.today(), cfg["tracking"]["nachfassen_nach_tagen"],
                                     antworten.beantwortet(alle))
        entwuerfe = {r["link"]: nachfassen.entwurf(self.root, cfg, r) for r in follow if r.get("link")}
        ki_entwuerfe = {k: v for k, v in ki.nachfass_entwuerfe(self.root).items() if k in entwuerfe}
        entwuerfe.update(ki_entwuerfe)
        ki_an = bool(ki.schluessel())
        jobs = self.jobs()
        notizen = ggs.laden(self.root)
        angebote = ggs.angebote_html(ggs.angebote(rows, {d["url"]: d for d in jobs}, notizen))
        body = (layout.head("Bewerbungen", "Deine Liste (applications.csv) · wird automatisch synchronisiert")
                + message + gb.render(rows, follow, self.token, show_hidden, entwuerfe,
                                      gb.offene_antworten(self.root, rows), antworten.neueste(alle),
                                      anzeigen_check.offline(anzeigen_check.laden(self.root)),
                                      gb.gespraeche(rows, date.today()),
                                      {d["url"]: (d["passt"], d["fehlt"]) for d in jobs},
                                      kalender.eingetragen(self.root), ki.vorbereitungen(self.root),
                                      ki_an, offen_link, set(ki_entwuerfe), ki.firmenprofile(self.root),
                                      notizen, angebote)
                + gbw.list_card(self.root, cfg))
        return self.page("Bewerbungen", body, "bewerbungen", ggs.CSS)

    def nachbereitung(self, form: dict) -> bytes:
        """Nach dem Gespräch: Notizen und Bauchgefühl speichern, optional Danke-Mail mit KI entwerfen."""
        link = form.get("link", "")
        rows = tracking.load(self.root / "applications.csv")
        row = next((r for r in rows if r.get("link") == link and r.get("termin")), None)
        if row is None:
            return self.bewerbungen('<div class="card err">Gespräch nicht gefunden.</div>')
        ggs.notiz_speichern(self.root, link, form.get("notizen", ""), form.get("gefuehl", ""))
        if form.get("aktion") != "danke":
            return self.bewerbungen('<div class="card"><p class="ok">Notizen gespeichert.</p></div>', offen_link=link)
        cfg = load_config(self.root / "config.yaml")
        stelle = next((d for d in self.jobs() if d["url"] == link), None) or {}
        titel = bw.clean_title(stelle.get("title") or (row.get("notizen") or "").split("\n")[0]) or "Stelle"
        try:
            ggs.danke(self.root, cfg, row, titel, (bw.load_profile(self.root) or {}).get("name", ""))
        except ki.KiError as exc:
            return self.bewerbungen(f'<div class="card err">{esc(exc)}</div>', offen_link=link)
        return self.bewerbungen(f'<div class="card"><p class="ok">Danke-Mail an {esc(row.get("firma"))} entworfen '
                                f'(unter „Gespräche“ → „Nach dem Gespräch“). Lesen, kopieren und selbst senden.</p>'
                                f'</div>', offen_link=link)

    def rueckblick(self) -> bytes:
        state = State(self.root / "state" / "seen.sqlite", readonly=True)
        stellen = state.job_details(limit=5000)
        state.close()
        z = grb.zahlen(tracking.load(self.root / "applications.csv"), antworten.laden(self.root), stellen, date.today())
        return self.page("Rückblick", grb.render(z), "rueckblick", grb.CSS)

    def nachfassen_ki(self, form: dict) -> bytes:
        """Nachfrage-Mail für eine fällige Bewerbung mit KI formulieren (statt der Textvorlage)."""
        cfg = load_config(self.root / "config.yaml")
        link = form.get("link", "")
        rows = tracking.load(self.root / "applications.csv")
        row = next((r for r in tracking.follow_ups(rows, date.today(), cfg["tracking"]["nachfassen_nach_tagen"])
                    if r.get("link") == link), None)
        if row is None:
            return self.bewerbungen('<div class="card err">Für diese Bewerbung ist gerade keine Nachfrage fällig.</div>')
        folder = nachfassen._ordner(self.root, cfg, link)
        titel = (bw.clean_title(bw.meta(folder)["title"]) if folder else
                 bw.clean_title((row.get("notizen") or "").split("\n")[0]) or "Stelle")
        try:
            ki.nachfassen(self.root, cfg, row, titel, row.get("tage", 0), (bw.load_profile(self.root) or {}).get("name", ""))
        except ki.KiError as exc:
            return self.bewerbungen(f'<div class="card err">{esc(exc)}</div>')
        return self.bewerbungen(f'<div class="card"><p class="ok">Nachfrage an {esc(row.get("firma"))} mit KI formuliert '
                                f'(unter „Nachfassen“). Lesen, kopieren und selbst abschicken.</p></div>')

    def firmenprofil(self, form: dict) -> bytes:
        """Firmen-Kurzprofil mit KI für eine Bewerbung aus der Karte „Gespräche“."""
        from urllib.parse import urlsplit

        from .models import normalize
        cfg = load_config(self.root / "config.yaml")
        link = form.get("link", "")
        row = next((r for r in tracking.load(self.root / "applications.csv") if r.get("link") == link), None)
        if row is None:
            return self.bewerbungen('<div class="card err">Bewerbung nicht gefunden.</div>')
        firma = row.get("firma") or ""
        ziel = normalize(firma)
        try:
            eintrag = next((f for f in load_companies(self.root / "companies.yaml").get("firmen") or []
                            if normalize(f.get("name", "")) == ziel), None)
        except (OSError, ValueError):
            eintrag = None
        start = lambda u: f"{urlsplit(u).scheme}://{urlsplit(u).netloc}/"  # noqa: E731
        karriere = (eintrag or {}).get("karriereseite_url") or ""
        # Firma in companies.yaml: ihre Startseite und Karriereseite; sonst die Startseite der Anzeigen-Domain
        urls = [start(karriere), karriere] if karriere.startswith("http") else (
            [start(link)] if link.startswith("http") else [])
        state = State(self.root / "state" / "seen.sqlite", readonly=True)
        stellen = [d for d in state.job_details(limit=2000) if ziel and ziel in normalize(d["company"])]
        state.close()
        try:
            seiten = ki.firmen_text(urls, fetcher_from(cfg))
            ki.firmenprofil(self.root, cfg, firma, seiten, stellen)
        except ki.KiError as exc:
            return self.bewerbungen(f'<div class="card err">{esc(exc)}</div>', offen_link=link)
        hinweis = "" if seiten else " Die Webseite war nicht lesbar – das Profil stützt sich nur auf die gefundenen Stellen."
        return self.bewerbungen(f'<div class="card"><p class="ok">Firmenprofil für {esc(firma)} erstellt (unter '
                                f'„Gespräche“ → „Firmenprofil“).{esc(hinweis)}</p></div>', offen_link=link)

    def anki(self, form: dict) -> bytes:
        """Gesprächsvorbereitung als Karteikarten nach Anki (AnkiConnect, lokal)."""
        link = form.get("link", "")
        text = ki.vorbereitungen(self.root).get(link)
        row = next((r for r in tracking.load(self.root / "applications.csv") if r.get("link") == link), None)
        if not text or row is None:
            return self.bewerbungen('<div class="card err">Für diese Bewerbung gibt es noch keine KI-Vorbereitung.</div>')
        try:
            neu, alt, stapel = anki.senden(row.get("firma") or "Firma", anki.karten(text, row.get("firma") or "der Firma"))
        except anki.AnkiError as exc:
            return self.bewerbungen(f'<div class="card err">{esc(exc)}</div>', offen_link=link)
        rest = f" {alt} gab es schon." if alt else ""
        return self.bewerbungen(f'<div class="card"><p class="ok">{neu} Karte(n) im Anki-Stapel „{esc(stapel)}“ angelegt.'
                                f'{esc(rest)} Viel Erfolg beim Üben!</p></div>', offen_link=link)

    def vorbereitung(self, form: dict) -> bytes:
        """Gesprächsvorbereitung mit KI für eine Bewerbung aus der Karte „Gespräche“."""
        cfg = load_config(self.root / "config.yaml")
        link = form.get("link", "")
        row = next((r for r in tracking.load(self.root / "applications.csv") if r.get("link") == link), None)
        if row is None:
            return self.bewerbungen('<div class="card err">Bewerbung nicht gefunden.</div>')
        stelle = next((d for d in self.jobs() if d["url"] == link), None) or {}
        stelle = {"title": stelle.get("title") or (row.get("notizen") or "").split("\n")[0] or "Stelle",
                  "company": row.get("firma"), "anforderungen": stelle.get("anforderungen") or {}}
        try:
            cv, _ = load_cv_master(self.root)
            if not cv:
                raise ki.KiError("Keine cv_master.yaml – ohne Lebenslauf kann die KI nichts belegen.")
            anzeige = ki.anzeige(self.root, link, fetcher_from(cfg))
            frueher = ggs.frueher_notizen(ggs.laden(self.root), tracking.load(self.root / "applications.csv"),
                                          row.get("firma", ""), link)
            ki.vorbereitung(self.root, cfg, link, stelle, anzeige, cv, notizen=frueher)
        except (ki.KiError, CvDataError) as exc:
            return self.bewerbungen(f'<div class="card err">{esc(exc)}</div>')
        hinweis = "" if anzeige else " Die Anzeige selbst war nicht lesbar; die KI kannte nur Titel und Anforderungen."
        return self.bewerbungen(f'<div class="card"><p class="ok">Vorbereitung für {esc(row.get("firma"))} erstellt '
                                f'(unter „Gespräche“ → „Darauf vorbereiten“).{esc(hinweis)}</p></div>',
                                offen_link=link)

    def termin(self, form: dict) -> bytes:
        """Gesprächstermin setzen, in den Kalender eintragen oder entfernen (applications.csv → termin)."""
        path = self.root / "applications.csv"
        rows = tracking.load(path)
        row = next((r for r in rows if r.get("link") == form.get("link")), None)
        if row is None:
            return self.bewerbungen('<div class="card err">Eintrag nicht gefunden.</div>')
        aktion = form.get("aktion")
        try:
            if aktion == "setzen":
                start = datetime.fromisoformat(form.get("termin", ""))
                row["termin"] = start.isoformat(timespec="minutes")
                if row.get("status") in ("beworben", "nachgefasst"):
                    row["status"] = "Antwort"
                tracking.save(path, rows)
                msg = f"{row['firma']}: Gespräch am {start:%d.%m.%Y um %H:%M} Uhr eingetragen."
            elif aktion == "kalender":
                start = datetime.fromisoformat(row.get("termin") or "")
                titel = (row.get("notizen") or "").splitlines()[0] if row.get("notizen") else ""
                notiz = f"{titel}\n{row.get('link', '')}\nVorbereitung in Job-Monitor → Bewerbungen → Gespräche."
                ergebnis = kalender.anlegen(self.root, load_config(self.root / "config.yaml"), row.get("link", ""),
                                            f"Vorstellungsgespräch {row['firma']}", start, notiz)
                msg = (f"{row['firma']}: im Kalender eingetragen (Hinweis einen Tag und eine Stunde vorher)."
                       if ergebnis == "neu" else f"{row['firma']}: stand schon im Kalender.")
            elif aktion == "entfernen":
                row["termin"] = ""
                tracking.save(path, rows)
                msg = f"{row['firma']}: Termin entfernt (im Kalender bleibt er, falls eingetragen)."
            else:
                return self.bewerbungen('<div class="card err">Unbekannte Aktion.</div>')
        except ValueError:
            return self.bewerbungen('<div class="card err">Bitte Datum und Uhrzeit angeben.</div>')
        except kalender.KalenderError as exc:
            return self.bewerbungen(f'<div class="card err">{esc(exc)}</div>')
        return self.bewerbungen(f'<div class="card"><p class="ok">{esc(msg)}</p></div>')

    def antwort(self, form: dict) -> bytes:
        """Erkannte Antwort übernehmen (Status setzen) oder nur abhaken."""
        path = self.root / "applications.csv"
        rows = tracking.load(path)
        a = next((x for x in antworten.laden(self.root) if x.schluessel == form.get("schluessel")), None)
        if a is None:
            return self.bewerbungen('<div class="card err">Antwort nicht gefunden.</div>')
        msg = f"{a.firma}: {a.label} abgehakt."
        if form.get("aktion") == "uebernehmen" and a.status:
            row = next((r for r in rows if r.get("link") == a.link), None)
            if row is None:
                return self.bewerbungen('<div class="card err">Bewerbung nicht mehr in der Liste.</div>')
            row["status"] = a.status
            notiz = f"{a.label} am {a.datum} (aus dem Postfach erkannt)"
            row["notizen"] = f"{row.get('notizen', '')}\n{notiz}".strip()
            if a.termin and not row.get("termin"):
                row["termin"] = a.termin
            tracking.save(path, rows)
            msg = f"{a.firma}: Status auf „{a.status}“ gesetzt. Wird beim Synchronisieren hochgeladen."
            if a.termin and row["termin"] == a.termin:
                msg += f" Gesprächstermin {a.termin[8:10]}.{a.termin[5:7]}. um {a.termin[11:16]} Uhr eingetragen."
        gb.erledigen(self.root, a.schluessel)
        gruss = (spenden.zusage(load_config(self.root / "config.yaml"), a.firma)
                 if form.get("aktion") == "uebernehmen" and a.status == "Zusage" else "")
        return self.bewerbungen(f'<div class="card"><p class="ok">{esc(msg)}</p></div>{gruss}')

    def nachgefasst(self, form: dict) -> bytes:
        path = self.root / "applications.csv"
        rows = tracking.load(path)
        row = nachfassen.markieren(rows, form.get("link", ""), date.today())
        if row is None:
            return self.bewerbungen('<div class="card err">Eintrag nicht gefunden (Status nicht mehr „beworben“?).'
                                    '</div>')
        tracking.save(path, rows)
        return self.bewerbungen(f'<div class="card"><p class="ok">{esc(row["firma"])}: als nachgefasst markiert. '
                                f'Die Erinnerung ist erledigt; das Datum steht in den Notizen.</p></div>')

    def bewerbungen_save(self, form: dict) -> bytes:
        path = self.root / "applications.csv"
        vorher = {r.get("link"): r.get("status") for r in tracking.load(path)}
        rows, changes = gb.apply(tracking.load(path), form, date.today())
        if changes:
            tracking.save(path, rows)
        msg = f"{changes} Änderung(en) gespeichert." if changes else "Keine Änderungen."
        neu_zugesagt = [r for r in rows if r.get("status") == "Zusage" and vorher.get(r.get("link")) != "Zusage"]
        gruss = (spenden.zusage(load_config(self.root / "config.yaml"), neu_zugesagt[0].get("firma", ""))
                 if neu_zugesagt else "")
        return self.bewerbungen(f'<div class="card"><p class="ok">{msg}</p></div>{gruss}', bool(form.get("alle")))
