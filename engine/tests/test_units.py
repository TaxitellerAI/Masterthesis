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
    num_cols = old.select_dtypes("number").columns          # start/end are strings
    assert float((old[num_cols] - new[num_cols]).abs().max().max()) == 0.0


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


def test_constant_mix_turnover_is_positive():
    """Constant-mix trades back to target daily — its turnover is NOT zero."""
    from volcontrol import strategies as stt
    from volcontrol.config import EngineConfig
    from volcontrol.backtest import run_strategies
    r = simple_returns(load_prices(_FROZEN)[["MSCI_World", "Global_Bonds", "Gold",
                                             "Bitcoin", "Ethereum", "XRP"]].dropna())
    cm = stt.constant_mix_weight_path(r, {"MSCI_World": 0.6, "Global_Bonds": 0.3, "Gold": 0.1})
    assert float((cm.sum(axis=1) - 1.0).abs().max()) < 1e-12
    assert float(stt.weights_turnover(cm).sum()) > 0.0

    run = run_strategies(r, EngineConfig(rf_mode="constant"), 0.10)
    assert run["strategies"]["BuyHold"]["turnover"] > 0.0
    assert run["strategies"]["Benchmark_6040"]["turnover"] > 0.0
    assert run["strategies"]["Benchmark_RiskParity"]["turnover"] > 0.0
    # TrueBH is the only one whose zero is factually right
    assert run["strategies"]["Benchmark_TrueBH"]["turnover"] == 0.0


def test_gross_beats_net_when_costs_apply():
    """Net metrics must be worse than gross whenever turnover was charged."""
    from volcontrol.config import EngineConfig
    from volcontrol.backtest import run_strategies
    r = simple_returns(load_prices(_FROZEN)[["MSCI_World", "Global_Bonds", "Gold",
                                             "Bitcoin", "Ethereum", "XRP"]].dropna())
    bh = run_strategies(r, EngineConfig(rf_mode="constant"), 0.10)["strategies"]["BuyHold"]
    assert bh["ann_return_gross"] > bh["ann_return"]


def test_strategies_report_own_sample_size():
    """Each row carries n + window; risk parity must be visibly shorter."""
    from volcontrol.config import EngineConfig
    from volcontrol.backtest import run_strategies
    r = simple_returns(load_prices(_FROZEN)[["MSCI_World", "Global_Bonds", "Gold",
                                             "Bitcoin", "Ethereum", "XRP"]].dropna())
    st_ = run_strategies(r, EngineConfig(rf_mode="constant"), 0.10)["strategies"]
    for d in st_.values():
        assert d["observations"] > 0 and d["start"] and d["end"]
    assert st_["Benchmark_RiskParity"]["observations"] < st_["BuyHold"]["observations"]


def test_dsr_counts_the_real_search_space():
    """DSR must deflate by the grids actually explored, not the 4 table rows."""
    from volcontrol.config import EngineConfig
    from volcontrol.backtest import dsr_trial_returns, sweep_shares
    cfg = EngineConfig(rf_mode="constant")
    r = simple_returns(load_prices(_FROZEN)[["MSCI_World", "Global_Bonds", "Gold",
                                             "Bitcoin", "Ethereum", "XRP"]].dropna())
    trials = dsr_trial_returns(r, cfg, 0.10, 0.10)
    grid = len(cfg.stability_lookbacks) * len(cfg.stability_target_vols)
    assert len(trials) > grid                      # grid PLUS the sweep
    assert len(trials) <= grid + len(sweep_shares(cfg))
    assert len(trials) > 4                         # the old, wrong count


def test_wilcoxon_outside_holm_family():
    """Confirmatory family = pre-specified hypotheses only; Wilcoxon is descriptive."""
    from volcontrol.config import EngineConfig
    from volcontrol.backtest import hypothesis_tests
    r = simple_returns(load_prices(_FROZEN)[["MSCI_World", "Global_Bonds", "Gold",
                                             "Bitcoin", "Ethereum", "XRP"]].dropna())
    res = hypothesis_tests(r, EngineConfig(rf_mode="constant", bootstrap_n=200), 0.10, 0.10)
    assert "wilcoxon_daily" not in res["holm_adjusted"]
    assert "wilcoxon_daily" in res["holm_adjusted_incl_wilcoxon"]
    assert set(res["holm_family"]) == {"H1_max_drawdown", "H2_sharpe",
                                       "H3_dMDD_vs_share", "H3_dCVaR_vs_share"}
    assert res["wilcoxon_daily"]["p_value"] >= 0.0     # still reported


