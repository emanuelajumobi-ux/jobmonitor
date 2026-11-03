"""Ortsbewertung: geschätzte ÖPNV-Fahrzeit ab dem Wohnort (statische Tabelle, keine Routing-API).

Die Tabelle steht in config.yaml unter ort.fahrzeiten (für eine andere Stadt in der App unter Einstellungen → Wohnort
von der KI erstellt); fehlt sie, gilt FAHRZEIT_MIN ab Köln Hbf.
"""
from __future__ import annotations

import re

from .models import normalize

# Minuten ab Köln Hbf, grobe Schätzung (Regionalbahn/S-Bahn inkl. Umstieg). Bei Bedarf hier ergänzen.
FAHRZEIT_MIN: dict[str, int] = {
    "köln": 0, "koeln": 0, "cologne": 0,
    "leverkusen": 20, "hürth": 20, "brühl": 20, "dormagen": 25, "langenfeld": 25,
    "frechen": 25, "pulheim": 25, "wesseling": 25, "troisdorf": 25, "siegburg": 25,
    "bergisch gladbach": 30, "bonn": 30, "düsseldorf": 30, "sankt augustin": 30, "st augustin": 30,
    "kerpen": 35, "bergheim": 35, "erftstadt": 35, "hennef": 35, "rhein erft": 35, "rhein sieg": 35,
    "neuss": 40, "solingen": 40, "monheim": 40, "düren": 40, "overath": 40,
    "ratingen": 45, "euskirchen": 50, "wuppertal": 50, "remscheid": 55, "aachen": 55,
    "gummersbach": 60, "krefeld": 60, "mönchengladbach": 65, "duisburg": 60, "essen": 65,
    "wiesbaden": 120, "frankfurt": 75, "neu isenburg": 90,
}

REMOTE_RE = re.compile(r"home[\s-]?office|remote|mobiles? arbeiten|ortsunabhängig|deutschlandweit|bundesweit",
                       re.IGNORECASE)


# Remote-Stellen mit Arbeitsort im Ausland (z. B. von Arbeitnow): Als Werkstudent brauchst du meist einen Vertrag in
# Deutschland. Nur aussortiert, wenn der Ort eindeutig im Ausland liegt und nichts auf Deutschland hinweist.
AUSLAND_RE = re.compile(
    r"(?<![a-zäöüß])(?:schweiz|switzerland|suisse|zürich|zurich|basel|bern|genf|geneva|lausanne|zug|"
    r"österreich|austria|wien|vienna|graz|linz|salzburg|innsbruck|"
    r"frankreich|france|paris|île de france|ile de france|lyon|"
    r"niederlande|netherlands|nederland|amsterdam|rotterdam|utrecht|eindhoven|"
    r"belgien|belgium|brüssel|brussels|antwerpen|luxemburg|luxembourg|"
    r"united kingdom|großbritannien|england|london|manchester|uk|"
    r"irland|ireland|dublin|spanien|spain|madrid|barcelona|portugal|lissabon|lisbon|"
    r"italien|italy|mailand|milan|rom|rome|polen|poland|warschau|warsaw|krakau|krakow|"
    r"tschechien|czech|prag|prague|dänemark|denmark|kopenhagen|copenhagen|schweden|sweden|stockholm|"
    r"norwegen|norway|oslo|finnland|finland|helsinki|usa|united states|new york|kanada|canada|indien|india)"
    r"(?![a-zäöüß])", re.IGNORECASE)
DEUTSCHLAND_RE = re.compile(
    r"(?<![a-zäöüß])(?:deutschland|germany|bundesweit|deutschlandweit|berlin|hamburg|münchen|munich|frankfurt|"
    r"stuttgart|leipzig|dresden|hannover|nürnberg|bremen|mannheim|karlsruhe|nrw|bayern|hessen)(?![a-zäöüß])",
    re.IGNORECASE)


def im_ausland(location: str, tabelle: dict[str, int] | None = None) -> bool:
    """True, wenn der Ort eindeutig im Ausland liegt (kein Hinweis auf Deutschland, kein bekannter Ort im Umkreis)."""
    loc = location or ""
    return bool(AUSLAND_RE.search(loc)) and not DEUTSCHLAND_RE.search(loc) and travel_minutes(loc, None, tabelle) is None


def is_remote(*texts: str) -> bool:
    return any(REMOTE_RE.search(t or "") for t in texts)


def travel_minutes(location: str, distance_km: float | None = None, tabelle: dict[str, int] | None = None) -> int | None:
    """Kleinste bekannte Fahrzeit über alle genannten Orte; None wenn unbekannt."""
    loc = normalize(location)
    best: int | None = None
    for place, minutes in (tabelle or FAHRZEIT_MIN).items():
        if re.search(rf"(?<![a-zäöüß]){re.escape(normalize(place))}(?![a-zäöüß])", loc):
            best = minutes if best is None else min(best, minutes)
    if best is None and distance_km is not None:
        # BA liefert die Luftlinie zum Suchort; grob in ÖPNV-Minuten umrechnen
        best = int(15 + distance_km * 1.1)
    return best


def zentrum(ort: dict | None) -> str | None:
    """Wohnort aus config.yaml → ort. Fehlt der Eintrag ganz, gilt Köln (Einstellungen von vor dem Wohnort-Feld);
    ist er leer, ist noch kein Wohnort festgelegt (neue Nutzer bis zum Einrichtungs-Assistenten)."""
    ort = ort or {}
    if "zentrum" not in ort:
        return "Köln"
    return str(ort.get("zentrum") or "").strip() or None


def location_points(location: str, remote: bool, cfg: dict, distance_km: float | None = None) -> tuple[int, str] | None:
    """(Punkte, Beschreibung) oder None, wenn Ort nicht passt. Ohne festgelegten Wohnort zählen nur Remote-Stellen."""
    if zentrum(cfg) is None:
        return (cfg["punkte_remote"], "Remote/Homeoffice") if remote and not (
            cfg.get("remote_nur_deutschland", True) and im_ausland(location, None)) else None
    tabelle = cfg.get("fahrzeiten") or None
    minutes = travel_minutes(location, distance_km, tabelle)
    max_min = cfg["max_fahrzeit_min"]
    if minutes is not None and minutes <= max_min:
        if minutes == 0:
            return cfg["punkte_koeln"], zentrum(cfg) or "Köln"
        if minutes <= 45:
            return cfg["punkte_umkreis"], f"{location} (~{minutes} min)"
        return cfg["punkte_grenze"], f"{location} (~{minutes} min, Grenze)"
    if remote:
        if cfg.get("remote_nur_deutschland", True) and im_ausland(location, tabelle):
            return None   # Remote, aber mit Arbeitsort/Vertrag im Ausland
        return cfg["punkte_remote"], "Remote/Homeoffice"
    return None
