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
from . import sample as sm
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


def weight_cost(W: pd.DataFrame, cfg: EngineConfig) -> tuple:
    """(turnover, cost) implied by a weight path, priced per asset class.

    Crypto legs are charged cost_crypto_bps, everything else cost_traditional_bps.
    Constant-mix and risk-parity DO trade — pretending their turnover is zero made
    the vol-control comparison inconsistent (only one side paid costs).
    """
    dw = W.diff().abs().fillna(0.0)
    bps = pd.Series(
        {c: (cfg.cost_crypto_bps if c in cfg.crypto else cfg.cost_traditional_bps)
         for c in W.columns}, dtype=float)
    return dw.sum(axis=1), (dw * bps).sum(axis=1) / 1e4


def run_strategies(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                   crypto_share: float = 0.10, pit_builder=None) -> dict:
    """`pit_builder` (optional) switches the BASE portfolio to a point-in-time sleeve
    whose composition grows as coins become investable. When it is None the original
    static path runs completely unchanged — that equivalence is covered by a test."""
    available = list(returns.columns)
    cost_bps = _blended_cost_bps(crypto_share, cfg)
    sleeve_info = None
    if pit_builder is None:
        weights = portfolio_weights(crypto_share, available, cfg)
        # The base weights are rebalanced on cfg.weight_rebalance (monthly by default).
        # CRITICAL: vol_control below scales THIS series, so the vol-control strategy
        # and the Buy-and-Hold benchmark rest on the identical base portfolio — the
        # two are never different grundportfolios.
        port_gross, wpath = st.periodic_mix(returns, weights, cfg.weight_rebalance)
        bh_turn, bh_cost = weight_cost(wpath, cfg)
        port = port_gross - bh_cost
    else:
        W, sleeve_cost, sleeve_info = pit_builder(crypto_share, returns.index)
        # Re-spreading the sleeve when a coin enters is a REAL trade and is charged
        # at the crypto cost — otherwise the growing basket would look free.
        bh_turn, bh_cost = weight_cost(W, cfg)
        port_gross = sm.weighted_portfolio(returns, W) - sleeve_cost
        port = port_gross - bh_cost
        weights = {c: round(float(W[c].iloc[-1]), 6) for c in W.columns}

    def _summ(series, gross=None, turnover=0.0, turnover_parts=None):
        # rf is aligned to each strategy's OWN calendar (they differ in length
        # after warm-up/dropna), so every metric uses the rate that truly applied.
        out = mt.summary(series.values, cfg.rf_for(series.index),
                         cfg.trading_days, cfg.cvar_alpha)
        # Strategies run on different calendars (risk parity drops a warm-up), so n
        # and the effective window travel WITH each row — comparing without them
        # would be misleading.
        out["observations"] = int(len(series))
        out["start"] = str(series.index.min().date()) if len(series) else None
        out["end"] = str(series.index.max().date()) if len(series) else None
        out["turnover"] = float(turnover)
        # Vol-control trades on TWO levels; reporting only one made it look like the
        # lower-turnover strategy when it is in fact the higher one. The parts stay
        # visible so the headline figure can be taken apart.
        if turnover_parts is not None:
            out["turnover_exposure"] = float(turnover_parts[0])
            out["turnover_sleeve"] = float(turnover_parts[1])
        if gross is not None:      # keep the cost effect visible, never silently net
            g = mt.summary(gross.values, cfg.rf_for(gross.index),
                           cfg.trading_days, cfg.cvar_alpha)
            out["ann_return_gross"] = g["ann_return"]
            out["cagr_gross"] = g["cagr"]
            out["sharpe_gross"] = g["sharpe"]
        return out

    out = {"weights": weights, "crypto_share": crypto_share, "strategies": {}}
    if sleeve_info is not None:
        out["sleeve"] = sleeve_info
    out["strategies"]["BuyHold"] = {"returns": port,
                                    **_summ(port, gross=port_gross, turnover=bh_turn.sum())}

    for tv in cfg.target_vols:
        strat, exposure = st.vol_control(
            port, tv, cfg.lookback, cfg.rf_for(port.index), cfg.trading_days,
            cfg.max_leverage, cost_bps, cfg.vol_method, cfg.ewma_halflife,
            cfg.rebalance, cfg.dead_band,
        )
        # Like-for-like turnover. A vol-control strategy trades twice over: it moves
        # the investment ratio (|d exposure|) AND it carries its share of the base
        # portfolio's own rebalancing (exposure_t x sleeve turnover_t). Reporting
        # only the first understated it against Buy-and-Hold, whose column counts the
        # full sleeve turnover — the table then read as "vol control trades less",
        # which is the opposite of the truth. Costs were always charged on both legs
        # (the base series is already net of bh_cost, vol_control charges cost_bps on
        # the exposure change), so this changes the REPORTED figure only.
        exp_turn = float(exposure.diff().abs().sum())
        sleeve_turn = float((bh_turn * exposure.reindex(bh_turn.index).fillna(0.0)).sum())
        out["strategies"][f"VolControl_{int(tv*100)}"] = {
            "returns": strat,
            "exposure": exposure,
            **_summ(strat, turnover=exp_turn + sleeve_turn,
                    turnover_parts=(exp_turn, sleeve_turn)),
        }

    # --- comparators ---
    # True buy-and-hold (drift, zero turnover) — the honest low-turnover baseline
    # next to the daily-rebalanced constant-mix used as the vol-control base.
    if pit_builder is None:      # a drifting basket is undefined when members enter later
        # TrueBH is the ONLY strategy whose zero turnover is factually correct:
        # it buys once and never trades again.
        tbh = st.true_buy_and_hold(returns, weights)
        out["strategies"]["Benchmark_TrueBH"] = {"returns": tbh, **_summ(tbh, turnover=0.0)}

    if "MSCI_World" in available and "Global_Bonds" in available:
        w6040 = {"MSCI_World": 0.6, "Global_Bonds": 0.4}
        g6040, wp6040 = st.periodic_mix(returns, w6040, cfg.weight_rebalance)
        t6040, c6040 = weight_cost(wp6040, cfg)
        n6040 = g6040 - c6040
        out["strategies"]["Benchmark_6040"] = {
            "returns": n6040, **_summ(n6040, gross=g6040, turnover=t6040.sum())}

    # Rolling (time-varying) inverse-vol risk parity — more realistic than static
    # full-sample weights.
    if returns.shape[1] >= 2 and len(returns) > 80:
        prp_gross, Wrp = st.rolling_risk_parity(returns, return_weights=True)
        if len(prp_gross) > 20:
            trp, crp = weight_cost(Wrp, cfg)
            prp = prp_gross - crp
            out["strategies"]["Benchmark_RiskParity"] = {
                "returns": prp, **_summ(prp, gross=prp_gross, turnover=trp.sum())}

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
            "turnover_exposure": d.get("turnover_exposure"),
            "turnover_sleeve": d.get("turnover_sleeve"),
            "observations": d.get("observations"),
            "start": d.get("start"),
            "end": d.get("end"),
            "ann_return_gross": d.get("ann_return_gross"),
            "cagr_gross": d.get("cagr_gross"),
            "sharpe_gross": d.get("sharpe_gross"),
        })
    return pd.DataFrame(rows).set_index("strategy").round(4)