def test_rf_negative_share_comes_from_the_window():
    """The negative-rate share must be computed per window, not hard-coded."""
    from volcontrol.data import load_rf_frozen
    rf, _ = load_rf_frozen(os.path.join(os.path.dirname(__file__), "..",
                                        "data", "frozen_rf_eur.csv"))
    early = float((rf.loc["2018-01-01":"2019-12-31"] < 0).mean())
    late = float((rf.loc["2023-01-01":"2025-12-31"] < 0).mean())
    assert early > 0.9 and late == 0.0      # negative then, positive later
    assert early != late                     # a single constant cannot describe both


# ── Sweep bootstrap (H3/TF4 on the data level) ───────────────────────────────
def _s1_returns():
    from volcontrol import sample as sm
    kept, _ = sm.resolve_sample(load_prices(_FROZEN), sm.S1)
    return simple_returns(kept)


def test_sweepboot_matches_engine_sweep():
    """The vectorised sweep must reproduce the existing engine sweep exactly."""
    from volcontrol import sweepboot as sb
    from volcontrol.config import EngineConfig
    from volcontrol.backtest import crypto_sweep
    r = _s1_returns()
    cfg = EngineConfig(rf_mode="constant", rf_annual=0.02, weight_rebalance="daily")
    ref = crypto_sweep(r, cfg, 0.10)
    shares = np.asarray(ref["crypto_share"])
    W = sb._weight_matrix(shares, list(r.columns), cfg)
    bps = sb._blended_bps(shares, cfg)
    mine = sb._sweep_once(np.nan_to_num(r.to_numpy(float)), W, bps, cfg, 0.10, cfg.rf_daily)
    for k in ("d_mdd", "d_cvar", "sharpe_bh", "sharpe_vc"):
        assert np.abs(mine[k] - ref[k].to_numpy()).max() < 1e-10, k


def test_sweepboot_paired_indices_across_shares():
    """One index sequence per replicate must serve ALL shares (paired design).

    Verified structurally: _sweep_once receives ONE resampled matrix and derives
    every share from it by matrix product, so per-share divergence is impossible.
    Empirically, a replicate reproduces exactly when the same indices are reused.
    """
    from volcontrol import sweepboot as sb
    from volcontrol.stats import stationary_bootstrap_indices
    from volcontrol.config import EngineConfig
    r = _s1_returns()
    cfg = EngineConfig(rf_mode="constant")
    shares = np.array([0.0, 0.1, 0.25, 0.5])
    W = sb._weight_matrix(shares, list(r.columns), cfg)
    bps = sb._blended_bps(shares, cfg)
    R = np.nan_to_num(r.to_numpy(float))
    idx = stationary_bootstrap_indices(len(R), cfg.expected_block,
                                       np.random.default_rng(1))
    a = sb._sweep_once(R[idx], W, bps, cfg, 0.10, 0.0)
    b = sb._sweep_once(R[idx], W, bps, cfg, 0.10, 0.0)
    for k in a:
        assert np.allclose(a[k], b[k], equal_nan=True)
    # all four shares come from the SAME resampled rows -> one matmul
    assert (R[idx] @ W).shape == (len(R), len(shares))


def test_sweepboot_preserves_cross_correlation():
    """Resampling ROWS keeps the cross-sectional correlation — the economic core."""
    from volcontrol.stats import stationary_bootstrap_indices
    r = _s1_returns()
    R = np.nan_to_num(r.to_numpy(float))
    c0 = np.corrcoef(R, rowvar=False)
    rng = np.random.default_rng(7)
    diffs = []
    for _ in range(20):
        idx = stationary_bootstrap_indices(len(R), 20, rng)
        diffs.append(np.abs(np.corrcoef(R[idx], rowvar=False) - c0).max())
    assert np.median(diffs) < 0.15      # correlation structure survives resampling


