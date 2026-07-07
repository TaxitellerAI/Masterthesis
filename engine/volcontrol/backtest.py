"""Backtest orchestration — ties data, strategies, metrics and inference together.

Public entry points:
    run_strategies(returns, cfg, crypto_share)  -> metrics for BH + each target vol
    crypto_sweep(returns, cfg, target_vol)      -> effect sizes across crypto share
    hypothesis_tests(returns, cfg)              -> H1 / H2 / H3 results
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .config import EngineConfig
from . import strategies as st
from . import metrics as mt
from . import stats as stx


def portfolio_weights(crypto_share: float, available: list, cfg: EngineConfig) -> dict:
    """Allocate (1 - crypto_share) across the traditional sleeve at institutional
    weights, and crypto_share equally across the available cryptocurrencies."""
    trad = {k: v for k, v in cfg.traditional_weights if k in available}
    s = sum(trad.values())
    trad = {k: v / s * (1.0 - crypto_share) for k, v in trad.items()} if s else {}

    cryptos = [c for c in cfg.crypto if c in available]
    weights = dict(trad)
    if cryptos and crypto_share > 0:
        each = crypto_share / len(cryptos)
        for c in cryptos:
            weights[c] = each
    return weights


def _blended_cost_bps(crypto_share: float, cfg: EngineConfig) -> float:
    return (1.0 - crypto_share) * cfg.cost_traditional_bps + crypto_share * cfg.cost_crypto_bps


def run_strategies(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                   crypto_share: float = 0.10) -> dict:
    available = list(returns.columns)
    weights = portfolio_weights(crypto_share, available, cfg)
    port = st.buy_and_hold(returns, weights)
    cost_bps = _blended_cost_bps(crypto_share, cfg)

    def _summ(series):
        return mt.summary(series.values, cfg.rf_daily, cfg.trading_days, cfg.cvar_alpha)

    out = {"weights": weights, "crypto_share": crypto_share, "strategies": {}}
    out["strategies"]["BuyHold"] = {"returns": port, "turnover": 0.0, **_summ(port)}

    for tv in cfg.target_vols:
        strat, exposure = st.vol_control(
            port, tv, cfg.lookback, cfg.rf_daily, cfg.trading_days,
            cfg.max_leverage, cost_bps, cfg.vol_method, cfg.ewma_halflife,
            cfg.rebalance, cfg.dead_band,
        )
        out["strategies"][f"VolControl_{int(tv*100)}"] = {
            "returns": strat,
            "exposure": exposure,
            "turnover": float(exposure.diff().abs().sum()),
            **_summ(strat),
        }

    # --- comparators ---
    # True buy-and-hold (drift, zero turnover) — the honest low-turnover baseline
    # next to the daily-rebalanced constant-mix used as the vol-control base.
    tbh = st.true_buy_and_hold(returns, weights)
    out["strategies"]["Benchmark_TrueBH"] = {"returns": tbh, "turnover": 0.0, **_summ(tbh)}

    if "MSCI_World" in available and "Global_Bonds" in available:
        p6040 = st.buy_and_hold(returns, {"MSCI_World": 0.6, "Global_Bonds": 0.4})
        out["strategies"]["Benchmark_6040"] = {"returns": p6040, "turnover": 0.0, **_summ(p6040)}

    # Rolling (time-varying) inverse-vol risk parity — more realistic than static
    # full-sample weights.
    if returns.shape[1] >= 2 and len(returns) > 80:
        prp = st.rolling_risk_parity(returns)
        if len(prp) > 20:
            out["strategies"]["Benchmark_RiskParity"] = {"returns": prp, "turnover": 0.0, **_summ(prp)}

    return out


def metrics_table(run_result: dict) -> pd.DataFrame:
    rows = []
    for name, d in run_result["strategies"].items():
        rows.append({
            "strategy": name,
            "ann_return": d["ann_return"],
            "cagr": d["cagr"],
            "ann_vol": d["ann_vol"],
            "sharpe": d["sharpe"],
            "max_drawdown": d["max_drawdown"],
            "cvar_95": d["cvar_95"],
            "turnover": d.get("turnover", 0.0),
        })
    return pd.DataFrame(rows).set_index("strategy").round(4)


def crypto_sweep(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                 target_vol: float = 0.10, shares=None) -> pd.DataFrame:
    """Vary the crypto allocation 0..50% and record the vol-control effect sizes."""
    if shares is None:
        shares = np.round(np.arange(0.0, 0.5001, 0.025), 4)
    rows = []
    for s in shares:
        weights = portfolio_weights(float(s), list(returns.columns), cfg)
        port = st.buy_and_hold(returns, weights)
        bh = mt.summary(port.values, cfg.rf_daily, cfg.trading_days, cfg.cvar_alpha)
        strat, _ = st.vol_control(
            port, target_vol, cfg.lookback, cfg.rf_daily, cfg.trading_days,
            cfg.max_leverage, _blended_cost_bps(float(s), cfg),
            cfg.vol_method, cfg.ewma_halflife, cfg.rebalance, cfg.dead_band,
        )
        vc = mt.summary(strat.values, cfg.rf_daily, cfg.trading_days, cfg.cvar_alpha)
        rows.append({
            "crypto_share": float(s),
            "d_mdd": vc["max_drawdown"] - bh["max_drawdown"],
            "d_cvar": vc["cvar_95"] - bh["cvar_95"],
            "sharpe_bh": bh["sharpe"],
            "sharpe_vc": vc["sharpe"],
        })
    return pd.DataFrame(rows)


def hypothesis_tests(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                     crypto_share: float = 0.10, target_vol: float = 0.10) -> dict:
    """H1 (MDD), H2 (Sharpe) via paired bootstrap; H3 (interaction) via HAC slope."""
    run = run_strategies(returns, cfg, crypto_share)
    bh = run["strategies"]["BuyHold"]["returns"].values
    vc = run["strategies"][f"VolControl_{int(target_vol*100)}"]["returns"].values

    h1 = stx.paired_bootstrap_diff(
        vc, bh, mt.max_drawdown, cfg.bootstrap_n, cfg.expected_block, cfg.seed)
    h2 = stx.paired_bootstrap_diff(
        vc, bh, lambda r: mt.sharpe_ratio(r, cfg.rf_daily, cfg.trading_days),
        cfg.bootstrap_n, cfg.expected_block, cfg.seed)
    wilcox = stx.wilcoxon_test(vc, bh)

    sweep = crypto_sweep(returns, cfg, target_vol)
    shares = sweep["crypto_share"].values
    h3_mdd = stx.hac_ols(shares, sweep["d_mdd"].values)
    h3_cvar = stx.hac_ols(shares, sweep["d_cvar"].values)
    # More robust H3 inference: monotone-trend test + pair-resampling slope CI.
    h3_mdd_mk = stx.mann_kendall(sweep["d_mdd"].values)
    h3_cvar_mk = stx.mann_kendall(sweep["d_cvar"].values)
    h3_mdd_boot = stx.bootstrap_slope(shares, sweep["d_mdd"].values, seed=cfg.seed)
    h3_cvar_boot = stx.bootstrap_slope(shares, sweep["d_cvar"].values, seed=cfg.seed)

    # Family-wise error control across the primary hypotheses.
    holm = stx.holm_correction({
        "H1_max_drawdown": h1["p_value"],
        "H2_sharpe": h2["p_value"],
        "wilcoxon_daily": wilcox["p_value"],
        "H3_dMDD_vs_share": h3_mdd["p_value"],
        "H3_dCVaR_vs_share": h3_cvar["p_value"],
    })

    # Deflated Sharpe of the selected vol-control strategy against the family of
    # configurations tried (guards the Sharpe against data-snooping).
    trials = [d["returns"].values for k, d in run["strategies"].items()
              if k.startswith("VolControl") or k == "BuyHold"]
    dsr = stx.deflated_sharpe_ratio(vc, trials)
    psr = stx.probabilistic_sharpe_ratio(vc)

    return {
        "H1_max_drawdown": h1,
        "H2_sharpe": h2,
        "wilcoxon_daily": wilcox,
        "H3_dMDD_vs_share": h3_mdd,
        "H3_dCVaR_vs_share": h3_cvar,
        "H3_dMDD_mann_kendall": h3_mdd_mk,
        "H3_dCVaR_mann_kendall": h3_cvar_mk,
        "H3_dMDD_boot_slope": h3_mdd_boot,
        "H3_dCVaR_boot_slope": h3_cvar_boot,
        "holm_adjusted": holm,
        "deflated_sharpe": dsr,
        "probabilistic_sharpe": psr,
        "sweep": sweep,
    }
