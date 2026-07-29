"""Every generated exhibit must carry the archive's numbers, unrounded-in-meaning.

This is the highest-stakes test in the project: the exhibits go into the thesis
without anyone re-checking them. A generator that silently swaps two columns, drops
a sign, or formats 0.0847 as 0,847 would put a wrong number in front of an examiner
with a hash next to it vouching for it.

The checks therefore parse the GENERATED CSV back, undo the German formatting, and
compare against the archive record field by field — the opposite direction from how
the file was written, so a shared bug cannot cancel out.

Run:  python tests/test_exhibits.py
"""
from __future__ import annotations
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ARCHIVE = os.path.join(os.path.dirname(__file__), "..", "results", "freeze")
EXHIBITS = os.path.join(os.path.dirname(__file__), "..", "results", "exhibits")


def _rec(name: str) -> dict:
    with open(os.path.join(ARCHIVE, f"{name}.json")) as f:
        return json.load(f)


def _read(ident: str) -> tuple[list[str], list[list[str]], str]:
    """(header, rows, run_hash) of a generated table, found by identifier."""
    hits = [p for p in glob.glob(os.path.join(EXHIBITS, f"{ident}_*.csv"))]
    assert len(hits) == 1, f"{ident}: {len(hits)} CSV-Dateien gefunden, erwartet genau eine"
    run_hash = os.path.basename(hits[0])[len(ident) + 1:-4]
    with open(hits[0], encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f, delimiter=";")]
    body = [r for r in rows if r and not r[0].startswith("#")]
    return body[0], body[1:], run_hash


def num(s: str) -> float:
    """Undo the German formatting: '1.234,56 %' -> 12.3456 ; '−0,27' -> -0.27."""
    s = s.strip().replace("−", "-").replace("−", "-")
    pct = s.endswith("%")
    s = s.rstrip("% ").strip()
    s = s.replace(".", "").replace(",", ".")
    v = float(s)
    return v / 100 if pct else v


