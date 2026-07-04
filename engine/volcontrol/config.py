"""Central configuration for the volatility-control backtest engine.

All thesis-relevant assumptions live here so that the tool and the written
thesis can be driven from one identical parameter set (reproducibility).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class EngineConfig:
    # --- strategy parameters ---
    target_vols: Tuple[float, ...] = (0.05, 0.10, 0.15)   # annualised vol targets
    lookback: int = 60                                     # rolling window (trading days)
    trading_days: int = 252
    max_leverage: float = 1.0                              # exposure cap (no leverage)

    # --- volatility estimator & rebalancing (robustness levers) ---
    vol_method: str = "rolling"                            # "rolling" | "ewma"
    ewma_halflife: int = 20                                # half-life for the EWMA estimator
    rebalance: str = "daily"                               # "daily" | "weekly" | "monthly"
    dead_band: float = 0.0                                 # exposure no-trade zone (0 = off)

    # --- market / cost assumptions ---
    rf_annual: float = 0.03                                # risk-free p.a. (3M-EURIBOR proxy)
    base_currency: str = "EUR"                             # "EUR" matches thesis, "USD" for demo
    cost_traditional_bps: float = 10.0                     # transaction cost, traditional assets
    cost_crypto_bps: float = 25.0                          # transaction cost, crypto

    # --- risk metric / inference ---
    cvar_alpha: float = 0.05                               # CVaR / ES tail level (95%)
    bootstrap_n: int = 10_000
    expected_block: int = 20                               # stationary block-bootstrap mean length
    seed: int = 42
    n_trials: int = 9                                      # configs tried, for the Deflated Sharpe

    # --- named sub-periods / regimes (for regime analysis) ---
    subperiods: Tuple[Tuple[str, str, str], ...] = (
        ("Vor-COVID", "2015-01-01", "2020-02-19"),
        ("COVID-Crash", "2020-02-20", "2020-04-30"),
        ("Erholung/Bull", "2020-05-01", "2021-11-10"),
        ("Krypto-Winter/Zinswende", "2021-11-11", "2022-12-31"),
        ("Post-2022", "2023-01-01", "2100-01-01"),
    )

    # --- asset universe ---
    traditional: Tuple[str, ...] = ("MSCI_World", "Global_Bonds", "Gold")
    crypto: Tuple[str, ...] = ("Bitcoin", "Ethereum", "XRP", "BNB", "Solana")

    # institutional-typical split *within* the traditional sleeve
    traditional_weights: Tuple[Tuple[str, float], ...] = (
        ("MSCI_World", 0.60),
        ("Global_Bonds", 0.30),
        ("Gold", 0.10),
    )

    @property
    def rf_daily(self) -> float:
        return self.rf_annual / self.trading_days
