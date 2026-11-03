"""Nachfassen: Entwurf für eine kurze Nachfrage zu Bewerbungen, die seit `tracking.nachfassen_nach_tagen` ohne
Antwort auf „beworben“ stehen, und „nachgefasst“ markieren (Status + Notiz, Bewerbungsdatum bleibt).

Der Entwurf kommt aus cv/nachfassen_vorlage.txt. Stellentitel und Anrede stammen aus dem Bewerbungsordner, falls es
einen gibt, der Name aus profile.yaml. Abgeschickt wird nichts: Du kopierst den Text selbst.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from . import bewerbung as bw
from .cv_build import load_profile

STATUS = "nachgefasst"
DEFAULT = ("Nachfrage zu meiner Bewerbung als {stelle}\n\n{anrede}\n\nam {datum} habe ich mich bei Ihnen als {stelle} "
           "beworben und möchte mich nach dem aktuellen Stand erkundigen.\n\nViele Grüße\n{name}")


def _ordner(root: Path, cfg: dict, link: str) -> Path | None:
    return next((f for f in bw.workspaces(root, cfg) if link and bw.meta(f).get("url") == link), None)


def entwurf(root: Path, cfg: dict, row: dict) -> tuple[str, str]:
    """(Betreff, Text) für eine Zeile aus applications.csv."""
    path = root / (cfg["tracking"].get("nachfassen_vorlage") or "cv/nachfassen_vorlage.txt")
    vorlage = path.read_text(encoding="utf-8") if path.is_file() else DEFAULT
    lines = [line for line in vorlage.splitlines() if not line.startswith("#")]
    while lines and not lines[0].strip():
        lines.pop(0)
    folder = _ordner(root, cfg, row.get("link", ""))
    if folder is not None:
        stelle = bw.clean_title(bw.meta(folder)["title"])
        anrede = (bw.letter(folder) or {}).get("anrede") or bw.ANREDE
    else:
        notiz = (row.get("notizen") or "").splitlines()[0].strip() if row.get("notizen") else ""
        notiz = re.sub(r"\s*\(Score \d+\)$", "", notiz)   # Notiz aus früheren Auto-Einträgen
        stelle = ("Initiativbewerbung" if row.get("typ") == "Initiativ"
                  else bw.clean_title(notiz) if notiz else "[Stellentitel]")
        anrede = bw.ANREDE
    try:
        datum = f"{date.fromisoformat(row.get('datum', '')):%d.%m.%Y}"
    except ValueError:
        datum = "[Datum]"
    name = (load_profile(root) or {}).get("name") or "[Dein Name]"
    values = {"firma": row.get("firma", ""), "stelle": stelle, "datum": datum, "anrede": anrede, "name": name}
    filled = re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), "\n".join(lines))
    betreff, _, text = filled.partition("\n")
    if stelle == "Initiativbewerbung":   # „als Initiativbewerbung“ klingt schief
        betreff = betreff.replace("als Initiativbewerbung", "(Initiativbewerbung)")
        text = text.replace("als Initiativbewerbung beworben", "initiativ beworben")
    return betreff.strip(), text.strip()


def markieren(rows: list[dict], link: str, today: date) -> dict | None:
    """Status „nachgefasst“ und Notiz mit Datum; das Bewerbungsdatum bleibt. Gibt die Zeile zurück."""
    row = next((r for r in rows if r.get("link") == link and r.get("status") == "beworben"), None)
    if row is None:
        return None
    row["status"] = STATUS
    notiz = f"Nachgefasst am {today:%d.%m.%Y}"
    row["notizen"] = f"{row['notizen']}\n{notiz}".strip() if row.get("notizen") else notiz
    return row