def test_formatter_roundtrip():
    """The German formatter must be losslessly reversible at the printed precision —
    otherwise every comparison below is meaningless."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    from exhibits import de, dei
    cases = [(0.084662, 4, True, 0.084662), (-0.271400, 2, True, -0.2714),
             (0.709898, 6, False, 0.709898), (1234.5678, 2, False, 1234.57),
             (0.9040, 3, False, 0.904), (-0.0243, 2, True, -0.0243)]
    for v, nd, pct, want in cases:
        got = num(de(v, nd, pct))
        assert abs(got - want) < 1e-9, f"de({v},{nd},{pct}) -> {de(v, nd, pct)!r} -> {got}"
    assert dei(2010) == "2.010" and num(dei(2010)) == 2010
    assert dei(1002) == "1.002"
    print("ok  Zahlenformat verlustfrei umkehrbar (6 Fälle + Tausendertrennung)")


def test_tab_4_1_matches_metrics():
    """Kennzahlentabelle — the single most-cited exhibit."""
    header, rows, run_hash = _read("tab_4_1")
    r = _rec("S1")
    assert run_hash == r["hashes"]["run_hash"], f"Hash im Dateinamen: {run_hash}"
    metrics = r["backtest"]["metrics"]
    assert len(rows) == len(metrics), f"{len(rows)} Zeilen statt {len(metrics)}"
    # column order is asserted, not assumed — a swap here is exactly the failure mode
    assert header[:7] == ["Strategie", "Rendite p.a.", "CAGR", "Vol p.a.", "Sharpe",
                          "Max. Drawdown", "CVaR 95 %"], header
    checked = 0
    for row, m in zip(rows, metrics):
        for idx, key, tol in ((1, "ann_return", 5e-5), (2, "cagr", 5e-5),
                              (3, "ann_vol", 5e-5), (4, "sharpe", 5e-4),
                              (5, "max_drawdown", 5e-5), (6, "cvar_95", 5e-5),
                              (7, "turnover", 5e-3)):
            got, want = num(row[idx]), m[key]
            assert abs(got - want) < tol, (
                f"{m['strategy']}.{key}: Exhibit {got} vs Archiv {want}")
            checked += 1
        assert num(row[8]) == m["observations"], f"{m['strategy']}: N"
        checked += 1
    print(f"ok  tab_4_1: {checked} Werte über {len(rows)} Strategien identisch zum Archiv")


def test_tab_4_4_matches_hypotheses():
    """H1/H2 — the confirmatory result. Intervals are parsed apart and compared."""
    _header, rows, run_hash = _read("tab_4_4")
    h = _rec("S1")["hypotheses"]
    assert run_hash == _rec("S1")["hashes"]["run_hash"]
    checked = 0
    for row, key, is_pct in ((rows[0], "H1_max_drawdown", True),
                             (rows[1], "H2_sharpe", False)):
        t = h[key]
        scale = 1.0
        assert abs(num(row[1]) - t["observed_diff"]) < 5e-5, f"{key}: observed_diff"
        for col, (lo_k, hi_k) in ((2, ("ci_low_bca", "ci_high_bca")),
                                  (3, ("ci_low", "ci_high"))):
            lo, hi = row[col].strip("[] ").split(";")
            assert abs(num(lo) - t[lo_k]) < 5e-5, f"{key}.{lo_k}: {num(lo)} vs {t[lo_k]}"
            assert abs(num(hi) - t[hi_k]) < 5e-5, f"{key}.{hi_k}: {num(hi)} vs {t[hi_k]}"
            checked += 2
        assert abs(num(row[4]) - t["p_value"]) < 5e-5, f"{key}: p"
        assert abs(num(row[5]) - h["holm_adjusted"][key]) < 5e-5, f"{key}: Holm"
        checked += 3
        # the verdict must follow the number, not a hard-coded string
        want = "signifikant" if h["holm_adjusted"][key] < 0.05 else "nicht signifikant"
        assert row[6] == want, f"{key}: Beurteilung '{row[6]}' statt '{want}'"
        checked += 1
    print(f"ok  tab_4_4: {checked} Werte (H1/H2, beide Intervalltypen, Holm, Urteil) identisch")


def test_tab_4_7_matches_three_records():
    """Szenariovergleich — reads from three separate records, so a mix-up between
    them is the risk this covers."""
    _header, rows, _h = _read("tab_4_7")
    checked = 0
    for row, name in zip(rows, ("S1", "S2", "S3")):
        r = _rec(name)
        h = r["hypotheses"]
        assert num(row[1]) == r["backtest"]["sample"]["n_return_days"], f"{name}: N"
        assert abs(num(row[2]) - h["H1_max_drawdown"]["observed_diff"]) < 5e-5, f"{name}: H1"
        assert abs(num(row[4]) - h["H2_sharpe"]["observed_diff"]) < 5e-5, f"{name}: H2"
        assert abs(num(row[6]) - h["sweep_bootstrap"]["slopes"]["d_mdd"]["slope"]) < 5e-5, \
            f"{name}: H3"
        assert abs(num(row[8]) - h["sweep_bootstrap"]["argmax"]["best_share_point"]) < 5e-5, \
            f"{name}: Argmax"
        checked += 5
    # S2 must not accidentally show S1's numbers
    assert rows[0][2] != rows[1][2], "S1 und S2 zeigen dasselbe H1 — Records vertauscht?"
    print(f"ok  tab_4_7: {checked} Werte aus drei Records korrekt zugeordnet")


def test_tab_4_9_rf_pair():
    """rf-Sensitivität — two records side by side; the difference column must be the
    actual difference, not a copy."""
    _header, rows, _h = _read("tab_4_9")
    A, B = _rec("S1"), _rec("S1_rf3")
    MA = {m["strategy"]: m for m in A["backtest"]["metrics"]}
    MB = {m["strategy"]: m for m in B["backtest"]["metrics"]}
    checked = 0
    for row in rows:
        if row[0] == "H1":
            continue
        strat = {"Buy-and-Hold": "BuyHold", "Vol-Control 5 %": "VolControl_5",
                 "Vol-Control 10 %": "VolControl_10", "Vol-Control 15 %": "VolControl_15"}[row[0]]
        key = {"Rendite p.a.": "ann_return", "CAGR": "cagr", "Vol p.a.": "ann_vol",
               "Sharpe": "sharpe", "Max. Drawdown": "max_drawdown",
               "CVaR 95 %": "cvar_95"}[row[1]]
        a, b = MA[strat][key], MB[strat][key]
        assert abs(num(row[2]) - a) < 5e-5, f"{strat}.{key} links"
        assert abs(num(row[3]) - b) < 5e-5, f"{strat}.{key} rechts"
        assert abs(num(row[4]) - (b - a)) < 5e-5, f"{strat}.{key} Differenz"
        checked += 3
    assert abs(MA["BuyHold"]["ann_return"] - MB["BuyHold"]["ann_return"]) < 1e-9
    print(f"ok  tab_4_9: {checked} Werte inkl. korrekt berechneter Differenzspalte")


def test_tab_4_2_matches_crypto_share_records():
    """Teilfrage-1-Tabelle — four SEPARATE records, one row each. The failure mode
    this covers is a row silently showing the wrong record's portfolio: all four
    share the same run hash (the fingerprint does not cover crypto_share), so the
    filename cannot distinguish them and only the values can."""
    header, rows, _h = _read("tab_4_2")
    assert header[0] == "Krypto-Quote", header
    assert len(rows) == 4, f"{len(rows)} Zeilen statt 4"
    expected = [("S1_bh0", 0.0), ("S1", 0.10), ("S1_bh25", 0.25), ("S1_bh50", 0.50)]
    checked = 0
    for row, (name, share) in zip(rows, expected):
        r = _rec(name)
        assert abs(r["backtest"]["crypto_share"] - share) < 1e-9, (
            f"{name} traegt Quote {r['backtest']['crypto_share']}, erwartet {share}")
        assert abs(num(row[0]) - share) < 1e-9, f"{name}: Quote in Spalte 1"
        m = next(x for x in r["backtest"]["metrics"] if x["strategy"] == "BuyHold")
        for idx, key, tol in ((1, "ann_return", 5e-5), (2, "cagr", 5e-5),
                              (3, "ann_vol", 5e-5), (4, "sharpe", 5e-4),
                              (5, "max_drawdown", 5e-5), (6, "cvar_95", 5e-5),
                              (7, "turnover", 5e-3)):
            got, want = num(row[idx]), m[key]
            assert abs(got - want) < tol, f"{name}.{key}: Exhibit {got} vs Archiv {want}"
            checked += 1
    # A higher crypto share must move the portfolio — identical rows would mean the
    # generator read the same record four times.
    assert len({r[1] for r in rows}) == 4, "Vier identische Renditen — Records vertauscht?"
    assert num(rows[0][5]) > num(rows[3][5]), "Drawdown wird mit mehr Krypto nicht tiefer"
    print(f"ok  tab_4_2: {checked} Werte aus vier Records, Quoten und Monotonie geprüft")


def test_timeseries_and_rf_blocks_present():
    """The additive archive extension must actually be in every record."""
    for name in ("S1", "S2", "S3", "S1_rf3"):
        r = _rec(name)
        assert "rf_series" in r and r["rf_series"]["dates"], f"{name}: rf_series fehlt"
        assert len(r["rf_series"]["dates"]) == len(r["rf_series"]["daily"])
        ts = r.get("timeseries")
        assert ts and set(ts) == {"vol_5", "vol_10", "vol_15"}, f"{name}: timeseries {list(ts or [])}"
        for k, want in (("vol_5", "VolControl_5"), ("vol_10", "VolControl_10"),
                        ("vol_15", "VolControl_15")):
            assert ts[k]["selected"] == want, f"{name}.{k}: selected={ts[k]['selected']}"
            for f in ("wealth", "drawdown", "exposure"):
                assert ts[k]["series"][want][f], f"{name}.{k}.{want}.{f} leer"
    n = len(_rec("S1")["rf_series"]["dates"])
    print(f"ok  Archiv-Erweiterung vorhanden: rf_series ({n} Tage) und "
          f"timeseries für drei Zielvolatilitäten in allen geprüften Records")


def test_abb_4_13_lines_match_the_record():
    """The rolling-correlation figure: read the DRAWN lines back out of the figure.

    A figure cannot be parsed back like a CSV, so the builder's `figure()` call is
    intercepted and the Matplotlib artists are inspected before the figure is closed.
    That compares what was actually plotted against the record — not the builder's
    input, which would be circular.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import exhibits

    captured = {}
    real_figure = exhibits.figure

    def spy(ident, chapter, placement, scenario, source, title, fig, caption=""):
        captured["fig"] = fig
        captured["caption"] = caption
        real_figure(ident, chapter, placement, scenario, source, title, fig, caption)

    exhibits.figure = spy
    try:
        exhibits.abb_4_13()
    finally:
        exhibits.figure = real_figure

    c = _rec("S1")["analytics"]["correlation"]
    d, S = c["dates"], c["series"]
    ax = captured["fig"].axes[0]
    drawn = {ln.get_label(): (list(ln.get_xdata()), list(ln.get_ydata()))
             for ln in ax.get_lines() if ln.get_label() in S}
    assert set(drawn) == set(S), f"Gezeichnet: {sorted(drawn)}, im Record: {sorted(S)}"

    checked = 0
    for asset, (xs, ys) in drawn.items():
        v = S[asset]
        expected_x = [i for i, y in enumerate(v) if y is not None]
        assert xs == expected_x, f"{asset}: x-Positionen weichen ab"
        assert len(ys) == len(expected_x), f"{asset}: {len(ys)} Punkte statt {len(expected_x)}"
        # Three probes per series: first drawn point, the COVID-window maximum and
        # the last point — start, extremum and end of each line.
        covid = [i for i in expected_x if "2020-02-01" <= d[i] < "2020-07-01"]
        peak = max(covid, key=lambda i: v[i])
        for i in (expected_x[0], peak, expected_x[-1]):
            got = ys[xs.index(i)]
            assert abs(got - v[i]) < 1e-12, (
                f"{asset} am {d[i]}: gezeichnet {got}, Record {v[i]}")
            checked += 1
    assert checked >= 3, checked

    # The caption's block means must equal a fresh recomputation from the record.
    def mean_of(lo, hi):
        out = {}
        for asset, v in S.items():
            vals = [v[i] for i, x in enumerate(d) if lo <= x < hi and v[i] is not None]
            out[asset] = sum(vals) / len(vals)
        return min(out.values()), max(out.values())

    cap = captured["caption"]
    for lo, hi in (("2018-01-01", "2020-02-01"), ("2020-02-01", "2020-07-01"),
                   ("2023-01-01", "2026-01-01")):
        a_lo, a_hi = mean_of(lo, hi)
        for value in (a_lo, a_hi):
            assert exhibits.de(value, 3) in cap, (
                f"Blockmittel {exhibits.de(value, 3)} ({lo}..{hi}) fehlt in der "
                f"Beschriftung")
            checked += 1
    print(f"ok  abb_4_13: {checked} Werte — 12 Linienpunkte direkt aus der Figur "
          f"zurückgelesen, 6 Blockmittel in der Beschriftung nachgerechnet")


