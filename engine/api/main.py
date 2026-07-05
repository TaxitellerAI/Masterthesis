"""FastAPI layer — the only thing the Next.js frontend talks to.

Run locally:  uvicorn api.main:app --reload --port 8000
The frontend on Vercel calls these endpoints; the heavy compute stays in Python.

This layer is pure transport + data plumbing. It selects WHICH data feeds the
engine (synthetic fixture or live Yahoo Finance, full universe or a chosen
subset) but never re-implements any of the statistical model.
"""
from __future__ import annotations
import time
from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from volcontrol import (
    EngineConfig, load_prices, simple_returns, fetch_prices_yf, fetch_rf_estr, fingerprint,
    run_strategies, metrics_table, crypto_sweep, hypothesis_tests,
    describe_assets, correlation_matrix, sample_window, asset_calendar_returns,
    ticker_map, universe_payload,
    time_series, subperiod_metrics, param_stability, cost_sensitivity,
    walk_forward, rolling_metrics, return_distribution, monthly_returns,
    build_workbook,
)
from volcontrol.backtest import portfolio_weights, _blended_cost_bps

app = FastAPI(title="Volatility-Control Treasury Engine", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DATA_PATH = "data/synthetic_prices.csv"   # synthetic fixture for the "synthetic" source
LIVE_TTL_SECONDS = 900                     # reuse a live pull for 15 min (data is daily)


class RunRequest(BaseModel):
    crypto_share: float = 0.10
    target_vol: float = 0.10
    base_currency: str = "EUR"
    rf_annual: float = 0.03
    # --- data selection (additive; defaults reproduce the original behaviour) ---
    assets: Optional[list[str]] = None     # canonical names to include; None = full universe
    source: str = "synthetic"              # "synthetic" | "live"
    years: int = 8                          # history length for the live pull
    # --- robustness levers ---
    vol_method: str = "rolling"            # "rolling" | "ewma"
    rebalance: str = "daily"               # "daily" | "weekly" | "monthly"
    dead_band: float = 0.0                 # exposure no-trade zone (e.g. 0.05)
    rf_mode: str = "manual"                # "manual" (rf_annual) | "estr" (ECB window mean)
    # --- optional custom base allocation (traditional sleeve, relative weights);
    #     None reproduces the documented 60/30/10 thesis base case ---
    trad_weights: Optional[dict[str, float]] = None
    # --- treasury risk limits (optional; negative thresholds, e.g. -0.25) ---
    mdd_limit: Optional[float] = None
    cvar_limit: Optional[float] = None


# ── Price sources ────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _synthetic_prices() -> pd.DataFrame:
    return load_prices(DATA_PATH)


# Live pulls are cached per (years, base_currency) for the full universe, so
# changing the asset subset or tuning sliders never triggers a refetch. The
# cache expires after LIVE_TTL_SECONDS; a fresh configurator run after that
# pulls current quotes again.
_live_cache: dict[tuple[int, str], tuple[float, pd.DataFrame]] = {}


def _live_prices(years: int, base_currency: str) -> pd.DataFrame:
    key = (years, base_currency.upper())
    hit = _live_cache.get(key)
    now = time.time()
    if hit and now - hit[0] < LIVE_TTL_SECONDS:
        return hit[1]
    prices = fetch_prices_yf(ticker_map(), years, base_currency)  # full universe
    _live_cache[key] = (now, prices)
    return prices


def _prices_raw(req: RunRequest) -> pd.DataFrame:
    """Native (un-aligned) price matrix for the selected assets and source."""
    try:
        prices = (
            _live_prices(req.years, req.base_currency)
            if req.source == "live"
            else _synthetic_prices()
        )
    except Exception as e:                                  # live fetch / network failure
        raise HTTPException(status_code=502, detail=f"Datenquelle nicht verfügbar: {e}")

    cols = [c for c in (req.assets or list(prices.columns)) if c in prices.columns]
    if not cols:
        raise HTTPException(status_code=400, detail="Keine gültigen Assets ausgewählt.")
    return prices[cols]


def _returns_for(req: RunRequest) -> pd.DataFrame:
    """Aligned daily-return matrix for the portfolio backtest.

    For live data we first restrict the PRICES to the common trading days
    (complete-case rows), then take returns — so each return is computed between
    consecutive shared trading days and no values are fabricated. Doing it the
    other way round would turn every post-weekend equity return into a NaN (its
    previous row would be an empty weekend), which is wrong. The synthetic fixture
    keeps its original NaN-tolerant behaviour so the reference numbers are unchanged.
    """
    prices = _prices_raw(req)
    if req.source == "live":
        rets = simple_returns(prices.dropna())   # align prices, then differentiate
    else:
        rets = simple_returns(prices)
    if rets.empty:
        raise HTTPException(status_code=422, detail="Kein gemeinsames Datenfenster für die Auswahl.")
    return rets


TRAD_ORDER = ("MSCI_World", "Global_Bonds", "Gold")

# €STR window means, cached per (start, end) — the ECB series is daily and static
# for past windows, so a long TTL is safe.
_estr_cache: dict[tuple[str, str], dict] = {}


def _resolve_rf(req: RunRequest, rets: pd.DataFrame) -> tuple[float, Optional[dict]]:
    """Effective risk-free rate: the manual constant, or the realised €STR mean
    over the sample window (ECB). Falls back to manual if the ECB is unreachable."""
    if req.rf_mode != "estr" or rets.empty:
        return req.rf_annual, None
    key = (str(rets.index.min().date()), str(rets.index.max().date()))
    info = _estr_cache.get(key)
    if info is None:
        try:
            info = fetch_rf_estr(*key)
            _estr_cache[key] = info
        except Exception:
            return req.rf_annual, {"error": "ECB nicht erreichbar — manueller Zins verwendet."}
    return info["mean_annual"], info


def _cfg(req: RunRequest, **overrides) -> EngineConfig:
    kw = dict(
        base_currency=req.base_currency, rf_annual=req.rf_annual,
        vol_method=req.vol_method, rebalance=req.rebalance, dead_band=req.dead_band,
    )
    # Optional custom base allocation — passed as relative weights (portfolio_weights
    # renormalises them). Only the three traditional sleeve assets are configurable.
    if req.trad_weights:
        tw = tuple((k, float(req.trad_weights[k])) for k in TRAD_ORDER
                   if k in req.trad_weights and req.trad_weights[k] > 0)
        if tw:
            kw["traditional_weights"] = tw
    kw.update(overrides)
    return EngineConfig(**kw)


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    r = simple_returns(_synthetic_prices())
    return {"status": "ok", "assets": list(r.columns), "observations": int(len(r))}


@app.get("/assets")
def assets():
    """The curated asset universe for the configurator's selection step."""
    return {"assets": universe_payload()}


def _limit_flags(table: list, req: RunRequest) -> list:
    """Attach treasury risk-limit breach flags (limits are negative thresholds)."""
    for row in table:
        row["mdd_breach"] = (
            req.mdd_limit is not None and row["max_drawdown"] < req.mdd_limit
        )
        row["cvar_breach"] = (
            req.cvar_limit is not None and row["cvar_95"] < req.cvar_limit
        )
    return table


def _prepared(req: RunRequest, **cfg_overrides):
    """Returns (returns_matrix, cfg, rf_info) with the risk-free rate resolved —
    the one place where rf_mode='estr' swaps the constant for the ECB window mean."""
    rets = _returns_for(req)
    rf_annual, rf_info = _resolve_rf(req, rets)
    cfg = _cfg(req, rf_annual=rf_annual, **cfg_overrides)
    return rets, cfg, rf_info


@app.post("/backtest")
def backtest(req: RunRequest):
    rets, cfg, rf_info = _prepared(req)
    run = run_strategies(rets, cfg, req.crypto_share)
    table = metrics_table(run).reset_index().to_dict(orient="records")
    table = _limit_flags(table, req)
    return {
        "crypto_share": req.crypto_share,
        "metrics": table,
        "limits": {"mdd_limit": req.mdd_limit, "cvar_limit": req.cvar_limit},
        "fingerprint": fingerprint(rets),
        "rf": {"mode": req.rf_mode, "effective_annual": cfg.rf_annual, "estr": rf_info},
    }


@app.post("/sweep")
def sweep(req: RunRequest):
    rets, cfg, _ = _prepared(req)
    df = crypto_sweep(rets, cfg, req.target_vol)
    return {"target_vol": req.target_vol, "points": df.round(5).to_dict(orient="records")}


@app.post("/hypotheses")
def hypotheses(req: RunRequest):
    rets, cfg, _ = _prepared(req, bootstrap_n=1200)   # smaller default for API latency (free-tier CPU)
    res = hypothesis_tests(rets, cfg, req.crypto_share, req.target_vol)
    res = {k: (v if k != "sweep" else v.round(5).to_dict(orient="records"))
           for k, v in res.items()}
    return res


@app.post("/timeseries")
def timeseries(req: RunRequest):
    """Wealth, drawdown and exposure paths for the charts."""
    rets, cfg, _ = _prepared(req)
    return time_series(rets, cfg, req.crypto_share, req.target_vol)


@app.post("/robustness")
def robustness(req: RunRequest):
    """Parameter-stability grid, cost sensitivity, regime breakdown, walk-forward OOS."""
    rets, cfg, _ = _prepared(req)
    return {
        "param_stability": param_stability(rets, cfg, req.crypto_share),
        "cost_sensitivity": cost_sensitivity(rets, cfg, req.crypto_share, req.target_vol),
        "subperiods": subperiod_metrics(rets, cfg, req.crypto_share, req.target_vol),
        "walk_forward": walk_forward(rets, cfg, req.crypto_share),
    }


@app.post("/dataset")
def dataset(req: RunRequest):
    """Frozen dataset export: the exact aligned price matrix the run used, as CSV,
    with the fingerprint hash in the filename — the citable data snapshot."""
    prices = _prices_raw(req)
    if req.source == "live":
        prices = prices.dropna()
    rets = _returns_for(req)
    fp = fingerprint(rets)
    csv = prices.to_csv(index_label="date")
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="treasury-dataset-{fp["hash"]}.csv"'},
    )


