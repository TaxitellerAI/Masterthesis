"""Higher-level analyses built on the existing strategies/metrics — all additive,
none of them touch the core model. These power the robustness and time-series
exhibits: wealth/drawdown/exposure paths, sub-period (regime) breakdowns,
parameter-stability grids and transaction-cost sensitivity.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .config import EngineConfig
from . import strategies as st
from . import metrics as mt
from .backtest import run_strategies, portfolio_weights, _blended_cost_bps


def _stride(n: int, cap: int = 400) -> int:
    """Downsample stride so a series returns at most ~`cap` points."""
    return max(1, n // cap)


def time_series(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                crypto_share: float = 0.10, target_vol: float = 0.10) -> dict:
    """Wealth, drawdown and exposure paths for Buy-and-Hold, the selected
    vol-control variant and the benchmarks, rebased to 1 at a common start."""
    run = run_strategies(returns, cfg, crypto_share)
    key = f"VolControl_{int(target_vol * 100)}"
    names = [n for n in ["BuyHold", key, "Benchmark_TrueBH", "Benchmark_6040", "Benchmark_RiskParity"]
             if n in run["strategies"]]

    wealth, drawdown, exposure = {}, {}, {}
    for n in names:
        s = run["strategies"][n]["returns"]
        w = (1.0 + s).cumprod()
        wealth[n] = w
        drawdown[n] = w / w.cummax() - 1.0
        exposure[n] = run["strategies"][n].get("exposure")

    # common calendar = union of dates, then rebase all wealth to 1 at the first
    # date where every plotted series exists (fair visual comparison).
    cal = sorted(set().union(*[w.index for w in wealth.values()]))
    cal = pd.DatetimeIndex(cal)
    aligned_w = {n: wealth[n].reindex(cal).ffill() for n in names}
    common = None
    both = pd.concat([aligned_w[n] for n in names], axis=1).dropna()
    if not both.empty:
        common = both.index[0]
    stride = _stride(len(cal))
    sample = cal[::stride]
    dates = [str(d.date()) for d in sample]

    def _clean(series):
        return [None if pd.isna(x) else round(float(x), 5) for x in series.reindex(sample).values]

    series = {}
    for n in names:
        w = aligned_w[n]
        if common is not None:
            base = w.loc[common]
            w = w / base if base and base == base else w
        dd = drawdown[n].reindex(cal).ffill()
        exp = exposure[n]
        series[n] = {
            "wealth": _clean(w),
            "drawdown": _clean(dd),
            "exposure": _clean(exp.reindex(cal).ffill()) if exp is not None else None,
        }
    return {"dates": dates, "series": series, "selected": key}


def subperiod_metrics(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                      crypto_share: float = 0.10, target_vol: float = 0.10) -> list:
    """Metrics for Buy-and-Hold vs. the selected vol-control variant within each
    named regime — the crisis-period evidence that risk management must show."""
    run = run_strategies(returns, cfg, crypto_share)
    bh = run["strategies"]["BuyHold"]["returns"]
    vc = run["strategies"][f"VolControl_{int(target_vol * 100)}"]["returns"]

    rows = []
    for name, start, end in cfg.subperiods:
        m_bh, m_vc = bh.loc[start:end], vc.loc[start:end]
        if len(m_bh) < 15 or len(m_vc) < 15:
            continue
        s_bh = mt.summary(m_bh.values, cfg.rf_daily, cfg.trading_days, cfg.cvar_alpha)
        s_vc = mt.summary(m_vc.values, cfg.rf_daily, cfg.trading_days, cfg.cvar_alpha)
        rows.append({
            "period": name,
            "start": str(m_vc.index.min().date()),
            "end": str(m_vc.index.max().date()),
            "observations": int(len(m_vc)),
            "bh_cagr": s_bh["cagr"], "bh_vol": s_bh["ann_vol"],
            "bh_max_drawdown": s_bh["max_drawdown"], "bh_sharpe": s_bh["sharpe"],
            "vc_cagr": s_vc["cagr"], "vc_vol": s_vc["ann_vol"],
            "vc_max_drawdown": s_vc["max_drawdown"], "vc_sharpe": s_vc["sharpe"],
        })
    return rows


def param_stability(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                    crypto_share: float = 0.10, lookbacks=None, target_vols=None) -> dict:
    """Grid of vol-control Sharpe over (lookback × target vol) — evidence that the
    result is not an artefact of one lucky parameter choice."""
    lookbacks = lookbacks or [20, 40, 60, 90, 120]
    target_vols = target_vols or [0.05, 0.075, 0.10, 0.125, 0.15]
    port = st.buy_and_hold(returns, portfolio_weights(crypto_share, list(returns.columns), cfg))
    cost = _blended_cost_bps(crypto_share, cfg)

    grid = []
    for lb in lookbacks:
        row = []
        for tv in target_vols:
            strat, _ = st.vol_control(
                port, tv, lb, cfg.rf_daily, cfg.trading_days, cfg.max_leverage,
                cost, cfg.vol_method, cfg.ewma_halflife, cfg.rebalance, cfg.dead_band,
            )
            row.append(round(mt.sharpe_ratio(strat.values, cfg.rf_daily, cfg.trading_days), 3))
        grid.append(row)
    return {"lookbacks": lookbacks, "target_vols": target_vols, "sharpe": grid}


def walk_forward(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                 crypto_share: float = 0.10, n_folds: int = 5, train_frac: float = 0.4) -> dict:
    """Walk-forward out-of-sample test.

    The target volatility is a free parameter — this shows the strategy is not
    overfit. On each expanding fold we PICK the target vol that maximised the
    in-sample Sharpe, then measure it purely out-of-sample. Concatenating the OOS
    segments gives an honest, selection-aware equity curve.
    """
    port = st.buy_and_hold(returns, portfolio_weights(crypto_share, list(returns.columns), cfg))
    cost = _blended_cost_bps(crypto_share, cfg)

    # Precompute each candidate strategy once over the full sample.
    strat = {}
    for tv in cfg.target_vols:
        s, _ = st.vol_control(port, tv, cfg.lookback, cfg.rf_daily, cfg.trading_days,
                              cfg.max_leverage, cost, cfg.vol_method, cfg.ewma_halflife, cfg.rebalance, cfg.dead_band)
        strat[tv] = s
    idx = strat[cfg.target_vols[0]].index
    n = len(idx)
    if n < 200:
        return {"folds": [], "oos": {"dates": [], "wealth": [], "bh_wealth": []}, "oos_metrics": {}, "bh_oos_metrics": {}}

    def _sh(series):
        return mt.sharpe_ratio(series.values, cfg.rf_daily, cfg.trading_days)

    start = int(n * train_frac)
    bounds = np.linspace(start, n, n_folds + 1).astype(int)
    folds, oos_parts = [], []
    port_al = port.reindex(idx)
    for k in range(n_folds):
        t0, t1 = bounds[k], bounds[k + 1]
        if t1 - t0 < 10:
            continue
        # choose target vol on the in-sample window [0, t0)
        best_tv, best_is = cfg.target_vols[0], -1e9
        for tv in cfg.target_vols:
            s_is = _sh(strat[tv].iloc[:t0])
            if s_is == s_is and s_is > best_is:
                best_is, best_tv = s_is, tv
        oos = strat[best_tv].iloc[t0:t1]
        oos_parts.append(oos)
        folds.append({
            "train_start": str(idx[0].date()), "train_end": str(idx[t0 - 1].date()),
            "test_start": str(idx[t0].date()), "test_end": str(idx[t1 - 1].date()),
            "chosen_target_vol": float(best_tv),
            "is_sharpe": round(float(best_is), 3),
            "oos_sharpe": round(float(_sh(oos)), 3),
        })

    if not oos_parts:
        return {"folds": [], "oos": {"dates": [], "wealth": [], "bh_wealth": []}, "oos_metrics": {}, "bh_oos_metrics": {}}

    oos_ret = pd.concat(oos_parts)
    bh_oos = port_al.reindex(oos_ret.index)
    vc_wealth = (1 + oos_ret).cumprod()
    bh_wealth = (1 + bh_oos).cumprod()
    stride = _stride(len(oos_ret))
    return {
        "folds": folds,
        "oos": {
            "dates": [str(d.date()) for d in oos_ret.index[::stride]],
            "wealth": [round(float(x), 5) for x in vc_wealth.values[::stride]],
            "bh_wealth": [round(float(x), 5) for x in bh_wealth.values[::stride]],
        },
        "oos_metrics": mt.summary(oos_ret.values, cfg.rf_daily, cfg.trading_days, cfg.cvar_alpha),
        "bh_oos_metrics": mt.summary(bh_oos.values, cfg.rf_daily, cfg.trading_days, cfg.cvar_alpha),
    }


def rolling_metrics(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                    crypto_share: float = 0.10, target_vol: float = 0.10, window: int = 126) -> dict:
    """Rolling annualised Sharpe for Buy-and-Hold vs. the selected vol-control —
    shows whether the edge is stable over time or driven by one episode."""
    run = run_strategies(returns, cfg, crypto_share)
    bh = run["strategies"]["BuyHold"]["returns"]
    vc = run["strategies"][f"VolControl_{int(target_vol * 100)}"]["returns"]

    def _roll(s):
        m = s.rolling(window).mean() - cfg.rf_daily
        sd = s.rolling(window).std(ddof=1)
        return (m / sd) * np.sqrt(cfg.trading_days)

    bh_r, vc_r = _roll(bh), _roll(vc)
    cal = vc_r.index
    stride = _stride(len(cal))
    sample = cal[::stride]

    def _c(series):
        return [None if pd.isna(x) else round(float(x), 4) for x in series.reindex(sample).values]

    return {
        "window": window,
        "dates": [str(d.date()) for d in sample],
        "bh_sharpe": _c(bh_r),
        "vc_sharpe": _c(vc_r),
    }


def return_distribution(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                        crypto_share: float = 0.10, target_vol: float = 0.10, bins: int = 41) -> dict:
    """Histogram of daily returns for Buy-and-Hold vs. the selected vol-control,
    with VaR/CVaR markers — the tail-risk story made visual."""
    run = run_strategies(returns, cfg, crypto_share)
    bh = run["strategies"]["BuyHold"]["returns"].values
    vc = run["strategies"][f"VolControl_{int(target_vol * 100)}"]["returns"].values

    lo = min(np.quantile(bh, 0.005), np.quantile(vc, 0.005))
    hi = max(np.quantile(bh, 0.995), np.quantile(vc, 0.995))
    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    bh_counts, _ = np.histogram(bh, bins=edges, density=True)
    vc_counts, _ = np.histogram(vc, bins=edges, density=True)

    return {
        "centers": [round(float(c), 5) for c in centers],
        "bh": [round(float(x), 4) for x in bh_counts],
        "vc": [round(float(x), 4) for x in vc_counts],
        "bh_var": float(np.quantile(bh, cfg.cvar_alpha)),
        "vc_var": float(np.quantile(vc, cfg.cvar_alpha)),
        "bh_cvar": mt.cvar(bh, cfg.cvar_alpha),
        "vc_cvar": mt.cvar(vc, cfg.cvar_alpha),
    }


def monthly_returns(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                    crypto_share: float = 0.10, target_vol: float = 0.10) -> dict:
    """Calendar of monthly compounded returns for the selected vol-control
    strategy (year × month heatmap) plus the annual total."""
    run = run_strategies(returns, cfg, crypto_share)
    vc = run["strategies"][f"VolControl_{int(target_vol * 100)}"]["returns"]
    grp = (1 + vc).groupby([vc.index.year, vc.index.month]).prod() - 1
    years = sorted({y for y, _ in grp.index})
    matrix, totals = [], []
    for y in years:
        row = []
        for m in range(1, 13):
            row.append(round(float(grp.loc[(y, m)]), 5) if (y, m) in grp.index else None)
        matrix.append(row)
        yr = vc[vc.index.year == y]
        totals.append(round(float((1 + yr).prod() - 1), 5))
    return {"years": years, "matrix": matrix, "annual": totals}


def cost_sensitivity(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                     crypto_share: float = 0.10, target_vol: float = 0.10,
                     multipliers=None) -> dict:
    """Net Sharpe / CAGR of the vol-control strategy as transaction costs scale —
    does the edge survive higher (more realistic) crypto trading costs?"""
    multipliers = multipliers or [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
    port = st.buy_and_hold(returns, portfolio_weights(crypto_share, list(returns.columns), cfg))
    base = _blended_cost_bps(crypto_share, cfg)

    points = []
    for m in multipliers:
        strat, _ = st.vol_control(
            port, target_vol, cfg.lookback, cfg.rf_daily, cfg.trading_days,
            cfg.max_leverage, base * m, cfg.vol_method, cfg.ewma_halflife, cfg.rebalance, cfg.dead_band,
        )
        s = mt.summary(strat.values, cfg.rf_daily, cfg.trading_days, cfg.cvar_alpha)
        points.append({
            "cost_mult": m, "cost_bps": round(base * m, 2),
            "sharpe": round(s["sharpe"], 4), "cagr": round(s["cagr"], 4),
        })
    return {"base_cost_bps": round(base, 2), "points": points}