def sweep_shares(cfg: EngineConfig) -> np.ndarray:
    """The crypto-share grid — one definition, used by the sweep AND the DSR trials."""
    return np.round(np.arange(0.0, cfg.sweep_max_share + 1e-9, cfg.sweep_step), 4)


def crypto_sweep(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                 target_vol: float = 0.10, shares=None, pit_builder=None) -> pd.DataFrame:
    """Vary the crypto allocation 0..50% and record the vol-control effect sizes."""
    if shares is None:
        shares = sweep_shares(cfg)
    rows = []
    for s in shares:
        if pit_builder is None:
            weights = portfolio_weights(float(s), list(returns.columns), cfg)
            port, _wp = st.periodic_mix(returns, weights, cfg.weight_rebalance)
        else:
            W, sleeve_cost, _ = pit_builder(float(s), returns.index)
            port = sm.weighted_portfolio(returns, W) - sleeve_cost
        bh = mt.summary(port.values, cfg.rf_for(port.index), cfg.trading_days, cfg.cvar_alpha)
        strat, _ = st.vol_control(
            port, target_vol, cfg.lookback, cfg.rf_for(port.index), cfg.trading_days,
            cfg.max_leverage, _blended_cost_bps(float(s), cfg),
            cfg.vol_method, cfg.ewma_halflife, cfg.rebalance, cfg.dead_band,
        )
        vc = mt.summary(strat.values, cfg.rf_for(strat.index), cfg.trading_days, cfg.cvar_alpha)
        rows.append({
            "crypto_share": float(s),
            "d_mdd": vc["max_drawdown"] - bh["max_drawdown"],
            "d_cvar": vc["cvar_95"] - bh["cvar_95"],
            "sharpe_bh": bh["sharpe"],
            "sharpe_vc": vc["sharpe"],
        })
    return pd.DataFrame(rows)


