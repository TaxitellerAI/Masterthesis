"""The frozen archive must exist, be complete, and still hold the cited numbers.

`scripts/freeze_run.py --verify` recomputes everything and is the authoritative check
(~42 s). This test is the cheap guard that runs with every suite: it only reads the
archive and asserts the values the thesis actually quotes, so an archive that was
never regenerated after an engine change cannot ship unnoticed.

Run:  python tests/test_freeze_archive.py
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ARCHIVE = os.path.join(os.path.dirname(__file__), "..", "results", "freeze")

RECORDS = ["S1", "S2", "S3", "S4_2018", "S4_2019", "S4_2020",
           "S4_2021", "S4_2022", "S1_rf3"]

# The S1 figures the written thesis cites. Pinned literally: if the engine ever moves
# one of them, that has to be a deliberate decision with a new run and a change note,
# not something noticed after submission.
S1_REFERENCE = {
    "dataset_hash": "715caf81d0dd19d5",
    "run_hash": "f0129516a99f9c4a",
    "h1_bca": (0.036536, 0.202189),
    "h2_bca": (-0.158576, 0.340757),
    "h3_slope": 0.709898,
    "h3_ci": (0.383607, 0.965290),
    "dsr": 0.993942,
    "psr": 0.998373,
    "n_trials": 45,
    "argmax": 0.15,
    "indistinguishable": [0.0, 0.5],
    "n_return_days": 2010,
}
TOL = 5e-6


def _load(name: str) -> dict:
    p = os.path.join(ARCHIVE, f"{name}.json")
    assert os.path.exists(p), (
        f"Archiv-Record fehlt: {p}. Erzeugen mit: python scripts/freeze_run.py")
    with open(p) as f:
        return json.load(f)


def test_archive_is_complete():
    for name in RECORDS:
        r = _load(name)
        for block in ("backtest", "hypotheses", "sweep", "analytics",
                      "robustness", "describe"):
            assert block in r and r[block], f"{name}: Block '{block}' fehlt oder leer"
        for k in ("dataset_hash", "run_hash"):
            assert r["hashes"].get(k), f"{name}: {k} fehlt"
        env = r["environment"]
        for k in ("python", "numpy", "pandas", "scipy", "statsmodels"):
            assert env.get(k), f"{name}: Version '{k}' fehlt"
        assert r["git"].get("commit"), f"{name}: Git-Commit fehlt"
    print(f"ok  {len(RECORDS)} Records vollständig (Bloecke, Hashes, Umgebung, Commit)")


def test_archive_was_built_from_a_clean_tree():
    """A record built from uncommitted changes cannot be cited — the commit in it
    does not describe the code that produced the numbers."""
    dirty = [n for n in RECORDS if _load(n)["git"].get("dirty")]
    assert not dirty, (
        f"Aus unsauberem Arbeitsbaum erzeugt: {dirty}. Erst committen, "
        f"dann 'python scripts/freeze_run.py' erneut ausführen.")
    print("ok  Archiv stammt aus sauberem Arbeitsbaum "
          f"({_load('S1')['git']['describe']})")


def test_s1_reference_values_unchanged():
    r = _load("S1")
    h = r["hypotheses"]
    h1, h2 = h["H1_max_drawdown"], h["H2_sharpe"]
    sb = h["sweep_bootstrap"]
    md, am = sb["slopes"]["d_mdd"], sb["argmax"]
    ref = S1_REFERENCE

    assert r["hashes"]["dataset_hash"] == ref["dataset_hash"]
    assert r["hashes"]["run_hash"] == ref["run_hash"]
    assert r["backtest"]["sample"]["n_return_days"] == ref["n_return_days"]

    pairs = [
        ("H1 BCa unten", h1["ci_low_bca"], ref["h1_bca"][0]),
        ("H1 BCa oben", h1["ci_high_bca"], ref["h1_bca"][1]),
        ("H2 BCa unten", h2["ci_low_bca"], ref["h2_bca"][0]),
        ("H2 BCa oben", h2["ci_high_bca"], ref["h2_bca"][1]),
        ("H3 Steigung", md["slope"], ref["h3_slope"]),
        ("H3 KI unten", md["ci_low"], ref["h3_ci"][0]),
        ("H3 KI oben", md["ci_high"], ref["h3_ci"][1]),
        ("DSR", h["deflated_sharpe"]["dsr"], ref["dsr"]),
        ("PSR", h["probabilistic_sharpe"]["psr"], ref["psr"]),
        ("Argmax", am["best_share_point"], ref["argmax"]),
    ]
    for label, got, want in pairs:
        assert abs(got - want) < TOL, f"{label}: {got:.6f} statt {want:.6f}"
    assert h["deflated_sharpe"]["n_trials"] == ref["n_trials"]
    assert list(am["indistinguishable_range"]) == ref["indistinguishable"]
    print(f"ok  S1 hält alle {len(pairs) + 4} zitierten Referenzwerte")


def test_rf_sensitivity_pair_is_comparable():
    """S1 and S1_rf3 must differ in the rf mode and NOTHING else — otherwise the
    appendix comparison attributes to the interest rate what another change caused."""
    a, b = _load("S1"), _load("S1_rf3")
    assert a["hashes"]["dataset_hash"] == b["hashes"]["dataset_hash"], (
        "Unterschiedliche Datenbasis — der Vergleich misst dann nicht nur den Zins")
    assert a["hashes"]["run_hash"] != b["hashes"]["run_hash"], (
        "Gleicher Lauf-Hash trotz anderem Zinsmodus — der Fingerprint erfasst rf nicht")
    ra, rb = a["request"], b["request"]
    diff = {k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k)}
    # rf_annual is already 0.03 by default, so only the MODE actually flips — the
    # requirement is that nothing beyond the rf knobs differs, not that both differ.
    extra = diff - {"rf_mode", "rf_annual"}
    assert not extra, f"Zusätzliche Unterschiede neben dem Zins: {extra}"
    assert "rf_mode" in diff, "rf_mode identisch — die beiden Records sind derselbe Lauf"
    # The return series of a fully invested benchmark cannot depend on rf.
    A = {m["strategy"]: m for m in a["backtest"]["metrics"]}
    B = {m["strategy"]: m for m in b["backtest"]["metrics"]}
    assert abs(A["BuyHold"]["ann_return"] - B["BuyHold"]["ann_return"]) < 1e-9
    assert abs(A["BuyHold"]["max_drawdown"] - B["BuyHold"]["max_drawdown"]) < 1e-9
    # ... but its Sharpe MUST move, because rf is the benchmark in the numerator.
    assert abs(A["BuyHold"]["sharpe"] - B["BuyHold"]["sharpe"]) > 0.1, (
        "Buy-and-Hold-Sharpe unverändert — dann ginge rf nicht in den Sharpe ein")
    print(f"ok  rf-Paar sauber isoliert (nur rf_mode/rf_annual; BH-Rendite identisch, "
          f"BH-Sharpe {A['BuyHold']['sharpe']:.4f} -> {B['BuyHold']['sharpe']:.4f})")


if __name__ == "__main__":
    test_archive_is_complete()
    test_archive_was_built_from_a_clean_tree()
    test_s1_reference_values_unchanged()
    test_rf_sensitivity_pair_is_comparable()
