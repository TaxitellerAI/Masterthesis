"""Inference layer: stationary block bootstrap, paired tests, HAC regression.

This is the part the Bachelor thesis did NOT have and the Master thesis needs:
genuine hypothesis testing rather than narrative 'verification'.
"""
from __future__ import annotations
import numpy as np


def stationary_bootstrap_indices(n: int, expected_block: float, rng) -> np.ndarray:
    """Politis-Romano stationary bootstrap index sequence (geometric block lengths)."""
    p = 1.0 / expected_block
    idx = np.empty(n, dtype=int)
    idx[0] = rng.integers(0, n)
    for t in range(1, n):
        if rng.random() < p:
            idx[t] = rng.integers(0, n)
        else:
            idx[t] = (idx[t - 1] + 1) % n
    return idx


def block_bootstrap_metric(returns, metric_fn, n_boot=10_000,
                           expected_block=20, seed=42) -> np.ndarray:
    """Bootstrap distribution of a path-dependent metric (MDD, CVaR)."""
    rng = np.random.default_rng(seed)
    r = np.asarray(returns, float)
    n = len(r)
    out = np.empty(n_boot)
    for b in range(n_boot):
        out[b] = metric_fn(r[stationary_bootstrap_indices(n, expected_block, rng)])
    return out


def _bca_bounds(observed, boot, jack, alpha=0.05):
    """Bias-corrected and accelerated (BCa) interval bounds.

    More accurate than the plain percentile interval when the bootstrap
    distribution is skewed or biased (typical for drawdown/Sharpe differences).
    """
    from scipy.stats import norm
    boot = np.asarray(boot, float)
    prop = np.mean(boot < observed)
    prop = min(max(prop, 1e-6), 1 - 1e-6)      # guard against 0/1
    z0 = norm.ppf(prop)
    jbar = jack.mean()
    num = np.sum((jbar - jack) ** 3)
    den = 6.0 * (np.sum((jbar - jack) ** 2) ** 1.5)
    a_hat = num / den if den != 0 else 0.0

    def _adj(q):
        zq = norm.ppf(q)
        return float(norm.cdf(z0 + (z0 + zq) / (1 - a_hat * (z0 + zq))))

    lo = np.quantile(boot, _adj(alpha / 2))
    hi = np.quantile(boot, _adj(1 - alpha / 2))
    return float(lo), float(hi)


def paired_bootstrap_diff(a, b, metric_fn, n_boot=10_000,
                          expected_block=20, seed=42) -> dict:
    """Paired bootstrap of metric(a) - metric(b) using shared resample indices.

    Returns the observed difference, a two-sided bootstrap p-value, the plain
    percentile 95% CI, and a bias-corrected & accelerated (BCa) 95% CI. The BCa
    interval uses a delete-one jackknife for the acceleration term.
    """
    rng = np.random.default_rng(seed)
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        idx = stationary_bootstrap_indices(n, expected_block, rng)
        diffs[i] = metric_fn(a[idx]) - metric_fn(b[idx])
    observed = metric_fn(a) - metric_fn(b)
    p_two_sided = 2.0 * min((diffs <= 0).mean(), (diffs >= 0).mean())

    # delete-one jackknife for BCa acceleration
    jack = np.empty(n)
    mask = np.ones(n, dtype=bool)
    for i in range(n):
        mask[i] = False
        jack[i] = metric_fn(a[mask]) - metric_fn(b[mask])
        mask[i] = True
    bca_lo, bca_hi = _bca_bounds(observed, diffs, jack)

    return {
        "observed_diff": float(observed),
        "p_value": float(min(p_two_sided, 1.0)),
        "ci_low": float(np.quantile(diffs, 0.025)),
        "ci_high": float(np.quantile(diffs, 0.975)),
        "ci_low_bca": bca_lo,
        "ci_high_bca": bca_hi,
    }


def wilcoxon_test(a, b) -> dict:
    """Wilcoxon signed-rank test on paired daily returns."""
    from scipy.stats import wilcoxon
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    n = min(len(a), len(b))
    stat, p = wilcoxon(a[-n:], b[-n:])
    return {"statistic": float(stat), "p_value": float(p)}


def holm_correction(pvalues: dict) -> dict:
    """Holm–Bonferroni step-down adjustment for a family of p-values.

    Controls the family-wise error rate without assuming independence. Returns a
    dict of adjusted p-values keyed like the input.
    """
    items = sorted(pvalues.items(), key=lambda kv: (kv[1] if kv[1] == kv[1] else 1.0))
    m = len(items)
    adjusted = {}
    running = 0.0
    for i, (k, p) in enumerate(items):
        p = p if p == p else 1.0
        a = min((m - i) * p, 1.0)
        running = max(running, a)          # enforce monotonicity
        adjusted[k] = float(running)
    return adjusted


