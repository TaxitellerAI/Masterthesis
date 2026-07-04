"""Descriptive statistics for the selected asset universe.

This is an ADDITION, not a change to the model: it reuses the very same metric
functions (volatility, Sharpe, max drawdown, CVaR) the backtest uses, so the
descriptive table and the strategy table can never disagree. The volatility-
control / bootstrap / HAC code is untouched.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import skew, kurtosis

from . import metrics as mt


def describe_assets(prices: pd.DataFrame, rf_annual: float, alpha: float) -> pd.DataFrame:
    """Per-asset descriptive statistics on each asset's NATIVE trading calendar.

    Crucially, every asset is described on its own observed days: crypto keeps its
    ~365 trading days per year, ETFs their ~252. Each asset is therefore annualised
    with its OWN periods-per-year (inferred from the observed span), so a mixed
    equity/crypto universe is compared on an honest footing rather than being
    force-fitted onto one calendar. (The portfolio backtest, by contrast, uses a
    single aligned calendar — that is a different, deliberate choice.)
    """
    rows = []
    for col in prices.columns:
        s = prices[col].dropna()
        r = s.pct_change().dropna().values
        if r.size < 3:
            continue
        span_years = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
        td = int(round(r.size / span_years))
        td = min(max(td, 200), 366)            # clamp to a sane daily range
        rf_daily = rf_annual / td
        rows.append({
            "asset": col,
            "observations": int(r.size),
            "trading_days": td,                 # inferred periods-per-year
            "first": str(s.index[0].date()),
            "last": str(s.index[-1].date()),
            "ann_return": float(np.mean(r) * td),
            "ann_vol": mt.ann_volatility(r, td),
            "sharpe": mt.sharpe_ratio(r, rf_daily, td),
            "skew": float(skew(r)),
            "excess_kurtosis": float(kurtosis(r, fisher=True)),
            "max_drawdown": mt.max_drawdown(r),
            "var_95": float(np.quantile(r, alpha)),
            "cvar_95": mt.cvar(r, alpha),
            "best_day": float(r.max()),
            "worst_day": float(r.min()),
            "pct_positive": float(np.mean(r > 0)),
        })
    return pd.DataFrame(rows)


def correlation_matrix(returns: pd.DataFrame) -> dict:
    """Pearson correlation of daily returns over the common sample."""
    common = returns.dropna()
    corr = common.corr()
    return {
        "assets": list(corr.columns),
        "matrix": corr.round(3).values.tolist(),
    }


def asset_calendar_returns(prices: pd.DataFrame) -> dict:
    """Per-asset calendar-year returns plus cumulative return from each year's
    start to the end of the data — the numbers behind questions like "which
    asset performed best since 2021?". Computed on each asset's native calendar.
    """
    rets = prices.pct_change()
    years = sorted({y for y in rets.index.year})
    assets = list(prices.columns)

    yearly = []      # rows per year: {year, <asset>: compounded return or None}
    for y in years:
        row = {"year": int(y)}
        block = rets[rets.index.year == y]
        for a in assets:
            r = block[a].dropna()
            row[a] = round(float((1 + r).prod() - 1), 5) if len(r) >= 10 else None
        yearly.append(row)

    since = []       # rows per start year: cumulative return start-of-year -> end
    for y in years:
        row = {"since": int(y)}
        block = rets[rets.index.year >= y]
        for a in assets:
            r = block[a].dropna()
            row[a] = round(float((1 + r).prod() - 1), 5) if len(r) >= 10 else None
        since.append(row)

    return {"assets": assets, "yearly": yearly, "since": since}


def sample_window(returns: pd.DataFrame) -> dict:
    """Common (complete-case) sample window across the selected assets."""
    common = returns.dropna()
    if common.empty:
        return {"start": None, "end": None, "observations": 0}
    return {
        "start": str(common.index.min().date()),
        "end": str(common.index.max().date()),
        "observations": int(len(common)),
    }
