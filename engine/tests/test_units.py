"""Unit tests for the metric and inference primitives — known-value checks that
demonstrate correctness (the thesis defence needs more than a smoke test).

Run:  python tests/test_units.py    (or: pytest -q)
"""
from __future__ import annotations
import math
import os
import sys
import numpy as np
import pandas as pd

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


def test_rf_act360_weekend_accrual():
    """A Monday after a normal weekend must accrue THREE days of interest."""
    from volcontrol.data import rf_daily_series
    idx = pd.DatetimeIndex(["2024-01-04", "2024-01-05", "2024-01-08"])  # Thu, Fri, Mon
    rf = rf_daily_series(pd.Series(0.0360, index=idx), idx, "act360")
    assert abs(float(rf.iloc[-1]) - 0.0360 * 3 / 360) < 1e-12   # Fri -> Mon = 3 days
    assert abs(float(rf.iloc[1]) - 0.0360 * 1 / 360) < 1e-12    # Thu -> Fri = 1 day


def test_rf_negative_rates_survive():
    """The chained series must keep negative rates — that is the whole point."""
    from volcontrol.data import rf_daily_series
    idx = pd.date_range("2019-01-01", periods=5, freq="D")
    rf = rf_daily_series(pd.Series(-0.005, index=idx), idx, "act360")
    assert (rf < 0).all()


def test_rf_scalar_path_unchanged():
    """Scalar rf must still behave exactly like the legacy constant/252 model."""
    from volcontrol.data import rf_daily_series
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    rf = rf_daily_series(0.03, idx, "simple_252", trading_days=252)
    assert np.allclose(rf.to_numpy(), 0.03 / 252)


def test_vol_control_cash_leg_uses_series():
    """A negative rf must REDUCE the vol-control return via the cash leg."""
    from volcontrol import strategies as stt
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    rng = np.random.default_rng(7)
    port = pd.Series(rng.normal(0.0002, 0.02, len(idx)), index=idx)
    pos = stt.vol_control(port, 0.10, 60, pd.Series(0.0002, index=idx), cost_bps=0.0)[0]
    neg = stt.vol_control(port, 0.10, 60, pd.Series(-0.0002, index=idx), cost_bps=0.0)[0]
    assert pos.sum() > neg.sum()          # positive carry beats negative carry


def test_fingerprint_separates_rf_modes():
    """Same data, different rf treatment -> different citable hash."""
    from volcontrol.data import fingerprint
    idx = pd.date_range("2020-01-01", periods=50, freq="B")
    df = pd.DataFrame({"A": np.linspace(0.001, 0.002, 50)}, index=idx)
    h1 = fingerprint(df, {"rf_mode": "estr_chained"})["hash"]
    h2 = fingerprint(df, {"rf_mode": "constant"})["hash"]
    assert h1 != h2


def test_study_window_is_fixed_calendar():
    """The default window must be explicit bounds, not a rolling period."""
    import inspect
    from volcontrol import data as vd
    assert vd.STUDY_START == "2018-01-01" and vd.STUDY_END == "2025-12-31"
    sig = inspect.signature(vd.fetch_prices_yf)
    assert "start" in sig.parameters and "end" in sig.parameters
    assert "years" not in sig.parameters          # rolling window must be gone
    # Inspect the CODE, not the docstring (which explains why period= was dropped).
    src = inspect.getsource(vd.fetch_prices_yf)
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    code = code.split('"""')[0] + '"""'.join(code.split('"""')[2:])   # drop docstring
    assert "period=" not in code                  # no rolling window in the actual call
    assert "start=start" in code and "end=end_excl" in code


# ── Sample design (S1..S4, point-in-time sleeve) ─────────────────────────────
_FROZEN = os.path.join(os.path.dirname(__file__), "..", "data", "frozen_prices_eur.csv")


def _frozen():
    return load_prices(_FROZEN)


