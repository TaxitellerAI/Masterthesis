"""Sweep bootstrap — H3/TF4 inference on the DATA level.

Why this exists
---------------
The previous H3 inference tested across the 21 crypto shares of the sweep. Those
21 points are not 21 observations: they are 21 deterministic transformations of the
SAME price history. A monotone, smooth curve must make Mann-Kendall fire (τ = 1.00)
and HAC-OLS fit almost perfectly (R² ≈ 0.96–0.98) — nearly tautological, carrying
almost no information. The HAC lag structure over a share index has no meaning at
all: there is no serial dependence "along" an allocation axis.

The uncertainty lives in the DATA, so that is where it must be generated. Each
replicate resamples the asset return matrix once and re-runs the ENTIRE sweep on it.

Two design rules make the result economically meaningful:
  * ONE index sequence per replicate, applied to ALL assets — this preserves the
    cross-sectional correlation between equities, bonds, gold and the coins, which
    IS the diversification argument under test.
  * The SAME index sequence for all 21 shares within a replicate (paired design).
    Drawing separately per share would inject noise onto the allocation axis where
    none belongs and make the sweep curve artificially jagged.

Why a separate module: `stats.py` is deliberately domain-free (it knows arrays, not
portfolios); this needs weights, strategy logic and metrics, so putting it there
would break that separation and invite an import cycle. `backtest.py` is the
orchestration layer and would be bloated by ~200 lines of vectorised numerics.

Documented simplifications (they matter for the write-up)
--------------------------------------------------------
  * A resampled path has no calendar, so the risk-free leg uses the sample MEAN of
    the realised rf as a scalar, and the exposure step function runs DAILY with no
    dead band. Both are calendar-based rules that are undefined on a shuffled index.
    If the active config sets a non-daily rebalance or a dead band, that is reported
    in the result so the deviation is never silent.
  * The BASE portfolio is rebalanced daily and gross, while the primary specification
    rebalances monthly and net. Slope on the primary spec: 0.753635 against 0.709898
    here (S1). This deviation is deliberate — see below.

Why not a position-based rebalancing grid
-----------------------------------------
The obvious repair is to replace the calendar month by "every 21 observations",
which IS well-defined on a resampled path and matches the calendar frequency
(S1: 95 calendar rebalancings, mean spacing 20.94 rows). It was measured and
REJECTED. Same frequency, same net costs, same rf convention, only the grid
differs — and the slope lands at 0.703713 instead of the calendar 0.742462.
Worse, the result depends on the PHASE of the grid: sweeping the offset over all
21 possible starting rows moves the slope from 0.578070 to 0.817021 — a spread of
0.238951, which is 41 % of the width of the reported bootstrap CI, and far larger
than the daily-vs-monthly gap the grid was meant to close. With only ~95 rebalancing
events over 2010 rows, WHICH rows carry them dominates; the frequency does not pin
the estimate down. Picking one offset would introduce a researcher degree of freedom
of the same order as the effect under test. Averaging over phases would be a
different estimator again.

So the deviation stays and is labelled instead: the estimator is internally
consistent (point estimate and all replicates use the identical rule), and the
primary specification's 0.753635 lies well inside the reported CI [0.383607;
0.965290].
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .config import EngineConfig
from .stats import stationary_bootstrap_indices

# Selection criterion for TF4. Declared here as a NAMED, pre-registered choice so it
# is visible that it was fixed in advance rather than picked after seeing results.
CRITERION_PRIMARY = "sharpe_vc"
CRITERIA = ("sharpe_vc", "calmar_vc", "d_mdd")


# ── vectorised primitives (2-D: rows = time, cols = the 21 shares) ───────────
def _rolling_std(X: np.ndarray, w: int) -> np.ndarray:
    """Rolling sample std along axis 0 for every column at once."""
    from numpy.lib.stride_tricks import sliding_window_view
    out = np.full(X.shape, np.nan)
    if X.shape[0] >= w:
        v = sliding_window_view(X, w, axis=0)          # (n-w+1, k, w)
        out[w - 1:] = v.std(axis=-1, ddof=1)
    return out


def _vol_control(port: np.ndarray, target_vol: float, lookback: int, rf: float,
                 td: int, max_leverage: float, cost_bps: np.ndarray) -> np.ndarray:
    """Vectorised vol-control, mirroring strategies.vol_control column-wise."""
    rv = _rolling_std(port, lookback) * np.sqrt(td)
    with np.errstate(divide="ignore", invalid="ignore"):
        expo = np.minimum(target_vol / rv, max_leverage)
    expo = np.vstack([np.zeros((1, port.shape[1])), expo[:-1]])   # shift(1)
    expo = np.nan_to_num(expo, nan=0.0)
    turn = np.abs(np.diff(expo, axis=0, prepend=np.zeros((1, port.shape[1]))))
    cost = turn * (cost_bps / 1e4)
    return expo * port + (1.0 - expo) * rf - cost


def _sharpe(X: np.ndarray, rf: float, td: int) -> np.ndarray:
    ex = X - rf
    sd = ex.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(sd > 0, ex.mean(axis=0) / sd * np.sqrt(td), np.nan)


def _max_drawdown(X: np.ndarray) -> np.ndarray:
    w = np.cumprod(1.0 + X, axis=0)
    peak = np.maximum.accumulate(w, axis=0)
    return (w / peak - 1.0).min(axis=0)


def _cvar(X: np.ndarray, alpha: float) -> np.ndarray:
    q = np.quantile(X, alpha, axis=0)
    return np.array([X[:, j][X[:, j] <= q[j]].mean() if np.any(X[:, j] <= q[j]) else q[j]
                     for j in range(X.shape[1])])


def _cagr(X: np.ndarray, td: int) -> np.ndarray:
    growth = np.prod(1.0 + X, axis=0)
    n = X.shape[0]
    return np.where(growth > 0, np.sign(growth) * np.abs(growth) ** (td / n) - 1.0, -1.0)


def _weight_matrix(shares: np.ndarray, columns: list, cfg: EngineConfig) -> np.ndarray:
    """(k_assets x n_shares) weights — the sweep as one linear operator.

    Turning the sweep into a matrix product is what makes B = 1000 feasible: the
    portfolio for every share is one matmul on the resampled asset matrix.
    """
    trad = {k: v for k, v in cfg.traditional_weights if k in columns}
    tsum = sum(trad.values()) or 1.0
    cryptos = [c for c in cfg.crypto if c in columns]
    W = np.zeros((len(columns), len(shares)))
    for j, s in enumerate(shares):
        for name, v in trad.items():
            W[columns.index(name), j] = v / tsum * (1.0 - s)
        if cryptos and s > 0:
            for c in cryptos:
                W[columns.index(c), j] = s / len(cryptos)
    return W


def _blended_bps(shares: np.ndarray, cfg: EngineConfig) -> np.ndarray:
    return (1.0 - shares) * cfg.cost_traditional_bps + shares * cfg.cost_crypto_bps


def _sweep_once(R: np.ndarray, W: np.ndarray, bps: np.ndarray, cfg: EngineConfig,
                target_vol: float, rf: float) -> dict:
    """One full sweep (all shares at once) on a given asset return matrix."""
    port = R @ W                                        # (n, n_shares)
    vc = _vol_control(port, target_vol, cfg.lookback, rf, cfg.trading_days,
                      cfg.max_leverage, bps)
    mdd_bh, mdd_vc = _max_drawdown(port), _max_drawdown(vc)
    cv_bh, cv_vc = _cvar(port, cfg.cvar_alpha), _cvar(vc, cfg.cvar_alpha)
    sh_bh, sh_vc = _sharpe(port, rf, cfg.trading_days), _sharpe(vc, rf, cfg.trading_days)
    cagr_vc = _cagr(vc, cfg.trading_days)
    with np.errstate(divide="ignore", invalid="ignore"):
        calmar_vc = np.where(mdd_vc < 0, cagr_vc / np.abs(mdd_vc), np.nan)
    return {
        "d_mdd": mdd_vc - mdd_bh,
        "d_cvar": cv_vc - cv_bh,
        "sharpe_bh": sh_bh,
        "sharpe_vc": sh_vc,
        "calmar_vc": calmar_vc,
    }


def _slope(x: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """OLS slope of every ROW of Y on x (one slope per replicate)."""
    xc = x - x.mean()
    return (Y - Y.mean(axis=1, keepdims=True)) @ xc / (xc @ xc)


def sweep_bootstrap(returns: pd.DataFrame, cfg: EngineConfig = EngineConfig(),
                    target_vol: float = 0.10, n_boot: int = 1000,
                    criterion: str = CRITERION_PRIMARY,
                    shares: np.ndarray | None = None,
                    alpha: float = 0.05, seed: int | None = None) -> dict:
    """Bootstrap the ENTIRE sweep on the data level. See module docstring.

    `criterion` is the pre-registered TF4 selection metric (default: Sharpe of the
    vol-control portfolio). Calmar and ΔMDD are reported alongside but are NOT
    selection criteria.
    """
    if criterion not in CRITERIA:
        raise ValueError(f"Unbekanntes Zielkriterium {criterion!r}; erlaubt: {CRITERIA}")
    if shares is None:
        from .backtest import sweep_shares
        shares = sweep_shares(cfg)
    shares = np.asarray(shares, float)

    cols = list(returns.columns)
    R0 = np.ascontiguousarray(returns.to_numpy(dtype=float))
    R0 = np.nan_to_num(R0, nan=0.0)
    n = R0.shape[0]
    W = _weight_matrix(shares, cols, cfg)
    bps = _blended_bps(shares, cfg)

    # Scalar rf: a resampled path carries no dates (see module docstring).
    rf_arr = np.asarray(cfg.rf_for(returns.index), dtype=float)
    rf = float(np.mean(rf_arr))

    point = _sweep_once(R0, W, bps, cfg, target_vol, rf)          # original sample
    keys = ("d_mdd", "d_cvar", "sharpe_bh", "sharpe_vc", "calmar_vc")
    draws = {k: np.empty((n_boot, len(shares))) for k in keys}

    rng = np.random.default_rng(cfg.seed if seed is None else seed)
    for b in range(n_boot):
        # ONE index sequence -> same rows for every asset AND every share.
        idx = stationary_bootstrap_indices(n, cfg.expected_block, rng)
        rep = _sweep_once(R0[idx], W, bps, cfg, target_vol, rf)
        for k in keys:
            draws[k][b] = rep[k]

    lo, hi = 100 * (alpha / 2), 100 * (1 - alpha / 2)

    def _band(k):
        d = draws[k]
        pw_lo, pw_hi = np.nanpercentile(d, lo, axis=0), np.nanpercentile(d, hi, axis=0)
        # Simultaneous band: the (1-alpha) quantile of the per-replicate MAXIMUM
        # standardised deviation. Pointwise bands understate joint uncertainty
        # across 21 points — the curve as a WHOLE is what H3 is about.
        sd = np.nanstd(d, axis=0, ddof=1)
        sd = np.where(sd > 0, sd, np.nan)
        z = np.nanmax(np.abs((d - point[k]) / sd), axis=1)
        c = float(np.nanpercentile(z, 100 * (1 - alpha)))
        return {
            "point": [_f(v) for v in point[k]],
            "pointwise_low": [_f(v) for v in pw_lo],
            "pointwise_high": [_f(v) for v in pw_hi],
            "simultaneous_low": [_f(v) for v in point[k] - c * sd],
            "simultaneous_high": [_f(v) for v in point[k] + c * sd],
            "simultaneous_factor": c,
        }

    def _slope_result(k):
        s = _slope(shares, draws[k])
        obs = float(_slope(shares, point[k][None, :])[0])
        # Two-sided bootstrap p-value: how often does a recentred replicate slope
        # reach the observed magnitude? (null = no dependence on the crypto share)
        centred = s - np.nanmean(s)
        p = float((np.sum(np.abs(centred) >= abs(obs)) + 1) / (len(s) + 1))
        return {
            "slope": obs,
            "slope_boot_mean": float(np.nanmean(s)),
            "ci_low": float(np.nanpercentile(s, lo)),
            "ci_high": float(np.nanpercentile(s, hi)),
            "p_value": min(1.0, p),
            "share_positive": float(np.mean(s > 0)),
        }

    # ── TF4: argmax distribution + the honest "indistinguishable" set ────────
    crit = draws[criterion]
    crit_point = point[criterion]
    best_idx = int(np.nanargmax(crit_point))
    arg = np.nanargmax(crit, axis=1)
    counts = np.bincount(arg, minlength=len(shares))

    # The argmax is a NON-REGULAR functional: a naive bootstrap CI for it is known
    # to be unreliable. The informative result is therefore the difference to the
    # ORIGINAL-sample optimum: every share whose CI for
    # criterion(s) - criterion(s*) covers zero is statistically indistinguishable
    # from the optimum. That is the defensible answer to TF4.
    diff = crit - crit[:, [best_idx]]
    d_lo = np.nanpercentile(diff, lo, axis=0)
    d_hi = np.nanpercentile(diff, hi, axis=0)
    indist = [bool(l <= 0.0 <= h) for l, h in zip(d_lo, d_hi)]
    ind_shares = [float(s) for s, ok in zip(shares, indist) if ok]

    return {
        "n_boot": int(n_boot),
        "criterion": criterion,
        "criterion_note": ("Vorab festgelegt: primär Sharpe des Vol-Control-Portfolios. "
                           "Calmar und ΔMDD werden nur zusätzlich berichtet und sind "
                           "KEINE Auswahlkriterien."),
        "alpha": alpha,
        "shares": [float(s) for s in shares],
        "observations": int(n),
        "expected_block": cfg.expected_block,
        "rf_scalar_annual": rf * cfg.trading_days,
        "simplifications": {
            "rf": "Sample-Mittel als Skalar (resampelter Pfad hat keinen Kalender).",
            "exposure_rebalance": "täglich",
            "dead_band": 0.0,
            "config_deviates": bool(cfg.rebalance != "daily" or cfg.dead_band > 0),
        },
        "bands": {k: _band(k) for k in ("d_mdd", "d_cvar", "sharpe_bh", "sharpe_vc")},
        "slopes": {k: _slope_result(k) for k in ("d_mdd", "d_cvar")},
        "argmax": {
            "best_share_point": float(shares[best_idx]),
            "distribution": [{"share": float(s), "freq": int(c), "prob": float(c / n_boot)}
                             for s, c in zip(shares, counts)],
            "share_ci_low": float(np.nanpercentile(shares[arg], lo)),
            "share_ci_high": float(np.nanpercentile(shares[arg], hi)),
            "naive_ci_warning": ("Der Argmax ist ein nicht-reguläres Funktional; das obige "
                                 "Quantil-Intervall ist NICHT verlässlich und wird nur zur "
                                 "Vollständigkeit gezeigt. Belastbar ist der Bereich "
                                 "statistisch nicht unterscheidbarer Quoten."),
            "indistinguishable_shares": ind_shares,
            "indistinguishable_range": ([min(ind_shares), max(ind_shares)]
                                        if ind_shares else None),
            "diff_ci_low": [_f(v) for v in d_lo],
            "diff_ci_high": [_f(v) for v in d_hi],
        },
    }


def _f(v):
    """JSON-safe float (NaN/Inf are not valid JSON)."""
    v = float(v)
    return None if not np.isfinite(v) else round(v, 6)
