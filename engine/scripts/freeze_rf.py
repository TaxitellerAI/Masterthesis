"""Freeze the chained euro risk-free rate to a CSV committed to the repo.

Why: the reported thesis figures must not depend on the ECB API being reachable
(or on it ever revising a series). The frozen file makes every run reproducible
offline; `fetch_rf_chained` stays available for refreshing it.

Run:  python scripts/freeze_rf.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from volcontrol.data import fetch_rf_chained

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "frozen_rf_eur.csv")
# Widest sensible range: EONIA is available well before the study window, so any
# window the configurator allows is covered without a refetch.
START, END = "2013-01-01", "2025-12-31"

if __name__ == "__main__":
    ser, meta = fetch_rf_chained(START, END)
    ser.index.name = "date"
    ser.name = "rf_annual"
    ser.to_csv(OUT, float_format="%.8f")
    print(f"geschrieben: {os.path.abspath(OUT)}")
    for k, v in meta.items():
        print(f"  {k:22} {v}")