def test_pit_weight_zero_before_entry():
    """No look-ahead: a coin's weight must be EXACTLY 0 before its entry date."""
    from volcontrol import sample as sm
    from volcontrol.config import EngineConfig
    prices = _frozen()
    kept, _ = sm.resolve_sample(prices, sm.S2)
    rets = simple_returns(kept)
    W = sm.pit_weight_matrix(rets.index, sm.S2, prices, 0.10,
                             EngineConfig().traditional_weights, kept.columns)
    entries = sm.entry_dates(prices, sm.S2.crypto_members, sm.S2.listing_buffer_days)
    for coin, entry in entries.items():
        before = W.loc[W.index < entry, coin]
        assert (before == 0.0).all(), f"{coin} hat Gewicht vor {entry.date()}"


def test_pit_weights_sum_to_one():
    """Every row of the weight matrix must sum to 1 (tolerance 1e-9)."""
    from volcontrol import sample as sm
    from volcontrol.config import EngineConfig
    prices = _frozen()
    kept, _ = sm.resolve_sample(prices, sm.S2)
    rets = simple_returns(kept)
    W = sm.pit_weight_matrix(rets.index, sm.S2, prices, 0.10,
                             EngineConfig().traditional_weights, kept.columns)
    assert float((W.sum(axis=1) - 1.0).abs().max()) < 1e-9


def test_s1_fixed_matches_static_path_exactly():
    """Regression guard: S1 (fixed) must reproduce the untouched static path."""
    from volcontrol import sample as sm
    from volcontrol.config import EngineConfig
    from volcontrol.backtest import run_strategies, metrics_table
    prices = _frozen()
    kept, _ = sm.resolve_sample(prices, sm.S1)
    rets = simple_returns(kept)
    cfg = EngineConfig(rf_mode="constant")
    old = metrics_table(run_strategies(rets, cfg, 0.10))
    new = metrics_table(run_strategies(rets, cfg, 0.10, pit_builder=None))
    assert old.equals(new)
    assert float((old - new).abs().max().max()) == 0.0


def test_s1_effective_sample_bounds():
    """S1 must resolve to the first trading day of 2018 through 2025-12-31."""
    from volcontrol import sample as sm
    _, rep = sm.resolve_sample(_frozen(), sm.S1)
    assert rep["effective_start"].startswith("2018-01")
    assert rep["effective_end"] == "2025-12-31"
    assert rep["n_rows"] > 1900


def test_pit_row_not_killed_by_unlisted_coin():
    """A coin that is not yet listed must NOT drop a row (that was the whole point)."""
    from volcontrol import sample as sm
    prices = _frozen()
    _, s2 = sm.resolve_sample(prices, sm.S2)
    _, s1 = sm.resolve_sample(prices, sm.S1)
    # S2 includes Solana yet still starts in 2015 and keeps far more rows than the
    # fixed basket would if SOL were required throughout.
    assert "Solana" in s2["crypto_members"]
    assert s2["effective_start"] < s1["effective_start"]
    assert s2["n_rows"] > s1["n_rows"]


def test_sleeve_entry_is_charged():
    """Adding a coin re-spreads the sleeve — that trade must cost something."""
    from volcontrol import sample as sm
    from volcontrol.config import EngineConfig
    cfg = EngineConfig()
    prices = _frozen()
    kept, _ = sm.resolve_sample(prices, sm.S2)
    rets = simple_returns(kept)
    W = sm.pit_weight_matrix(rets.index, sm.S2, prices, 0.10,
                             cfg.traditional_weights, kept.columns)
    cost, info = sm.sleeve_rebalance_cost(W, sm.S2.crypto_members, cfg.cost_crypto_bps)
    assert info["events"] >= 2          # ETH/XRP/BNB enter, later SOL
    assert info["total_cost"] > 0.0
    assert cost.sum() > 0.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\nAll {len(tests)} unit tests passed.")
