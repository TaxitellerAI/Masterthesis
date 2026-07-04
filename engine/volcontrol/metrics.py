"""Risk and performance metrics. All operate on a 1-D array of daily returns."""
from __future__ import annotations
import numpy as np


def ann_volatility(r: np.ndarray, td: int = 252) -> float:
    return float(np.std(r, ddof=1) * np.sqrt(td))


def sharpe_ratio(r: np.ndarray, rf_daily: float = 0.0, td: int = 252) -> float:
    excess = np.asarray(r, float) - rf_daily
    sd = np.std(excess, ddof=1)
    if sd == 0:
        return float("nan")
    return float(np.mean(excess) / sd * np.sqrt(td))


def cagr(r: np.ndarray, td: int = 252) -> float:
    """Geometric annualised return (compound growth rate).

    Unlike the arithmetic annualisation (mean·td) this compounds the realised
    path, so it does not overstate the return of a volatile series. Reporting
    both is good practice; CAGR is the honest 'what an investor earned'.
    """
    r = np.asarray(r, float)
    if r.size == 0:
        return float("nan")
    growth = np.prod(1.0 + r)
    if growth <= 0:                      # wiped out -> total loss
        return -1.0
    return float(growth ** (td / r.size) - 1.0)


def max_drawdown(r: np.ndarray) -> float:
    """Most negative peak-to-trough on the cumulative wealth path (<= 0)."""
    wealth = np.cumprod(1.0 + np.asarray(r, float))
    peak = np.maximum.accumulate(wealth)
    dd = wealth / peak - 1.0
    return float(dd.min())


def cvar(r: np.ndarray, alpha: float = 0.05) -> float:
    """Conditional VaR / Expected Shortfall: mean of the worst alpha-tail (<= 0)."""
    r = np.asarray(r, float)
    q = np.quantile(r, alpha)
    tail = r[r <= q]
    return float(tail.mean()) if tail.size else float(q)


def summary(r: np.ndarray, rf_daily: float = 0.0, td: int = 252,
            alpha: float = 0.05) -> dict:
    r = np.asarray(r, float)
    return {
        "ann_return": float(np.mean(r) * td),   # arithmetic annualisation
        "cagr": cagr(r, td),                     # geometric (compound) annualisation
        "ann_vol": ann_volatility(r, td),
        "sharpe": sharpe_ratio(r, rf_daily, td),
        "max_drawdown": max_drawdown(r),
        "cvar_95": cvar(r, alpha),
    }
