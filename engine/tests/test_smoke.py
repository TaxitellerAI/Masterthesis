"""Smoke test: the full pipeline runs end-to-end on synthetic data and the
numbers are finite and internally consistent."""
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from volcontrol import EngineConfig, simple_returns, run_strategies, metrics_table, crypto_sweep, hypothesis_tests
from scripts.make_synthetic_data import make_synthetic_prices


def test_pipeline():
    prices = make_synthetic_prices(n_days=1500, seed=1)
    rets = simple_returns(prices)
    cfg = EngineConfig(bootstrap_n=300)

    run = run_strategies(rets, cfg, crypto_share=0.15)
    table = metrics_table(run)
    # BuyHold + one row per target vol, plus any available benchmarks
    assert table.shape[0] >= 1 + len(cfg.target_vols)
    assert {"BuyHold", "VolControl_5"}.issubset(set(table.index))
    assert np.isfinite(table.values).all()

    # vol-control should not have HIGHER realised vol than buy-and-hold at the
    # tightest target (sanity, not a guarantee under costs)
    assert table.loc["VolControl_5", "ann_vol"] <= table.loc["BuyHold", "ann_vol"] + 1e-6

    sweep = crypto_sweep(rets, cfg, target_vol=0.10)
    assert sweep["crypto_share"].between(0, 0.5).all()

    tests = hypothesis_tests(rets, cfg, crypto_share=0.15, target_vol=0.10)
    for key in ("H1_max_drawdown", "H2_sharpe", "H3_dMDD_vs_share"):
        assert "p_value" in tests[key]
    print("OK — pipeline runs, metrics finite, H1/H2/H3 produced.")


if __name__ == "__main__":
    test_pipeline()
