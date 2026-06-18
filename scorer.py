#!/usr/bin/env python3
"""
scorer.py — bewertet die SUBJEKTIVEN Persona-Achsen (snark, sturheit, neugier,
logik_emotion) aus dem laufenden Transkript und schreibt sie als
traits_<suffix>.json. Der Viewer merged das ins Persona-Panel.

Laeuft als Schleife NEBEN dem Dreh - greift nicht in die Engine ein, setzt
nichts zurueck. Clean-Instruct-Modell (gemma3:12b), 1 Call pro Runde.

  python3 scorer.py            # Endlosschleife, alle ~50s
  python3 scorer.py --once     # einmal
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import llm

BASE = Path(__file__).resolve().parent
MODEL = "gemma3:12b"
INTERVAL = 50

SCHEMA = {
    "type": "object",
    "properties": {"personas": {"type": "array", "items": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "snark": {"type": "number"},
                       "sturheit": {"type": "number"}, "neugier": {"type": "number"},
                       "logik_emotion": {"type": "number"}},
        "required": ["name", "snark", "sturheit", "neugier", "logik_emotion"]}}},
    "required": ["personas"],
}


def latest() -> Path | None:
    ts = sorted(BASE.glob("transkript_v2_*.md"))
    return ts[-1] if ts else None


def speaker_lines(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for m in re.finditer(r"^\*\*([^:*]+):\*\*\s*(.+)$", text, re.M):
        out.setdefault(m.group(1).strip(), []).append(m.group(2).strip())
    return out


def score_once() -> str | None:
    t = latest()
    if not t:
        return None
    lines = speaker_lines(t.read_text(encoding="utf-8"))
    if not lines:
        return None
    blob = "\n".join(f"{n}: " + " | ".join(ls[-7:]) for n, ls in lines.items())
    sysp = ("Bewerte jede Figur auf einer Skala 0-10 anhand IHRER REPLIKEN: "
            "snark (Spott/Ironie), sturheit (Sturheit), neugier (Neugier), "
            "logik_emotion (0=ganz emotional ... 10=kuehl-rational). Nur was im "
            "Text steht. Gib JSON mit personas[].")
    try:
        out = llm.chat_json(MODEL, sysp, f"REPLIKEN:\n{blob}\n\nBewertung:", SCHEMA)
    except Exception:  # noqa: BLE001
        return None
    traits: dict[str, dict] = {}
    for p in out.get("personas", []):
        n = p.get("name", "").strip()
        if not n:
            continue
        traits[n] = {ax: {"value": int(round(float(p.get(ax, 0)))), "evidence": "Scorer"}
                     for ax in ("snark", "sturheit", "neugier", "logik_emotion")}
    side = BASE / ("traits_" + t.name[len("transkript_"):].replace(".md", ".json"))
    side.write_text(json.dumps(traits, ensure_ascii=False, indent=2), encoding="utf-8")
    return side.name


if __name__ == "__main__":
    once = "--once" in sys.argv
    while True:
        r = score_once()
        print(f"gescort -> {r}" if r else "kein Transkript")
        if once:
            break
        time.sleep(INTERVAL)
