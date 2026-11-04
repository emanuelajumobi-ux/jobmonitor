"""Bewerbungen (applications.csv) in der Oberfläche: Status, Datum, Notizen, Merken/Ausblenden von Stellen.

"verworfen" blendet eine Stelle in der Liste aus. Weil sie in applications.csv steht, trägt die Pipeline sie
nicht erneut ein. Wechselt der Status auf "beworben", wird das Datum auf heute gesetzt (außer du hast es selbst
geändert), damit die Nachfass-Erinnerung richtig rechnet.
"""
from __future__ import annotations

from datetime import date, timedelta
from html import escape
from urllib.parse import quote

from . import antworten as aw
from . import gui_gespraech as ggs
from . import kalender, ki
from . import tracking

HIDDEN = "verworfen"
ERLEDIGT = ".gui_antworten.json"     # erledigte Antwort-Vorschläge (lokal, gitignored)


def erledigt(root) -> set[str]:
    import json
    try:
        return set(json.loads((root / ERLEDIGT).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return set()


def erledigen(root, schluessel: str) -> None:
    import json
    data = erledigt(root) | {schluessel}
    (root / ERLEDIGT).write_text(json.dumps(sorted(data), ensure_ascii=False, indent=1), encoding="utf-8")


def offene_antworten(root, rows: list[dict]) -> list:
    """Erkannte Antworten zu Einträgen dieser Liste, die du noch nicht übernommen oder abgehakt hast (neueste zuerst).
    Eine Statusänderung erledigt sie von selbst, wenn der Status schon passt."""
    links = {r.get("link"): r for r in rows}
    fertig = erledigt(root)
    out = []
    for a in sorted(aw.laden(root), key=lambda a: a.datum, reverse=True):
        row = links.get(a.link)
        if row is None or a.schluessel in fertig or (a.status and row.get("status") == a.status):
            continue
        out.append(a)
    return out


NACHBEREITEN_TAGE = 14


def gespraeche(rows: list[dict], heute: date) -> list[dict]:
    """Einträge mit Gesprächstermin ab gestern (früheste zuerst), danach „Antwort“ ohne Termin, zuletzt Gespräche der
    letzten NACHBEREITEN_TAGE Tage (neueste zuerst) – für Notizen und Danke-Mail."""
    gestern = (heute - timedelta(days=1)).isoformat()
    grenze = (heute - timedelta(days=NACHBEREITEN_TAGE)).isoformat()
    mit = sorted((r for r in rows if (r.get("termin") or "")[:10] >= gestern), key=lambda r: r["termin"])
    ohne = [r for r in rows if r.get("status") == "Antwort" and not r.get("termin")]
    vorbei = sorted((r for r in rows if grenze <= (r.get("termin") or "")[:10] < gestern),
                    key=lambda r: r["termin"], reverse=True)
    return mit + ohne + vorbei


def _firmenprofil(link: str, firma: str, token: str, esc, profil: dict | None, ki_an: bool) -> str:
    """Zweites Aufklappfeld in der Gesprächskarte: Firmen-Kurzprofil (ki.firmenprofil)."""
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    if not ki_an and not profil:
        return ""
    knopf = (f'<form method="post" action="/bewerbungen/firmenprofil" class="row" style="margin-top:8px">'
             f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="link" value="{esc(link)}">'
             f'<button class="{"ghost " if profil else ""}small" data-ki="KI liest die Webseite von {esc(firma)} …">'
             f'{"Neu erstellen" if profil else "Firmenprofil mit KI erstellen"}</button><span class="muted">Aus der '
             f'Webseite der Firma und ihren gefundenen Stellen.</span></form>' if ki_an else "")
    inhalt = (f'<div class="ki-text">{ki.als_html(profil["text"], esc)}</div>' if profil else "")
    stand = f' <span class="muted">· Stand {esc(profil["datum"][8:10])}.{esc(profil["datum"][5:7])}.</span>' if profil else ""
    return f'<details><summary>Firmenprofil{stand}</summary>{inhalt}{knopf}</details>'


def _vorbereitung(link: str, token: str, esc, punkte: str, ki_text: str | None, ki_an: bool) -> str:
    """Inhalt von „Darauf vorbereiten“: KI-Vorbereitung, sobald vorhanden, sonst die kurze Liste aus dem Fit."""
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    hidden = (f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="link" '
              f'value="{esc(link)}">')
    knopf = (f'<form method="post" action="/bewerbungen/vorbereitung" class="row" style="margin-top:8px">{hidden}'
             f'<button class="{"ghost " if ki_text else ""}small" data-ki="KI bereitet das Gespräch vor …">'
             f'{"Neu mit KI erstellen" if ki_text else "Mit KI vorbereiten"}</button><span class="muted">Gesendet: Anzeige und Master-CV, keine persönlichen Daten.</span></form>'
             if ki_an else '<p class="muted"><a href="/einstellungen#ki">Mit KI vorbereiten: API-Schlüssel in den '
                           'Einstellungen hinterlegen</a></p>')
    if ki_text:
        anki = (f'<form method="post" action="/bewerbungen/anki" style="display:inline">{hidden}'
                f'<button class="ghost small" title="Fragen und Antworten als Karteikarten in den Stapel '
                f'Job-Monitor::Firma (Anki muss geöffnet sein)">Als Anki-Karten</button></form>')
        return f'<div class="ki-text">{ki.als_html(ki_text, esc)}</div><div class="row">{knopf}{anki}</div>'
    return f'<ul>{punkte}</ul>{knopf}'


def _wann(termin: str) -> str:
    return f"{termin[8:10]}.{termin[5:7]}.{termin[:4]}, {termin[11:16]} Uhr"


def _gespraech_item(r: dict, token: str, esc, fit: dict, im_kalender: set, ki_texte: dict | None = None,
                    ki_an: bool = False, offen_link: str = "", vorschlag: str = "", profile: dict | None = None,
                    notizen: dict | None = None, heute: date | None = None) -> str:
    link, termin = r.get("link", ""), r.get("termin") or ""
    passt, fehlt = fit.get(link, ([], []))
    punkte = "".join(f"<li>{esc(p)}</li>" for p in kalender.vorbereitung(passt, fehlt))
    hidden = (f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="link" '
              f'value="{esc(link)}">')
    titel = (r.get("notizen") or "").splitlines()[0] if r.get("notizen") else ""
    vorbei = bool(termin) and termin[:10] < ((heute or date.today()) - timedelta(days=1)).isoformat()
    if vorbei:
        aktion = ""
        kopf = f'<b>{esc(r.get("firma"))}</b><span class="chip">war am {esc(_wann(termin))}</span>'
    elif termin:
        wann = _wann(termin)
        drin = kalender.schluessel(link, termin[:16]) in im_kalender
        aktion = (('<span class="chip einladung">im Kalender</span>' if drin else
                   '<button name="aktion" value="kalender" class="small">In Kalender eintragen</button>')
                  + '<button name="aktion" value="entfernen" class="ghost small">Termin entfernen</button>')
        kopf = f'<b>{esc(r.get("firma"))}</b><span class="chip einladung">{esc(wann)}</span>'
    else:
        aktion = (f'<input type="datetime-local" name="termin" required style="width:auto" value="{esc(vorschlag)}">'
                  '<button name="aktion" value="setzen" class="small">Termin eintragen</button>')
        kopf = (f'<b>{esc(r.get("firma"))}</b><span class="chip">'
                f'{"Termin laut Mail – bitte bestätigen" if vorschlag else "Termin fehlt"}</span>')
    return (f'<li class="gespraech"><div class="antwort"><div>{kopf}'
            f'<p class="muted">{esc(titel)}</p></div><form method="post" action="/bewerbungen/termin" class="row">'
            f'{hidden}{aktion}</form></div><details{" open" if link == offen_link else ""}>'
            f'<summary>Darauf vorbereiten</summary>'
            f'{_vorbereitung(link, token, esc, punkte, (ki_texte or {}).get(link), ki_an)}'
            f'<p style="margin-top:8px"><a class="btn ghost small" href="/uebung?link={quote(link, safe="")}">'
            f'Gespräch üben (KI)</a></p></details>'
            f'{_firmenprofil(link, r.get("firma", ""), token, esc, (profile or {}).get(str(r.get("firma", "")).lower()), ki_an)}'
            f'{ggs.nachbereitung_html(link, (notizen or {}).get(link), token, ki_an) if termin else ""}'
            f'</li>')


def _antwort_item(a, token: str, esc) -> str:
    knopf = (f'<button name="aktion" value="uebernehmen" class="small">Status „{esc(a.status)}“ setzen</button>'
             if a.status else "")
    termin = f" · Termin laut Mail: {esc(_wann(a.termin))}" if a.termin else ""
    return (f'<li class="antwort {esc(a.art)}"><div><b>{esc(a.firma)}</b><span class="chip {esc(a.art)}">'
            f'{esc(a.label)}</span><p class="muted">am {esc(a.datum[8:10])}.{esc(a.datum[5:7])}. · von {esc(a.absender)}'
            f'{termin}</p></div><form method="post" action="/bewerbungen/antwort" class="row">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="schluessel" '
            f'value="{esc(a.schluessel)}">{knopf}<button name="aktion" value="erledigt" class="ghost small">'
            f'{"Nur abhaken" if a.status else "Gesehen"}</button></form></li>')


def by_link(rows: list[dict]) -> dict[str, dict]:
    return {r.get("link", ""): r for r in rows if r.get("link")}


def mark(rows: list[dict], job: dict, aktion: str, today: date) -> str:
    """aktion 'merken' → Status neu, 'ausblenden' → verworfen. Gibt eine kurze Meldung zurück."""
    row = by_link(rows).get(job["url"])
    status = "neu" if aktion == "merken" else HIDDEN
    if row is None:
        tracking.add_if_missing(rows, job["company"], "Stelle", job["url"], today, job["title"])
        row = rows[-1]
    elif aktion == "merken" and row.get("status") != HIDDEN:
        return f"„{job['title']}“ steht schon in deinen Bewerbungen ({row.get('status')})."
    row["status"] = status
    return (f"„{job['title']}“ gemerkt." if aktion == "merken"
            else f"„{job['title']}“ ausgeblendet (Status verworfen).")


def undo_hide(rows: list[dict], job: dict, vorher: str) -> str:
    """Ausblenden zurücknehmen: alten Status wiederherstellen bzw. den dabei angelegten Eintrag entfernen."""
    row = by_link(rows).get(job["url"])
    if row is None or row.get("status") != HIDDEN:
        return f"„{job['title']}“ ist nicht ausgeblendet."
    if vorher:
        row["status"] = vorher
    else:
        rows.remove(row)
    return f"„{job['title']}“ wird wieder angezeigt."


def apply(rows: list[dict], form: dict, today: date) -> tuple[list[dict], int]:
    """Formularwerte übernehmen. Zeilen werden über Index + Link zugeordnet (Schutz, falls die Datei sich
    inzwischen geändert hat). Gibt (neue Zeilen, Anzahl Änderungen) zurück."""
    out, changes = [], 0
    for i, row in enumerate(rows):
        if form.get(f"link_{i}") != row.get("link", ""):
            out.append(row)        # Zeile nicht im Formular (oder verschoben) → unverändert lassen
            continue
        if form.get(f"loeschen_{i}"):
            changes += 1
            continue
        new = dict(row)
        new["status"] = form.get(f"status_{i}", row.get("status", "")).strip()
        new["datum"] = form.get(f"datum_{i}", row.get("datum", "")).strip()
        new["notizen"] = form.get(f"notizen_{i}", row.get("notizen", "")).strip()
        if new["status"] == "beworben" and row.get("status") != "beworben" and new["datum"] == row.get("datum"):
            new["datum"] = today.isoformat()
        changes += new != row
        out.append(new)
    return out, changes


def _nachfassen_item(i: int, r: dict, entwurf: tuple[str, str] | None, token: str, esc, ki_an: bool = False,
                     von_ki: bool = False) -> str:
    ki_an = True   # KI-Knöpfe immer zeigen; ohne KI graut App.page sie aus (gui_layout.ki_aus)
    link = r.get("link", "")
    anzeige = (f' <a href="{esc(link)}" target="_blank" rel="noopener">Anzeige</a>' if link.startswith("http") else "")
    head = (f"<b>{esc(r['firma'])}</b> – beworben am {esc(r['datum'])}, seit {r['tage']} Tagen keine Antwort."
            f"{anzeige}")
    mark = (f'<form method="post" action="/bewerbungen/nachgefasst" style="display:inline">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="link" value="{esc(link)}">'
            f'<button class="small">Als nachgefasst markieren</button></form>')
    if entwurf is None:
        return f"<li>{head}<div class=\"row\">{mark}</div></li>"
    betreff, text = entwurf
    ki_knopf = (f'<form method="post" action="/bewerbungen/nachfassen_ki" style="display:inline">'
                f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="link" '
                f'value="{esc(link)}"><button class="ghost small" data-ki="KI formuliert die Nachfrage …">'
                f'{"Neu mit KI formulieren" if von_ki else "Mit KI formulieren"}</button></form>' if ki_an else "")
    return f"""<li>{head}
<details{" open" if von_ki else ""}><summary>Entwurf für die Nachfrage{" (von der KI)" if von_ki else ""}</summary>
<label>Betreff</label><input id="nf-b{i}" value="{esc(betreff)}" readonly>
<label>Text</label><textarea id="nf-t{i}" rows="10" readonly>{esc(text)}</textarea>
<div class="row"><button type="button" class="ghost small" data-copy="nf-b{i}">Betreff kopieren</button>
<button type="button" class="ghost small" data-copy="nf-t{i}">Text kopieren</button>{ki_knopf}{mark}</div>
</details></li>"""


def render(rows: list[dict], follow_ups: list[dict], token: str, show_hidden: bool,
           entwuerfe: dict[str, tuple[str, str]] | None = None, offen: list | None = None,
           letzte: dict | None = None, weg: dict | None = None, termine: list | None = None,
           fit: dict | None = None, im_kalender: set | None = None, ki_texte: dict | None = None,
           ki_an: bool = False, offen_link: str = "", von_ki: set | None = None,
           firmenprofile: dict | None = None, notizen: dict | None = None, angebote: str = "") -> str:
    """`entwuerfe`: Link → (Betreff, Text) der Nachfrage für fällige Bewerbungen (nachfassen.py).
    `offen`: erkannte, noch nicht erledigte Antworten; `letzte`: Link → neueste Antwort (Chip in der Tabelle);
    `weg`: Link → Datum, seit dem die Anzeige nicht mehr online ist (anzeigen_check.py); `termine`: Gespräche
    (gespraeche()); `fit`: Link → (erfüllt, fehlt) für die Vorbereitung; `im_kalender`: eingetragene Termine;
    `ki_texte`: Link → KI-Vorbereitung (ki.py), `ki_an`: Schlüssel vorhanden, `offen_link`: Vorbereitung aufklappen."""
    esc = lambda v: escape(str(v if v is not None else ""))  # noqa: E731
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("status", "")] = counts.get(r.get("status", ""), 0) + 1
    summary = " · ".join(f"{esc(s or '–')}: {n}" for s, n in sorted(counts.items(), key=lambda kv: (
        tracking.STATUSES.index(kv[0]) if kv[0] in tracking.STATUSES else 99)))
    nach = "".join(_nachfassen_item(i, r, (entwuerfe or {}).get(r.get("link", "")), token, esc, ki_an,
                                    r.get("link", "") in (von_ki or set()))
                   for i, r in enumerate(follow_ups))
    nach_html = (f'<div class="card"><h2>Nachfassen</h2><p class="muted">Seit einiger Zeit keine Antwort. Eine kurze '
                 f'Nachfrage ist üblich – der Entwurf wird nicht verschickt, du kopierst ihn selbst.</p>'
                 f'<ul class="follow">{nach}</ul></div>' if nach else "")

    antwort_html = (f'<div class="card"><h2>Antworten von Firmen</h2><p class="muted">Im Postfach erkannt (nur gelesen, '
                    f'nichts verschickt). Prüf die Mail kurz selbst, dann den Status mit einem Klick übernehmen.</p>'
                    f'<ul class="follow">{"".join(_antwort_item(a, token, esc) for a in offen)}</ul></div>'
                    if offen else "")
    letzte, weg = letzte or {}, weg or {}
    gespraech_html = (f'<div class="card"><h2>Gespräche</h2><p class="muted">Termin eintragen, mit einem Klick in den '
                      f'Kalender (Hinweis einen Tag und eine Stunde vorher) und vorbereiten.</p><ul class="follow">'
                      + "".join(_gespraech_item(r, token, esc, fit or {}, im_kalender or set(), ki_texte, ki_an,
                                                offen_link, getattr(letzte.get(r.get("link", "")), "termin", ""),
                                                firmenprofile, notizen)
                                for r in termine)
                      + '</ul></div>' if termine else "")

    trs = []
    for i in reversed(range(len(rows))):           # neueste zuerst
        r = rows[i]
        if r.get("status") == HIDDEN and not show_hidden:
            continue
        status = r.get("status", "")
        options = tracking.STATUSES + ([status] if status and status not in tracking.STATUSES else [])
        opts = "".join(f'<option{" selected" if o == status else ""}>{esc(o)}</option>' for o in options)
        link = r.get("link", "")
        link_html = (f'<a href="{esc(link)}" target="_blank" rel="noopener">{esc(r.get("firma"))}</a>'
                     if link.startswith("http") else esc(r.get("firma")))
        search = f"{r.get('firma', '')} {r.get('notizen', '')} {status}".lower()
        a = letzte.get(link)
        chip = (f' <span class="chip {esc(a.art)}" title="erkannt am {esc(a.datum)}">{esc(a.label)}</span>' if a else "")
        if link in weg:
            chip += (f' <span class="chip abgelaufen" title="Die Anzeige ist seit {esc(weg[link])} nicht mehr erreichbar">'
                     f'nicht mehr online</span>')
        trs.append(f"""<tr data-s="{esc(search)}"><td>{link_html}{chip}<br><span class="muted">{esc(r.get('typ'))}</span>
<input type="hidden" name="link_{i}" value="{esc(link)}"></td>
<td><select name="status_{i}" data-old="{esc(status)}" data-datum="datum_{i}">{opts}</select></td>
<td><input name="datum_{i}" value="{esc(r.get('datum'))}" style="width:120px"></td>
<td><textarea name="notizen_{i}" rows="2">{esc(r.get('notizen'))}</textarea></td>
<td class="act"><label class="check"><input type="checkbox" name="loeschen_{i}" value="1"> entfernen</label></td></tr>""")
    hidden_n = counts.get(HIDDEN, 0)
    toggle = ('<a href="/bewerbungen">verworfene ausblenden</a>' if show_hidden
              else f'<a href="/bewerbungen?alle=1">{hidden_n} verworfene anzeigen</a>' if hidden_n else "")
    table = ("<table class=\"apps\">" + "".join(trs) + "</table>") if trs else \
        '<p class="muted">Noch keine Einträge.</p>'
    return f"""
{angebote}
{gespraech_html}
{antwort_html}
{nach_html}
<div class="card"><h2>Alle Einträge</h2><p class="muted">{summary} {toggle}</p>
<input id="filter" placeholder="Filtern nach Firma, Notiz oder Status" style="margin-bottom:8px">
<form method="post" action="/bewerbungen"><input type="hidden" name="token" value="{token}">
<input type="hidden" name="alle" value="{1 if show_hidden else ''}">
{table}
<div class="sticky row"><button>Speichern</button><a class="btn ghost" href="/bewerbungen">Verwerfen</a></div>
</form></div>
<script>
document.querySelectorAll('select[data-old]').forEach(s => s.addEventListener('change', () => {{
  if (s.value === 'beworben' && s.dataset.old !== 'beworben')
    document.querySelector('input[name="' + s.dataset.datum + '"]').value = new Date().toISOString().slice(0, 10);
}}));
</script>"""


FRUEHER = ("Entwurf", "beworben", "nachgefasst", "Antwort", "Absage", "Zusage")


def frueher_bei_firma(rows: list[dict], firma: str, link: str) -> list[dict]:
    """Andere Bewerbungen bei derselben Firma (Name in beide Richtungen enthalten, ohne Rechtsform), neueste zuerst."""
    from .models import normalize
    ziel = normalize(firma)
    if not ziel:
        return []
    treffer = [r for r in rows if r.get("link") != link and r.get("status") in FRUEHER
               and (ziel in normalize(r.get("firma", "")) or normalize(r.get("firma", "")) in ziel)
               and normalize(r.get("firma", ""))]
    return sorted(treffer, key=lambda r: r.get("datum", ""), reverse=True)


def frueher_html(treffer: list[dict], firma: str) -> str:
    if not treffer:
        return ""
    def zeile(r):
        titel = (r.get("notizen") or "").split("\n")[0].strip() or r.get("typ", "Bewerbung")
        datum = r.get("datum", "")
        wann = f"am {datum[8:10]}.{datum[5:7]}.{datum[:4]}" if len(datum) >= 10 else ""
        return f"<li>{escape(titel)} – {escape(r.get('status', ''))} {escape(wann)}</li>"
    return (f'<div class="card info"><p><b>Bei {escape(firma)} hast du dich schon beworben:</b></p>'
            f'<ul>{"".join(zeile(r) for r in treffer[:5])}</ul><p class="muted">Bei mehreren Bewerbungen gleichzeitig '
            f'lieber im Anschreiben darauf eingehen oder vorher bei der Firma nachfragen.</p></div>')
