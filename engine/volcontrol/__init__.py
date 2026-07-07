"""volcontrol — volatility-control backtest engine for the master's thesis."""
from .config import EngineConfig
from .data import load_prices, simple_returns, fetch_prices_yf, fetch_rf_estr, fingerprint
from . import metrics, strategies, stats, descriptive, universe, analysis
from .descriptive import describe_assets, correlation_matrix, sample_window, asset_calendar_returns
from .universe import UNIVERSE, ticker_map, universe_payload
from .analysis import (
    time_series, subperiod_metrics, param_stability, cost_sensitivity,
    walk_forward, rolling_metrics, return_distribution, monthly_returns,
    drawdown_table, rolling_correlation,
)
from .workbook import build_workbook
from .backtest import (
    run_strategies,
    metrics_table,
    crypto_sweep,
    hypothesis_tests,
    portfolio_weights,
)

__all__ = [
    "EngineConfig",
    "load_prices",
    "simple_returns",
    "fetch_prices_yf",
    "fetch_rf_estr",
    "fingerprint",
    "metrics",
    "strategies",
    "stats",
    "descriptive",
    "universe",
    "analysis",
    "describe_assets",
    "correlation_matrix",
    "sample_window",
    "asset_calendar_returns",
    "UNIVERSE",
    "ticker_map",
    "universe_payload",
    "time_series",
    "subperiod_metrics",
    "param_stability",
    "cost_sensitivity",
    "walk_forward",
    "rolling_metrics",
    "return_distribution",
    "monthly_returns",
    "drawdown_table",
    "rolling_correlation",
    "build_workbook",
    "run_strategies",
    "metrics_table",
    "crypto_sweep",
    "hypothesis_tests",
    "portfolio_weights",
]
__version__ = "0.1.0"