def test_reproducibility_table_covers_every_record():
    """tab_a_1 is the appendix's reproducibility proof — it must list every archived
    record, and every run hash in it must be unique.

    Both halves have already failed once: the record list was hard-coded and fell
    behind when the archive grew, and before the run-hash fix four records shared one
    hash. A table that omits records or repeats an identifier defeats its own purpose.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import exhibits
    _header, rows, _h = _read("tab_a_1")
    listed = [r[0] for r in rows]
    archived = exhibits.all_records()
    assert listed == archived, f"tab_a_1 fuehrt {listed}, Archiv hat {archived}"
    run_hashes = [r[2] for r in rows]
    assert len(set(run_hashes)) == len(run_hashes), (
        f"Doppelte Lauf-Hashes: "
        f"{[h for h in run_hashes if run_hashes.count(h) > 1]}")
    for row in rows:
        r = _rec(row[0])
        assert row[1] == r["hashes"]["dataset_hash"], f"{row[0]}: Datensatz-Hash"
        assert row[2] == r["hashes"]["run_hash"], f"{row[0]}: Lauf-Hash"
    # The two-anchor design made visible: same data, different configuration.
    shared = [r[0] for r in rows if r[1] == _rec("S1")["hashes"]["dataset_hash"]]
    assert len(shared) > 1, "Kein Record teilt die Datenbasis mit S1"
    print(f"ok  tab_a_1: {len(rows)} Records, {len(set(run_hashes))} verschiedene "
          f"Lauf-Hashes; {len(shared)} teilen die Datenbasis von S1 bei "
          f"unterschiedlicher Konfiguration")


def test_every_file_carries_its_run_hash():
    """The hash in the filename must be the hash of the record the exhibit came from —
    that link is what makes the appendix defensible."""
    reg = os.path.join(EXHIBITS, "REGISTER.csv")
    assert os.path.exists(reg), "REGISTER.csv fehlt"
    with open(reg, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    real = [r for r in rows if r["typ"] != "FEHLT"]
    assert real, "Register enthält keine erzeugten Exhibits"
    for r in real:
        for fn in r["dateien"].split(", "):
            p = os.path.join(EXHIBITS, fn)
            assert os.path.exists(p), f"{r['bezeichner']}: Datei fehlt: {fn}"
            assert r["lauf_hash"] in fn, f"{fn} trägt nicht den Lauf-Hash {r['lauf_hash']}"
    figs = [r for r in real if r["typ"] == "Abbildung"]
    for r in figs:
        exts = {fn.rsplit(".", 1)[1] for fn in r["dateien"].split(", ")}
        assert {"pdf", "svg", "png"} <= exts, f"{r['bezeichner']}: nur {exts}"
    print(f"ok  {len(real)} Exhibits registriert, alle Dateien vorhanden, "
          f"{len(figs)} Abbildungen in PDF+SVG+PNG")


def test_register_matches_declared_gaps():
    """The register must mirror the generator's own gap list exactly.

    Both directions matter: a gap the generator knows about but the register omits
    would be an exhibit that silently disappears from the thesis, and a FEHLT row for
    something that was in fact generated would send the reader looking for nothing.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import exhibits
    with open(os.path.join(EXHIBITS, "REGISTER.csv"), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    listed = {r["bezeichner"] for r in rows if r["typ"] == "FEHLT"}
    declared = {g[0] for g in exhibits.GAPS}
    assert listed == declared, f"Register {sorted(listed)} vs Generator {sorted(declared)}"
    built = {r["bezeichner"] for r in rows if r["typ"] != "FEHLT"}
    assert not (built & listed), f"Als FEHLT gelistet und trotzdem erzeugt: {built & listed}"
    # Every builder must appear in the register — a builder that runs but registers
    # nothing produces an untraceable file.
    names = {b.__name__ for b in exhibits.BUILDERS}
    assert names <= built, f"Erzeugt, aber nicht registriert: {sorted(names - built)}"
    if listed:
        print(f"ok  {len(listed)} Lücken ausgewiesen statt still übersprungen: "
              f"{', '.join(sorted(listed))}")
    else:
        print(f"ok  keine offenen Lücken; alle {len(built)} Exhibits erzeugt, "
              f"registriert und auf Builder rückführbar")


if __name__ == "__main__":
    test_formatter_roundtrip()
    test_tab_4_1_matches_metrics()
    test_tab_4_4_matches_hypotheses()
    test_tab_4_7_matches_three_records()
    test_tab_4_9_rf_pair()
    test_tab_4_2_matches_crypto_share_records()
    test_timeseries_and_rf_blocks_present()
    test_abb_4_13_lines_match_the_record()
    test_reproducibility_table_covers_every_record()
    test_every_file_carries_its_run_hash()
    test_register_matches_declared_gaps()
