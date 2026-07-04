"""Transparency guarantee test: the Excel formulas in the exported workbook must
reproduce the engine's metrics EXACTLY. Builds the workbook, recalculates it with
headless LibreOffice, and compares the Kennzahlen sheet against the engine.

Skips (with a clear message) if LibreOffice is not installed — the guarantee is
then only checked on machines that can recalculate formulas.

Run:  python tests/test_workbook.py
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from volcontrol import (
    EngineConfig, simple_returns, run_strategies, portfolio_weights,
    build_workbook, fingerprint,
)
from volcontrol.backtest import _blended_cost_bps
from scripts.make_synthetic_data import make_synthetic_prices

SOFFICE = shutil.which("soffice") or (
    "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.exists("/Applications/LibreOffice.app/Contents/MacOS/soffice") else None
)

TOL = 5e-4  # metrics agree to 4 decimals (rounding of exposure values in the sheet)


def test_workbook_reproduces_engine():
    if not SOFFICE:
        print("SKIP — LibreOffice (soffice) nicht gefunden; Formel-Recalc nicht prüfbar.")
        return

    prices = make_synthetic_prices(n_days=900, seed=3)
    rets = simple_returns(prices)
    cfg = EngineConfig()
    crypto_share, target_vol = 0.15, 0.10

    run = run_strategies(rets, cfg, crypto_share)
    key = f"VolControl_{int(target_vol * 100)}"
    engine_bh = run["strategies"]["BuyHold"]
    engine_vc = run["strategies"][key]

    meta = {
        "crypto_share": crypto_share, "target_vol": target_vol,
        "base_currency": "EUR", "source": "synthetic",
        "cost_bps": _blended_cost_bps(crypto_share, cfg),
        "fingerprint": fingerprint(rets),
        "trad_split": {"MSCI_World": 0.6, "Global_Bonds": 0.3, "Gold": 0.1},
        "trad_is_base": True, "rf_mode": "manual", "generated_at": "test",
    }
    weights = portfolio_weights(crypto_share, list(rets.columns), cfg)
    xbytes = build_workbook(prices, rets, weights, engine_vc["exposure"],
                            engine_vc["returns"], cfg, meta, {})

    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "wb.xlsx")
        with open(src, "wb") as f:
            f.write(xbytes)
        subprocess.run(
            [SOFFICE, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", td, src],
            check=True, capture_output=True, timeout=180,
        )
        import openpyxl
        wb = openpyxl.load_workbook(os.path.join(td, "wb.xlsx"), data_only=True)
        ws = wb["Kennzahlen"]
        # row 2 = Buy-and-Hold, row 3 = selected vol-control; columns B..G
        excel = {
            "bh": [ws.cell(2, c).value for c in range(2, 8)],
            "vc": [ws.cell(3, c).value for c in range(2, 8)],
        }

    def _check(tag, cells, eng):
        expected = [eng["ann_return"], eng["cagr"], eng["ann_vol"],
                    eng["sharpe"], eng["max_drawdown"], eng["cvar_95"]]
        names = ["ann_return", "cagr", "ann_vol", "sharpe", "max_drawdown", "cvar_95"]
        for name, got, want in zip(names, cells, expected):
            assert isinstance(got, (int, float)), f"{tag}.{name}: Formel ergab {got!r}"
            assert abs(got - want) < TOL, f"{tag}.{name}: Excel {got:.6f} vs Engine {want:.6f}"

    _check("BuyHold", excel["bh"], engine_bh)
    _check(key, excel["vc"], engine_vc)
    print("OK — Excel-Formeln reproduzieren die Engine-Kennzahlen (Toleranz "
          f"{TOL}); BH & {key} über 6 Metriken geprüft.")


if __name__ == "__main__":
    test_workbook_reproduces_engine()
