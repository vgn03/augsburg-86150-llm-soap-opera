#!/usr/bin/env python3
"""
run_week.py — die volle Arbeitswoche Montag bis Freitag, mit Continuity.

Jeder Tag: Showrunner (day_focus + Tagesziele, Druck Richtung Freitag) ->
Tages-Loop mit Arbeitstag-Uhr (08:00-17:30) -> Reflexion (Zustand/Beziehungen/
Tagebuch/canon). Tag N+1 erinnert sich an alles davor. Freitag = Stichtag der
Quartalszahlen, maximaler Druck.

  python3 run_week.py            # Mo-Fr
  python3 run_week.py 3          # nur die ersten 3 Tage (Mo-Mi)
"""

from __future__ import annotations

import sys

import engine
from run_slice import run_one, snapshot

WORKWEEK = engine.WEEKDAYS_FULL[:5]   # Montag .. Freitag


if __name__ == "__main__":
    ndays = int(sys.argv[1]) if len(sys.argv) > 1 else len(WORKWEEK)
    snapshot("START (Wochenbeginn)")
    for wd in WORKWEEK[:ndays]:
        run_one(wd)
        snapshot(f"NACH {wd}")
    # Samstagnacht: die Bar, wo der Druck der Woche detoniert (nur nach voller Woche)
    if ndays >= len(WORKWEEK):
        run_one("Samstag", mode="bar")
        snapshot("NACH Samstagnacht")
    print("\n✓ Woche + Samstagnacht durch. Continuity ueber alle Tage.")