def test_sweepboot_reproducible_and_band_contains_point():
    """Fixed seed -> identical result; the band must bracket the point estimate."""
    from volcontrol import sweepboot as sb
    from volcontrol.config import EngineConfig
    r = _s1_returns()
    cfg = EngineConfig(rf_mode="constant")
    a = sb.sweep_bootstrap(r, cfg, 0.10, n_boot=60, seed=123)
    b = sb.sweep_bootstrap(r, cfg, 0.10, n_boot=60, seed=123)
    assert a["slopes"]["d_mdd"] == b["slopes"]["d_mdd"]
    assert a["argmax"]["distribution"] == b["argmax"]["distribution"]
    for k, band in a["bands"].items():
        for lo, pt, hi in zip(band["simultaneous_low"], band["point"],
                              band["simultaneous_high"]):
            if None in (lo, pt, hi):
                continue
            assert lo <= pt <= hi, k


def test_periodic_mix_daily_equals_buy_and_hold():
    """The old daily specification must remain exactly reproducible."""
    from volcontrol import strategies as stt
    r = _s1_returns()
    w = {"MSCI_World": 0.54, "Global_Bonds": 0.27, "Gold": 0.09,
         "Bitcoin": 0.025, "Ethereum": 0.025, "XRP": 0.025, "BNB": 0.025}
    port, wp = stt.periodic_mix(r, w, "daily")
    assert np.allclose(port.values, stt.buy_and_hold(r, w).values)
    for freq in ("monthly", "quarterly"):
        p2, w2 = stt.periodic_mix(r, w, freq)
        assert float((w2.sum(axis=1) - 1.0).abs().max()) < 1e-9
        assert float(stt.weights_turnover(w2).sum()) > 0.0


def test_grid_matches_metrics_table():
    """Parameter-stability grid and metrics table must agree for the same config."""
    from volcontrol.config import EngineConfig
    from volcontrol import analysis as ana
    from volcontrol.backtest import run_strategies, metrics_table
    r = _s1_returns()
    cfg = EngineConfig(rf_mode="constant")
    t = metrics_table(run_strategies(r, cfg, 0.10))
    g = ana.param_stability(r, cfg, 0.10)
    i = g["lookbacks"].index(cfg.lookback)
    j = g["target_vols"].index(0.10)
    assert abs(g["sharpe"][i][j] - float(t.loc["VolControl_10", "sharpe"])) < 6e-4


def test_hypothesis_tests_accepts_precomputed_inputs():
    """Handing over already-computed pieces must not move a single number."""
    from volcontrol.config import EngineConfig
    from volcontrol.backtest import (hypothesis_tests, run_strategies, crypto_sweep)
    r = _s1_returns()
    cfg = EngineConfig(rf_mode="constant", bootstrap_n=300)
    fresh = hypothesis_tests(r, cfg, 0.10, 0.10)
    run = run_strategies(r, cfg, 0.10)
    sw = crypto_sweep(r, cfg, 0.10)
    reused = hypothesis_tests(r, cfg, 0.10, 0.10, run=run, sweep_df=sw)
    for k in ("H1_max_drawdown", "H2_sharpe", "H3_dMDD_vs_share", "H3_dCVaR_vs_share"):
        assert fresh[k] == reused[k], k
    assert fresh["holm_adjusted"] == reused["holm_adjusted"]
    assert fresh["deflated_sharpe"] == reused["deflated_sharpe"]


def test_cache_key_separates_every_relevant_setting():
    """A cache keyed on a subset could serve figures from another configuration.

    This drives the API's real key builder, so the guard cannot drift from the code
    it protects.
    """
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
    from api.main import RunRequest, _analysis_key, _prepared
    base = RunRequest(scenario="S1", crypto_share=0.10, target_vol=0.10)
    rets, cfg, *_ = _prepared(base)
    k0 = _analysis_key(base, rets, cfg)

    variants = {
        "target_vol": {"target_vol": 0.15},
        "rf_mode": {"rf_mode": "constant"},
        "rf_annual": {"rf_mode": "constant", "rf_annual": 0.05},
        "scenario": {"scenario": "S3"},
        "vol_method": {"vol_method": "ewma"},
        "rebalance": {"rebalance": "monthly"},
        "dead_band": {"dead_band": 0.05},
        "trad_weights": {"trad_weights": {"MSCI_World": 0.5, "Global_Bonds": 0.3, "Gold": 0.2}},
    }
    for name, mod in variants.items():
        req = RunRequest(**{**base.model_dump(), **mod})
        rr, cc, *_ = _prepared(req)
        assert _analysis_key(req, rr, cc) != k0, f"Cache-Key unterscheidet {name} NICHT"
    # identical request -> identical key (otherwise the cache would never hit)
    again = RunRequest(**base.model_dump())
    ra, ca, *_ = _prepared(again)
    assert _analysis_key(again, ra, ca) == k0