def dsr_trial_returns(returns: pd.DataFrame, cfg: EngineConfig, crypto_share: float,
                      target_vol: float, pit_builder=None) -> list:
    """Return series of EVERY vol-control configuration this study actually explores.

    The Deflated Sharpe deflates the selected Sharpe by the expected maximum that
    N independent trials would produce by luck. Feeding it only the four rows of
    the metrics table understates the search badly: the study additionally scans

        * the parameter-stability grid  cfg.stability_lookbacks x cfg.stability_target_vols
        * the crypto-share sweep        sweep_shares(cfg) at the selected target vol

    Both grids are read from the config, so this set can never drift apart from what
    the exhibits actually compute. Configurations are de-duplicated by
    (lookback, target_vol, crypto_share) so the overlap of the two grids is counted once.

    Note the formula also needs the VARIANCE of Sharpe across trials, so the real
    series are returned — simply raising N would be wrong.
    """
    trials: dict[tuple, np.ndarray] = {}

    def _add(lb, tv, share, port):
        key = (int(lb), round(float(tv), 6), round(float(share), 6))
        if key in trials:
            return
        strat, _ = st.vol_control(
            port, tv, lb, cfg.rf_for(port.index), cfg.trading_days, cfg.max_leverage,
            _blended_cost_bps(share, cfg), cfg.vol_method, cfg.ewma_halflife,
            cfg.rebalance, cfg.dead_band,
        )
        trials[key] = strat.values

    def _port(share):
        if pit_builder is None:
            return st.buy_and_hold(returns, portfolio_weights(share, list(returns.columns), cfg))
        W, sleeve_cost, _ = pit_builder(share, returns.index)
        return sm.weighted_portfolio(returns, W) - sleeve_cost

    # 1) parameter-stability grid at the selected crypto share
    base_port = _port(crypto_share)
    for lb in cfg.stability_lookbacks:
        for tv in cfg.stability_target_vols:
            _add(lb, tv, crypto_share, base_port)

    # 2) crypto-share sweep at the selected target vol and base lookback
    for share in sweep_shares(cfg):
        _add(cfg.lookback, target_vol, float(share), _port(float(share)))

    return list(trials.values())


