"""Data layer: load prices, compute simple returns.

We deliberately use *simple* returns for portfolio aggregation, because simple
returns are weight-additive (r_p = sum_i w_i * r_i) whereas log returns are not.
This is a correctness improvement over aggregating log returns directly.
"""
from __future__ import annotations
import pandas as pd


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


def fingerprint(returns: pd.DataFrame) -> dict:
    """Deterministic content hash of a returns matrix — for reproducibility, so a
    report can be tied to the exact data that produced it."""
    import hashlib
    import numpy as np
    arr = np.ascontiguousarray(returns.fillna(0.0).to_numpy(dtype="float64"))
    digest = hashlib.sha256(arr.tobytes()).hexdigest()[:16]
    idx = returns.dropna(how="all").index
    return {
        "hash": digest,
        "rows": int(len(returns)),
        "columns": list(map(str, returns.columns)),
        "start": str(idx.min().date()) if len(idx) else None,
        "end": str(idx.max().date()) if len(idx) else None,
    }


def fetch_prices_yf(
    name_to_ticker: dict[str, str],
    years: int = 8,
    base_currency: str = "EUR",
) -> pd.DataFrame:
    """Pull daily adjusted close prices from Yahoo Finance and return the SAME
    price-matrix shape the rest of the engine expects (DatetimeIndex × canonical
    asset-name columns).

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

    tickers = list(name_to_ticker.values())
    raw = yf.download(
        tickers, period=f"{years}y", interval="1d",
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

    # Currency conversion (Yahoo quotes the selected assets in USD).
    if base_currency.upper() == "EUR":
        fx = yf.download(
            "EURUSD=X", period=f"{years}y", interval="1d",
            auto_adjust=True, progress=False,
        )
        fx_close = fx["Close"]
        if isinstance(fx_close, pd.DataFrame):
            fx_close = fx_close.iloc[:, 0]
        fx_close = fx_close.reindex(close.index).ffill().bfill()  # USD per 1 EUR
        close = close.div(fx_close, axis=0)                       # USD price -> EUR price

    return close