@app.post("/analytics")
def analytics(req: RunRequest):
    """Rolling Sharpe, return distribution and the monthly-returns calendar."""
    rets, cfg, _ = _prepared(req)
    return {
        "rolling": rolling_metrics(rets, cfg, req.crypto_share, req.target_vol),
        "distribution": return_distribution(rets, cfg, req.crypto_share, req.target_vol),
        "monthly": monthly_returns(rets, cfg, req.crypto_share, req.target_vol),
    }


@app.post("/workbook")
def workbook(req: RunRequest):
    """Transparency workbook (.xlsx): raw prices + every value as a live Excel
    formula, so the examiner can reproduce each number by hand."""
    rets, cfg, rf_info = _prepared(req)
    prices = _prices_raw(req)
    if req.source == "live":
        prices = prices.dropna()                 # aligned prices that rets came from

    run = run_strategies(rets, cfg, req.crypto_share)
    key = f"VolControl_{int(req.target_vol * 100)}"
    if key not in run["strategies"]:
        raise HTTPException(status_code=400, detail="Zielvolatilität nicht verfügbar.")
    exposure = run["strategies"][key]["exposure"]
    vc_ret = run["strategies"][key]["returns"]
    weights = portfolio_weights(req.crypto_share, list(rets.columns), cfg)

    stats = describe_assets(_prices_raw(req), cfg.rf_annual, cfg.cvar_alpha)
    hyp_cfg = EngineConfig(**{**cfg.__dict__, "bootstrap_n": 1200})
    extras = {
        "describe": stats.round(6).to_dict(orient="records"),
        "sweep": crypto_sweep(rets, cfg, req.target_vol).round(6).to_dict(orient="records"),
        "subperiods": subperiod_metrics(rets, cfg, req.crypto_share, req.target_vol),
        "walk_forward_folds": walk_forward(rets, cfg, req.crypto_share).get("folds", []),
        "hypotheses": {k: v for k, v in
                       hypothesis_tests(rets, hyp_cfg, req.crypto_share, req.target_vol).items()
                       if k != "sweep"},
    }
    tw = dict(cfg.traditional_weights)
    s = sum(tw.values()) or 1.0
    trad_split = {k: round(v / s, 4) for k, v in tw.items()}
    base = {"MSCI_World": 0.6, "Global_Bonds": 0.3, "Gold": 0.1}
    trad_is_base = all(abs(trad_split.get(k, 0.0) - base[k]) < 1e-6 for k in base)
    meta = {
        "crypto_share": req.crypto_share, "target_vol": req.target_vol,
        "base_currency": req.base_currency, "source": req.source,
        "cost_bps": _blended_cost_bps(req.crypto_share, cfg),
        "fingerprint": fingerprint(rets),
        "trad_split": trad_split, "trad_is_base": trad_is_base,
        "rf_mode": req.rf_mode, "rf_effective": cfg.rf_annual,
        "rf_estr": rf_info,
        "generated_at": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
    }
    xbytes = build_workbook(prices, rets, weights, exposure, vc_ret, cfg, meta, extras)
    return Response(
        content=xbytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="treasury-transparenz.xlsx"'},
    )


@app.post("/describe")
def describe(req: RunRequest):
    """Descriptive statistics for the selected universe + correlation + window.

    Per-asset stats use each asset's NATIVE calendar (so observation counts differ
    between crypto and equities). Correlation and the reported window use the
    ALIGNED complete-case sample, since correlation requires paired observations.
    """
    cfg = _cfg(req)
    native = _prices_raw(req)
    aligned = _returns_for(req)
    stats = describe_assets(native, cfg.rf_annual, cfg.cvar_alpha)
    return {
        "source": req.source,
        "base_currency": req.base_currency,
        "fetched_at": pd.Timestamp.utcnow().isoformat(),
        "window": sample_window(aligned),   # common (aligned) analysis window
        "assets": stats.round(6).to_dict(orient="records"),
        "correlation": correlation_matrix(aligned),
        "calendar": asset_calendar_returns(native),  # yearly + since-year per asset
    }