def hypothesis_tests(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                     crypto_share: float = 0.10, target_vol: float = 0.10,
                     pit_builder=None, n_sweep_boot: int = 0,
                     run=None, sweep_df=None, sweep_boot=None) -> dict:
    """H1 (MDD), H2 (Sharpe) via paired bootstrap; H3 (interaction) via data-level slope.

    `run`, `sweep_df` and `sweep_boot` accept ALREADY COMPUTED results so the API can
    hand over what other panels produced instead of recomputing them. Passing None
    reproduces the previous behaviour exactly — the inputs are identical objects, so
    no number can move.
    """
    if run is None:
        run = run_strategies(returns, cfg, crypto_share, pit_builder)
    bh = run["strategies"]["BuyHold"]["returns"].values
    vc = run["strategies"][f"VolControl_{int(target_vol*100)}"]["returns"].values

    # The block bootstrap RESAMPLES days, so a dated rf vector cannot be aligned to
    # a resampled path. We therefore use the sample MEAN of the realised rf as the
    # scalar hurdle here — the realised level, not an assumed constant. Documented
    # simplification: within-sample rf variation is second-order for the Sharpe
    # DIFFERENCE, which is what H2 tests (both legs face the same hurdle).
    rf_bar = float(np.mean(np.asarray(
        cfg.rf_for(run["strategies"][f"VolControl_{int(target_vol*100)}"]["returns"].index),
        dtype=float)))

    h1 = stx.paired_bootstrap_diff(
        vc, bh, mt.max_drawdown, cfg.bootstrap_n, cfg.expected_block, cfg.seed)
    h2 = stx.paired_bootstrap_diff(
        vc, bh, lambda r: mt.sharpe_ratio(r, rf_bar, cfg.trading_days),
        cfg.bootstrap_n, cfg.expected_block, cfg.seed)
    wilcox = stx.wilcoxon_test(vc, bh)

    sweep = crypto_sweep(returns, cfg, target_vol, pit_builder=pit_builder) \
        if sweep_df is None else sweep_df
    shares = sweep["crypto_share"].values
    h3_mdd = stx.hac_ols(shares, sweep["d_mdd"].values)
    h3_cvar = stx.hac_ols(shares, sweep["d_cvar"].values)
    # More robust H3 inference: monotone-trend test + pair-resampling slope CI.
    h3_mdd_mk = stx.mann_kendall(sweep["d_mdd"].values)
    h3_cvar_mk = stx.mann_kendall(sweep["d_cvar"].values)
    h3_mdd_boot = stx.bootstrap_slope(shares, sweep["d_mdd"].values, seed=cfg.seed)
    h3_cvar_boot = stx.bootstrap_slope(shares, sweep["d_cvar"].values, seed=cfg.seed)

    # Family-wise error control across the CONFIRMATORY family only.
    #
    # The family is defined by the pre-specified research questions — H1 (drawdown),
    # H2 (Sharpe) and the two H3 interaction slopes. The Wilcoxon test on paired
    # DAILY returns answers none of them: it asks whether the two return
    # DISTRIBUTIONS differ at all, which at n > 1400 is almost mechanically
    # significant and says nothing about drawdown, Sharpe or the crypto interaction.
    # It is therefore reported as a DESCRIPTIVE companion outside the correction.
    #
    # This is a content-driven definition, not a result-driven one: the decision
    # rests on which tests answer a stated hypothesis, and it was made without
    # regard to which side of alpha the p-values fall on. Both variants are reported
    # (holm_adjusted vs. holm_adjusted_incl_wilcoxon) so the effect of the choice is
    # documented rather than hidden.
    # H3 on the DATA level (bootstrap of the whole sweep). The 21 sweep points are
    # not 21 observations but deterministic transforms of one price history, so the
    # HAC-OLS slope over the share axis is near-tautological. When available, the
    # data-level slope is the CONFIRMATORY test for H3 and the HAC/Mann-Kendall
    # results move to a clearly marked supplementary block.
    sboot = sweep_boot
    if sboot is None and n_sweep_boot > 0:
        from . import sweepboot as sbm
        sboot = sbm.sweep_bootstrap(returns, cfg, target_vol, n_boot=n_sweep_boot,
                                    shares=shares)

    confirmatory = {
        "H1_max_drawdown": h1["p_value"],
        "H2_sharpe": h2["p_value"],
    }
    if sboot is not None:
        confirmatory["H3_dMDD_slope_data"] = sboot["slopes"]["d_mdd"]["p_value"]
        confirmatory["H3_dCVaR_slope_data"] = sboot["slopes"]["d_cvar"]["p_value"]
        h3_family_basis = "data_level_sweep_bootstrap"
    else:
        confirmatory["H3_dMDD_vs_share"] = h3_mdd["p_value"]
        confirmatory["H3_dCVaR_vs_share"] = h3_cvar["p_value"]
        h3_family_basis = "sweep_level_hac_ols"

    holm = stx.holm_correction(confirmatory)
    holm_with_wilcox = stx.holm_correction({**confirmatory, "wilcoxon_daily": wilcox["p_value"]})
    # Both H3 variants side by side, so the difference is documentable in the thesis.
    holm_sweep_level = stx.holm_correction({
        "H1_max_drawdown": h1["p_value"], "H2_sharpe": h2["p_value"],
        "H3_dMDD_vs_share": h3_mdd["p_value"], "H3_dCVaR_vs_share": h3_cvar["p_value"],
    })

    # Deflated Sharpe against the configurations the study REALLY explored
    # (stability grid + sweep), not just the rows of the metrics table.
    trials = dsr_trial_returns(returns, cfg, crypto_share, target_vol, pit_builder)
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
        "holm_adjusted_incl_wilcoxon": holm_with_wilcox,
        "holm_adjusted_sweep_level_h3": holm_sweep_level,
        "holm_family": list(confirmatory.keys()),
        "h3_family_basis": h3_family_basis,
        "sweep_bootstrap": sboot,
        "sweep_level_note": ("Mann-Kendall und HAC-OLS laufen über die 21 Sweep-Punkte. "
                             "Diese sind KEINE 21 Beobachtungen, sondern deterministische "
                             "Transformationen derselben Preisreihe — ein Monotonietest muss "
                             "auf einer glatten Kurve anschlagen (τ = 1,00). Sie werden daher "
                             "nur ergänzend berichtet; konfirmatorisch ist die Steigung auf "
                             "Datenebene."),
        "holm_note": ("Konfirmatorische Familie = vorab spezifizierte Hypothesen H1, H2 und die "
                      "beiden H3-Steigungen. Der Wilcoxon-Test auf Tagesrenditen beantwortet keine "
                      "davon und wird deskriptiv AUSSERHALB der Holm-Korrektur berichtet."),
        "deflated_sharpe": dsr,
        "probabilistic_sharpe": psr,
        "sweep": sweep,
    }
