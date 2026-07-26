"""Data layer: load prices, compute simple returns.

We deliberately use *simple* returns for portfolio aggregation, because simple
returns are weight-additive (r_p = sum_i w_i * r_i) whereas log returns are not.
This is a correctness improvement over aggregating log returns directly.
"""
from __future__ import annotations
import logging
import pandas as pd

log = logging.getLogger(__name__)

# --- ECB SDMX series (verified against the live API before being hard-wired) ---
# €STR, the euro-area risk-free overnight benchmark, published from 2019-10-01.
ECB_ESTR_KEY = "EST/B.EU000A2X2A25.WT"
# EONIA, the pre-€STR overnight benchmark, published until its discontinuation
# on 2021-12-31. From 2019-10-01 the ECB recalibrated it to €STR + 8.5 bp, which
# we verified empirically: over the 579 overlapping observations the difference
# is exactly 0.085 pp on every single day (min = max = mean). Subtracting the
# spread therefore back-extends €STR *exactly*, not approximately.
ECB_EONIA_KEY = "EON/D.EONIA_TO.RATE"
EONIA_ESTR_SPREAD = 0.00085          # 8.5 basis points, official ECB transition spread
ESTR_FIRST_DAY = "2019-10-01"        # first €STR publication date


def load_prices(path: str, sheet: str = "Prices_EUR") -> pd.DataFrame:
    """Load a price matrix (index = date, columns = asset names)."""
    path = str(path)
    if path.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, sheet_name=sheet, index_col=0)
    else:
        df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns, weight-additive across assets."""
    return prices.pct_change().dropna(how="all")


def _ecb_series(flow_key: str, start: str, end: str) -> pd.Series:
    """One ECB SDMX series as a decimal-p.a. Series (the API quotes percent)."""
    import ssl
    import urllib.request
    import certifi

    url = (f"https://data-api.ecb.europa.eu/service/data/{flow_key}"
           f"?format=csvdata&startPeriod={start}&endPeriod={end}")
    ctx = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, timeout=60, context=ctx) as resp:
        df = pd.read_csv(resp)
    if df.empty or "OBS_VALUE" not in df.columns:
        raise ValueError(f"ECB lieferte keine Daten für {flow_key} in [{start}, {end}].")
    ser = pd.Series(pd.to_numeric(df["OBS_VALUE"], errors="coerce").values / 100.0,
                    index=pd.to_datetime(df["TIME_PERIOD"]))
    return ser.dropna().sort_index()


def fetch_rf_chained(start: str, end: str) -> tuple[pd.Series, dict]:
    """Chained DAILY euro risk-free rate over [start, end] — the honest cash leg.

    A single constant (e.g. 3 % p.a.) is not merely cosmetic for volatility
    targeting: `vol_control` remunerates the un-invested share with
    (1 - exposure) · rf. With exposure at 0.3–0.5 in stress periods, half the
    portfolio would earn a positive carry that, in reality (2018 – mid-2022), was
    NEGATIVE — flattering the strategy exactly where it is supposed to win.

    Construction:
        from 2019-10-01 : €STR                     (ECB, EST.B.EU000A2X2A25.WT)
        before          : EONIA − 8.5 bp           (ECB, EON.D.EONIA_TO.RATE)

    The 8.5 bp is the official ECB transition spread; over the overlap it holds
    exactly, so the splice introduces no level break.

    Returns (series in decimal p.a. on ECB business days, metadata dict).
    """
    estr = _ecb_series(ECB_ESTR_KEY, max(start, ESTR_FIRST_DAY), end) \
        if end >= ESTR_FIRST_DAY else pd.Series(dtype=float)

    eonia_end = min(end, str(pd.Timestamp(ESTR_FIRST_DAY) - pd.Timedelta(days=1))[:10])
    eonia = pd.Series(dtype=float)
    if start < ESTR_FIRST_DAY:
        raw = _ecb_series(ECB_EONIA_KEY, start, eonia_end)
        eonia = raw - EONIA_ESTR_SPREAD          # back-extend €STR exactly

    ser = pd.concat([eonia, estr]).sort_index()
    ser = ser[~ser.index.duplicated(keep="last")]
    if ser.empty:
        raise ValueError(f"Keine risikofreie Zinsreihe für [{start}, {end}] verfügbar.")

    meta = {
        "mode": "estr_chained",
        "source": "ECB SDMX · €STR (EST.B.EU000A2X2A25.WT) verkettet mit "
                  "EONIA−8,5bp (EON.D.EONIA_TO.RATE)",
        "splice_date": ESTR_FIRST_DAY,
        "spread_bps": EONIA_ESTR_SPREAD * 1e4,
        "eonia_observations": int(len(eonia)),
        "estr_observations": int(len(estr)),
        "observations": int(len(ser)),
        "first": str(ser.index.min().date()),
        "last": str(ser.index.max().date()),
        "mean_annual": float(ser.mean()),
        "min_annual": float(ser.min()),
        "max_annual": float(ser.max()),
        "share_negative": float((ser < 0).mean()),
    }
    return ser, meta


def load_rf_frozen(path: str) -> tuple[pd.Series, dict]:
    """Load the frozen chained rf series (see scripts/freeze_rf.py).

    Reproduction must not depend on the ECB API being reachable, so the committed
    snapshot — not a live fetch — is what the reported figures are built on.
    """
    df = pd.read_csv(path, index_col=0)
    ser = pd.Series(pd.to_numeric(df.iloc[:, 0], errors="coerce").values,
                    index=pd.to_datetime(df.index)).dropna().sort_index()
    if ser.empty:
        raise ValueError(f"Eingefrorene rf-Reihe ist leer: {path}")
    meta = {
        "mode": "estr_chained",
        "source": "eingefroren · ECB SDMX €STR verkettet mit EONIA−8,5bp",
        "splice_date": ESTR_FIRST_DAY,
        "spread_bps": EONIA_ESTR_SPREAD * 1e4,
        "observations": int(len(ser)),
        "first": str(ser.index.min().date()),
        "last": str(ser.index.max().date()),
        "mean_annual": float(ser.mean()),
        "min_annual": float(ser.min()),
        "max_annual": float(ser.max()),
        "share_negative": float((ser < 0).mean()),
        "frozen": True,
    }
    return ser, meta


def rf_daily_series(rf_annual, index: pd.DatetimeIndex,
                    convention: str = "act360", trading_days: int = 252) -> pd.Series:
    """Per-period risk-free accrual aligned to a return series' calendar.

    `rf_annual` may be a scalar (constant assumption) or a dated Series of
    annualised rates; the result is always a Series on `index`.

    Conventions
    -----------
    "act360"  (default) — the MARKET convention for €STR/EONIA: rates are quoted
        annualised on an actual/360 basis, so the accrual between two observation
        dates is rate · (actual calendar days) / 360. This is the only convention
        that charges a weekend correctly (3 days, not 1) and is what a treasury
        actually earns on cash. The rate used for a period is the one prevailing
        at its START (shifted by one observation) — no look-ahead.
    "simple_252" — legacy/comparison: rate / trading_days, matching the engine's
        original constant-rate behaviour. Kept so the constant-rate results stay
        exactly reproducible for the sensitivity analysis.

    Rates are forward-filled between ECB fixings (a money-market rate IS constant
    between fixings — this is not fabricated data). Gaps before the first / after
    the last fixing are back-/forward-filled and logged.
    """
    index = pd.DatetimeIndex(index)
    if isinstance(rf_annual, (int, float)):
        rates = pd.Series(float(rf_annual), index=index)
    else:
        src = pd.Series(rf_annual).sort_index()
        rates = src.reindex(src.index.union(index)).ffill().reindex(index)
        n_lead = int(rates.isna().sum())
        if n_lead:
            rates = rates.bfill()
            log.warning("rf-Reihe: %d Tage vor der ersten EZB-Feststellung "
                        "rückwärts gefüllt (Randfall).", n_lead)
        if index.max() > src.index.max():
            log.warning("rf-Reihe: Kalender reicht bis %s, letzte EZB-Feststellung "
                        "%s — Rest vorwärts gefüllt.",
                        index.max().date(), src.index.max().date())
    if rates.isna().any():
        raise ValueError("Risikofreie Zinsreihe konnte nicht vollständig belegt werden.")

    if convention == "simple_252":
        return rates / float(trading_days)

    # act/360 over the ACTUAL gap between consecutive observations
    days = pd.Series(index, index=index).diff().dt.days.astype("float64")
    if len(days) > 1:
        days.iloc[0] = float(days.iloc[1:].median())   # first period: typical gap
    else:
        days.iloc[0] = 1.0
    applied = rates.shift(1)                            # rate at period start
    applied.iloc[0] = rates.iloc[0]
    return applied * days / 360.0


def fetch_rf_estr(start: str, end: str) -> dict:
    """Realised euro short-term rate (€STR) over [start, end] from the official
    ECB SDMX API (series EST/B.EU000A2X2A25.WT, in % p.a.).

    Returns the window MEAN as an annualised decimal plus coverage metadata. The
    engine then uses this mean as rf_annual — replacing an arbitrary constant with
    the realised policy-rate level of the sample (documented simplification: the
    level effect is first-order; intra-window variation is second-order for the
    cash leg). €STR exists from 2019-10-01; earlier windows are partially covered.
    """
    import ssl
    import urllib.request
    import certifi

    url = ("https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT"
           f"?format=csvdata&startPeriod={start}&endPeriod={end}")
    ctx = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, timeout=30, context=ctx) as resp:
        df = pd.read_csv(resp)
    if df.empty or "OBS_VALUE" not in df.columns:
        raise ValueError("ECB lieferte keine €STR-Daten für dieses Fenster.")
    ser = pd.Series(df["OBS_VALUE"].values / 100.0,
                    index=pd.to_datetime(df["TIME_PERIOD"])).sort_index()
    return {
        "mean_annual": float(ser.mean()),
        "min_annual": float(ser.min()),
        "max_annual": float(ser.max()),
        "first": str(ser.index.min().date()),
        "last": str(ser.index.max().date()),
        "observations": int(len(ser)),
        "source": "ECB SDMX · EST.B.EU000A2X2A25.WT (€STR)",
    }


def stable_data_hash(returns: pd.DataFrame, decimals: int = 12) -> str:
    """Environment-STABLE content hash of a returns matrix.

    `fingerprint` hashes the raw float64 bytes, which makes it exact but also
    machine-dependent: the same data on macOS (Accelerate) and Linux (OpenBLAS)
    differs by up to one ULP after the reduction chain, and one differing bit
    changes the digest completely. Measured on this project: H1's observed
    difference came out as ...587 on the deployed host and ...598 locally.

    Rounding to `decimals` (1e-12) before hashing removes that last-bit noise while
    remaining far more precise than any real data change could ever be — a changed
    price moves returns by orders of magnitude more. This is what cache and
    precompute keys must use so a locally built artefact still matches in
    production. The reported/citable fingerprint stays byte-exact and unchanged.
    """
    import hashlib
    import numpy as np
    arr = np.ascontiguousarray(
        np.round(returns.fillna(0.0).to_numpy(dtype="float64"), decimals))
    arr = arr + 0.0                      # normalise -0.0 to 0.0
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def fingerprint(returns: pd.DataFrame, spec: dict | None = None) -> dict:
    """Deterministic content hash of a returns matrix — for reproducibility, so a
    report can be tied to the exact data that produced it.

    `spec` carries the run's defining choices (requested window bounds, data
    source, rf mode). They are hashed IN, so two runs that differ only in, say,
    the risk-free treatment can never collide on the same fingerprint.
    """
    import hashlib
    import numpy as np
    arr = np.ascontiguousarray(returns.fillna(0.0).to_numpy(dtype="float64"))
    h = hashlib.sha256()
    h.update(arr.tobytes())
    h.update(repr(sorted((spec or {}).items())).encode("utf-8"))
    idx = returns.dropna(how="all").index
    # Two clearly separated, ENVIRONMENT-STABLE identifiers plus the byte-exact one:
    #   dataset_hash — vouches for the DATA alone
    #   run_hash     — vouches for data AND configuration (scenario, window, rf mode …)
    #   hash_exact   — byte-exact, but machine-dependent (verified: the same data gives
    #                  ...587 on Linux/OpenBLAS and ...598 on macOS/Accelerate, which
    #                  changes the digest completely). Kept for traceability only; it
    #                  must never be the value a thesis cites.
    import hashlib as _hl
    d_hash = stable_data_hash(returns)
    r_hash = _hl.sha256(
        (d_hash + repr(sorted((spec or {}).items()))).encode("utf-8")
    ).hexdigest()[:16]
    out = {
        "hash": r_hash,               # primary, stable: the run hash
        "dataset_hash": d_hash,
        "run_hash": r_hash,
        "hash_exact": h.hexdigest()[:16],
        "rows": int(len(returns)),
        "columns": list(map(str, returns.columns)),
        "start": str(idx.min().date()) if len(idx) else None,
        "end": str(idx.max().date()) if len(idx) else None,
    }
    out.update(spec or {})
    return out


# Fixed study window. Eight FULL calendar years, and 2018 is the first year in
# which every default crypto asset (BTC, ETH, XRP) has a complete history — so the
# window is defensible on data grounds, not chosen to flatter a result.
STUDY_START = "2018-01-01"
STUDY_END = "2025-12-31"


def fetch_prices_yf(
    name_to_ticker: dict[str, str],
    start: str = STUDY_START,
    end: str = STUDY_END,
    base_currency: str = "EUR",
) -> pd.DataFrame:
    """Pull daily adjusted close prices from Yahoo Finance and return the SAME
    price-matrix shape the rest of the engine expects (DatetimeIndex × canonical
    asset-name columns).

    The window is given as EXPLICIT calendar bounds, never as a rolling
    `period="8y"`: a rolling window silently returns a different data set on every
    call, which would make the reported figures irreproducible.

    The prices are returned on their NATIVE calendar (the union of all tickers'
    trading days). Crypto therefore keeps its weekend rows and the ETFs are NaN on
    days they did not trade — we deliberately do NOT forward-fill, because filling
    an ETF's holidays would fabricate zero-return days and distort its statistics.
    Alignment for the portfolio backtest happens later, as an honest complete-case
    intersection (drop rows where any selected asset is missing).

    USD quotes are converted to the requested base currency via the EURUSD=X spot
    series (forward-filling the FX rate is fine — it is a continuous market).

    Network access is required; callers should handle exceptions.
    """
    import yfinance as yf

    # yfinance treats `end` as EXCLUSIVE, so ask for one day more and verify below
    # that the requested last trading day actually made it into the result.
    end_excl = str((pd.Timestamp(end) + pd.Timedelta(days=1)).date())

    tickers = list(name_to_ticker.values())
    raw = yf.download(
        tickers, start=start, end=end_excl, interval="1d",
        auto_adjust=True, progress=False, threads=True,
    )
    # yfinance returns a column MultiIndex for >1 ticker, flat for exactly one.
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if not isinstance(raw.columns, pd.MultiIndex):
        close.columns = [tickers[0]]

    inv = {t: n for n, t in name_to_ticker.items()}
    close = close.rename(columns=inv)
    cols = [n for n in name_to_ticker if n in close.columns]
    close = close[cols].sort_index()  # native calendar, NaNs kept — no forward fill

    if close.empty:
        raise ValueError("Yahoo Finance returned no data for the requested tickers.")

    # Guard the end-exclusive pitfall explicitly: if the requested final day is a
    # trading day it MUST be present, otherwise the window silently lost a day.
    want_end = pd.Timestamp(end)
    if close.index.max() < want_end - pd.Timedelta(days=4):
        raise ValueError(
            f"Datenfenster endet am {close.index.max().date()}, angefordert war {end} — "
            "Yahoo lieferte das Fensterende nicht (end ist exklusiv?).")
    log.info("Kursfenster %s..%s: %d Handelstage, letzter Kurs %s",
             start, end, len(close), close.index.max().date())

    # Currency conversion (Yahoo quotes the selected assets in USD).
    if base_currency.upper() == "EUR":
        fx = yf.download(
            "EURUSD=X", start=start, end=end_excl, interval="1d",
            auto_adjust=True, progress=False,
        )
        fx_close = fx["Close"]
        if isinstance(fx_close, pd.DataFrame):
            fx_close = fx_close.iloc[:, 0]
        fx_close = fx_close.reindex(close.index).ffill().bfill()  # USD per 1 EUR
        close = close.div(fx_close, axis=0)                       # USD price -> EUR price

    return close

