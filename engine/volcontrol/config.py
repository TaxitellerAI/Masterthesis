"""Central configuration for the volatility-control backtest engine.

All thesis-relevant assumptions live here so that the tool and the written
thesis can be driven from one identical parameter set (reproducibility).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple


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
    rebalance: str = "daily"                               # EXPOSURE grid of vol-control
    # Rebalancing grid of the BASE WEIGHTS — a separate decision from the exposure
    # grid above. Primary specification is monthly: daily constant-mix would charge
    # the comparison benchmark for behaviour no treasury exhibits. "daily" and the
    # true-BH drift remain available as edge cases.
    weight_rebalance: str = "monthly"                      # "daily" | "monthly" | "quarterly"
    dead_band: float = 0.0                                 # exposure no-trade zone (0 = off)

    # --- market / cost assumptions ---
    # The risk-free rate is NOT a cosmetic input here: vol_control remunerates the
    # un-invested share with (1 - exposure) * rf. Default is the realised, chained
    # daily €STR/EONIA series (see data.fetch_rf_chained); rf_annual survives as the
    # constant fallback for the sensitivity analysis ("what if we had assumed 3 %").
    rf_mode: str = "estr_chained"                          # "estr_chained" | "constant"
    rf_annual: float = 0.03                                # constant fallback, p.a.
    rf_convention: str = "act360"                          # "act360" (market) | "simple_252"
    # Realised annualised rf series (DatetimeIndex). Injected by the data layer;
    # compare=False so two configs stay comparable and hashable-by-value elsewhere.
    rf_series: Optional[object] = field(default=None, compare=False, repr=False)
    base_currency: str = "EUR"                             # "EUR" matches thesis, "USD" for demo
    cost_traditional_bps: float = 10.0                     # transaction cost, traditional assets
    cost_crypto_bps: float = 25.0                          # transaction cost, crypto

    # --- risk metric / inference ---
    cvar_alpha: float = 0.05                               # CVaR / ES tail level (95%)
    bootstrap_n: int = 10_000
    expected_block: int = 20                               # stationary block-bootstrap mean length
    seed: int = 42

    # --- the search space the study ACTUALLY explores -----------------------
    # The Deflated Sharpe must deflate by the number of configurations that were
    # really tried, not by the handful that end up in the metrics table. These
    # grids are the single source of truth for the sweep, the stability exhibit
    # AND the DSR trial set — so the three can never disagree.
    # (The former `n_trials = 9` constant was unused dead weight and is gone.)
    stability_lookbacks: Tuple[int, ...] = (20, 40, 60, 90, 120)
    stability_target_vols: Tuple[float, ...] = (0.05, 0.075, 0.10, 0.125, 0.15)
    sweep_max_share: float = 0.50
    sweep_step: float = 0.025

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
        """Constant per-day risk-free rate (fallback / legacy scalar path)."""
        return self.rf_annual / self.trading_days

    def rf_for(self, index):
        """Per-period risk-free accrual aligned to a specific return series.

        Returns a numpy array when a realised rf series is configured, otherwise
        the constant scalar — so every metric and strategy consumes the SAME rate
        definition without any call site having to know which mode is active.
        """
        if self.rf_mode != "estr_chained" or self.rf_series is None:
            return self.rf_daily
        from .data import rf_daily_series
        return rf_daily_series(
            self.rf_series, index, self.rf_convention, self.trading_days
        ).to_numpy()
