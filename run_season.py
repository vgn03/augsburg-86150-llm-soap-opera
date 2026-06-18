#!/usr/bin/env python3
"""
run_season.py — eine ganze STAFFEL = ein MONAT.

4 Arbeitswochen a 6 Tage (Mo-Sa) = 24 Episoden, durchgehende Continuity.
Jeden Samstag: Bar-Nacht. Druck waechst ueber den Monat; der Monatsabschluss
(Quartalscrunch) am Ende ist das Staffelfinale, wo die Wahrheit rausmuss.

  python3 run_season.py            # voller Monat (24 Tage)
  python3 run_season.py 12         # nur die ersten 12 Tage (2 Wochen)
"""

from __future__ import annotations

import sys

import engine
from run_slice import run_one, snapshot


if __name__ == "__main__":
    ndays = int(sys.argv[1]) if len(sys.argv) > 1 else engine.SEASON_DAYS
    snapshot("START (Staffel-/Monatsbeginn)")
    for d in range(1, ndays + 1):
        wd = engine.weekday_of(d)
        mode = "bar" if wd == "Samstag" else "work"
        run_one(wd, mode=mode)
        snapshot(f"NACH Woche {engine.week_of(d)} · {wd}")
    print(f"\n✓ Staffel (Monat) durch: {ndays} Tage, Continuity ueber alles.")