def test_precomputed_matches_live_exactly():
    """Shipped inference must equal what the live path computes — bit for bit.

    A precomputed answer that drifts from the live one would be the worst possible
    failure: the defence would cite numbers the tool no longer reproduces.
    """
    import json as _json
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
    from api.main import (RunRequest, _prepared, _analysis_key, _freeze,
                          SWEEP_BOOT_N, API_BOOTSTRAP_N, PRECOMPUTED_PATH)
    from volcontrol.backtest import hypothesis_tests
    from volcontrol import sweepboot as sbm

    with open(_os.path.join(_os.path.dirname(__file__), "..", PRECOMPUTED_PATH)) as f:
        payload = _json.load(f)
    entry = next(e for e in payload["entries"] if e["scenario"] == "S1")

    req = RunRequest(scenario="S1", crypto_share=entry["crypto_share"],
                     target_vol=entry["target_vol"])
    rets, cfg, _i, _s, report, pit = _prepared(req, bootstrap_n=API_BOOTSTRAP_N)

    # the stored key must still describe THIS configuration
    assert _freeze(entry["key"]) == _freeze(_analysis_key(req, rets, cfg))

    sboot = sbm.sweep_bootstrap(rets, cfg, req.target_vol, n_boot=SWEEP_BOOT_N,
                                seed=cfg.seed)
    live = hypothesis_tests(rets, cfg, req.crypto_share, req.target_vol,
                            pit_builder=pit, sweep_boot=sboot)
    pre = entry["result"]
    for k in ("H1_max_drawdown", "H2_sharpe", "wilcoxon_daily",
              "deflated_sharpe", "probabilistic_sharpe", "holm_adjusted"):
        for kk, vv in live[k].items():
            got = pre[k][kk]
            if isinstance(vv, float):
                assert abs(got - vv) < 1e-9, f"{k}.{kk}: {got} vs {vv}"
            else:
                assert got == vv, f"{k}.{kk}"
    for metric in ("d_mdd", "d_cvar"):
        for kk, vv in live["sweep_bootstrap"]["slopes"][metric].items():
            assert abs(pre["sweep_bootstrap"]["slopes"][metric][kk] - vv) < 1e-9


def test_precomputed_not_served_for_other_config():
    """A different setting must MISS the shipped result and fall through to live."""
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
    from api.main import RunRequest, _prepared, _precomputed_for, API_BOOTSTRAP_N
    base = RunRequest(scenario="S1", crypto_share=0.10, target_vol=0.10)
    r0, c0, *_ = _prepared(base, bootstrap_n=API_BOOTSTRAP_N)
    assert _precomputed_for(base, r0, c0) is not None      # the shipped one hits

    for mod in ({"target_vol": 0.15}, {"rf_mode": "constant"},
                {"vol_method": "ewma"}, {"dead_band": 0.05},
                {"trad_weights": {"MSCI_World": 0.5, "Global_Bonds": 0.3, "Gold": 0.2}}):
        req = RunRequest(**{**base.model_dump(), **mod})
        rr, cc, *_ = _prepared(req, bootstrap_n=API_BOOTSTRAP_N)
        assert _precomputed_for(req, rr, cc) is None, f"{mod} bekam ein fremdes Ergebnis"


def test_stable_hash_survives_one_ulp_but_catches_real_change():
    """Cache/precompute keys must not break on last-bit noise across platforms.

    Measured on this project: the byte-exact fingerprint of the SAME data differed
    between macOS and the Linux host (H1 came out ...587 there vs ...598 here), so a
    locally built precompute artefact could never match in production.
    """
    from volcontrol.data import stable_data_hash, fingerprint
    r = _s1_returns()
    h0 = stable_data_hash(r)

    ulp = r.copy()
    ulp.iloc[0, 0] = np.nextafter(ulp.iloc[0, 0], 1.0)     # one ULP up
    assert stable_data_hash(ulp) == h0                      # stable key survives
    assert fingerprint(ulp)["hash"] != fingerprint(r)["hash"]   # exact hash does not

    real = r.copy()
    real.iloc[0, 0] += 1e-9                                 # a REAL change
    assert stable_data_hash(real) != h0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\nAll {len(tests)} unit tests passed.")
