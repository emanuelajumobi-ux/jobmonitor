"""Stellenwerk-Portale (Jobbörsen von Hochschulen) für den Wohnort vorschlagen – im Einrichtungs-Assistenten.

Stellenwerk hat Portale für diese Städte (Stand 03.11.2026, von stellenwerk.de). Vorgeschlagen werden Portale, deren
Stadt in der Fahrzeit-Tabelle des Wohnorts liegt. Wichtig: robots.txt von stellenwerk.de antwortet mit HTTP 403 statt
mit Regeln. Deshalb ist nichts davon vorausgewählt – wer ein Portal einschaltet, entscheidet das bewusst (wie die
Freigabe in companies.yaml). Gesucht wird sparsam: wenige Suchen je Lauf, jede Anzeige nur einmal.
"""
from __future__ import annotations

from pathlib import Path

from .config import load_companies, save_companies

# Portal → (Name, Städte in der Fahrzeit-Tabelle, klein)
PORTALE = {
    "aachen": ("Aachen", ["aachen"]), "berlin": ("Berlin", ["berlin"]), "bochum": ("Bochum", ["bochum"]),
    "bonn-rhein-sieg": ("Bonn/Rhein-Sieg", ["bonn", "sankt augustin", "st augustin", "siegburg", "rheinbach"]),
    "darmstadt": ("Darmstadt", ["darmstadt"]), "dortmund": ("Dortmund", ["dortmund"]),
    "duesseldorf": ("Düsseldorf", ["düsseldorf", "duesseldorf"]),
    "duisburg-essen": ("Duisburg-Essen", ["duisburg", "essen"]),
    "erlangen-nuernberg": ("Erlangen-Nürnberg", ["erlangen", "nürnberg", "nuernberg", "fürth"]),
    "frankfurt-am-main": ("Frankfurt am Main", ["frankfurt", "frankfurt am main", "offenbach"]),
    "goettingen": ("Göttingen", ["göttingen", "goettingen"]), "hamburg": ("Hamburg", ["hamburg"]),
    "koeln": ("Köln", ["köln", "koeln", "cologne"]), "luebeck": ("Lübeck", ["lübeck", "luebeck"]),
    "schleswig-holstein": ("Schleswig-Holstein", ["kiel", "flensburg"]),
    "stuttgart": ("Stuttgart", ["stuttgart"]), "wuerzburg": ("Würzburg", ["würzburg", "wuerzburg"]),
    "wuppertal": ("Wuppertal", ["wuppertal"]),
}


def vorschlaege(zentrum: str, fahrzeiten: dict | None, max_min: int = 60) -> list[tuple[str, str]]:
    """[(Portal, Name)] in Reichweite des Wohnorts."""
    nah = {str(o).lower() for o, m in (fahrzeiten or {}).items() if isinstance(m, (int, float)) and m <= max_min}
    nah.add((zentrum or "").strip().lower())
    return [(k, name) for k, (name, orte) in PORTALE.items() if nah & set(orte)]


def eintragen(root: Path, portale: list[str]) -> list[str]:
    """Gewählte Portale als Hochschulbörse (quelle: stellenwerk) in companies.yaml; gibt die neuen Namen zurück."""
    path = root / "companies.yaml"
    doc = load_companies(path)
    if doc.get("hochschulen") is None:
        doc["hochschulen"] = []
    vorhanden = {str(h.get("karriereseite_url", "")).rstrip("/") for h in doc["hochschulen"]}
    neu = []
    for key in portale:
        if key not in PORTALE:
            continue
        url = f"https://www.stellenwerk.de/{key}"
        if url in vorhanden:
            continue
        doc["hochschulen"].append({"name": f"Stellenwerk {PORTALE[key][0]}", "kategorie": "hochschule",
                                   "karriereseite_url": url, "quelle": "stellenwerk", "aktiv": True,
                                   "notizen": "im Einrichtungs-Assistenten bewusst eingeschaltet (robots.txt: HTTP 403)"})
        neu.append(PORTALE[key][0])
    if neu:
        save_companies(doc, path)
    return neu
