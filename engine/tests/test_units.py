"""Unit tests for the metric and inference primitives — known-value checks that
demonstrate correctness (the thesis defence needs more than a smoke test).

Run:  python tests/test_units.py    (or: pytest -q)
"""
from __future__ import annotations
import math
import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from volcontrol import metrics as mt
from volcontrol import stats as sx
from volcontrol import strategies as strat
from volcontrol import analysis as an
from volcontrol import load_prices, simple_returns

_PRICES = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_prices.csv")


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol


def test_cagr_constant():
    r = np.full(252, 0.001)
    expected = (1.001 ** 252) ** (252 / 252) - 1
    assert approx(mt.cagr(r, 252), expected, 1e-12)


def test_cagr_total_loss():
    assert mt.cagr(np.array([0.5, -1.0, 0.2]), 252) == -1.0


def test_max_drawdown_known():
    # +10% then -50%: trough at 0.55 vs peak 1.1 -> -0.5
    assert approx(mt.max_drawdown(np.array([0.10, -0.50])), -0.5, 1e-12)


def test_max_drawdown_monotonic_up():
    assert mt.max_drawdown(np.array([0.01, 0.01, 0.01])) >= 0.0 - 1e-12


def test_ann_vol_scaling():
    r = np.array([0.01, -0.01, 0.01, -0.01, 0.02, -0.02])
    daily = np.std(r, ddof=1)
    assert approx(mt.ann_volatility(r, 252), daily * math.sqrt(252), 1e-12)


def test_cvar_tail_mean():
    r = np.array([-0.10, -0.08, -0.05, 0.0, 0.02, 0.03, 0.04, 0.05, 0.06, 0.10])
    # 5% quantile picks the worst tail; CVaR is the mean of returns <= that quantile
    q = np.quantile(r, 0.05)
    tail = r[r <= q]
    assert approx(mt.cvar(r, 0.05), tail.mean(), 1e-12)


def test_sharpe_zero_std_is_nan():
    assert math.isnan(mt.sharpe_ratio(np.full(50, 0.001), 0.0, 252))


def test_holm_monotone_and_bounded():
    adj = sx.holm_correction({"a": 0.01, "b": 0.04, "c": 0.03})
    assert approx(adj["a"], 0.03, 1e-12)      # 3 * 0.01
    assert adj["c"] <= adj["b"] + 1e-12       # monotone after sorting
    assert all(0.0 <= v <= 1.0 for v in adj.values())


def test_mann_kendall_increasing():
    res = sx.mann_kendall(np.arange(20, dtype=float))
    assert approx(res["tau"], 1.0, 1e-9)
    assert res["p_value"] < 0.01


def test_mann_kendall_flat():
    res = sx.mann_kendall(np.ones(10))
    assert res["p_value"] > 0.99


def test_bootstrap_slope_positive():
    x = np.linspace(0, 0.5, 21)
    y = 0.3 * x + 0.001                       # clean positive slope
    res = sx.bootstrap_slope(x, y, n_boot=500, seed=1)
    assert res["slope"] > 0
    assert res["ci_low"] > 0                   # clearly excludes zero


def test_psr_positive_mean():
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.01, 1000)          # positive Sharpe
    out = sx.probabilistic_sharpe_ratio(r)
    assert out["sr"] > 0 and out["psr"] > 0.5


def test_deflated_sharpe_runs():
    rng = np.random.default_rng(1)
    trials = [rng.normal(0.0005, 0.01, 800) for _ in range(9)]
    out = sx.deflated_sharpe_ratio(trials[0], trials)
    assert out["n_trials"] == 9
    assert 0.0 <= out["dsr"] <= 1.0
    assert out["sr0"] == out["sr0"]            # not NaN


def test_rolling_risk_parity_valid():
    r = simple_returns(load_prices(_PRICES))
    prp = strat.rolling_risk_parity(r)
    assert len(prp) > 100
    assert not prp.isna().any()                # warm-up dropped, no NaNs leak through


def test_drawdown_table_sorted_and_negative():
    r = simple_returns(load_prices(_PRICES))
    dt = an.drawdown_table(r)
    for key in ("buy_hold", "vol_control"):
        depths = [e["depth"] for e in dt[key]]
        assert depths == sorted(depths)        # deepest first
        assert all(d < 0 for d in depths)      # a drawdown is negative


def test_rolling_correlation_bounded():
    r = simple_returns(load_prices(_PRICES))
    rc = an.rolling_correlation(r)
    assert rc["series"]                        # at least one crypto vs equity
    for vals in rc["series"].values():
        finite = [x for x in vals if x is not None]
        assert all(-1.0001 <= x <= 1.0001 for x in finite)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\nAll {len(tests)} unit tests passed.")
