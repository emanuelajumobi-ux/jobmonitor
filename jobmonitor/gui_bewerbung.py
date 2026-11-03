"""Seite „Bewerbung“ je Stelle: Anschreiben bearbeiten, PDFs bauen, Mappe zusammenstellen."""
from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from datetime import date

from . import bewerbung as bw
from . import fristen


def esc(value) -> str:
    return escape(str(value if value is not None else ""))


def render(slug: str, stelle: dict, data: dict, fit_line: str, files: list[str], anlagen: list[dict],
           token: str, message: str = "", ki_an: bool = False, abschicken: str = "", design_html: str = "") -> str:
    offen = bw.placeholders(data["text"])
    frist_txt = fristen.label(stelle.get("frist"), date.today())
    frist_html = f' · <b class="{"err" if "abgelaufen" in frist_txt else ""}">{esc(frist_txt)}</b>' if frist_txt else ""
    warn = (f'<div class="card"><p class="err">Noch {len(offen)} Platzhalter in [eckigen Klammern] – bitte vor dem '
            f'Abschicken ersetzen.</p></div>' if offen else "")
    links = "".join(f'<a class="btn ghost" href="/bewerbung/{quote(slug)}/{quote(f)}" target="_blank" data-open>{esc(f)}</a> '
                    for f in files) or '<span class="muted">Noch keine PDFs gebaut.</span>'
    anl = "".join(
        f'<li>{esc(a["name"])}{"" if a["pdfs"] else " <span class=chip>fehlt</span>"} '
        f'<span class="muted">({esc(a["pfad"])}{", " + str(len(a["pdfs"])) + " PDF" if len(a["pdfs"]) > 1 else ""})'
        f'</span></li>' for a in anlagen)
    ki = ('<button name="aktion" value="ki" class="ghost" data-ki="KI schreibt das Anschreiben …" '
          'onclick="return confirm(\'Text durch einen KI-Entwurf ersetzen? Gesendet werden die Anzeige und dein '
          'Master-CV, keine persönlichen Daten.\')">Entwurf mit KI</button>' if ki_an else
          '<a class="btn ghost" href="/einstellungen#ki" title="API-Schlüssel in den Einstellungen hinterlegen">'
          'Entwurf mit KI …</a>')
    ki_cv = ' data-ki="KI schneidet den Lebenslauf auf die Stelle zu …"' if ki_an else ""
    alles = (f'<div class="card vorbereiten row"><button form="anschreiben-form" name="aktion" value="vorbereiten"'
             f'{' data-ki="KI bereitet die Bewerbung vor …"' if ki_an else ""}>Alles vorbereiten</button>'
             f'<span class="muted">Anzeige sichern, {"Anschreiben mit KI entwerfen, " if ki_an else ""}Lebenslauf '
             f'zuschneiden und die Mappe bauen – in einem Schritt. Danach liest du alles noch einmal; abgeschickt '
             f'wird nichts.</span></div>')
    return f"""
<h1>Bewerbung: {esc(bw.clean_title(stelle["title"]))}</h1>
<p class="sub">{esc(stelle["company"])} · <a href="{esc(stelle["url"])}" target="_blank" rel="noopener">Anzeige</a> ·
{esc(fit_line)}{frist_html}</p>
{message}{warn}{alles}
<div class="card"><h2>Dateien</h2><div class="row">{links}</div>
<form method="post" action="/bewerbung/{quote(slug)}" style="margin-top:10px">
<input type="hidden" name="token" value="{token}"><button name="aktion" value="ordner" class="ghost">Ordner im Finder zeigen</button>
</form>
<form method="post" action="/bewerbung/{quote(slug)}" style="margin-top:10px" class="row"
      onsubmit="return confirm('Bewerbung verwerfen? Der Ordner mit Anschreiben und PDFs wandert in den Papierkorb.')">
<input type="hidden" name="token" value="{token}">
<label class="check"><input type="checkbox" name="ausblenden" value="1"> Stelle auch ausblenden</label>
<button name="aktion" value="verwerfen" class="ghost danger">Bewerbung verwerfen</button>
</form></div>
<form method="post" action="/bewerbung/{quote(slug)}" id="anschreiben-form"><input type="hidden" name="token" value="{token}">
<div class="card"><h2>Anschreiben</h2>
<div class="grid2"><div><label>Anrede (Ansprechperson nur, wenn die Firma sie selbst für Bewerbungen nennt)</label>
<input name="anrede" value="{esc(data["anrede"])}"></div>
<div><label>Empfänger unter dem Firmennamen (optional, z. B. Abteilung, Straße, PLZ Ort – eine Zeile je Zeile)</label>
<textarea name="empfaenger" rows="3" style="min-height:0">{esc(data["empfaenger"])}</textarea></div></div>
<label>Text (Absätze durch Leerzeile trennen; Gruß und Name ergänzt das PDF)</label>
<textarea name="text" rows="18" style="min-height:360px">{esc(data["text"])}</textarea>
</div>
<div class="card"><h2>Anlagen für die Mappe</h2><ul>{anl}</ul>
<p class="muted"><a href="/unterlagen">Unterlagen hochladen</a> (landen in cv/private/, gitignored).</p></div>
<div class="sticky row">
<button name="aktion" value="mappe"{ki_cv}>Speichern und Mappe bauen</button>
<button name="aktion" value="anschreiben" class="ghost">Nur Anschreiben-PDF</button>
<button name="aktion" value="lebenslauf" class="ghost"{ki_cv}>Nur Lebenslauf</button>
<button name="aktion" value="speichern" class="ghost">Nur speichern</button>
<button name="aktion" value="neu" class="ghost" onclick="return confirm('Text durch einen neuen Entwurf aus der Vorlage ersetzen?')">Neuer Entwurf aus Vorlage</button>
{ki}</div></form>
{design_html}
{abschicken}"""


