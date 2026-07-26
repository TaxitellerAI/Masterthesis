"""Vorberechnete Inferenz für die Hauptspezifikationen (S1/S2/S3).

Warum
-----
Gemessen: /hypotheses braucht auf dem deployten Free-Tier-Host 192 s, die
Next.js-Route darf aber nur 60 s warten. Die Live-Rechnung KANN dort also nie
durchlaufen — unabhängig davon, wie schnell die Engine lokal ist (7,7 s). Ein
Cache allein hilft nicht, weil bereits die erste Berechnung in den Timeout läuft.

Die Hauptspezifikation muss für die Verteidigung ohnehin sofort und netzunabhängig
auf dem Schirm stehen. Sie wird daher hier einmal gerechnet und als JSON mit
ausgeliefert; abweichende Konfigurationen rechnen weiterhin live.

Der gespeicherte Schlüssel ist derselbe, den die API zur Laufzeit bildet
(api.main._analysis_key) — inklusive Daten-Hash. Ein vorberechnetes Ergebnis kann
deshalb NUR bei exakt passender Konfiguration ausgeliefert werden; jede Abweichung
(Zielvol, rf-Modus, Fenster, Gewichte …) fällt automatisch auf die Live-Rechnung
zurück. Das ist die Bedingung dafür, dass hier keine falschen Zahlen entstehen.

Run:  python scripts/precompute_inference.py
"""
from __future__ import annotations
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "precomputed_inference.json")
SCENARIOS = ("S1", "S2", "S3")


def _plain(o):
    """numpy -> builtin, damit das JSON exakt dem entspricht, was die API liefert."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"nicht serialisierbar: {type(o)}")


def main():
    from api.main import (RunRequest, _prepared, _analysis_key, SWEEP_BOOT_N,
                          API_BOOTSTRAP_N)
    from volcontrol.backtest import hypothesis_tests
    from volcontrol import sweepboot as sbm

    entries = []
    for name in SCENARIOS:
        req = RunRequest(scenario=name, crypto_share=0.10, target_vol=0.10)
        # MUSS dieselbe Config sein wie im Endpoint (bootstrap_n = 1200),
        # sonst gehoerten die Bootstrap-p-Werte zu einer anderen Konfiguration.
        rets, cfg, _rf_info, _spec, report, pit = _prepared(req, bootstrap_n=API_BOOTSTRAP_N)
        t0 = time.time()
        sboot = sbm.sweep_bootstrap(rets, cfg, req.target_vol,
                                    n_boot=SWEEP_BOOT_N, seed=cfg.seed)
        sboot["runtime_seconds"] = round(time.time() - t0, 2)
        sboot["sample"] = report
        res = hypothesis_tests(rets, cfg, req.crypto_share, req.target_vol,
                               pit_builder=pit, sweep_boot=sboot)
        res = {k: (v if k != "sweep" else v.round(5).to_dict(orient="records"))
               for k, v in res.items()}
        dt = time.time() - t0
        entries.append({
            "scenario": name,
            "crypto_share": req.crypto_share,
            "target_vol": req.target_vol,
            "key": list(_analysis_key(req, rets, cfg)),
            "result": res,
        })
        print(f"  {name}: {dt:6.2f}s  n={report['n_return_days']}  "
              f"H1 dMDD {res['H1_max_drawdown']['observed_diff']:+.4f}  "
              f"Steigung {sboot['slopes']['d_mdd']['slope']:+.4f}")

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sweep_boot_n": SWEEP_BOOT_N,
        "note": ("Vorberechnet für die Hauptspezifikationen. Wird nur bei EXAKT "
                 "passendem Analyse-Schlüssel ausgeliefert, sonst Live-Rechnung."),
        "entries": entries,
    }
    with open(OUT, "w") as f:
        json.dump(payload, f, default=_plain, separators=(",", ":"))
    print(f"geschrieben: {os.path.abspath(OUT)} "
          f"({os.path.getsize(OUT) / 1024:.0f} KB, {len(entries)} Szenarien)")


if __name__ == "__main__":
    main()
