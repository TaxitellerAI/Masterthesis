"""Strategy implementations: static buy-and-hold and dynamic volatility control."""
from __future__ import annotations
import numpy as np
import pandas as pd


def buy_and_hold(asset_returns: pd.DataFrame, weights: dict) -> pd.Series:
    """Constant-mix portfolio return: r_p = Σ w_i r_i with FIXED weights.

    Note: fixed weights imply the portfolio is rebalanced back to target each day
    (constant-mix), which is the standard weight-additive portfolio return used as
    the base for volatility targeting. For a true, un-rebalanced buy-and-hold whose
    weights drift with performance, see `true_buy_and_hold`.
    """
    w = pd.Series(weights, dtype=float)
    cols = [c for c in w.index if c in asset_returns.columns]
    w = w[cols]
    if w.sum() == 0:
        raise ValueError("Weights sum to zero for the available asset universe.")
    w = w / w.sum()
    return (asset_returns[cols] * w).sum(axis=1)


def true_buy_and_hold(asset_returns: pd.DataFrame, weights: dict) -> pd.Series:
    """True buy-and-hold: invest once at target weights, then let them DRIFT.

    Portfolio value V_t = Σ w_i · Π_{s≤t}(1+r_{i,s}); the daily return is V_t/V_{t-1}−1.
    No rebalancing → zero turnover. This is the honest low-turnover comparator to the
    daily-rebalanced constant-mix base.
    """
    w = pd.Series(weights, dtype=float)
    cols = [c for c in w.index if c in asset_returns.columns]
    w = w[cols]
    w = w / w.sum()
    wealth = (1.0 + asset_returns[cols].fillna(0.0)).cumprod()
    value = (wealth * w).sum(axis=1)
    return value.pct_change().fillna(0.0)


def realized_vol(port_returns: pd.Series, lookback: int = 60, td: int = 252,
                 method: str = "rolling", halflife: int = 20) -> pd.Series:
    """Annualised realised volatility.

    method="rolling": equal-weighted rolling window (simple, transparent).
    method="ewma":    exponentially weighted (RiskMetrics-style), reacts faster
                      to volatility clustering — the more standard estimator for
                      volatility targeting.
    """
    if method == "ewma":
        return port_returns.ewm(halflife=halflife, min_periods=max(5, halflife)).std() * np.sqrt(td)
    return port_returns.rolling(lookback).std(ddof=1) * np.sqrt(td)


def _apply_rebalance(exposure: pd.Series, rebalance: str) -> pd.Series:
    """Hold the target exposure constant between rebalancing dates (step function).

    Daily rebalancing is the theoretical ideal but unrealistically expensive; a
    treasury rebalances periodically. We sample the target on period boundaries
    and forward-fill, which cuts turnover materially.
    """
    if rebalance == "daily":
        return exposure
    idx = exposure.index
    if rebalance == "weekly":
        keys = [(d.isocalendar()[0], d.isocalendar()[1]) for d in idx]
    elif rebalance == "monthly":
        keys = [(d.year, d.month) for d in idx]
    else:
        return exposure
    # hold the first target of each period constant (no resample-alias churn)
    grouped = pd.Series(exposure.values, index=pd.MultiIndex.from_tuples(keys))
    held = grouped.groupby(level=[0, 1]).transform("first")
    return pd.Series(held.values, index=idx)


def _apply_dead_band(exposure: pd.Series, band: float) -> pd.Series:
    """Only trade to a new exposure once it moves more than `band` from the last
    traded level — a no-trade zone that cuts turnover without much tracking drift."""
    if band <= 0:
        return exposure
    e = exposure.to_numpy(dtype=float)
    out = e.copy()
    for i in range(1, len(e)):
        if abs(e[i] - out[i - 1]) < band:
            out[i] = out[i - 1]
    return pd.Series(out, index=exposure.index)


def vol_control(port_returns: pd.Series, target_vol: float, lookback: int = 60,
                rf_daily=0.0, td: int = 252, max_leverage: float = 1.0,
                cost_bps: float = 15.0, vol_method: str = "rolling",
                ewma_halflife: int = 20, rebalance: str = "daily", dead_band: float = 0.0):
    """Scale exposure inversely to realised volatility.

    exposure_t = min(target_vol / realised_vol_{t-1}, max_leverage)
    The shift by one day removes look-ahead: today's allocation uses only
    information available at yesterday's close. Uninvested capital earns the
    risk-free rate; turnover is charged at `cost_bps`. `rebalance` controls how
    often the target is actually traded to; `vol_method` selects the estimator.

    `rf_daily` is a scalar OR a per-period series/array on `port_returns`' index.
    The series form matters: the cash leg (1 - exposure) is exactly where a
    constant positive rate would flatter the strategy through the negative-rate
    years, since exposure is lowest precisely in those stress periods.

    Returns (strategy_returns, exposure_series).
    """
    rv = realized_vol(port_returns, lookback, td, vol_method, ewma_halflife)
    exposure = (target_vol / rv).clip(upper=max_leverage)
    exposure = exposure.shift(1).fillna(0.0)               # no look-ahead
    exposure = _apply_rebalance(exposure, rebalance)
    exposure = _apply_dead_band(exposure, dead_band)

    turnover = exposure.diff().abs()
    turnover.iloc[0] = abs(exposure.iloc[0])
    cost = turnover * (cost_bps / 1e4)

    # Align a dated/array rf to the return calendar so the cash leg accrues the
    # rate that actually prevailed on each day.
    if isinstance(rf_daily, pd.Series):
        rf = rf_daily.reindex(port_returns.index).ffill().bfill()
    elif np.ndim(rf_daily) > 0:
        rf = pd.Series(np.asarray(rf_daily, float), index=port_returns.index)
    else:
        rf = float(rf_daily)

    strat = exposure * port_returns + (1.0 - exposure) * rf - cost
    return strat.dropna(), exposure


