"""Traumprofil (Standard: Cloud Security): Stellen erkennen, bei denen Cloud- und Security-Themen zusammenkommen.

Stufe 2 (⭐⭐, stark): beide Themen im Titel oder ein Kernbegriff wie „Cloud Security“/„DevSecOps“ im Titel.
Stufe 1 (⭐, passend): ein Thema im Titel, das andere in der Anzeige.
Score und Filter bleiben unverändert; das Profil hebt nur hervor. Einstellungen: config.yaml → traumprofil.
"""
from __future__ import annotations

from .scoring import matches


def classify(title: str, text: str, cfg: dict) -> tuple[int, str]:
    """(Stufe 0–2, Begründung)."""
    if not cfg or not cfg.get("enabled", True):
        return 0, ""
    title_l, text_l = (title or "").lower(), (text or "").lower()
    kern = matches(title_l, cfg.get("kern") or [])
    if kern:
        return 2, f"„{kern[0]}“ im Titel"
    cloud_t, sec_t = matches(title_l, cfg["cloud"]), matches(title_l, cfg["security"])
    if cloud_t and sec_t:
        return 2, f"{cloud_t[0]} + {sec_t[0]} im Titel"
    cloud_x, sec_x = matches(text_l, cfg["cloud"]), matches(text_l, cfg["security"])
    if cloud_t and sec_x:
        return 1, f"{cloud_t[0]} im Titel, {', '.join(sec_x[:2])} in der Anzeige"
    if sec_t and cloud_x:
        return 1, f"{sec_t[0]} im Titel, {', '.join(cloud_x[:2])} in der Anzeige"
    return 0, ""


def stars(stufe: int) -> str:
    return "⭐" * stufe
