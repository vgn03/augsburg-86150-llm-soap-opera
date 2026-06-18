#!/usr/bin/env python3
"""
critic.py — Feuilleton-Kritik einer Augsburg-86150-Episode.

Ein grosses Modell liest eine fertige Folge und schreibt eine geistreiche,
leicht ueberhebliche Theaterkritik. Comedy + Qualitaetssignal (haelt die Folge
zusammen, kann der Kritiker sie ueberhaupt rezensieren).

  python3 critic.py                       # neueste Folge
  python3 critic.py transkript_v2_d3_*.md # bestimmte Folge
"""

from __future__ import annotations

import sys
from pathlib import Path

import llm

BASE = Path(__file__).resolve().parent
CRITIC_MODEL = "gemma3:12b"


def critique(transcript: str) -> str:
    sysp = ("Du bist ein Feuilleton-Kritiker einer ueberregionalen Zeitung. "
            "Schreibe eine geistreiche, leicht ueberhebliche Kritik (4-6 Saetze) "
            "dieser Folge - als waere die Buero-Soap grosses Theater. Nimm Figuren "
            "und Dialoge ernst-ironisch beim Wort. Deutsch, ein Absatz.")
    return llm.chat(CRITIC_MODEL, sysp,
                    f"DIE FOLGE:\n{transcript[:7000]}\n\nIhre Kritik:",
                    temperature=0.9, num_predict=420).strip()


def main() -> None:
    if len(sys.argv) > 1:
        cands = sorted(BASE.glob(sys.argv[1]))
        t = cands[-1] if cands else BASE / sys.argv[1]
    else:
        ts = sorted(BASE.glob("transkript_v2_*.md"))
        t = ts[-1] if ts else None
    if not t or not t.is_file():
        print("Kein Transkript gefunden.")
        sys.exit(1)
    review = critique(t.read_text(encoding="utf-8"))
    out = BASE / ("kritik_" + t.name[len("transkript_"):].replace(".md", ".txt"))
    out.write_text(review, encoding="utf-8")
    print(f"Kritik → {out.name}\n\n{review}")


if __name__ == "__main__":
    main()