def _period_keys(idx: pd.DatetimeIndex, freq: str):
    if freq == "monthly":
        return [(d.year, d.month) for d in idx]
    if freq == "quarterly":
        return [(d.year, (d.month - 1) // 3) for d in idx]
    return None                                    # "daily" -> no grouping


def periodic_mix(asset_returns: pd.DataFrame, weights: dict, freq: str = "monthly"):
    """Constant-mix rebalanced on a CALENDAR grid, drifting in between.

    Daily rebalancing back to target is the textbook constant-mix but unrealistic for
    a corporate treasury — and since turnover is now charged, daily rebalancing
    PENALISES the comparison benchmark for behaviour no treasurer would exhibit.
    Between rebalancing dates the weights therefore drift with relative performance;
    at each period start they are reset to target.

    Returns (portfolio_returns, weight_path). `freq="daily"` reproduces
    `buy_and_hold` exactly, so the old specification remains available.
    """
    w = pd.Series(weights, dtype=float)
    cols = [c for c in w.index if c in asset_returns.columns]
    w = w[cols]
    if w.sum() == 0:
        raise ValueError("Weights sum to zero for the available asset universe.")
    w = w / w.sum()
    R = asset_returns[cols].fillna(0.0)

    if freq == "daily":
        wp = constant_mix_weight_path(asset_returns, weights)
        return buy_and_hold(asset_returns, weights), wp

    keys = _period_keys(R.index, freq)
    if keys is None:
        wp = constant_mix_weight_path(asset_returns, weights)
        return buy_and_hold(asset_returns, weights), wp

    gr = (1.0 + R.to_numpy())
    n, k = gr.shape
    held = np.empty((n, k))          # weights held INTO day t (known at t-1 close)
    cur = w.to_numpy().copy()
    prev_key = None
    for t in range(n):
        if keys[t] != prev_key:      # period boundary -> reset to target
            cur = w.to_numpy().copy()
            prev_key = keys[t]
        held[t] = cur
        val = cur * gr[t]
        cur = val / val.sum()        # drift into the next day
    port = pd.Series((held * R.to_numpy()).sum(axis=1), index=R.index)
    return port, pd.DataFrame(held, index=R.index, columns=cols)


def weights_turnover(W: pd.DataFrame) -> pd.Series:
    """Per-day one-way turnover Σ|Δw| implied by a weight path.

    A constant-mix portfolio holds FIXED weights, which means it trades back to
    target every day as prices move — that is real turnover, not zero. This makes
    it measurable for any strategy that can state its realised weight path.
    """
    return W.diff().abs().sum(axis=1).fillna(0.0)


def constant_mix_weight_path(asset_returns: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Weight path a constant-mix portfolio must trade back to each day.

    Between rebalances the weights DRIFT with relative performance; at the close
    they are reset to target. The traded amount is therefore the gap between the
    drifted weights and the target — this returns the drifted path, so
    `weights_turnover` measures exactly that gap.
    """
    w = pd.Series(weights, dtype=float)
    cols = [c for c in w.index if c in asset_returns.columns]
    w = w[cols]
    w = w / w.sum()
    r = asset_returns[cols].fillna(0.0)
    drifted = w.values * (1.0 + r.values)                 # value shares before reset
    drifted = drifted / drifted.sum(axis=1, keepdims=True)
    return pd.DataFrame(drifted, index=asset_returns.index, columns=cols)


def rolling_risk_parity(returns: pd.DataFrame, lookback: int = 63,
                        rebalance: str = "monthly", td: int = 252,
                        return_weights: bool = False):
    """Rolling (time-varying) inverse-volatility portfolio — a more realistic
    risk-parity benchmark than static full-sample weights. Weights are recomputed
    from trailing volatility and rebalanced on a weekly/monthly grid, shifted one
    day to avoid look-ahead."""
    vol = returns.rolling(lookback).std(ddof=1)
    inv = 1.0 / vol
    w = inv.div(inv.sum(axis=1), axis=0).shift(1)          # daily target, no look-ahead

    idx = returns.index
    if rebalance == "weekly":
        keys = [(d.isocalendar()[0], d.isocalendar()[1]) for d in idx]
    elif rebalance == "monthly":
        keys = [(d.year, d.month) for d in idx]
    else:
        keys = None
    if keys is not None:                                    # hold weights within each period
        grp = pd.DataFrame(w.values, index=pd.MultiIndex.from_tuples(keys), columns=w.columns)
        held = grp.groupby(level=[0, 1]).transform("first")
        w = pd.DataFrame(held.values, index=idx, columns=w.columns)

    w = w.fillna(0.0)
    port = (returns.fillna(0.0) * w).sum(axis=1)
    live = w.sum(axis=1) > 0.5                              # drop the warm-up period
    if return_weights:                                      # backwards-compatible opt-in
        return port[live], w[live]
    return port[live]


def inverse_vol_weights(returns: pd.DataFrame, lookback: int | None = None) -> dict:
    """Risk-parity (inverse-volatility) weights across the available assets.

    A naive risk-parity benchmark: each asset weighted by 1/vol so that riskier
    assets (crypto) receive less capital. Uses full-sample vol for a static,
    transparent benchmark allocation.
    """
    vol = returns.std(ddof=1)
    vol = vol[vol > 0]
    if vol.empty:
        return {}
    inv = 1.0 / vol
    w = inv / inv.sum()
    return w.to_dict()
