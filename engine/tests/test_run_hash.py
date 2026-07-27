"""The run hash must distinguish every configuration that moves a number.

It is the reproducibility anchor the thesis appendix cites. Before this was fixed,
`_run_spec` hashed only source, window, rf mode, currency, scenario and sleeve mode —
so S1 and three records with 0 %, 25 % and 50 % crypto all reported
f0129516a99f9c4a. Four different portfolios behind one identifier that claims to
vouch for the configuration is worse than no identifier at all: it invites the reader
to conclude the numbers were copied.

The dataset hash must NOT move for any of these — it vouches for the price data
alone, and that separation is the point of having two anchors.

Run:  python tests/test_run_hash.py
"""
from __future__ import annotations
import dataclasses
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.main import RunRequest, _run_spec, _prepared, _spec_with_effective, _sample_for
from volcontrol import EngineConfig, fingerprint


def _hashes(**overrides) -> tuple[str, str]:
    req = RunRequest(**overrides)
    scoped, _spec, report = _sample_for(req)
    rets = scoped if scoped is not None else _prepared(req)[0]
    fp = fingerprint(rets, _spec_with_effective(req, report))
    return fp["dataset_hash"], fp["run_hash"]


def _assert_distinct(label: str, variants: list[dict]) -> None:
    ds, rh = zip(*(_hashes(**v) for v in variants))
    assert len(set(rh)) == len(variants), (
        f"{label}: nur {len(set(rh))} von {len(variants)} Lauf-Hashes verschieden "
        f"-> {rh}")
    assert len(set(ds)) == 1, (
        f"{label}: der Datensatz-Hash hat sich mitbewegt {set(ds)} — er darf nur für "
        f"die Kursdaten bürgen, nicht für die Konfiguration")
    print(f"ok  {label}: {len(variants)} Varianten, {len(set(rh))} verschiedene "
          f"Lauf-Hashes, Datensatz-Hash unverändert ({ds[0]})")


def test_crypto_share_changes_run_hash():
    """The defect that triggered the fix."""
    _assert_distinct("crypto_share", [{"scenario": "S1", "crypto_share": s}
                                      for s in (0.0, 0.10, 0.25, 0.50)])


def test_target_vol_changes_run_hash():
    _assert_distinct("target_vol", [{"scenario": "S1", "target_vol": v}
                                    for v in (0.05, 0.10, 0.15)])


def test_traditional_weights_change_run_hash():
    """A different split inside the traditional sleeve is a different portfolio."""
    _assert_distinct("trad_weights", [
        {"scenario": "S1"},
        {"scenario": "S1", "trad_weights": {"MSCI_World": 0.5, "Global_Bonds": 0.4,
                                            "Gold": 0.1}},
        {"scenario": "S1", "trad_weights": {"MSCI_World": 0.7, "Global_Bonds": 0.2,
                                            "Gold": 0.1}},
    ])


def test_robustness_levers_change_run_hash():
    """Every lever the UI exposes must be visible in the hash."""
    _assert_distinct("vol_method", [{"scenario": "S1", "vol_method": m}
                                    for m in ("rolling", "ewma")])
    _assert_distinct("rebalance", [{"scenario": "S1", "rebalance": r}
                                   for r in ("daily", "weekly", "monthly")])
    _assert_distinct("dead_band", [{"scenario": "S1", "dead_band": d}
                                   for d in (0.0, 0.05, 0.10)])
    _assert_distinct("rf_mode", [{"scenario": "S1", "rf_mode": m}
                                 for m in ("estr_chained", "constant")])
    _assert_distinct("rf_annual (bei konstantem Zins)", [
        {"scenario": "S1", "rf_mode": "constant", "rf_annual": r}
        for r in (0.00, 0.03, 0.05)])
    _assert_distinct("Risikolimits", [
        {"scenario": "S1"},
        {"scenario": "S1", "mdd_limit": -0.25},
        {"scenario": "S1", "cvar_limit": -0.03},
    ])


def test_equal_configurations_share_a_hash():
    """Reproducibility cuts both ways: the same run must hash the same, and passing
    the base case explicitly must equal omitting it — otherwise a cited link could
    never be matched back to its report."""
    a = _hashes(scenario="S1")
    b = _hashes(scenario="S1", crypto_share=0.10, target_vol=0.10,
                trad_weights={"MSCI_World": 0.6, "Global_Bonds": 0.3, "Gold": 0.1})
    assert a == b, f"Basisfall explizit vs. implizit: {a} != {b}"
    assert _hashes(scenario="S1") == a, "Zwei identische Läufe, zwei Hashes"
    print(f"ok  identische Konfiguration -> identischer Lauf-Hash ({a[1]})")


def test_every_engine_config_field_is_covered():
    """The spec is enumerated from `dataclasses.fields`, not written out by hand.

    This asserts that contract: if someone adds a parameter to EngineConfig, it must
    appear in the spec automatically. A hand-maintained list would silently fall
    behind, which is exactly how the original gap arose.
    """
    spec = _run_spec(RunRequest(scenario="S1"))
    missing = [f.name for f in dataclasses.fields(EngineConfig)
               if f.compare and f"cfg_{f.name}" not in spec]
    assert not missing, f"Nicht im Lauf-Hash erfasst: {missing}"
    excluded = [f.name for f in dataclasses.fields(EngineConfig) if not f.compare]
    assert excluded == ["rf_series"], (
        f"Unerwartet vom Vergleich ausgenommen: {excluded} — bitte prüfen, ob das "
        f"Feld ergebnisrelevant ist")
    assert spec["rf_series_digest"].startswith("series:"), spec["rf_series_digest"]
    n = sum(1 for f in dataclasses.fields(EngineConfig) if f.compare)
    print(f"ok  alle {n} wertrelevanten EngineConfig-Felder im Spec, "
          f"rf-Reihe über Digest erfasst ({len(spec)} Schlüssel gesamt)")


def test_rf_file_swap_would_be_detected():
    """A changed frozen rf file must move the run hash — it moves every vol-control
    number, and the dataset hash covers prices only."""
    from api.main import _rf_series_digest, _frozen_rf
    import numpy as np
    import pandas as pd
    real = _rf_series_digest(RunRequest(scenario="S1"))
    ser, meta = _frozen_rf()
    tampered = pd.Series(ser.to_numpy() + 1e-4, index=ser.index)
    _frozen_rf.cache_clear()
    import api.main as M
    orig = M._frozen_rf
    M._frozen_rf = lambda: (tampered, meta)
    try:
        after = M._rf_series_digest(RunRequest(scenario="S1"))
    finally:
        M._frozen_rf = orig
        _frozen_rf.cache_clear()
    assert real != after, "Geänderte rf-Reihe ändert den Digest nicht"
    assert real == _rf_series_digest(RunRequest(scenario="S1")), "Digest nicht stabil"
    print(f"ok  veränderte rf-Reihe verschiebt den Digest ({real} -> {after})")


if __name__ == "__main__":
    test_crypto_share_changes_run_hash()
    test_target_vol_changes_run_hash()
    test_traditional_weights_change_run_hash()
    test_robustness_levers_change_run_hash()
    test_equal_configurations_share_a_hash()
    test_every_engine_config_field_is_covered()
    test_rf_file_swap_would_be_detected()
