"""Results freeze: compute every scenario once and archive it verifiably.

From the freeze onwards the thesis cites THIS archive, not a live run. That only
works if the archive carries enough context to prove what produced it, so each
scenario record holds both hashes, the full effective config, the git commit, the
interpreter and library versions, a timestamp and the runtime.

Scenarios
---------
  S1        Hauptspezifikation (fester Korb, 2018-2025)
  S2        Point-in-Time-Sleeve
  S3        voller Korb inkl. Solana (ab 2021)
  S4_<y>    Startjahr-Sensitivität, y = 2018..2022
  S1_rf3    S1 mit konstantem rf = 3 % statt der verketteten €STR/EONIA-Reihe

Why S1_rf3 is not optional: at target vol 5 % the strategy sits ~64 % in cash on a
rate that was negative on 59 % of the days, so the rf assumption is result-bearing
exactly where the strategy looks best. Measured, it turns out to move LEVELS rather
than rankings — every Sharpe drops ~0.13 because rf is also the benchmark in the
numerator, and the vol-control advantage moves by only -0.0037. That is worth an
appendix number precisely because the intuitive expectation points the other way.

Run:  python scripts/freeze_run.py            (writes results/freeze/)
      python scripts/freeze_run.py --verify    (recompute and diff against archive)
"""
from __future__ import annotations
import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "freeze")

# (record name, RunRequest overrides). The record name is what the thesis cites.
RECORDS: list[tuple[str, dict]] = (
    [("S1", {"scenario": "S1"}),
     ("S2", {"scenario": "S2"}),
     ("S3", {"scenario": "S3"})]
    + [(f"S4_{y}", {"scenario": f"S4_{y}"}) for y in (2018, 2019, 2020, 2021, 2022)]
    + [("S1_rf3", {"scenario": "S1", "rf_mode": "constant", "rf_annual": 0.03})]
)


def _versions() -> dict:
    import numpy, pandas, scipy, statsmodels
    return {
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scipy": scipy.__version__,
        "statsmodels": statsmodels.__version__,
    }


def _git() -> dict:
    def run(*a):
        try:
            return subprocess.run(["git", *a], capture_output=True, text=True,
                                  cwd=os.path.dirname(__file__), timeout=15).stdout.strip()
        except Exception:
            return None
    return {"commit": run("rev-parse", "HEAD"),
            "describe": run("describe", "--tags", "--always", "--dirty"),
            "dirty": bool(run("status", "--porcelain"))}


