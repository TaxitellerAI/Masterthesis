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
    EngineConfig, load_prices, simple_returns, fetch_prices_yf, fingerprint,
    load_rf_frozen, rf_daily_series, STUDY_START, STUDY_END, stable_data_hash,
    run_strategies, metrics_table, crypto_sweep, hypothesis_tests,
    describe_assets, correlation_matrix, sample_window, asset_calendar_returns,
    ticker_map, universe_payload,
    time_series, subperiod_metrics, param_stability, cost_sensitivity,
    walk_forward, rolling_metrics, return_distribution, monthly_returns,
    drawdown_table, rolling_correlation,
    build_workbook,
)
from volcontrol.backtest import portfolio_weights, _blended_cost_bps
from volcontrol import sample as sm
from volcontrol import sweepboot as sm_sweepboot

app = FastAPI(title="Volatility-Control Treasury Engine", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DATA_PATH = "data/synthetic_prices.csv"       # internal fixture (tests + /health only)
FROZEN_PATH = "data/frozen_prices_eur.csv"    # frozen real-market snapshot (EUR), reproducible
FROZEN_RF_PATH = "data/frozen_rf_eur.csv"     # frozen chained €STR/EONIA series
LIVE_TTL_SECONDS = 900         # reuse a live pull for 15 min (data is daily)
SWEEP_BOOT_N = 1000           # data-level H3/TF4 replicates; ~7 s. Do NOT reduce.
API_BOOTSTRAP_N = 1200        # paired-bootstrap replicates served by the API


class RunRequest(BaseModel):
    crypto_share: float = 0.10
    target_vol: float = 0.10
    base_currency: str = "EUR"
    rf_annual: float = 0.03
    # --- data selection (additive; defaults reproduce the original behaviour) ---
    assets: Optional[list[str]] = None     # canonical names to include; None = full universe
    source: str = "frozen"                 # "frozen" (default, reproducible) | "live" | "synthetic"
    # Explicit calendar window — NOT a rolling "last N years", which would return a
    # different data set on every call and make the reported figures irreproducible.
    start: str = STUDY_START
    end: str = STUDY_END
    # Named sample design (volcontrol/sample.py). "custom" keeps the explicit
    # assets/start/end selection; S1..S3 and S4_<year> drive window, crypto members
    # and sleeve mode from the spec instead.
    scenario: str = "S1"          # Hauptspezifikation; "custom" = assets/start/end selbst wählen
    # --- robustness levers ---
    vol_method: str = "rolling"            # "rolling" | "ewma"
    rebalance: str = "daily"               # "daily" | "weekly" | "monthly"
    dead_band: float = 0.0                 # exposure no-trade zone (e.g. 0.05)
    # "estr_chained" = realised daily €STR/EONIA series (default);
    # "constant" = the flat rf_annual assumption, kept for the sensitivity analysis.
    rf_mode: str = "estr_chained"
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


@lru_cache(maxsize=1)
def _frozen_prices() -> pd.DataFrame:
    """Frozen real-market EUR snapshot committed to the repo — reproducible, does
    not drift with live Yahoo Finance, so the reported thesis figures are stable."""
    return load_prices(FROZEN_PATH)


# Live pulls are cached per (years, base_currency) for the full universe, so
# changing the asset subset or tuning sliders never triggers a refetch. The
# cache expires after LIVE_TTL_SECONDS; a fresh configurator run after that
# pulls current quotes again.
_live_cache: dict[tuple[str, str, str], tuple[float, pd.DataFrame]] = {}


def _live_prices(start: str, end: str, base_currency: str) -> pd.DataFrame:
    key = (start, end, base_currency.upper())
    hit = _live_cache.get(key)
    now = time.time()
    if hit and now - hit[0] < LIVE_TTL_SECONDS:
        return hit[1]
    prices = fetch_prices_yf(ticker_map(), start, end, base_currency)  # full universe
    _live_cache[key] = (now, prices)
    return prices


@lru_cache(maxsize=1)
def _frozen_rf() -> tuple:
    """Frozen chained risk-free series — so reproduction never depends on the ECB API."""
    ser, meta = load_rf_frozen(FROZEN_RF_PATH)
    return ser, meta


def _check_currency(req: RunRequest) -> None:
    """The frozen snapshot is EUR-only — refuse to label it anything else.

    Selecting USD against the frozen source used to change nothing in the data while
    the response still reported "USD". Three reports in this project have already
    said something other than what they were; a silently wrong label is not an
    option, so the combination is rejected with a reason instead.
    """
    if req.source == "frozen" and req.base_currency.upper() != "EUR":
        raise HTTPException(
            status_code=400,
            detail=("Der eingefrorene Datensatz liegt ausschließlich in EUR vor — eine "
                    "USD-Auswertung würde dieselben EUR-Kurse mit falschem Etikett "
                    "ausweisen. Für USD bitte die Live-Datenquelle wählen."),
        )


def _prices_raw(req: RunRequest) -> pd.DataFrame:
    """Native (un-aligned) price matrix for the selected assets and source."""
    _check_currency(req)
    try:
        if req.source == "live":
            prices = _live_prices(req.start, req.end, req.base_currency)
        elif req.source == "frozen":
            prices = _frozen_prices()
        else:
            prices = _synthetic_prices()
    except Exception as e:                                  # live fetch / network failure
        raise HTTPException(status_code=502, detail=f"Datenquelle nicht verfügbar: {e}")

    cols = [c for c in (req.assets or list(prices.columns)) if c in prices.columns]
    if not cols:
        raise HTTPException(status_code=400, detail="Keine gültigen Assets ausgewählt.")
    prices = prices[cols]
    if req.source in ("live", "frozen"):       # enforce the explicit study window
        prices = prices.loc[req.start:req.end]
        if prices.empty:
            raise HTTPException(status_code=422,
                                detail=f"Keine Kurse im Fenster {req.start}..{req.end}.")
    return prices


def _spec_for(req: RunRequest):
    """The active SampleSpec, or None when the request drives assets/window itself."""
    if not req.scenario or req.scenario == "custom":
        return None
    return sm.get_spec(req.scenario)


def _sample_for(req: RunRequest):
    """(returns, spec, report) for a named scenario — the scenario defines window,
    crypto members and sleeve mode, so it overrides assets/start/end."""
    spec = _spec_for(req)
    if spec is None:
        return None, None, None
    _check_currency(req)
    try:
        prices = _frozen_prices() if req.source != "live" else _live_prices(
            spec.start, spec.end, req.base_currency)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Datenquelle nicht verfügbar: {e}")
    kept, report = sm.resolve_sample(prices, spec)
    rets = simple_returns(kept)
    if rets.empty:
        raise HTTPException(status_code=422, detail=f"{spec.name}: leeres Sample.")
    return rets, spec, report


def _pit_builder_for(req: RunRequest, spec, cfg, columns):
    """Point-in-time weight builder, or None for a fixed basket."""
    if spec is None or not spec.is_pit:
        return None
    prices = _frozen_prices() if req.source != "live" else _live_prices(
        spec.start, spec.end, req.base_currency)
    return sm.make_pit_builder(spec, prices, cfg, columns)


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
    if req.source in ("live", "frozen"):
        rets = simple_returns(prices.dropna())   # align real prices, then differentiate
    else:
        rets = simple_returns(prices)
    if rets.empty:
        raise HTTPException(status_code=422, detail="Kein gemeinsames Datenfenster für die Auswahl.")
    return rets


TRAD_ORDER = ("MSCI_World", "Global_Bonds", "Gold")

def _rf_mode(req: RunRequest) -> str:
    """Normalise the mode, accepting the legacy names from older permalinks."""
    m = {"manual": "constant", "estr": "estr_chained"}.get(req.rf_mode, req.rf_mode)
    return m if m in ("constant", "estr_chained") else "estr_chained"


def _resolve_rf(req: RunRequest, rets: pd.DataFrame):
    """Return (effective_annual, rf_series | None, info).

    Default is the frozen chained €STR/EONIA DAILY series. A single constant is
    not merely cosmetic here: vol_control remunerates the un-invested share with
    (1 - exposure) * rf, and over this sample the realised rate was NEGATIVE on
    ~59 % of days — a flat +3 % would credit the strategy a carry it never earned,
    precisely in the stress periods where exposure is lowest.
    """
    if _rf_mode(req) == "constant" or rets.empty:
        return req.rf_annual, None, {"mode": "constant", "rf_annual": req.rf_annual}
    try:
        ser, meta = _frozen_rf()
    except Exception as e:
        return req.rf_annual, None, {"mode": "constant",
                                     "error": f"rf-Reihe nicht ladbar ({e}) — Konstante verwendet."}
    win = ser.reindex(ser.index.union(rets.index)).ffill().reindex(rets.index).bfill()
    info = dict(meta)
    info.update({
        "window_mean_annual": float(win.mean()),
        "window_min_annual": float(win.min()),
        "window_max_annual": float(win.max()),
        "window_share_negative": float((win < 0).mean()),
        "convention": "act360",
    })
    # cfg.rf_annual is used for the per-asset descriptive Sharpe; set it to the
    # realised window mean so that block is consistent with the backtest.
    return float(win.mean()), ser, info


def _cfg(req: RunRequest, **overrides) -> EngineConfig:
    kw = dict(
        base_currency=req.base_currency, rf_annual=req.rf_annual,
        vol_method=req.vol_method, rebalance=req.rebalance, dead_band=req.dead_band,
        rf_mode=_rf_mode(req),
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


@app.get("/artefact")
def artefact():
    """Health of the shipped inference artefact.

    If the engine changed since the artefact was built, the stored keys stop matching
    and every request silently falls back to the (in production impossible) live
    computation. This surfaces that instead of letting it rot unnoticed.
    """
    import json
    try:
        with open(PRECOMPUTED_PATH) as f:
            payload = json.load(f)
    except Exception as e:
        return {"ok": False, "reason": f"Artefakt nicht ladbar: {e}", "entries": []}

    rows = []
    for e in payload.get("entries", []):
        req = RunRequest(scenario=e["scenario"], crypto_share=e["crypto_share"],
                         target_vol=e["target_vol"])
        try:
            rets, cfg, *_ = _prepared(req, bootstrap_n=API_BOOTSTRAP_N)
            matches = _freeze(e["key"]) == _freeze(_analysis_key(req, rets, cfg))
        except Exception as ex:
            matches, cfg = False, None
        rows.append({"scenario": e["scenario"], "matches": bool(matches)})
    stale = [r["scenario"] for r in rows if not r["matches"]]
    return {
        "ok": not stale,
        "generated_at": payload.get("generated_at"),
        "entries": rows,
        "stale": stale,
        "reason": (None if not stale else
                   f"Artefakt veraltet für {', '.join(stale)} — Engine hat sich seit dem "
                   f"Erzeugen geändert. Neu erzeugen: python scripts/precompute_inference.py"),
    }


@app.get("/scenarios")
def scenarios():
    """Scenario catalogue for the configurator (single source of truth: sample.py)."""
    return {"scenarios": sm.scenario_payload()}


@app.get("/assets")
def assets():
    """The curated asset universe for the configurator's selection step."""
    return {"assets": universe_payload()}


def _json_safe(table: list) -> list:
    """NaN is not valid JSON. Strategies without a separate gross variant (vol-control,
    true buy-and-hold) legitimately have empty gross fields — emit them as null."""
    import math
    for row in table:
        for k, v in list(row.items()):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                row[k] = None
    return table


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


def _run_spec(req: RunRequest) -> dict:
    """The choices that DEFINE a run — hashed into the fingerprint so a citable
    result can never be confused with one from a different window or rf mode."""
    spec = _spec_for(req)
    out = {
        "source": req.source,
        "window_start": spec.start if spec else req.start,
        "window_end": spec.end if spec else req.end,
        "rf_mode": _rf_mode(req),
        "base_currency": req.base_currency.upper(),
        "scenario": spec.name if spec else "custom",
        "sleeve_mode": spec.sleeve_mode if spec else "fixed",
    }
    return out


def _spec_with_effective(req: RunRequest, report: Optional[dict]) -> dict:
    """Run spec for the fingerprint, enriched with the sample that actually resolved."""
    out = _run_spec(req)
    if report:
        out["effective_start"] = report["effective_start"]
        out["effective_end"] = report["effective_end"]
        out["n_rows"] = report["n_rows"]
    return out


def _prepared(req: RunRequest, **cfg_overrides):
    """Returns (returns_matrix, cfg, rf_info) with the risk-free rate resolved —
    the one place where the realised rf series replaces the flat constant."""
    scoped, spec, report = _sample_for(req)
    rets = scoped if scoped is not None else _returns_for(req)
    rf_annual, rf_series, rf_info = _resolve_rf(req, rets)
    cfg = _cfg(req, rf_annual=rf_annual, rf_series=rf_series, **cfg_overrides)
    pit = _pit_builder_for(req, spec, cfg, list(rets.columns))
    return rets, cfg, rf_info, spec, report, pit


@app.post("/backtest")
def backtest(req: RunRequest):
    rets, cfg, rf_info, spec, sample_report, pit = _prepared(req)
    run = run_strategies(rets, cfg, req.crypto_share, pit_builder=pit)
    table = metrics_table(run).reset_index().to_dict(orient="records")
    table = _limit_flags(_json_safe(table), req)
    return {
        "crypto_share": req.crypto_share,
        "metrics": table,
        "sample": sample_report,
        "sleeve": run.get("sleeve"),
        "limits": {"mdd_limit": req.mdd_limit, "cvar_limit": req.cvar_limit},
        "fingerprint": fingerprint(rets, _spec_with_effective(req, sample_report)),
        "rf": {"mode": _rf_mode(req), "effective_annual": cfg.rf_annual, "estr": rf_info},
    }


@app.post("/sweep")
def sweep(req: RunRequest):
    rets, cfg, _, spec, sample_report, pit = _prepared(req)
    df = crypto_sweep(rets, cfg, req.target_vol, pit_builder=pit)
    return {"target_vol": req.target_vol, "points": df.round(5).to_dict(orient="records")}


_sweepboot_cache: dict[tuple, dict] = {}
_CACHE_MAX = 24
PRECOMPUTED_PATH = "data/precomputed_inference.json"


def _freeze(v):
    """Make a JSON-decoded key hashable again (nested lists -> tuples).

    The stored key round-trips through JSON, which turns the nested weight tuples
    into lists; comparing without normalising would silently never match and every
    request would fall back to the (impossible) live computation.
    """
    if isinstance(v, (list, tuple)):
        return tuple(_freeze(x) for x in v)
    return v


@lru_cache(maxsize=1)
def _precomputed() -> dict:
    """Inference results shipped with the repo, keyed by the SAME analysis key the
    live path builds.

    Measured reality: /hypotheses needs 192 s on the deployed free tier while the
    Next.js route may wait 60 s — the live call can never complete there. The main
    specifications are therefore computed once (scripts/precompute_inference.py) and
    served instantly. Because the stored key includes the data hash and every
    result-relevant setting, ANY deviation falls through to the live computation;
    a stale or mismatched result cannot be served.
    """
    import json
    try:
        with open(PRECOMPUTED_PATH) as f:
            payload = json.load(f)
    except Exception:
        return {}
    return {_freeze(e["key"]): e["result"] for e in payload.get("entries", [])}


def _analysis_key(req: RunRequest, rets: pd.DataFrame, cfg: EngineConfig) -> tuple:
    """Cache key covering the DATA and EVERY setting that can move the numbers.

    A cache keyed on a subset would be worse than a slow endpoint: it could serve
    figures from a different target volatility or risk-free treatment. The data hash
    pins the sample; the rest pins the model. `crypto_share` is deliberately absent —
    the sweep bootstrap varies the share itself and does not read it (verified by the
    signature of sweep_bootstrap), so including it would only cause needless misses.
    """
    return (
        # Environment-STABLE hash: the byte-exact fingerprint differs by one ULP
        # between macOS and the Linux host, so a locally built precompute artefact
        # could never match in production. Verified: it never did.
        stable_data_hash(rets),
        req.scenario, req.source, req.start, req.end, req.base_currency,
        round(float(req.target_vol), 10),
        _rf_mode(req), round(float(cfg.rf_annual), 12), cfg.rf_convention,
        req.vol_method, req.rebalance, round(float(req.dead_band), 10),
        cfg.weight_rebalance, cfg.lookback, cfg.trading_days, cfg.max_leverage,
        cfg.ewma_halflife, cfg.cost_traditional_bps, cfg.cost_crypto_bps,
        cfg.cvar_alpha, cfg.expected_block, cfg.seed, cfg.bootstrap_n,
        cfg.sweep_max_share, cfg.sweep_step,
        # EFFECTIVE weights from the config, not the request shape: passing the base
        # case explicitly and omitting it are the SAME computation and must share a
        # key, otherwise a precomputed result could never be found.
        tuple(cfg.traditional_weights),
        sm_sweepboot.CRITERION_PRIMARY, SWEEP_BOOT_N,
    )


def _sweep_boot_cached(req: RunRequest, rets, cfg, sample_report) -> dict:
    """One shared, correctly keyed sweep-bootstrap result for ALL endpoints.

    /hypotheses used to recompute this even though /sweepbootstrap had just cached
    it — 6.9 s of the 8.9 s total, recomputed for nothing.
    """
    key = _analysis_key(req, rets, cfg)
    hit = _sweepboot_cache.get(key)
    if hit is None:
        t0 = time.time()
        hit = sm_sweepboot.sweep_bootstrap(rets, cfg, req.target_vol,
                                           n_boot=SWEEP_BOOT_N, seed=cfg.seed)
        hit["runtime_seconds"] = round(time.time() - t0, 2)
        hit["sample"] = sample_report
        if len(_sweepboot_cache) >= _CACHE_MAX:      # bounded, FIFO
            _sweepboot_cache.pop(next(iter(_sweepboot_cache)))
        _sweepboot_cache[key] = hit
    return hit


@app.post("/sweepbootstrap")
def sweepbootstrap(req: RunRequest):
    """H3/TF4 inference on the DATA level — bootstraps the whole sweep (B = 1000)."""
    rets, cfg, _, spec, sample_report, pit = _prepared(req)
    return _sweep_boot_cached(req, rets, cfg, sample_report)


def _precomputed_for(req: RunRequest, rets, cfg):
    """Shipped result for this EXACT configuration, or None."""
    return _precomputed().get(_freeze(_analysis_key(req, rets, cfg)))


# ── Asynchronous jobs ────────────────────────────────────────────────────────
# Measured: a cold /hypotheses on the deployed free tier takes 192–234 s while the
# calling route may wait 60 s. Worse, an aborted request leaves NOTHING cached
# (verified: abort after 8 s -> next full call still 234 s -> only the call after
# that hit the cache in 0,67 s), so every retry restarts from zero. No timeout
# tuning fixes that; the request has to stop being synchronous.
#
# A job therefore runs in a background thread and each HTTP call returns in
# milliseconds — no gateway limit is ever approached, and the result lands in the
# same cache the synchronous path uses.
_jobs: dict[str, dict] = {}
_JOBS_MAX = 12


def _job_key(req: RunRequest, rets, cfg) -> str:
    import hashlib
    return hashlib.sha256(repr(_analysis_key(req, rets, cfg)).encode()).hexdigest()[:16]


@app.post("/jobs/hypotheses")
def start_hypotheses_job(req: RunRequest):
    """Start (or join) an inference job. Returns immediately with a job id."""
    import threading
    rets, cfg, _, spec, sample_report, pit = _prepared(req, bootstrap_n=API_BOOTSTRAP_N)

    pre = _precomputed_for(req, rets, cfg)
    if pre is not None:                     # nothing to schedule — ship it
        return {"job_id": None, "status": "done", "result": {**pre, "precomputed": True}}

    jid = _job_key(req, rets, cfg)
    job = _jobs.get(jid)
    if job and job["status"] in ("running", "done"):
        return {"job_id": jid, "status": job["status"]}

    if len(_jobs) >= _JOBS_MAX:
        for k, v in list(_jobs.items()):
            if v["status"] != "running":
                _jobs.pop(k, None)

    _jobs[jid] = {"status": "running", "started": time.time(), "result": None, "error": None}

    def _work():
        try:
            sboot = _sweep_boot_cached(req, rets, cfg, sample_report)
            res = hypothesis_tests(rets, cfg, req.crypto_share, req.target_vol,
                                   pit_builder=pit, sweep_boot=sboot)
            res = {k: (v if k != "sweep" else v.round(5).to_dict(orient="records"))
                   for k, v in res.items()}
            _jobs[jid].update(status="done", result={**res, "precomputed": False},
                              seconds=round(time.time() - _jobs[jid]["started"], 1))
        except Exception as e:                            # noqa: BLE001 - surfaced to the client
            _jobs[jid].update(status="error", error=str(e))

    threading.Thread(target=_work, daemon=True).start()
    return {"job_id": jid, "status": "running"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    """Poll a job. Returns the result once it is done."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unbekannte Job-ID (Server neu gestartet?).")
    out = {"job_id": job_id, "status": job["status"],
           "elapsed": round(time.time() - job["started"], 1)}
    if job["status"] == "done":
        out["result"] = job["result"]
        out["seconds"] = job.get("seconds")
    elif job["status"] == "error":
        out["error"] = job["error"]
    return out


@app.post("/hypotheses")
def hypotheses(req: RunRequest):
    rets, cfg, _, spec, sample_report, pit = _prepared(req, bootstrap_n=API_BOOTSTRAP_N)

    # Shipped result for this EXACT configuration? Then serve it — the live path
    # cannot finish inside the route budget on the deployed host (192 s measured
    # against a 60 s limit). Any deviation misses the key and computes live.
    pre = _precomputed_for(req, rets, cfg)
    if pre is not None:
        return {**pre, "precomputed": True}

    sboot = _sweep_boot_cached(req, rets, cfg, sample_report)
    res = hypothesis_tests(rets, cfg, req.crypto_share, req.target_vol,
                           pit_builder=pit, sweep_boot=sboot)
    res = {k: (v if k != "sweep" else v.round(5).to_dict(orient="records"))
           for k, v in res.items()}
    return {**res, "precomputed": False}


@app.post("/timeseries")
def timeseries(req: RunRequest):
    """Wealth, drawdown and exposure paths for the charts."""
    rets, cfg, _, spec, sample_report, pit = _prepared(req)
    return time_series(rets, cfg, req.crypto_share, req.target_vol, pit_builder=pit)


@app.post("/robustness")
def robustness(req: RunRequest):
    """Parameter-stability grid, cost sensitivity, regime breakdown, walk-forward OOS."""
    rets, cfg, _, spec, sample_report, pit = _prepared(req)
    return {
        "param_stability": param_stability(rets, cfg, req.crypto_share, pit_builder=pit),
        "cost_sensitivity": cost_sensitivity(rets, cfg, req.crypto_share, req.target_vol,
                                             pit_builder=pit),
        "subperiods": subperiod_metrics(rets, cfg, req.crypto_share, req.target_vol,
                                        pit_builder=pit),
        "walk_forward": walk_forward(rets, cfg, req.crypto_share, pit_builder=pit),
    }


@app.post("/dataset")
def dataset(req: RunRequest):
    """Frozen dataset export: the exact aligned price matrix the run used, as CSV,
    with the fingerprint hash in the filename — the citable data snapshot."""
    prices = _prices_raw(req)
    if req.source in ("live", "frozen"):
        prices = prices.dropna()
    rets = _returns_for(req)
    fp = fingerprint(rets, _run_spec(req))
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
    rets, cfg, _, spec, sample_report, pit = _prepared(req)
    return {
        "rolling": rolling_metrics(rets, cfg, req.crypto_share, req.target_vol, pit_builder=pit),
        "distribution": return_distribution(rets, cfg, req.crypto_share, req.target_vol,
                                            pit_builder=pit),
        "monthly": monthly_returns(rets, cfg, req.crypto_share, req.target_vol, pit_builder=pit),
        "drawdowns": drawdown_table(rets, cfg, req.crypto_share, req.target_vol, pit_builder=pit),
        "correlation": rolling_correlation(rets, cfg),
    }


@app.post("/workbook")
def workbook(req: RunRequest):
    """Transparency workbook (.xlsx): raw prices + every value as a live Excel
    formula, so the examiner can reproduce each number by hand."""
    rets, cfg, rf_info, spec, sample_report, pit = _prepared(req)
    prices = _prices_raw(req)
    if req.source in ("live", "frozen"):
        prices = prices.dropna()                 # aligned prices that rets came from

    run = run_strategies(rets, cfg, req.crypto_share, pit_builder=pit)
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
        "sweep": crypto_sweep(rets, cfg, req.target_vol,
                              pit_builder=pit).round(6).to_dict(orient="records"),
        "subperiods": subperiod_metrics(rets, cfg, req.crypto_share, req.target_vol,
                                        pit_builder=pit),
        "walk_forward_folds": walk_forward(rets, cfg, req.crypto_share,
                                           pit_builder=pit).get("folds", []),
        "hypotheses": {k: v for k, v in
                       hypothesis_tests(rets, hyp_cfg, req.crypto_share, req.target_vol,
                                        pit_builder=pit).items()
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
        "fingerprint": fingerprint(rets, _run_spec(req)),
        "trad_split": trad_split, "trad_is_base": trad_is_base,
        "rf_mode": _rf_mode(req), "rf_effective": cfg.rf_annual,
        "rf_estr": rf_info,
        "window_start": req.start, "window_end": req.end,
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
    scoped, spec, report = _sample_for(req)
    aligned = scoped if scoped is not None else _returns_for(req)
    native = _prices_raw(req)

    # Chapter 4.1 must describe the SAME data the backtest analyses. The primary
    # block is therefore the ACTIVE sample window; the full native history is kept
    # but clearly labelled separately (it is useful for "since year X" questions).
    if spec is not None:
        try:
            full = _frozen_prices() if req.source != "live" else _live_prices(
                spec.start, spec.end, req.base_currency)
            cols = [c for c in report["assets"] if c in full.columns]
            native = full[cols]
        except Exception:
            pass
    win_prices = native.loc[aligned.index.min():aligned.index.max()]

    rf_annual, _rf_series, rf_info = _resolve_rf(req, aligned)
    cfg = _cfg(req, rf_annual=rf_annual)
    stats = describe_assets(win_prices, cfg.rf_annual, cfg.cvar_alpha)      # sample window
    stats_full = describe_assets(native, cfg.rf_annual, cfg.cvar_alpha)     # native history
    y0, y1 = aligned.index.min().year, aligned.index.max().year
    partial_years = sorted({y for y in (y0, y1)
                            if not (aligned.index.min() <= pd.Timestamp(f"{y}-01-05")
                                    and aligned.index.max() >= pd.Timestamp(f"{y}-12-25"))})
    return {
        "scope": {
            "basis": "sample_window",
            "start": str(aligned.index.min().date()),
            "end": str(aligned.index.max().date()),
            "observations": int(len(aligned)),
            "partial_years": partial_years,
            "sample_years": [int(y0), int(y1)],
            "n_price_rows": (report or {}).get("n_price_rows"),
            "n_return_days": int(len(aligned)),
            "note": ("Primärblock = aktives Sample-Fenster (identisch zum Backtest). "
                     "'assets_full' beschreibt die vollständige verfügbare Historie je Asset "
                     "und ist NICHT die Datenbasis der Ergebnisse."),
        },
        "assets_full": stats_full.round(6).to_dict(orient="records"),
        "kurtosis_convention": "excess",   # Normalverteilung = 0 (nicht 3)
        "source": req.source,
        "base_currency": req.base_currency,
        "fetched_at": pd.Timestamp.utcnow().isoformat(),
        "requested_window": {"start": req.start, "end": req.end},
        "rf": {"mode": _rf_mode(req), "effective_annual": cfg.rf_annual, "estr": rf_info},
        "fingerprint": fingerprint(aligned, _run_spec(req)),
        "window": sample_window(aligned),   # common (aligned) analysis window
        "assets": stats.round(6).to_dict(orient="records"),
        "correlation": correlation_matrix(aligned),
        "calendar": asset_calendar_returns(native),  # yearly + since-year per asset
    }
