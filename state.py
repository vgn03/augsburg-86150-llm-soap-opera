#!/usr/bin/env python3
"""
state.py — Das State+Memory-Rueckgrat von Augsburg 86150 v2 (Phase 1).

Jede Figur ist ein Agent mit:
  - identity  : permanent (Name, Modell, Charakter-Prompt, Geheimnis) — IMMER im Kontext
  - state     : lebende Achsen (stress, caffeine, drunkenness, goal_today, secret_guard ...)
  - relationships : pro anderer Figur {trust, suspicion, affection}
  - suspicion_of_secrets : wie stark DIESE Figur das Geheimnis jeder anderen ahnt
  - memory.canon    : permanente Landmark-Fakten (aufgedeckte Geheimnisse, Verrat) — verblassen NIE
  - memory.episodic : rollendes 2-Wochen-Fenster (Tagesdetails), aelteres faellt raus
  - diary     : private POV-Eintraege pro Tag

Die 3-Tier-Memory (Tom): identity permanent, canon permanent, episodic rollt (14 Tage).
Reflection (Phase 4) entscheidet, was aus episodic zu canon promoviert wird — state.py
trimmt nur mechanisch das Fenster und haelt canon append-only.

Reine Stdlib. Kein Seiteneffekt ausser Datei-I/O.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CHAR_DIR = BASE_DIR / "characters"
SEASON_FILE = BASE_DIR / "season.json"

EPISODIC_WINDOW_DAYS = 14  # "letzte 2 Wochen" (Tom)

# Default-Achsen fuer einen Season-Reset (identity bleibt erhalten)
STATE_DEFAULTS: dict[str, Any] = {
    "stress": 0.2,
    "caffeine": 100,
    "drunkenness": 0,
    "mood": "neutral",
    "confidence": 0.5,
    "goal_today": None,
    "secret_guard": 1.0,
}


_TITLES = {"frau", "herr", "hausmeister", "dr", "prof"}


def _slug(name: str) -> str:
    """Stabiler Dateiname. Titel-Praefixe ('Frau Schmidt', 'Hausmeister
    Brunner') werden uebersprungen, damit Lesen und Schreiben dieselbe Datei
    treffen ('schmidt', 'brunner'). Sonst Vorname ('carmen', 'herbert')."""
    parts = name.strip().split()
    w = parts[0]
    if w.lower().rstrip(".") in _TITLES and len(parts) > 1:
        w = parts[1]
    return w.lower()


# ---------------------------------------------------------------------------
# Laden / Speichern
# ---------------------------------------------------------------------------

def load_character(name: str) -> dict[str, Any]:
    path = CHAR_DIR / f"{_slug(name)}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_character(data: dict[str, Any]) -> None:
    name = data["identity"]["name"]
    path = CHAR_DIR / f"{_slug(name)}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_season() -> dict[str, Any]:
    return json.loads(SEASON_FILE.read_text(encoding="utf-8"))


def save_season(data: dict[str, Any]) -> None:
    SEASON_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def all_characters() -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(CHAR_DIR.glob("*.json"))]


# ---------------------------------------------------------------------------
# Memory-Mechanik (3 Tiers)
# ---------------------------------------------------------------------------

def add_canon(char: dict[str, Any], fact: str, day: int) -> None:
    """Permanenter Landmark-Fakt — verblasst nie. Dedup gegen Wortlaut."""
    entry = {"day": day, "fact": fact}
    if entry not in char["memory"]["canon"]:
        char["memory"]["canon"].append(entry)


def add_episodic(char: dict[str, Any], day: int, summary: str) -> None:
    """Tagesdetail ins rollende Fenster; aelteres als 14 Tage faellt raus."""
    char["memory"]["episodic"].append({"day": day, "summary": summary})
    roll_episodic(char, current_day=day)


def roll_episodic(char: dict[str, Any], current_day: int,
                  window: int = EPISODIC_WINDOW_DAYS) -> None:
    """Trimmt episodic auf die letzten `window` Tage. canon bleibt unberuehrt."""
    cutoff = current_day - window
    char["memory"]["episodic"] = [
        e for e in char["memory"]["episodic"] if e["day"] > cutoff
    ]


def add_diary(char: dict[str, Any], day: int, entry: str) -> None:
    char["diary"].append({"day": day, "entry": entry})


# ---------------------------------------------------------------------------
# Kontext-Zusammenbau fuer den Figuren-Agenten (was die Figur "weiss")
# ---------------------------------------------------------------------------

def build_memory_context(char: dict[str, Any]) -> str:
    """identity ist immer separat im Prompt; hier nur das Erinnerte."""
    lines: list[str] = []
    canon = char["memory"]["canon"]
    if canon:
        lines.append("WAS DU SICHER WEISST (bleibt fuer immer):")
        lines += [f"- {c['fact']}" for c in canon]
    episodic = char["memory"]["episodic"]
    if episodic:
        lines.append("\nDIE LETZTEN TAGE:")
        lines += [f"- Tag {e['day']}: {e['summary']}" for e in episodic]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Season-Reset (identity behalten, state/memory/relationships nullen)
# ---------------------------------------------------------------------------

def reset_character(char: dict[str, Any]) -> dict[str, Any]:
    char["state"] = dict(STATE_DEFAULTS)
    char["relationships"] = {}
    char["suspicion_of_secrets"] = {}
    char["memory"] = {"canon": [], "episodic": []}
    char["diary"] = []
    return char


# ---------------------------------------------------------------------------
# Phase-1-Smoke-Test: beweist, dass State eine Runde ueberlebt
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("== Phase-1 Persistenz-Beweis ==")
    c = load_character("Carmen")
    print(f"Geladen: {c['identity']['name']} | stress={c['state']['stress']} "
          f"| canon={len(c['memory']['canon'])} | diary={len(c['diary'])}")

    # Simuliere einen Tag: Stress steigt, ein Verdacht waechst, Landmark-Fakt,
    # Tagesdetail, Tagebucheintrag.
    c["state"]["stress"] = round(c["state"]["stress"] + 0.25, 2)
    c["suspicion_of_secrets"]["Herbert Gruber"] = 0.7
    c["relationships"]["Herbert Gruber"] = {"trust": 0.3, "suspicion": 0.8, "affection": 0.2}
    add_canon(c, "Herbert weicht jeder Frage zum Konto aus.", day=1)
    add_episodic(c, day=1, summary="Kaffeeautomat kaputt, Herbert nervoes wegen der Zahlen.")
    add_diary(c, day=1, entry="Er luegt. Ich sehe es an seinen Haenden. Viktor wird es finden.")
    save_character(c)
    print("Gespeichert nach Tag 1.")

    # Frisch nachladen — hat es ueberlebt?
    c2 = load_character("Carmen")
    assert c2["state"]["stress"] == c["state"]["stress"]
    assert c2["suspicion_of_secrets"]["Herbert Gruber"] == 0.7
    assert len(c2["memory"]["canon"]) == 1
    assert len(c2["diary"]) == 1
    print(f"Nachgeladen: stress={c2['state']['stress']} "
          f"| suspicion(Herbert)={c2['suspicion_of_secrets']['Herbert Gruber']} "
          f"| canon={len(c2['memory']['canon'])} | diary={len(c2['diary'])}")
    print("\n-- Was Carmen jetzt erinnert --")
    print(build_memory_context(c2))
    print("\n✓ State ueberlebt die Runde. Phase-1-Spine steht.")
