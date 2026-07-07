"""Asset universe: maps the engine's canonical asset names to Yahoo Finance
tickers. The canonical names MUST match EngineConfig.traditional_weights and
EngineConfig.crypto so the existing portfolio-weighting logic keeps working
unchanged when a subset of assets is selected.

This module is pure metadata + a fetch helper signature; it adds NOTHING to the
statistical core (strategies / metrics / stats / backtest stay untouched).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Asset:
    name: str          # canonical engine name (column key)
    ticker: str        # Yahoo Finance symbol
    label: str         # human label for the UI
    asset_class: str   # "equity" | "bond" | "commodity" | "crypto"
    default: bool      # pre-selected in the configurator


# Order matters for display. Tickers are USD-denominated; the data layer
# converts to the requested base currency via EURUSD=X.
UNIVERSE: tuple[Asset, ...] = (
    Asset("MSCI_World", "URTH", "MSCI World (URTH)", "equity", True),
    Asset("Global_Bonds", "BNDX", "Global Bonds (BNDX)", "bond", True),
    Asset("Gold", "GLD", "Gold (GLD)", "commodity", True),
    Asset("Bitcoin", "BTC-USD", "Bitcoin (BTC)", "crypto", True),
    Asset("Ethereum", "ETH-USD", "Ethereum (ETH)", "crypto", True),
    Asset("XRP", "XRP-USD", "XRP", "crypto", True),
    Asset("BNB", "BNB-USD", "BNB", "crypto", False),
    Asset("Solana", "SOL-USD", "Solana (SOL)", "crypto", False),
)

_BY_NAME = {a.name: a for a in UNIVERSE}


def ticker_map(names: Optional[list[str]] = None) -> dict[str, str]:
    """canonical name -> ticker, restricted to `names` (or the full universe)."""
    sel = names or [a.name for a in UNIVERSE]
    return {n: _BY_NAME[n].ticker for n in sel if n in _BY_NAME}


def universe_payload() -> list[dict]:
    """Serializable universe description for the frontend's asset selector."""
    return [
        {
            "name": a.name,
            "ticker": a.ticker,
            "label": a.label,
            "asset_class": a.asset_class,
            "default": a.default,
        }
        for a in UNIVERSE
    ]