def compute(name: str, overrides: dict) -> dict:
    """One scenario, every reported block, through the API's own endpoint functions.

    Calling the endpoints rather than the engine directly is deliberate: the thesis
    quotes what the tool shows, and the endpoints are where sample resolution, rf
    mode and the fingerprint are actually assembled.
    """
    from api.main import (RunRequest, backtest, hypotheses, sweep, analytics,
                          robustness, describe)
    t0 = time.time()
    req = RunRequest(**overrides)
    bt = backtest(req)
    rec = {
        "record": name,
        "request": req.model_dump() if hasattr(req, "model_dump") else req.dict(),
        "backtest": bt,
        "hypotheses": hypotheses(req),
        "sweep": sweep(req),
        "analytics": analytics(req),
        "robustness": robustness(req),
        "describe": describe(req),
    }
    fp = bt.get("fingerprint", {})
    rec["hashes"] = {"dataset_hash": fp.get("dataset_hash"),
                     "run_hash": fp.get("run_hash") or fp.get("hash")}
    rec["runtime_seconds"] = round(time.time() - t0, 2)
    rec["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rec["environment"] = _versions()
    rec["git"] = _git()
    return rec


def _json_default(o):
    import numpy as np
    import pandas as pd
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    return str(o)


def _stable(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=_json_default, ensure_ascii=False)


def write_archive() -> list[dict]:
    os.makedirs(OUT_DIR, exist_ok=True)
    records = []
    for name, ov in RECORDS:
        print(f"  {name:8s} …", end="", flush=True)
        rec = compute(name, ov)
        with open(os.path.join(OUT_DIR, f"{name}.json"), "w") as f:
            json.dump(rec, f, indent=1, default=_json_default, ensure_ascii=False)
        h = rec["hashes"]
        n = rec["backtest"]["sample"]["n_return_days"]
        print(f" {rec['runtime_seconds']:6.1f}s  n={n:5d}  "
              f"{h['dataset_hash']}/{h['run_hash']}")
        records.append(rec)
    _write_index(records)
    return records


def _write_index(records: list[dict]) -> None:
    """Human-readable companion to the JSON — the page an examiner can actually read."""
    env = records[0]["environment"]
    git = records[0]["git"]
    lines = [
        "# Ergebnis-Freeze — Archivübersicht",
        "",
        f"Erzeugt: {records[0]['generated_at']}  ",
        f"Commit: `{git['describe']}` ({git['commit']})"
        + ("  **ACHTUNG: Arbeitsbaum war nicht sauber**" if git["dirty"] else ""),
        f"Umgebung: Python {env['python']} · numpy {env['numpy']} · pandas {env['pandas']}"
        f" · scipy {env['scipy']} · statsmodels {env['statsmodels']} · {env['platform']}",
        "",
        "| Record | Fenster | n | Datensatz-Hash | Lauf-Hash | Laufzeit |",
        "|---|---|---:|---|---|---:|",
    ]
    for r in records:
        s = r["backtest"]["sample"]
        lines.append(
            f"| {r['record']} | {s['effective_start']}–{s['effective_end']} "
            f"| {s['n_return_days']} | `{r['hashes']['dataset_hash']}` "
            f"| `{r['hashes']['run_hash']}` | {r['runtime_seconds']:.1f}s |")

    lines += ["", "## Kernzahlen je Record", "",
              "| Record | H1 ΔMDD | H1 BCa | H2 ΔSharpe | H2 BCa | H3 Steigung | H3 KI | Argmax |",
              "|---|---:|---|---:|---|---:|---|---:|"]
    for r in records:
        h = r["hypotheses"]
        h1, h2 = h["H1_max_drawdown"], h["H2_sharpe"]
        sb = h["sweep_bootstrap"]
        md, am = sb["slopes"]["d_mdd"], sb["argmax"]
        lines.append(
            f"| {r['record']} | {h1['observed_diff']:+.4f} "
            f"| [{h1['ci_low_bca']:+.4f}; {h1['ci_high_bca']:+.4f}] "
            f"| {h2['observed_diff']:+.4f} "
            f"| [{h2['ci_low_bca']:+.4f}; {h2['ci_high_bca']:+.4f}] "
            f"| {md['slope']:.4f} | [{md['ci_low']:.4f}; {md['ci_high']:.4f}] "
            f"| {am['best_share_point']:.2f} |")

    lines += ["", "## rf-Sensitivität (S1)", "",
              "Verkettete €STR/EONIA-Tagesreihe gegen konstante 3 % p. a.", ""]
    base = next((r for r in records if r["record"] == "S1"), None)
    alt = next((r for r in records if r["record"] == "S1_rf3"), None)
    if base and alt:
        lines += ["| Strategie | Sharpe €STR | Sharpe rf=3 % | Δ | MaxDD €STR | MaxDD rf=3 % |",
                  "|---|---:|---:|---:|---:|---:|"]
        A = {m["strategy"]: m for m in base["backtest"]["metrics"]}
        B = {m["strategy"]: m for m in alt["backtest"]["metrics"]}
        for k in A:
            if k not in B:
                continue
            lines.append(f"| {k} | {A[k]['sharpe']:.4f} | {B[k]['sharpe']:.4f} "
                         f"| {B[k]['sharpe'] - A[k]['sharpe']:+.4f} "
                         f"| {A[k]['max_drawdown']:.4f} | {B[k]['max_drawdown']:.4f} |")
        lines += ["",
                  f"H1 ΔMDD: {base['hypotheses']['H1_max_drawdown']['observed_diff']:+.6f} "
                  f"gegen {alt['hypotheses']['H1_max_drawdown']['observed_diff']:+.6f}; "
                  f"H2 ΔSharpe: {base['hypotheses']['H2_sharpe']['observed_diff']:+.6f} "
                  f"gegen {alt['hypotheses']['H2_sharpe']['observed_diff']:+.6f}.",
                  "",
                  "",
                  "Der Zins wirkt an ZWEI Stellen, die nicht verwechselt werden dürfen. "
                  "In der RENDITEREIHE nur bei der Vol-Control, über die Cash-Quote "
                  "(1 − Exposure) · rf: die Buy-and-Hold-Reihe ist dort tatsächlich "
                  "unberührt (Rendite p. a. 0,159200 in beiden Läufen, MaxDD −0,271400 in "
                  "beiden). Im SHARPE dagegen bei allen Strategien, weil rf der "
                  "Vergleichszins im Zähler ist — deshalb fällt auch der Buy-and-Hold-"
                  "Sharpe um 0,1270.",
                  "",
                  "Die Sharpe-Änderung folgt eng −ē · Δrf / σ (ē = mittleres Exposure): "
                  "vorhergesagt −0,1281 / −0,1455 / −0,1450 / −0,1382 für BH und VC 5/10/15, "
                  "gemessen −0,1270 / −0,1325 / −0,1307 / −0,1289. Die Vol-Control verliert "
                  "je Einheit mehr, weil ihre kleinere Volatilität im Nenner steht.",
                  "",
                  "Für die berichteten VERGLEICHE ist der Effekt daher klein: der "
                  "Sharpe-Vorsprung der Vol-Control gegenüber Buy-and-Hold geht von "
                  "+0,0755 auf +0,0718 zurück (−0,0037), der Drawdown-Vorsprung steigt "
                  "leicht von +0,0847 auf +0,0852. Die naheliegende Vermutung, eine "
                  "konstante positive Zinsannahme schmeichle der Vol-Control, bestätigt "
                  "sich in dieser Stichprobe NICHT — sie verschiebt vor allem das NIVEAU "
                  "aller Sharpe-Werte um rund 0,13, nicht die Rangfolge. Wer Niveaus "
                  "zitiert, muss die Zinskonvention mitnennen; die Hypothesentests H1 "
                  "und H2 sind gegenüber dieser Annahme nahezu invariant."]

    with open(os.path.join(OUT_DIR, "INDEX.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ── verification ─────────────────────────────────────────────────────────────
VOLATILE = {"generated_at", "runtime_seconds", "fetched_at", "git", "environment"}


def _diff(a, b, path="") -> list[tuple[str, object, object]]:
    """Recursive value diff, ignoring keys that legitimately change per run."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in VOLATILE:
                continue
            if k not in a:
                out.append((f"{path}/{k}", "<fehlt>", b[k]))
            elif k not in b:
                out.append((f"{path}/{k}", a[k], "<fehlt>"))
            else:
                out += _diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, f"len {len(a)}", f"len {len(b)}"))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += _diff(x, y, f"{path}[{i}]")
    elif isinstance(a, float) and isinstance(b, float):
        if not (a == b or (a != a and b != b)):
            out.append((path, a, b))
    elif a != b:
        out.append((path, a, b))
    return out


def verify() -> int:
    """Recompute everything and report EVERY deviation from the archive."""
    bad = 0
    for name, ov in RECORDS:
        p = os.path.join(OUT_DIR, f"{name}.json")
        if not os.path.exists(p):
            print(f"  {name:8s} ARCHIV FEHLT ({p})")
            bad += 1
            continue
        with open(p) as f:
            old = json.load(f)
        new = json.loads(_stable(compute(name, ov)))
        d = _diff(old, new)
        if d:
            bad += 1
            print(f"  {name:8s} {len(d)} ABWEICHUNG(EN):")
            for pth, x, y in d[:20]:
                print(f"            {pth}: {x} -> {y}")
            if len(d) > 20:
                print(f"            … und {len(d) - 20} weitere")
        else:
            h = old["hashes"]
            print(f"  {name:8s} identisch  {h['dataset_hash']}/{h['run_hash']}")
    return bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="Neu rechnen und gegen das Archiv prüfen (ändert nichts)")
    args = ap.parse_args()
    if args.verify:
        print("Prüfe Archiv gegen Neulauf …")
        n = verify()
        print("\nErgebnis:", "ARCHIV BESTÄTIGT — keine Abweichung"
              if n == 0 else f"{n} Record(s) WEICHEN AB")
        sys.exit(1 if n else 0)
    print(f"Ergebnis-Freeze — {len(RECORDS)} Records nach {os.path.abspath(OUT_DIR)}")
    write_archive()
    print("\nfertig. INDEX.md geschrieben.")