def anzeige_karte(token: str, ziel: str, stelle: dict, text: str, gesichert) -> str:
    """Gesicherter Anzeigentext (anzeige.txt im Bewerbungsordner) – bleibt, auch wenn die Anzeige offline geht."""
    form = (f'<form method="post" action="{ziel}#anzeige"><input type="hidden" name="token" value="{token}">')
    if text.strip():
        return (f'<div class="card" id="anzeige"><details><summary><h2 style="display:inline">Gesicherte Anzeige</h2> '
                f'<span class="muted">– Stand {gesichert:%d.%m.%Y}, bleibt auch, wenn die Anzeige offline geht'
                f'</span></summary><pre class="anzeige-text">{esc(text)}</pre>{form}<button name="aktion" '
                f'value="anzeige_eintragen" class="ghost small">Text ersetzen</button> <textarea name="anzeige" rows="4" '
                f'placeholder="Neuen Anzeigentext einfügen, um den gesicherten zu ersetzen"></textarea></form>'
                f'</details></div>')
    return (f'<div class="card" id="anzeige"><h2>Anzeige sichern</h2><p class="muted">Anzeigen verschwinden oft, '
            f'bevor das Gespräch stattfindet. Gesichert liegt der Text im Bewerbungsordner – für die '
            f'Gesprächsvorbereitung und zum Nachlesen. „Alles vorbereiten“ und „Mappe bauen“ sichern ihn automatisch.'
            f'</p>{form}<div class="row"><button name="aktion" value="anzeige_sichern" class="ghost small">Jetzt '
            f'sichern</button></div><label style="margin-top:10px">Oder Text selbst einfügen (z. B. von LinkedIn, das '
            f'die App nicht abruft)</label><textarea name="anzeige" rows="4"></textarea><button name="aktion" '
            f'value="anzeige_eintragen" class="ghost small" style="margin-top:6px">Text speichern</button></form></div>')


CSS = """
.vorbereiten { gap:14px; align-items:center; flex-wrap:nowrap; } .vorbereiten button { flex:none; }
.anzeige-text { white-space:pre-wrap; font:inherit; font-size:13px; max-height:420px; overflow:auto;
  background:var(--soft, rgba(0,0,0,.03)); padding:12px; border-radius:8px; }
#anzeige summary { cursor:pointer; list-style:none; } #anzeige summary::-webkit-details-marker { display:none; }
"""


def list_card(root: Path, cfg: dict) -> str:
    items = []
    for folder in bw.workspaces(root, cfg)[:8]:
        stelle = bw.meta(folder)
        n = len(bw.files(folder))
        items.append(f'<li><a href="/bewerbung/{quote(folder.name)}">{esc(bw.clean_title(stelle["title"]))}</a> '
                     f'<span class="muted">– {esc(stelle["company"])}{f" · {n} PDF" if n else ""}</span></li>')
    return f'<div class="card"><h2>Deine Bewerbungsordner</h2><ul>{"".join(items)}</ul></div>' if items else ""
