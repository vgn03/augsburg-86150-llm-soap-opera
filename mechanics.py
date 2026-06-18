#!/usr/bin/env python3
"""
mechanics.py — die DETERMINISTISCHEN Zustandsregeln (keine LLM-Calls).

Tracked dimensions (Toms 5): caffeine, suspicion_map, near_misses, momentum, tic.
Diese laufen pro gesprochener Zeile und halten die Soap-Mechanik "lebendig",
ohne pro Turn extra Modell-Calls zu kosten.
"""

from __future__ import annotations

import re
from typing import Any

# Schluesselwoerter, die das Geheimnis einer Figur "anstechen". Faellt ein
# solches Wort in irgendeiner Replik, steigt der Stress des Geheimnistraegers,
# seine Deckung broeckelt, Zuhoerer werden misstrauischer (suspicion_map),
# und es zaehlt als Beinahe-Enthuellung (near_miss).
SECRET_TOPICS: dict[str, list[str]] = {
    "Herbert Gruber": ["geld", "konto", "poker", "schulden", "pleite",
                       "80.000", "80000", "zahlen verschwinden", "wohin"],
    "Gisela Wimmer": ["datenbank", "geloescht", "loeschen", "backup",
                      "produktion", "kunde", "zeugnis"],
    "Carmen Gruber": ["detektiv", "viktor", "affaere", "angeheuert",
                      "privatermittler", "spioniert"],
    "Frau Schmidt": ["putzfrau", "nachts gesehen", "weiss zu viel",
                     "belauscht", "abends allein"],
    "Viktor Falk": ["detektiv", "auditor", "firewall", "ermittl",
                    "wer bist du wirklich", "tarnung", "kein it"],
    "Hausmeister Brunner": ["zweitschluessel", "serverraum", "cousin",
                            "schluessel", "verbotener zugang"],
}

CAFFEINE_DRAIN_PER_TURN = 4   # Kaffeeautomat kaputt -> nur Schwund
STRESS_POKE = 0.12            # Stress-Anstieg, wenn das eigene Geheimnis naht
GUARD_EROSION = 0.025         # Deckung broeckelt LANGSAM - Geheimnisse haelt man fest;
                             # erst sustained Druck ueber Tage/Wochen knackt sie
SUSPICION_GAIN = 0.08         # Misstrauen der Zuhoerer pro Anstich


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return round(max(lo, min(hi, x)), 3)


def drain_caffeine(char: dict[str, Any], amount: int = CAFFEINE_DRAIN_PER_TURN) -> None:
    """Kaffee schwindet ueber den Arbeitstag (Automat kaputt). Niedrig = gereizt."""
    s = char["state"]
    s["caffeine"] = max(0, s["caffeine"] - amount)
    if s["caffeine"] < 30 and s["mood"] not in ("gereizt", "nervoes"):
        s["mood"] = "gereizt"


def caffeine_note(char: dict[str, Any]) -> str:
    """Kurzer Hinweis fuer den Prompt, je nach Koffeinstand."""
    c = char["state"]["caffeine"]
    if c >= 70:
        return ""
    if c >= 40:
        return "Du haettest langsam gern einen Kaffee."
    if c >= 15:
        return "Du bist seit Stunden ohne Kaffee und wirst zunehmend gereizt."
    return "Komplett ohne Kaffee, duennhaeutig und kurz angebunden."


def drink(char: dict[str, Any], amount: int = 9) -> None:
    """Samstagnacht: Alkohol steigt (je nach Trinkfreudigkeit), Deckung broeckelt.
    Carmen (drink_rate 0) bleibt nuechtern und jagt; Gisela trinkt ueber den
    Durst; Viktor tut nur so."""
    rate = char["identity"].get("drink_rate", 1.0)
    st = char["state"]
    if rate <= 0:
        return
    st["drunkenness"] = min(100, st["drunkenness"] + int(amount * rate))
    d = st["drunkenness"]
    # Je betrunkener, desto schneller faellt die Deckung
    st["secret_guard"] = _clamp(st["secret_guard"] - 0.015 * rate * (d / 50 + 0.5))
    st["mood"] = ("sturzbetrunken" if d >= 75 else "betrunken" if d >= 50
                  else "angeheitert" if d >= 25 else st["mood"])


def drunk_note(char: dict[str, Any]) -> str:
    """Prompt-Hinweis je nach Promille - AUTORISIERT das Verhalten, nicht Wirrnis."""
    d = char["state"].get("drunkenness", 0)
    if d < 20:
        return ""
    if d < 50:
        return ("Du bist angeheitert - geselliger, redseliger, ein bisschen "
                "weniger vorsichtig als sonst.")
    if d < 75:
        return ("Du bist betrunken - du laberst, wirst sentimental, deine "
                "Vorsicht broeckelt, du verplapperst dich fast.")
    return ("Du bist sturzbetrunken - ungehemmt, du sagst Dinge, die du "
            "nuechtern NIE sagen wuerdest. (Bleib trotzdem verstaendlich.)")


def apply_line_effects(speaker: str, line: str, chars: dict[str, dict[str, Any]],
                       season: dict[str, Any]) -> list[str]:
    """
    Wertet eine gesprochene Zeile aus und aktualisiert alle Achsen.
    Gibt eine Liste von Event-Markern zurueck (fuer Momentum/Log).
    """
    events: list[str] = []
    low = line.lower()

    for owner, topics in SECRET_TOPICS.items():
        if owner not in chars:
            continue
        if any(t in low for t in topics):
            # Das Geheimnis von `owner` wurde angestochen.
            if owner != speaker:
                st = chars[owner]["state"]
                st["stress"] = _clamp(st["stress"] + STRESS_POKE)
                st["secret_guard"] = _clamp(st["secret_guard"] - GUARD_EROSION)
            # Beinahe-Enthuellung zaehlen
            exp = season["secret_exposure"].setdefault(
                owner, {"near_misses": 0, "revealed": False})
            exp["near_misses"] += 1
            events.append(f"near_miss:{owner}")
            # Zuhoerer (alle ausser owner) werden misstrauischer ggue. owner
            for other in chars:
                if other in (owner,):
                    continue
                sus = chars[other].setdefault("suspicion_of_secrets", {})
                sus[owner] = _clamp(sus.get(owner, 0.0) + SUSPICION_GAIN)

    # Momentum: Event treibt, Stille daempft
    if events:
        season["momentum"] = _clamp(season["momentum"] + 0.12)
    else:
        season["momentum"] = _clamp(season["momentum"] - 0.05)
    return events


# ---------------------------------------------------------------------------
# Tic-Detektor (Toms #5): erkennt wiederholte Satzanfaenge pro Figur
# ---------------------------------------------------------------------------

def detect_tic(recent_lines: list[str], window: int = 6, threshold: int = 3
               ) -> str | None:
    """
    Schaut auf die letzten `window` Repliken einer Figur. Beginnen >= `threshold`
    davon mit demselben ersten Wort, ist das ein Tic -> Nudge-String zurueck.
    """
    if len(recent_lines) < threshold:
        return None
    openers = [re.sub(r"[^\wäöüß]", "", l.strip().split()[0].lower())
               for l in recent_lines[-window:] if l.strip()]
    if not openers:
        return None
    top = max(set(openers), key=openers.count)
    if openers.count(top) >= threshold:
        return (f"ACHTUNG: Du hast zu oft mit '{top}...' begonnen. Beginne diese "
                f"Replik mit einem ANDEREN ersten Wort.")
    return None
