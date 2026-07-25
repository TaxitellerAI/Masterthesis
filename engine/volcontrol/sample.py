"""Sample design: explicit, named scenarios instead of an implicit intersection.

Why this module exists
----------------------
The backtest aligns assets by complete-case intersection. That is correct for a
fixed basket, but it silently couples the SAMPLE to the UNIVERSE: adding Solana
(first observed 2020-04-10) cuts the common sample from 2011 to 1439 trading days
and deletes the entire pre-COVID period. Worse, a basket that is fixed over the
whole horizon implies a treasurer could have held SOL in 2018 — a backfill bias.

We therefore name the sample designs and report what each one actually resolves to:

    S1  Hauptspezifikation      2018-2025, fixed basket, BTC/ETH/XRP/BNB
    S2  Point-in-Time           2015-2025, sleeve grows as coins become investable
    S3  Voller Korb inkl. SOL   2021-2025, fixed basket, all five coins
    S4  Startdatums-Sensitivität S1 with rolling start years 2018..2022

IMPORTANT LIMITATION (read before citing "point-in-time")
---------------------------------------------------------
Entry dates are derived from the PRICE PANEL (`first_valid_index`), i.e. from DATA
AVAILABILITY, not from the true exchange listing date. For Solana the two roughly
coincide (2020-04-10). For Ethereum and XRP they do NOT: both traded years before
2017-11-09, which is merely when this Yahoo panel begins. S2 therefore removes the
backfill bias *with respect to the available data*, and its early sleeve reflects
the data vendor's coverage, not the full investable history. This must be stated
in the thesis; it is a data limitation, not a bug.

The coin SELECTION itself (today's large caps) remains ex-post and survivorship-
biased by construction. That is a limitation for the written text, not something
this module tries to repair.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

TRADITIONAL = ("MSCI_World", "Global_Bonds", "Gold")


@dataclass(frozen=True)
class SampleSpec:
    """One explicitly specified sample design."""
    name: str                                   # short key, e.g. "S1"
    label: str                                  # human label for the UI/thesis
    start: str                                  # requested window start (inclusive)
    end: str                                    # requested window end (inclusive)
    sleeve_mode: str                            # "fixed" | "point_in_time"
    crypto_members: tuple[str, ...]             # coins allowed in this design
    listing_buffer_days: int = 30               # TRADING days after first observation
    rationale: str = ""                         # why this design, in plain German

    @property
    def is_pit(self) -> bool:
        return self.sleeve_mode == "point_in_time"


S1 = SampleSpec(
    name="S1",
    label="Hauptspezifikation (2018–2025, fester Korb)",
    start="2018-01-01", end="2025-12-31",
    sleeve_mode="fixed",
    crypto_members=("Bitcoin", "Ethereum", "XRP", "BNB"),
    rationale=(
        "Alle vier Coins sind im Datenpanel ab 09.11.2017 verfügbar, der Korb ist über den "
        "gesamten Zeitraum konstant besetzt. Start Anfang 2018 — also im Bärenmarkt und "
        "bewusst NICHT am Blow-off-Top im Dezember 2017 — vermeidet einen günstigen "
        "Startpunkt-Bias. Das Fenster enthält Krypto-Winter 2018, COVID-Crash, Bullenmarkt "
        "2020/21, Zinswende 2022 und die Post-2022-Phase. Solana ist ausgeschlossen, weil es "
        "erst ab 2020-04-10 vorliegt und den gemeinsamen Stichprobenzeitraum sonst auf "
        "1.439 Handelstage verkürzen würde."
    ),
)

S2 = SampleSpec(
    name="S2",
    label="Point-in-Time (2015–2025, wachsender Sleeve)",
    start="2015-01-01", end="2025-12-31",
    sleeve_mode="point_in_time",
    crypto_members=("Bitcoin", "Ethereum", "XRP", "BNB", "Solana"),
    rationale=(
        "Der Krypto-Sleeve enthält zu jedem Zeitpunkt nur die dann bereits verfügbaren "
        "Coins; die Krypto-Quote bleibt konstant, die Zusammensetzung wächst. Das nutzt die "
        "volle Historie inklusive Vor-COVID und beseitigt den Backfill-Bias eines fixen "
        "Korbs. Einschränkung: Eintrittszeitpunkte stammen aus der Datenverfügbarkeit des "
        "Kurspanels, nicht aus dem echten Listing-Datum (ETH und XRP handelten real vor "
        "2017-11-09). In der Frühphase besteht der Sleeve nur aus Bitcoin."
    ),
)

S3 = SampleSpec(
    name="S3",
    label="Voller Korb inkl. SOL (2021–2025)",
    start="2021-01-01", end="2025-12-31",
    sleeve_mode="fixed",
    crypto_members=("Bitcoin", "Ethereum", "XRP", "BNB", "Solana"),
    rationale=(
        "Fester Korb mit allen fünf Coins über ein Fenster, in dem alle durchgehend "
        "verfügbar sind. Prüft, ob die Aussage von der Aufnahme Solanas abhängt — zum Preis "
        "eines deutlich kürzeren Zeitraums ohne Vor-COVID-Phase."
    ),
)

SCENARIOS: dict[str, SampleSpec] = {s.name: s for s in (S1, S2, S3)}


def start_date_sensitivity(years=(2018, 2019, 2020, 2021, 2022)) -> list[SampleSpec]:
    """S4 — S1 with a rolling start year, to show the result is not an artefact of
    one lucky entry point."""
    out = []
    for y in years:
        out.append(SampleSpec(
            name=f"S4_{y}",
            label=f"Startjahr {y} (Sensitivität)",
            start=f"{y}-01-01", end="2025-12-31",
            sleeve_mode=S1.sleeve_mode,
            crypto_members=S1.crypto_members,
            listing_buffer_days=S1.listing_buffer_days,
            rationale=f"Wie S1, aber Start {y}-01-01 — Sensitivität gegenüber dem Startdatum.",
        ))
    return out


def get_spec(name: Optional[str]) -> SampleSpec:
    """Look up a scenario by name; unknown/None falls back to the main spec."""
    if not name:
        return S1
    if name in SCENARIOS:
        return SCENARIOS[name]
    for s in start_date_sensitivity():
        if s.name == name:
            return s
    return S1


# ── entry dates & activity ───────────────────────────────────────────────────
def entry_dates(prices: pd.DataFrame, members, buffer_days: int = 30) -> dict:
    """First date each member may enter the sleeve.

    Data-driven: `first_valid_index` (NOT hard-wired), plus `buffer_days` TRADING
    days. The buffer excludes the post-listing price-discovery phase — thin, highly
    volatile and not investable for a treasury at size.

    NOTE the entry date reflects DATA AVAILABILITY in this panel, not the true
    exchange listing (see module docstring).
    """
    out = {}
    for c in members:
        if c not in prices.columns:
            continue
        fv = prices[c].first_valid_index()
        if fv is None:
            continue
        after = prices.index[prices.index >= fv]
        out[c] = after[buffer_days] if len(after) > buffer_days else None
    return {k: v for k, v in out.items() if v is not None}


def active_matrix(index: pd.DatetimeIndex, entries: dict, columns) -> pd.DataFrame:
    """Boolean (date x asset): is the asset part of the investable set on that day?

    Traditional assets are always active; a crypto asset is active from its entry
    date onward. Anything before the entry date is False — the no-look-ahead
    guarantee the PIT design rests on.
    """
    act = pd.DataFrame(False, index=index, columns=list(columns))
    for c in columns:
        if c in entries:
            act[c] = index >= entries[c]
        else:
            act[c] = True                      # traditional sleeve / no entry rule
    return act


def resolve_sample(prices: pd.DataFrame, spec: SampleSpec,
                   traditional=TRADITIONAL) -> tuple[pd.DataFrame, dict]:
    """Apply a spec to a price panel and report what it ACTUALLY resolved to.

    Returns (retained_prices, report). The report carries the effective first/last
    trading day, n, and how many rows were dropped and why — these numbers go into
    the thesis and must never be estimated.
    """
    cols = [c for c in list(traditional) + list(spec.crypto_members) if c in prices.columns]
    if not cols:
        raise ValueError(f"{spec.name}: keine der angeforderten Assets im Panel.")

    win = prices.loc[spec.start:spec.end, cols]
    n_window = len(win)
    entries = entry_dates(prices, spec.crypto_members, spec.listing_buffer_days) \
        if spec.is_pit else {}

    if spec.is_pit:
        act = active_matrix(win.index, entries, cols)
        # A row survives if every asset ACTIVE on that day has a price. A coin that
        # is not yet listed must never kill a row.
        missing_active = (act & win.isna()).any(axis=1)
        # Need the traditional sleeve plus at least one active crypto to form a portfolio.
        has_crypto = act[[c for c in cols if c in spec.crypto_members]].any(axis=1) \
            if any(c in spec.crypto_members for c in cols) else pd.Series(True, index=win.index)
        keep = (~missing_active) & has_crypto
        kept = win[keep]
        reason = ("Zeile verworfen, wenn ein zum Stichtag AKTIVES Asset fehlt "
                  "(noch nicht gelistete Coins verwerfen keine Zeile) oder noch kein "
                  "Krypto-Asset aktiv war.")
    else:
        kept = win.dropna()
        reason = "Complete-Case über den fest besetzten Korb (alle Assets müssen vorliegen)."

    if kept.empty:
        raise ValueError(f"{spec.name}: leeres Sample für {spec.start}..{spec.end}.")

    report = {
        "scenario": spec.name,
        "label": spec.label,
        "sleeve_mode": spec.sleeve_mode,
        "requested_start": spec.start,
        "requested_end": spec.end,
        "effective_start": str(kept.index.min().date()),
        "effective_end": str(kept.index.max().date()),
        "n_rows": int(len(kept)),
        "n_rows_in_window": int(n_window),
        "n_dropped": int(n_window - len(kept)),
        "drop_reason": reason,
        "assets": cols,
        "crypto_members": list(spec.crypto_members),
        "listing_buffer_days": spec.listing_buffer_days,
        "entry_dates": {k: str(v.date()) for k, v in sorted(entries.items())},
        "entry_date_basis": ("Datenverfügbarkeit im Kurspanel (first_valid_index) + Puffer — "
                             "NICHT das echte Börsen-Listing."),
        "rationale": spec.rationale,
    }
    return kept, report


# ── point-in-time weights ────────────────────────────────────────────────────
def pit_weight_matrix(returns_index: pd.DatetimeIndex, spec: SampleSpec, prices: pd.DataFrame,
                      crypto_share: float, traditional_weights, columns) -> pd.DataFrame:
    """Time-varying weight matrix (date x asset), rows summing to 1.

    The traditional sleeve keeps its institutional split scaled to (1 - crypto_share);
    `crypto_share` is spread equally over the coins ACTIVE on that day. Weights are
    shifted by one observation so the allocation used for day t's return was known
    at t-1 — the same no-look-ahead convention `vol_control` uses for exposure.
    """
    cols = list(columns)
    entries = entry_dates(prices, spec.crypto_members, spec.listing_buffer_days)
    cryptos = [c for c in cols if c in spec.crypto_members]
    trads = [c for c in cols if c not in spec.crypto_members]

    act = active_matrix(returns_index, entries, cols)
    W = pd.DataFrame(0.0, index=returns_index, columns=cols)

    tw = {k: v for k, v in dict(traditional_weights).items() if k in trads}
    tsum = sum(tw.values())
    if tsum > 0:
        for k, v in tw.items():
            W[k] = (v / tsum) * (1.0 - crypto_share)

    if cryptos:
        n_active = act[cryptos].sum(axis=1)
        for c in cryptos:
            W[c] = np.where(act[c] & (n_active > 0), crypto_share / n_active.replace(0, np.nan), 0.0)
        W[cryptos] = W[cryptos].fillna(0.0)
        # Days with no active coin: give the crypto budget back to the traditional sleeve
        # rather than holding an unexplained cash stub.
        none_active = n_active == 0
        if none_active.any() and tsum > 0:
            for k, v in tw.items():
                W.loc[none_active, k] = v / tsum

    W = W.shift(1)                      # allocation known at t-1
    if len(W) > 0:
        W.iloc[0] = W.iloc[1] if len(W) > 1 else 1.0 / len(cols)
    return W


def weighted_portfolio(returns: pd.DataFrame, W: pd.DataFrame) -> pd.Series:
    """Portfolio return from a TIME-VARYING weight matrix: r_p,t = Σ_i w_{i,t} r_{i,t}.

    Deliberately separate from `buy_and_hold`, which stays untouched so the static
    path cannot change behaviour.
    """
    cols = [c for c in W.columns if c in returns.columns]
    R = returns[cols].fillna(0.0)
    return (R * W[cols]).sum(axis=1)


def make_pit_builder(spec: SampleSpec, prices: pd.DataFrame, cfg, columns):
    """Factory the backtest calls to obtain (weights, cost, info) for a crypto share.

    Passing a builder — rather than a prebuilt matrix — lets `crypto_sweep` vary the
    share while the point-in-time composition logic stays in this module.
    """
    def build(crypto_share: float, index: pd.DatetimeIndex):
        W = pit_weight_matrix(index, spec, prices, crypto_share,
                              cfg.traditional_weights, columns)
        cost, info = sleeve_rebalance_cost(W, spec.crypto_members, cfg.cost_crypto_bps)
        return W, cost, info
    return build


def sleeve_rebalance_cost(W: pd.DataFrame, crypto_members, cost_crypto_bps: float
                          ) -> tuple[pd.Series, dict]:
    """Cost of re-spreading the crypto sleeve when its composition changes.

    A new coin entering is a REAL transaction: the existing positions are trimmed to
    make room. Charging it is what keeps the PIT design honest — otherwise the
    growing sleeve would look free.

    Returns (per-day cost series, summary with event count and cumulative cost).
    """
    cryptos = [c for c in W.columns if c in crypto_members]
    if not cryptos:
        return pd.Series(0.0, index=W.index), {"events": 0, "total_cost": 0.0, "dates": []}
    turnover = W[cryptos].diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * (cost_crypto_bps / 1e4)
    events = turnover[turnover > 1e-9]
    return cost, {
        "events": int(len(events)),
        "total_cost": float(cost.sum()),
        "total_turnover": float(turnover.sum()),
        "dates": [str(d.date()) for d in events.index[:20]],
    }
