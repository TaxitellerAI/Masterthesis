"""Vergleich der Sample-Designs S1 / S2 / S3 (und S4-Sensitivität).

Zeigt, wie stark die Aussage vom Sample-Design abhängt — die Zahlen gehören
so in die Arbeit und dürfen nicht geschätzt werden.

Run:  python scripts/compare_samples.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from volcontrol.config import EngineConfig
from volcontrol.data import load_prices, simple_returns, load_rf_frozen
from volcontrol.backtest import run_strategies, metrics_table
from volcontrol import sample as sp

PRICES = os.path.join(os.path.dirname(__file__), "..", "data", "frozen_prices_eur.csv")
RF = os.path.join(os.path.dirname(__file__), "..", "data", "frozen_rf_eur.csv")

CRYPTO_SHARE = 0.10
TARGET_VOL = 0.10
SHOW = ["BuyHold", "VolControl_10"]


def run_spec(spec, prices, cfg):
    kept, report = sp.resolve_sample(prices, spec)
    rets = simple_returns(kept)
    builder = sp.make_pit_builder(spec, prices, cfg, kept.columns) if spec.is_pit else None
    run = run_strategies(rets, cfg, CRYPTO_SHARE, pit_builder=builder)
    return metrics_table(run), report, run.get("sleeve")


def main():
    prices = load_prices(PRICES)
    rf, _ = load_rf_frozen(RF)
    cfg = EngineConfig(rf_series=rf)

    rows = []
    for spec in (sp.S1, sp.S2, sp.S3):
        tbl, rep, sleeve = run_spec(spec, prices, cfg)
        print(f"\n=== {rep['scenario']} — {rep['label']} ===")
        print(f"    angefordert {rep['requested_start']} .. {rep['requested_end']}")
        print(f"    effektiv    {rep['effective_start']} .. {rep['effective_end']}   n = {rep['n_rows']}")
        print(f"    Fensterzeilen {rep['n_rows_in_window']}, verworfen {rep['n_dropped']}")
        print(f"    Grund: {rep['drop_reason']}")
        print(f"    Krypto: {', '.join(rep['crypto_members'])}  (Modus {rep['sleeve_mode']})")
        if rep["entry_dates"]:
            print(f"    Eintritte: {rep['entry_dates']}")
        if sleeve:
            print(f"    Sleeve-Umschichtungen: {sleeve['events']}, "
                  f"Kosten kumuliert {sleeve['total_cost']*100:.4f} % "
                  f"(Turnover {sleeve['total_turnover']:.3f})")
        for strat in SHOW:
            if strat not in tbl.index:
                continue
            r = tbl.loc[strat]
            rows.append({
                "Szenario": rep["scenario"], "Strategie": strat,
                "n": rep["n_rows"],
                "Zeitraum": f"{rep['effective_start'][:7]}..{rep['effective_end'][:7]}",
                "ann_return": r["ann_return"], "ann_vol": r["ann_vol"],
                "sharpe": r["sharpe"], "max_drawdown": r["max_drawdown"],
                "cvar_95": r["cvar_95"], "turnover": r["turnover"],
            })

    df = pd.DataFrame(rows)
    print("\n\n=== VERGLEICHSTABELLE (Krypto-Quote 10 %, Zielvol 10 %) ===")
    print(df.to_string(index=False))

    print("\n\n=== S4 — Startdatums-Sensitivität (nur VolControl_10) ===")
    s4 = []
    for spec in sp.start_date_sensitivity():
        tbl, rep, _ = run_spec(spec, prices, cfg)
        r = tbl.loc["VolControl_10"]
        b = tbl.loc["BuyHold"]
        s4.append({
            "Start": spec.start[:4], "n": rep["n_rows"],
            "VC_sharpe": r["sharpe"], "VC_cagr": r["cagr"], "VC_mdd": r["max_drawdown"],
            "BH_sharpe": b["sharpe"], "BH_cagr": b["cagr"], "BH_mdd": b["max_drawdown"],
            "d_sharpe": round(r["sharpe"] - b["sharpe"], 4),
            "d_mdd": round(r["max_drawdown"] - b["max_drawdown"], 4),
        })
    print(pd.DataFrame(s4).to_string(index=False))


if __name__ == "__main__":
    main()
