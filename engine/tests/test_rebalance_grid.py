"""Why the sweep bootstrap keeps its daily base portfolio (methodology argument).

The obvious repair for the daily-vs-monthly deviation in `sweepboot` is a POSITION-
based grid — "rebalance every 21 rows" — which is well defined on a resampled path,
unlike a calendar month. It was measured and rejected, and the numbers behind that
rejection appear in the module docstring of `sweepboot.py` and in the thesis. They
must therefore be reproducible, not a one-off measurement.

The positional mix here mirrors `strategies.periodic_mix` exactly (reset INTO the
boundary day, drift in between); `test_positional_mix_matches_periodic_mix` proves
that by driving it with the calendar keys and requiring bit-level agreement. An
earlier hand-rolled version reset at the END of a block instead and drifted from the
engine by ~1.1e-03 per day — close enough to look right, far enough to move a slope
by 0.011.

Run:  python tests/test_rebalance_grid.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from api.main import RunRequest, _prepared
from volcontrol import portfolio_weights, run_strategies
from volcontrol.backtest import sweep_shares, weight_cost
import volcontrol.strategies as st


def positional_mix(asset_returns: pd.DataFrame, weights: dict, keys: np.ndarray):
    """Constant mix reset whenever `keys` changes — same semantics as periodic_mix.

    `keys` replaces the calendar period label, so an arbitrary grid (positional,
    calendar, anything) can be driven through identical logic.
    """
    w = pd.Series(weights, dtype=float)
    cols = [c for c in w.index if c in asset_returns.columns]
    w = w[cols] / w[cols].sum()
    R = asset_returns[cols].fillna(0.0)
    gr = 1.0 + R.to_numpy()
    n, k = gr.shape
    held = np.empty((n, k))
    cur = w.to_numpy().copy()
    prev = None
    for t in range(n):
        if keys[t] != prev:
            cur = w.to_numpy().copy()
            prev = keys[t]
        held[t] = cur
        val = cur * gr[t]
        cur = val / val.sum()
    port = pd.Series((held * R.to_numpy()).sum(axis=1), index=R.index)
    return port, pd.DataFrame(held, index=R.index, columns=cols)


def _s1():
    req = RunRequest(scenario="S1")
    rets, cfg, _rf, _spec, _rep, pit = _prepared(req)
    return req, rets, cfg, pit


def test_positional_mix_matches_periodic_mix():
    """Driven with calendar keys, the helper must BE periodic_mix — else the phase
    numbers below describe a portfolio the engine never computes."""
    req, rets, cfg, _pit = _s1()
    w = portfolio_weights(0.15, list(rets.columns), cfg)
    cal = rets.index.to_period("M").astype(str).to_numpy()
    port_a, wp_a = st.periodic_mix(rets, w, "monthly")
    port_b, wp_b = positional_mix(rets, w, cal)
    dp = float(np.abs(port_a.to_numpy() - port_b.to_numpy()).max())
    dw = float(np.abs(wp_a[wp_b.columns].to_numpy() - wp_b.to_numpy()).max())
    assert dp < 1e-12, f"Portfoliorendite weicht ab: {dp:.3e}"
    assert dw < 1e-12, f"Gewichtspfad weicht ab: {dw:.3e}"
    print(f"ok  positional_mix == periodic_mix (Rendite {dp:.1e}, Gewichte {dw:.1e})")


def _slope_for(keys, rets, cfg, req, shares, x):
    """dMDD-slope over the sweep for one rebalancing grid, full net backtest path."""
    d = []
    for s in shares:
        w = portfolio_weights(float(s), list(rets.columns), cfg)
        gross, wp = positional_mix(rets, w, keys)
        _turn, cost = weight_cost(wp, cfg)
        port = gross - cost
        bps = (1.0 - float(s)) * cfg.cost_traditional_bps + float(s) * cfg.cost_crypto_bps
        strat, _e = st.vol_control(
            port, req.target_vol, cfg.lookback, cfg.rf_for(port.index), cfg.trading_days,
            cfg.max_leverage, bps, cfg.vol_method, cfg.ewma_halflife,
            cfg.rebalance, cfg.dead_band)
        def mdd(series):
            wl = (1.0 + series).cumprod()
            return float((wl / wl.cummax() - 1.0).min())
        d.append(mdd(strat) - mdd(port))
    d = np.asarray(d)
    return float((d - d.mean()) @ x / (x @ x))


def test_positional_grid_is_phase_dependent():
    """The rejection argument, reproduced: same frequency, wildly different slope.

    A 21-row grid matches the calendar frequency (95 resets, mean spacing 20.94) but
    the slope depends on WHERE the grid starts. If that spread ever collapsed, the
    rejection in sweepboot.py would no longer be justified and the thesis text would
    have to change — so it is asserted, not just printed.
    """
    req, rets, cfg, pit = _s1()
    shares = sweep_shares(cfg)
    x = shares - shares.mean()
    n = len(rets)

    cal_keys = rets.index.to_period("M").astype(str).to_numpy()
    s_cal = _slope_for(cal_keys, rets, cfg, req, shares, x)

    slopes = []
    for off in range(21):
        keys = (np.arange(n) + (21 - off)) // 21
        slopes.append(_slope_for(keys, rets, cfg, req, shares, x))
    slopes = np.asarray(slopes)
    spread = float(slopes.max() - slopes.min())
    ci_width = 0.965290 - 0.383607          # reported H3 bootstrap CI (S1)

    print(f"ok  Kalendermonatlich (Hauptspezifikation)      {s_cal:.6f}")
    print(f"ok  Positionsraster 21, Phase 0                 {slopes[0]:.6f}")
    print(f"ok  Phasen-Spannweite {slopes.min():.6f} .. {slopes.max():.6f} "
          f"(Breite {spread:.6f} = {spread/ci_width*100:.0f} % der KI-Breite)")

    assert spread > 0.15, (
        f"Phasen-Spannweite nur {spread:.6f} — die Begruendung in sweepboot.py, "
        f"das Positionsraster zu verwerfen, traegt dann nicht mehr.")
    assert abs(slopes[0] - s_cal) > 0.02, (
        f"Positionsraster reproduziert die Kalenderspezifikation ({slopes[0]:.6f} vs "
        f"{s_cal:.6f}) — dann waere es doch tragfaehig und sweepboot.py muesste neu bewertet werden.")


def test_primary_specification_point_estimate():
    """0.753635 is the ONE number the thesis may call 'Punktschätzung der
    Hauptspezifikation'. It comes from the same code path as the metrics table
    (run_strategies), not from the sweep bootstrap and not from crypto_sweep."""
    req, rets, cfg, pit = _s1()
    shares = sweep_shares(cfg)
    x = shares - shares.mean()
    key = f"VolControl_{int(req.target_vol * 100)}"
    d = []
    for s in shares:
        run = run_strategies(rets, cfg, float(s), pit_builder=pit)
        d.append(run["strategies"][key]["max_drawdown"]
                 - run["strategies"]["BuyHold"]["max_drawdown"])
    d = np.asarray(d)
    slope = float((d - d.mean()) @ x / (x @ x))
    assert abs(slope - 0.753635) < 5e-6, f"Hauptspezifikation {slope:.6f} statt 0.753635"
    print(f"ok  Punktschätzung der Hauptspezifikation {slope:.6f}")


if __name__ == "__main__":
    test_positional_mix_matches_periodic_mix()
    test_primary_specification_point_estimate()
    test_positional_grid_is_phase_dependent()
