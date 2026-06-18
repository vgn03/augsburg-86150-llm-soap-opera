#!/usr/bin/env python3
"""
run_slice.py — Phase-2-Beweis: 2 Tage, 3 Figuren, Continuity.

Tag 1 (Montag) -> Reflexion -> Tag 2 (Dienstag).
Der Beweis: Tag 2 oeffnet mit Stress/Verdacht/Erinnerung aus Tag 1.
Vorher/Nachher-Snapshot wird ausgegeben.

  python3 run_slice.py            # laeuft Tag 1 + Tag 2
"""

from __future__ import annotations

import state as S
import engine


def snapshot(label: str) -> None:
    print(f"\n===== {label} =====")
    for c in S.all_characters():
        n = c["identity"]["name"].split()[0]
        st = c["state"]
        sus = c.get("suspicion_of_secrets", {})
        sus_s = ", ".join(f"{k.split()[0]}={v}" for k, v in sus.items()) or "-"
        diary = c["diary"][-1]["entry"] if c["diary"] else "-"
        print(f"  {n:8s} stress={st['stress']:.2f} mood={st['mood']:<12} "
              f"conf={st['confidence']:.2f} | Verdacht: {sus_s}")
        print(f"           canon={len(c['memory']['canon'])} "
              f"episodic={len(c['memory']['episodic'])} | Tagebuch: \"{diary[:70]}\"")


WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
DAY_LENGTH = 60   # Beitraege pro Tag (volle Arbeitstage statt Mini-Szenen)


def run_one(weekday: str, mode: str = "work") -> None:
    season = S.load_season()
    season["day"] += 1
    season["weekday"] = weekday
    # Nur Figuren, die ab diesem Tag "im Stueck" sind (Gaeste kommen spaeter)
    chars = {c["identity"]["name"]: c for c in S.all_characters()
             if c["identity"].get("active_from_day", 1) <= season["day"]}
    tag = f"{weekday}nacht 🍸" if mode == "bar" else f"{weekday} (Tag {season['day']})"
    print(f"\n######## {tag} — {len(chars)} Figuren ########")
    tpath = engine.run_day(season, chars, max_turns=DAY_LENGTH, mode=mode)
    print(f"  Drehbuch: {tpath.name}")
    transcript = tpath.read_text(encoding="utf-8")
    print("  Reflexion laeuft (schreibt Zustand/Tagebuch/canon zurueck) ...")
    engine.reflect(season, chars, transcript)


if __name__ == "__main__":
    snapshot("START (vor Tag 1)")
    run_one(WEEKDAYS[0])
    snapshot("NACH TAG 1 (Montag)")
    run_one(WEEKDAYS[1])
    snapshot("NACH TAG 2 (Dienstag)")
    print("\n✓ Wenn Verdacht/Stress/canon von Montag in Dienstag getragen wurden, "
          "haelt die Continuity. Phase 2 bewiesen.")
