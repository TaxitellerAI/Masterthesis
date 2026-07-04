"""Generate plausible synthetic daily prices so the engine runs without live data.

This is for development/testing ONLY. The real thesis numbers must come from the
documented yfinance dataset (data layer reads the same CSV/Excel format).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

ASSETS = {
    # name: (annual drift, annual vol, first_day_offset)
    "MSCI_World":   (0.08, 0.16, 0),
    "Global_Bonds": (0.02, 0.05, 0),
    "Gold":         (0.05, 0.13, 0),
    "Bitcoin":      (0.40, 0.75, 0),
    "Ethereum":     (0.45, 0.90, 400),
    "XRP":          (0.20, 1.00, 0),
    "BNB":          (0.50, 0.95, 900),
    "Solana":       (0.60, 1.10, 1600),
}


def make_synthetic_prices(n_days: int = 3000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2014-01-01", periods=n_days)

    # light common market factor so assets are correlated, crypto loads more
    market = rng.normal(0, 1, n_days)
    cols = {}
    for name, (mu, vol, offset) in ASSETS.items():
        beta = 0.9 if name in ("MSCI_World",) else (0.5 if vol < 0.2 else 0.3)
        idio = rng.normal(0, 1, n_days)
        daily_mu = mu / 252
        daily_vol = vol / np.sqrt(252)
        shock = beta * market + np.sqrt(max(1 - beta**2, 0)) * idio
        rets = daily_mu + daily_vol * shock
        price = 100 * np.exp(np.cumsum(rets))
        if offset > 0:                       # asset not yet listed -> NaN before launch
            price[:offset] = np.nan
        cols[name] = price
    return pd.DataFrame(cols, index=dates)


if __name__ == "__main__":
    df = make_synthetic_prices()
    out = "data/synthetic_prices.csv"
    df.to_csv(out)
    print(f"Wrote {out}: {df.shape[0]} days x {df.shape[1]} assets")