def probabilistic_sharpe_ratio(returns, sr_benchmark: float = 0.0) -> dict:
    """Probabilistic Sharpe Ratio (Bailey & López de Prado).

    Probability that the true (per-period) Sharpe exceeds `sr_benchmark`, given
    the sample length, skewness and kurtosis of the returns. Higher is better;
    > 0.95 is the usual bar.
    """
    from scipy.stats import norm, skew, kurtosis
    r = np.asarray(returns, float)
    n = r.size
    sd = r.std(ddof=1)
    if n < 3 or sd == 0:
        return {"sr": float("nan"), "psr": float("nan")}
    sr = r.mean() / sd                       # per-period Sharpe
    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))    # non-excess (normal = 3)
    denom = np.sqrt(max(1 - g3 * sr + (g4 - 1) / 4.0 * sr ** 2, 1e-12))
    z = (sr - sr_benchmark) * np.sqrt(n - 1) / denom
    return {"sr": float(sr), "psr": float(norm.cdf(z))}


def deflated_sharpe_ratio(selected_returns, trial_returns: list) -> dict:
    """Deflated Sharpe Ratio: PSR against the expected maximum Sharpe that would
    arise from `N` trials by luck alone (guards against selection / data-snooping
    across the many strategy configurations compared).
    """
    from scipy.stats import norm
    srs = []
    for r in trial_returns:
        r = np.asarray(r, float)
        sd = r.std(ddof=1)
        if r.size >= 3 and sd > 0:
            srs.append(r.mean() / sd)
    srs = np.asarray(srs, float)
    N = srs.size
    if N < 2:
        return {"sr0": float("nan"), "dsr": float("nan"), "n_trials": int(N)}
    var_sr = srs.var(ddof=1)
    gamma = 0.5772156649015329               # Euler–Mascheroni
    e = np.e
    sr0 = np.sqrt(var_sr) * (
        (1 - gamma) * norm.ppf(1 - 1.0 / N) + gamma * norm.ppf(1 - 1.0 / (N * e))
    )
    psr = probabilistic_sharpe_ratio(selected_returns, sr_benchmark=sr0)
    return {"sr0": float(sr0), "dsr": float(psr["psr"]), "n_trials": int(N)}


def mann_kendall(y) -> dict:
    """Non-parametric Mann–Kendall monotone-trend test.

    A cleaner inference for H3 than an OLS slope across the ~21 crypto-share
    levels: it only asks whether the effect increases monotonically with the
    crypto share, without assuming a functional form or independent residuals.
    """
    from scipy.stats import norm
    y = np.asarray(y, float)
    n = y.size
    if n < 3:
        return {"tau": float("nan"), "s": float("nan"), "p_value": float("nan")}
    s = 0.0
    for i in range(n - 1):
        s += np.sign(y[i + 1:] - y[i]).sum()
    var = n * (n - 1) * (2 * n + 5) / 18.0
    if s > 0:
        z = (s - 1) / np.sqrt(var)
    elif s < 0:
        z = (s + 1) / np.sqrt(var)
    else:
        z = 0.0
    p = 2 * (1 - norm.cdf(abs(z)))
    tau = s / (n * (n - 1) / 2.0)
    return {"tau": float(tau), "s": float(s), "p_value": float(p)}


def bootstrap_slope(x, y, n_boot=2000, seed=42) -> dict:
    """Bootstrap the OLS slope of y on x by resampling (x, y) pairs.

    A distribution-light companion to the HAC slope for H3: it makes no residual
    assumptions, just resamples the observed share/effect points.
    """
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = x.size

    def _slope(xi, yi):
        xm, ym = xi.mean(), yi.mean()
        denom = np.sum((xi - xm) ** 2)
        return np.sum((xi - xm) * (yi - ym)) / denom if denom != 0 else np.nan

    obs = _slope(x, y)
    slopes = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        slopes[b] = _slope(x[idx], y[idx])
    slopes = slopes[np.isfinite(slopes)]
    p = 2.0 * min((slopes <= 0).mean(), (slopes >= 0).mean())
    return {
        "slope": float(obs),
        "p_value": float(min(p, 1.0)),
        "ci_low": float(np.quantile(slopes, 0.025)),
        "ci_high": float(np.quantile(slopes, 0.975)),
    }


def hac_ols(x, y, maxlags: int | None = None) -> dict:
    """OLS of y on x with Newey-West (HAC) standard errors. Used for H3 slope test.

    NOTE: the H3 design regresses an effect measure across crypto-share levels.
    With ~21 share points this is closer to cross-sectional than time-series;
    HAC is included to mirror the thesis spec, but the inference design here is
    worth a deliberate second look (flagged for discussion).
    """
    import statsmodels.api as sm
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    X = sm.add_constant(x)
    if maxlags is None:
        maxlags = max(1, int(round(len(x) ** 0.25)))
    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return {
        "intercept": float(model.params[0]),
        "slope": float(model.params[1]),
        "p_value": float(model.pvalues[1]),
        "r2": float(model.rsquared),
    }
