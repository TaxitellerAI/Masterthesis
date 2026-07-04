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
                rf_daily: float = 0.0, td: int = 252, max_leverage: float = 1.0,
                cost_bps: float = 15.0, vol_method: str = "rolling",
                ewma_halflife: int = 20, rebalance: str = "daily", dead_band: float = 0.0):
    """Scale exposure inversely to realised volatility.

    exposure_t = min(target_vol / realised_vol_{t-1}, max_leverage)
    The shift by one day removes look-ahead: today's allocation uses only
    information available at yesterday's close. Uninvested capital earns the
    risk-free rate; turnover is charged at `cost_bps`. `rebalance` controls how
    often the target is actually traded to; `vol_method` selects the estimator.

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

    strat = exposure * port_returns + (1.0 - exposure) * rf_daily - cost
    return strat.dropna(), exposure


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
