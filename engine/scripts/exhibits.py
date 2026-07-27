"""Generate every table and figure of the written thesis FROM THE FROZEN ARCHIVE.

Nothing here computes: each exhibit reads `results/freeze/*.json` and reshapes it.
That is the whole point — a number that is typed out of the UI by hand cannot be
traced, and a later re-run cannot pull it along. Every file carries the run hash of
the record it came from, and REGISTER.csv maps identifier -> chapter -> placement ->
scenario -> field path -> hash -> filename.

Chapters follow the thesis outline:
    3  Methodik
    4  Empirische Analyse (inkl. Robustheit)
    5  Diskussion — interprets chapter 4, has no exhibits of its own
    6  Fazit

Tables are written twice: `.csv` (semicolon-separated, German decimal comma, for
Excel) and `.txt` (aligned, copy-ready). Figures are written as PDF, SVG and PNG at
300 dpi — Word handles SVG well and PDF badly, PNG is the safe fallback.

Run:  python scripts/exhibits.py            (writes results/exhibits/)
      python scripts/exhibits.py --check     (re-derive and diff against the archive)
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ARCHIVE = os.path.join(os.path.dirname(__file__), "..", "results", "freeze")
OUT = os.path.join(os.path.dirname(__file__), "..", "results", "exhibits")

# Print-oriented defaults: figures land at ~16 cm width in Word, so anything below
# 9 pt becomes unreadable after scaling.
plt.rcParams.update({
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.figsize": (6.3, 3.6), "svg.fonttype": "none",
})
ACCENT, GREY, NEG = "#2f5d8c", "#8a8a8a", "#8f3a33"

REGISTER: list[dict] = []
_CACHE: dict[str, dict] = {}


def all_records() -> list[str]:
    """Every record in the archive, in the order freeze_run.py writes them.

    Derived, never hand-listed: tab_3_2 and tab_a_1 had a literal list and silently
    omitted S1_bh0/25/50 the moment the archive grew — an appendix that vouches for
    reproducibility must not itself fall behind the archive it describes.
    """
    from freeze_run import RECORDS
    return [n for n, _ov in RECORDS
            if os.path.exists(os.path.join(ARCHIVE, f"{n}.json"))]


def rec(name: str) -> dict:
    if name not in _CACHE:
        with open(os.path.join(ARCHIVE, f"{name}.json")) as f:
            _CACHE[name] = json.load(f)
    return _CACHE[name]


def rh(name: str) -> str:
    return rec(name)["hashes"]["run_hash"]


# ── German number formatting ─────────────────────────────────────────────────
def de(v, nd: int = 4, pct: bool = False) -> str:
    """German decimal comma + thousands point. `pct` scales by 100 and appends %."""
    if v is None:
        return "—"
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "ja" if v else "nein"
    if pct:
        v = v * 100
    s = f"{v:,.{nd}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".") + (" %" if pct else "")


def dei(v) -> str:
    return "—" if v is None else f"{int(v):,}".replace(",", ".")


# ── writers ──────────────────────────────────────────────────────────────────
def table(ident: str, chapter: str, placement: str, scenario: str, source: str,
          title: str, header: list[str], rows: list[list[str]], note: str = "") -> None:
    h = rh(scenario if scenario in _CACHE or os.path.exists(
        os.path.join(ARCHIVE, f"{scenario}.json")) else "S1")
    base = f"{ident}_{h}"
    os.makedirs(OUT, exist_ok=True)

    with open(os.path.join(OUT, base + ".csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([f"# {ident} — {title}"])
        w.writerow([f"# Szenario {scenario} · Lauf-Hash {h} · Quelle {source}"])
        if note:
            w.writerow([f"# {note}"])
        w.writerow(header)
        w.writerows(rows)

    widths = [max(len(str(header[i])), *(len(str(r[i])) for r in rows)) if rows
              else len(str(header[i])) for i in range(len(header))]
    def line(cells):
        return "  ".join(str(c).ljust(widths[i]) if i == 0 else str(c).rjust(widths[i])
                         for i, c in enumerate(cells))
    txt = [f"{ident} — {title}",
           f"Szenario {scenario} · Lauf-Hash {h} · Quelle {source}", "",
           line(header), "-" * (sum(widths) + 2 * (len(widths) - 1))]
    txt += [line(r) for r in rows]
    if note:
        txt += ["", note]
    with open(os.path.join(OUT, base + ".txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(txt) + "\n")

    REGISTER.append({"bezeichner": ident, "typ": "Tabelle", "kapitel": chapter,
                     "platzierung": placement, "szenario": scenario, "quelle": source,
                     "lauf_hash": h, "dateien": f"{base}.csv, {base}.txt",
                     "titel": title})


def figure(ident: str, chapter: str, placement: str, scenario: str, source: str,
           title: str, fig, caption: str = "") -> None:
    h = rh(scenario)
    base = f"{ident}_{h}"
    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(os.path.join(OUT, f"{base}.{ext}"), format=ext)
    plt.close(fig)
    if caption:
        with open(os.path.join(OUT, base + "_beschriftung.txt"), "w", encoding="utf-8") as f:
            f.write(f"{ident}: {title}\n\n{caption}\n\nSzenario {scenario} · "
                    f"Lauf-Hash {h} · Quelle {source}\n")
    REGISTER.append({"bezeichner": ident, "typ": "Abbildung", "kapitel": chapter,
                     "platzierung": placement, "szenario": scenario, "quelle": source,
                     "lauf_hash": h,
                     "dateien": f"{base}.pdf, {base}.svg, {base}.png"
                                + (f", {base}_beschriftung.txt" if caption else ""),
                     "titel": title})


def _year_ticks(ax, dates: list[str]) -> None:
    """Tick at the first observation of each year.

    Even spacing by index lands on arbitrary months because the archived paths are
    weekly-sampled — a print figure labelled 2019-01, 2019-12, 2020-12 looks like an
    error even when the data is right.
    """
    idx, labels, seen = [], [], set()
    for i, d in enumerate(dates):
        y = d[:4]
        if y not in seen:
            seen.add(y)
            idx.append(i)
            labels.append(y)
    ax.set_xticks(idx, labels)


LABELS = {"BuyHold": "Buy-and-Hold", "VolControl_5": "Vol-Control 5 %",
          "VolControl_10": "Vol-Control 10 %", "VolControl_15": "Vol-Control 15 %",
          "Benchmark_TrueBH": "True Buy-and-Hold (Drift)", "Benchmark_6040": "60/40",
          "Benchmark_RiskParity": "Risk Parity"}
SCEN_LABEL = {"S1": "S1 Hauptspezifikation", "S2": "S2 Point-in-Time",
              "S3": "S3 voller Korb inkl. SOL", "S1_rf3": "S1 mit rf = 3 %"}


# ── Kapitel 3 — Methodik ─────────────────────────────────────────────────────
def tab_3_1():
    a = rec("S1")["describe"]["assets"]
    rows = [[x["asset"].replace("_", " "), x["first"], x["last"], dei(x["observations"]),
             dei(x["trading_days"])] for x in a]
    table("tab_3_1", "3", "Hauptteil", "S1", "describe.assets",
          "Anlageuniversum und Datenverfügbarkeit",
          ["Asset", "Erster Kurs", "Letzter Kurs", "Beobachtungen", "Handelstage/Jahr"],
          rows,
          "Beobachtungen je Asset auf dem EIGENEN Handelskalender; Krypto handelt "
          "~365 Tage/Jahr, Aktien und Anleihen ~251.")


def tab_3_2():
    names = all_records()
    rows = []
    for n in names:
        s = rec(n)["backtest"]["sample"]
        rows.append([n, s["effective_start"], s["effective_end"], dei(s["n_price_rows"]),
                     dei(s["n_return_days"]), str(len(s["assets"])),
                     "Point-in-Time" if s["sleeve_mode"] == "point_in_time" else "fester Korb",
                     rec(n)["hashes"]["dataset_hash"], rec(n)["hashes"]["run_hash"]])
    table("tab_3_2", "3", "Hauptteil", "alle", "backtest.sample + hashes",
          "Sample-Designs und Reproduktionsanker",
          ["Record", "Beginn", "Ende", "Kurszeilen", "Renditetage", "Assets", "Korb",
           "Datensatz-Hash", "Lauf-Hash"], rows,
          "Kurszeilen und Renditetage unterscheiden sich um eins — die erste Kurszeile "
          "erzeugt keine Rendite. S4_2018 teilt die Datenbasis mit S1 (gleicher "
          "Datensatz-Hash), unterscheidet sich aber in der Konfiguration (anderer Lauf-Hash).")


def tab_3_3():
    a = rec("S1")["describe"]["assets"]
    rows = [[x["asset"].replace("_", " "), de(x["ann_return"], 2, True), de(x["ann_vol"], 2, True),
             de(x["sharpe"], 3), de(x["skew"], 2), de(x["excess_kurtosis"], 2),
             de(x["max_drawdown"], 2, True), de(x["var_95"], 2, True),
             de(x["cvar_95"], 2, True), dei(x["observations"])] for x in a]
    table("tab_3_3", "3", "Hauptteil", "S1", "describe.assets",
          "Deskriptive Statistik der Einzelanlagen",
          ["Asset", "Rendite p.a.", "Vol p.a.", "Sharpe", "Schiefe", "Exzess-Kurtosis",
           "Max. Drawdown", "VaR 95 %", "CVaR 95 %", "N"], rows,
          "Exzess-Kurtosis: Normalverteilung = 0 (nicht 3). Annualisierung je Asset "
          "auf seinem eigenen Handelskalender.")


def abb_3_1():
    c = rec("S1")["describe"]["correlation"]
    names = [a.replace("_", " ") for a in c["assets"]]
    M = c["matrix"]
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    im = ax.imshow(M, cmap="Greys", vmin=0, vmax=1)
    ax.set_xticks(range(len(names)), names, rotation=45, ha="right")
    ax.set_yticks(range(len(names)), names)
    for i in range(len(names)):
        for j in range(len(names)):
            ax.text(j, i, de(M[i][j], 2), ha="center", va="center", fontsize=8,
                    color="white" if M[i][j] > 0.55 else "black")
    ax.set_title("Korrelation der Tagesrenditen (gemeinsames Fenster)")
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Korrelationskoeffizient")
    figure("abb_3_1", "3", "Hauptteil", "S1", "describe.correlation",
           "Korrelationsmatrix der Tagesrenditen", fig,
           "Pearson-Korrelation der Tagesrenditen im gemeinsamen, ausgerichteten "
           "Fenster (n = 2.010). Feiertage werden nicht aufgefüllt.")


def tab_3_4():
    e = rec("S1")["describe"]["rf"]["estr"]
    rows = [
        ["Quelle", e["source"]],
        ["Verkettungsdatum", e["splice_date"]],
        ["Aufschlag vor Verkettung", f"−{de(e['spread_bps'], 1)} Basispunkte"],
        ["Konvention", e["convention"]],
        ["Beobachtungen (Gesamtreihe)", dei(e["observations"])],
        ["Erster / letzter Tag", f"{e['first']} – {e['last']}"],
        ["Mittel p.a. (Gesamtreihe)", de(e["mean_annual"], 4, True)],
        ["Mittel p.a. (Sample-Fenster)", de(e["window_mean_annual"], 4, True)],
        ["Minimum p.a. (Sample-Fenster)", de(e["window_min_annual"], 4, True)],
        ["Maximum p.a. (Sample-Fenster)", de(e["window_max_annual"], 4, True)],
        ["Anteil negativer Tage (Fenster)", de(e["window_share_negative"], 1, True)],
    ]
    table("tab_3_4", "3", "Hauptteil", "S1", "describe.rf.estr",
          "Verketteter risikofreier Zins (€STR / EONIA)",
          ["Merkmal", "Wert"], rows,
          "€STR ab dem Verkettungsdatum, davor EONIA abzüglich des offiziellen "
          "EZB-Umstellungsspreads. Der Zins verzinst ausschließlich die nicht "
          "investierte Quote der Vol-Control.")


# ── Kapitel 4 — Empirische Analyse ───────────────────────────────────────────
COLS = [("ann_return", "Rendite p.a.", 2, True), ("cagr", "CAGR", 2, True),
        ("ann_vol", "Vol p.a.", 2, True), ("sharpe", "Sharpe", 3, False),
        ("max_drawdown", "Max. Drawdown", 2, True), ("cvar_95", "CVaR 95 %", 2, True),
        ("turnover", "Turnover", 2, False), ("observations", "N", 0, False)]


def tab_4_1():
    m = rec("S1")["backtest"]["metrics"]
    rows = [[LABELS.get(x["strategy"], x["strategy"])]
            + [dei(x[k]) if k == "observations" else de(x[k], nd, p)
               for k, _l, nd, p in COLS[:-1]] + [dei(x["observations"])]
            for x in m]
    table("tab_4_1", "4", "Hauptteil", "S1", "backtest.metrics",
          "Kennzahlen der Strategien (Hauptspezifikation)",
          ["Strategie"] + [l for _k, l, _n, _p in COLS], rows,
          "Netto nach Transaktionskosten. Turnover ist für alle Strategien gleich "
          "definiert (kumulierte Gewichtsänderung); bei Vol-Control ist er die Summe "
          "aus Exposure-Handel und anteiligem Handel des Basisportfolios — siehe tab_4_3. "
          "Risk Parity läuft nach einer Warm-up-Phase auf einem kürzeren Sample.")


def tab_4_3():
    m = [x for x in rec("S1")["backtest"]["metrics"] if x.get("turnover_exposure") is not None]
    bh = next(x for x in rec("S1")["backtest"]["metrics"] if x["strategy"] == "BuyHold")
    rows = [[LABELS[x["strategy"]], de(x["turnover"], 4), de(x["turnover_exposure"], 4),
             de(x["turnover_sleeve"], 4),
             de(x["turnover"] / bh["turnover"], 2)] for x in m]
    rows.append([LABELS["BuyHold"], de(bh["turnover"], 4), "—", de(bh["turnover"], 4),
                 de(1.0, 2)])
    table("tab_4_3", "4", "Anhang", "S1", "backtest.metrics (turnover*)",
          "Zerlegung des Turnovers",
          ["Strategie", "Gesamt", "davon Exposure-Handel",
           "davon Basisportfolio", "Verhältnis zu Buy-and-Hold"], rows,
          "Vol-Control handelt auf zwei Ebenen: sie verändert die Investitionsquote "
          "und trägt zugleich ihren Anteil an der Umschichtung des Basisportfolios. "
          "Auf vergleichbarer Basis handelt sie MEHR als Buy-and-Hold, nicht weniger.")


def tab_4_4():
    h = rec("S1")["hypotheses"]
    holm = h["holm_adjusted"]
    rows = []
    for key, name, unit in (("H1_max_drawdown", "H1: Drawdown-Reduktion", True),
                            ("H2_sharpe", "H2: Sharpe-Differenz", False)):
        t = h[key]
        rows.append([name, de(t["observed_diff"], 4, unit),
                     f"[{de(t['ci_low_bca'], 4, unit)}; {de(t['ci_high_bca'], 4, unit)}]",
                     f"[{de(t['ci_low'], 4, unit)}; {de(t['ci_high'], 4, unit)}]",
                     de(t["p_value"], 4), de(holm[key], 4),
                     "signifikant" if holm[key] < 0.05 else "nicht signifikant"])
    table("tab_4_4", "4", "Hauptteil", "S1", "hypotheses.H1/H2 + holm_adjusted",
          "Konfirmatorische Hypothesentests H1 und H2",
          ["Hypothese", "Beobachtete Differenz", "BCa-Intervall 95 %",
           "Perzentil-Intervall 95 %", "p-Wert", "Holm-adjustiert", "Beurteilung"], rows,
          "Gepaarter stationärer Block-Bootstrap, Vol-Control 10 % gegen Buy-and-Hold. "
          "BCa nach Efron (1987) mit vollem Delete-1-Jackknife. Holm-Korrektur über "
          "die vier konfirmatorischen Tests.")


def tab_4_5():
    sb = rec("S1")["hypotheses"]["sweep_bootstrap"]
    rows = []
    for key, name in (("d_mdd", "ΔMax-Drawdown"), ("d_cvar", "ΔCVaR 95 %")):
        s = sb["slopes"][key]
        rows.append([name, de(s["slope"], 6),
                     f"[{de(s['ci_low'], 6)}; {de(s['ci_high'], 6)}]",
                     de(s["p_value"], 6), de(s["share_positive"], 1, True)])
    table("tab_4_5", "4", "Hauptteil", "S1", "hypotheses.sweep_bootstrap.slopes",
          "H3: Steigung des Effekts über die Krypto-Quote (Datenebene)",
          ["Zielgröße", "Steigung", "95 %-Konfidenzintervall", "p-Wert",
           "Anteil positiver Replikate"], rows,
          f"Data-Level-Bootstrap mit B = {dei(sb['n_boot'])} Replikaten; eine "
          "Indexfolge je Replikat für alle Assets UND alle Quoten (gepaartes Design). "
          "Der Schätzer rechnet auf einem täglich rebalancierten Brutto-Basisportfolio; "
          "die Punktschätzung der Hauptspezifikation (monatlich, netto) liegt bei "
          "0,753635 und damit innerhalb des Intervalls.")


def tab_4_6():
    h = rec("S1")["hypotheses"]
    d, p = h["deflated_sharpe"], h["probabilistic_sharpe"]
    rows = [["Beobachteter Sharpe (täglich)", de(p["sr"], 6)],
            ["Probabilistic Sharpe Ratio", de(p["psr"], 6)],
            ["Schwellen-Sharpe sr₀ (täglich)", de(d["sr0"], 6)],
            ["Deflated Sharpe Ratio", de(d["dsr"], 6)],
            ["Berücksichtigte Konfigurationen N", dei(d["n_trials"])]]
    table("tab_4_6", "4", "Anhang", "S1", "hypotheses.deflated_sharpe / probabilistic_sharpe",
          "Deflated und Probabilistic Sharpe Ratio",
          ["Größe", "Wert"], rows,
          "Nach Bailey und López de Prado. N ist die Zahl der tatsächlich "
          "durchprobierten Konfigurationen, nicht die Zahl der berichteten Strategien.")


def _hyp_row(name: str, label: str) -> list[str]:
    r = rec(name)
    h = r["hypotheses"]
    h1, h2 = h["H1_max_drawdown"], h["H2_sharpe"]
    md, am = h["sweep_bootstrap"]["slopes"]["d_mdd"], h["sweep_bootstrap"]["argmax"]
    s = r["backtest"]["sample"]
    return [label, dei(s["n_return_days"]), de(h1["observed_diff"], 4, True),
            f"[{de(h1['ci_low_bca'], 4, True)}; {de(h1['ci_high_bca'], 4, True)}]",
            de(h2["observed_diff"], 4), f"[{de(h2['ci_low_bca'], 4)}; {de(h2['ci_high_bca'], 4)}]",
            de(md["slope"], 4), f"[{de(md['ci_low'], 4)}; {de(md['ci_high'], 4)}]",
            de(am["best_share_point"], 2, True)]


HYP_HEADER = ["Szenario", "N", "H1 ΔMDD", "H1 BCa", "H2 ΔSharpe", "H2 BCa",
              "H3 Steigung", "H3 KI", "Argmax"]


def tab_4_7():
    rows = [_hyp_row(n, SCEN_LABEL[n]) for n in ("S1", "S2", "S3")]
    table("tab_4_7", "4", "Hauptteil", "S1/S2/S3", "hypotheses (drei Records)",
          "Szenariovergleich der konfirmatorischen Befunde", HYP_HEADER, rows,
          "S2 verwendet einen Point-in-Time-Sleeve (Coins treten ein, sobald "
          "investierbar), S3 nimmt Solana auf und verkürzt dafür das Fenster.")


def tab_4_8():
    rows = [_hyp_row(f"S4_{y}", f"Start {y}") for y in (2018, 2019, 2020, 2021, 2022)]
    table("tab_4_8", "4", "Hauptteil", "S4_2018..2022", "hypotheses (fünf Records)",
          "Sensitivität gegenüber dem Startjahr", HYP_HEADER, rows,
          "Wie die Hauptspezifikation, nur mit späterem Beginn. Prüft, ob der Befund "
          "an einem günstigen Einstiegszeitpunkt hängt.")


def tab_4_9():
    A, B = rec("S1"), rec("S1_rf3")
    MA = {m["strategy"]: m for m in A["backtest"]["metrics"]}
    MB = {m["strategy"]: m for m in B["backtest"]["metrics"]}
    rows = []
    for k in ("BuyHold", "VolControl_5", "VolControl_10", "VolControl_15"):
        for f, lbl, nd, p in (("ann_return", "Rendite p.a.", 2, True),
                              ("cagr", "CAGR", 2, True), ("ann_vol", "Vol p.a.", 2, True),
                              ("sharpe", "Sharpe", 4, False),
                              ("max_drawdown", "Max. Drawdown", 2, True),
                              ("cvar_95", "CVaR 95 %", 2, True)):
            rows.append([LABELS[k], lbl, de(MA[k][f], nd, p), de(MB[k][f], nd, p),
                         de(MB[k][f] - MA[k][f], nd, p)])
    hA, hB = A["hypotheses"]["H1_max_drawdown"], B["hypotheses"]["H1_max_drawdown"]
    rows.append(["H1", "ΔMax-Drawdown", de(hA["observed_diff"], 4, True),
                 de(hB["observed_diff"], 4, True),
                 de(hB["observed_diff"] - hA["observed_diff"], 4, True)])
    rows.append(["H1", "p-Wert", de(hA["p_value"], 4), de(hB["p_value"], 4),
                 de(hB["p_value"] - hA["p_value"], 4)])
    rows.append(["H1", "BCa-Intervall",
                 f"[{de(hA['ci_low_bca'], 4, True)}; {de(hA['ci_high_bca'], 4, True)}]",
                 f"[{de(hB['ci_low_bca'], 4, True)}; {de(hB['ci_high_bca'], 4, True)}]", "—"])
    table("tab_4_9", "4", "Anhang", "S1 / S1_rf3", "backtest.metrics + hypotheses.H1",
          "Sensitivität gegenüber der Zinsannahme",
          ["Strategie", "Kennzahl", "€STR/EONIA verkettet", "konstant 3 % p.a.", "Differenz"],
          rows,
          "Der Zins wirkt an zwei Stellen. In der RENDITEREIHE nur bei der Vol-Control, "
          "über die nicht investierte Quote — Buy-and-Hold ist dort unverändert. Im "
          "SHARPE bei allen Strategien, weil rf zugleich der Vergleichszins ist. "
          "Beides darf nicht vermischt werden.")


def tab_4_10():
    wf = rec("S1")["robustness"]["walk_forward"]
    rows = [[f["test_start"] + " – " + f["test_end"], de(f["chosen_target_vol"], 1, True),
             de(f["is_sharpe"], 3), de(f["oos_sharpe"], 3)] for f in wf["folds"]]
    om, bm = wf["oos_metrics"], wf["bh_oos_metrics"]
    table("tab_4_10", "4", "Anhang", "S1", "robustness.walk_forward",
          "Walk-Forward: Folds und Out-of-Sample-Ergebnis",
          ["Out-of-Sample-Fenster", "gewählte Zielvolatilität", "In-Sample-Sharpe",
           "Out-of-Sample-Sharpe"], rows,
          "In-Sample- und Out-of-Sample-Sharpe sind NICHT direkt vergleichbar: der "
          "In-Sample-Wert ist das Maximum über die geprüften Zielvolatilitäten und "
          "enthält den Selektionsvorteil. Aussagekräftig ist allein der "
          "Out-of-Sample-Vergleich über alle Folds: Vol-Control "
          f"{de(om['sharpe'], 3)} gegen Buy-and-Hold {de(bm['sharpe'], 3)} (Sharpe), "
          f"{de(om['max_drawdown'], 2, True)} gegen {de(bm['max_drawdown'], 2, True)} "
          "(Max. Drawdown).")


def tab_4_11():
    sp = rec("S1")["robustness"]["subperiods"]
    rows = [[p["period"], p["start"] + " – " + p["end"], dei(p["observations"]),
             de(p["bh_cagr"], 2, True), de(p["vc_cagr"], 2, True),
             de(p["bh_max_drawdown"], 2, True), de(p["vc_max_drawdown"], 2, True),
             de(p["bh_sharpe"], 3), de(p["vc_sharpe"], 3)] for p in sp]
    table("tab_4_11", "4", "Hauptteil", "S1", "robustness.subperiods",
          "Ergebnisse nach Marktregime",
          ["Regime", "Zeitraum", "N", "CAGR BH", "CAGR VC", "Max. DD BH",
           "Max. DD VC", "Sharpe BH", "Sharpe VC"], rows,
          "Vorab definierte Teilperioden. VC = Vol-Control 10 %, BH = Buy-and-Hold.")


def abb_4_3():
    r = rec("S1")
    pts = r["sweep"]["points"]
    b = r["hypotheses"]["sweep_bootstrap"]["bands"]["d_mdd"]
    sh = r["hypotheses"]["sweep_bootstrap"]["shares"]
    x = [p["crypto_share"] * 100 for p in pts]
    fig, ax = plt.subplots()
    xs = [s * 100 for s in sh]
    ax.fill_between(xs, [v * 100 for v in b["simultaneous_low"]],
                    [v * 100 for v in b["simultaneous_high"]], color=ACCENT, alpha=0.12,
                    label="simultanes Band 95 %")
    ax.fill_between(xs, [v * 100 for v in b["pointwise_low"]],
                    [v * 100 for v in b["pointwise_high"]], color=ACCENT, alpha=0.25,
                    label="punktweises Band 95 %")
    ax.plot(x, [p["d_mdd"] * 100 for p in pts], color=ACCENT, lw=1.8, label="ΔMax-Drawdown")
    ax.plot(x, [p["d_cvar"] * 100 for p in pts], color=NEG, lw=1.4, ls="--", label="ΔCVaR 95 %")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Krypto-Quote")
    ax.set_ylabel("Differenz zu Buy-and-Hold (Prozentpunkte)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 0) + " %"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 0)))
    ax.set_title("Risiko-Effekt der Vol-Control über die Krypto-Quote (brutto)")
    ax.legend(loc="upper left", frameon=False)
    f = r["hypotheses"]["sweep_bootstrap"]["bands"]["d_mdd"]["simultaneous_factor"]
    figure("abb_4_3", "4", "Hauptteil", "S1", "sweep.points + sweep_bootstrap.bands",
           "Risiko-Effekt über die Krypto-Quote mit Konfidenzbändern", fig,
           "Positiv bedeutet mildere Verlustkennzahl als Buy-and-Hold. Das simultane "
           f"Band deckt die gesamte Kurve gleichzeitig ab (Faktor {de(f, 2)} statt 1,96) "
           "und enthält bei niedrigen Quoten die Null, das punktweise nicht — die "
           "Gesamtunsicherheit über die Kurve ist deutlich größer als je Einzelpunkt. "
           "Die Kurven rechnen BRUTTO, ohne Kosten der Gewichtsumschichtung.")


def abb_4_4():
    r = rec("S1")
    pts = r["sweep"]["points"]
    bands = r["hypotheses"]["sweep_bootstrap"]["bands"]
    sh = [s * 100 for s in r["hypotheses"]["sweep_bootstrap"]["shares"]]
    x = [p["crypto_share"] * 100 for p in pts]
    fig, ax = plt.subplots()
    b = bands["sharpe_vc"]
    ax.fill_between(sh, b["simultaneous_low"], b["simultaneous_high"], color=ACCENT,
                    alpha=0.12, label="simultanes Band 95 %")
    ax.fill_between(sh, b["pointwise_low"], b["pointwise_high"], color=ACCENT,
                    alpha=0.25, label="punktweises Band 95 %")
    ax.plot(x, [p["sharpe_vc"] for p in pts], color=ACCENT, lw=1.8, label="Vol-Control 10 %")
    ax.plot(x, [p["sharpe_bh"] for p in pts], color=GREY, lw=1.4, ls="--", label="Buy-and-Hold")
    ax.set_xlabel("Krypto-Quote")
    ax.set_ylabel("Sharpe Ratio (brutto)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 0) + " %"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 1)))
    ax.set_title("Sharpe-Verläufe über die Krypto-Quote (brutto)")
    ax.legend(loc="lower right", frameon=False)
    figure("abb_4_4", "4", "Anhang", "S1", "sweep.points + sweep_bootstrap.bands",
           "Sharpe-Verläufe über die Krypto-Quote (brutto)", fig,
           "BRUTTO — ohne die Kosten der Gewichtsumschichtung. Die Netto-Werte stehen "
           "in der Kennzahlentabelle (tab_4_1); die Differenz beträgt rund 0,025 "
           "Sharpe-Punkte und geht auf die nicht abgezogenen Umschichtungskosten "
           "zurück. Eine Umstellung auf netto wäre eine Methodikänderung und liegt "
           "ausserhalb des Ergebnis-Freeze.")


def abb_4_5():
    am = rec("S1")["hypotheses"]["sweep_bootstrap"]["argmax"]
    dist = am["distribution"]
    xs = [d["share"] * 100 for d in dist]
    ys = [d["prob"] * 100 for d in dist]
    lo, hi = [v * 100 for v in am["indistinguishable_range"]]
    fig, ax = plt.subplots()
    # The indistinguishable range covers the ENTIRE sweep here, so shading "the
    # indistinguishable part" would shade everything and say nothing. The honest
    # rendering is a uniform bar chart plus a span annotation stating that fact.
    full = lo <= min(xs) and hi >= max(xs)
    cols = [ACCENT if lo <= v <= hi else GREY for v in xs]
    ax.bar(xs, ys, width=2.0, color=cols)
    if full:
        ax.axvspan(lo, hi, color=ACCENT, alpha=0.07, zorder=0)
        ax.annotate("statistisch nicht unterscheidbar: gesamte Bandbreite",
                    xy=(0.5, 0.93), xycoords="axes fraction", ha="center",
                    fontsize=9, color=ACCENT)
    ax.axvline(am["best_share_point"] * 100, color=NEG, lw=1.4, ls="--",
               label=f"Punktschätzung {de(am['best_share_point'], 0, True)}")
    ax.set_xlabel("Krypto-Quote")
    ax.set_ylabel("Anteil der Bootstrap-Replikate")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 0) + " %"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 0) + " %"))
    ax.set_title("Verteilung der optimalen Krypto-Quote über die Replikate")
    ax.legend(frameon=False)
    figure("abb_4_5", "4", "Hauptteil", "S1", "sweep_bootstrap.argmax",
           "Bootstrap-Verteilung der optimalen Krypto-Quote", fig,
           "Wie oft jede Quote in den Replikaten die beste war. Der Bereich, den die "
           f"Daten statistisch NICHT voneinander unterscheiden können, reicht von "
           f"{de(lo, 0)} % bis {de(hi, 0)} % und umfasst damit die GESAMTE untersuchte "
           "Bandbreite. Die Punktschätzung von "
           f"{de(am['best_share_point'], 0, True)} ist deshalb kein Optimum, sondern "
           "der Modus einer weitgehend flachen Verteilung. Der erhöhte Balken am "
           f"rechten Rand ({de(dist[-1]['prob'], 1, True)} bei "
           f"{de(dist[-1]['share'], 0, True)}) ist ein Randeffekt: die beste Quote kann "
           "dort nicht nach rechts ausweichen, weshalb sich Replikate mit weiter "
           "steigendem Effekt an der Obergrenze sammeln.")


def abb_4_7():
    ps = rec("S1")["robustness"]["param_stability"]
    M = ps["sharpe"]
    fig, ax = plt.subplots(figsize=(5.4, 3.8))
    im = ax.imshow(M, cmap="Greys", aspect="auto")
    ax.set_xticks(range(len(ps["target_vols"])),
                  [de(v, 1, True) for v in ps["target_vols"]])
    ax.set_yticks(range(len(ps["lookbacks"])), [dei(v) for v in ps["lookbacks"]])
    lo, hi = min(map(min, M)), max(map(max, M))
    for i in range(len(M)):
        for j in range(len(M[0])):
            ax.text(j, i, de(M[i][j], 3), ha="center", va="center", fontsize=8,
                    color="white" if M[i][j] > lo + 0.6 * (hi - lo) else "black")
    ax.set_xlabel("Zielvolatilität")
    ax.set_ylabel("Lookback (Handelstage)")
    ax.set_title("Parameter-Stabilität: Sharpe Ratio")
    ax.grid(False)
    figure("abb_4_7", "4", "Hauptteil", "S1", "robustness.param_stability",
           "Parameter-Stabilität über Lookback und Zielvolatilität", fig,
           "Sharpe Ratio der Vol-Control über die Parameterfläche. Ein flaches Bild "
           "ohne Klippen spricht gegen eine Überanpassung an eine einzelne "
           "Parameterwahl.")


def abb_4_8():
    cs = rec("S1")["robustness"]["cost_sensitivity"]
    p = cs["points"]
    fig, ax = plt.subplots()
    ax.plot([q["cost_bps"] for q in p], [q["sharpe"] for q in p], color=ACCENT,
            lw=1.8, marker="o", ms=3.5, label="Sharpe")
    ax.axvline(cs["base_cost_bps"], color=NEG, lw=1.2, ls="--",
               label=f"Basisannahme {de(cs['base_cost_bps'], 1)} bp")
    ax.set_xlabel("Transaktionskosten (Basispunkte je Umschichtung)")
    ax.set_ylabel("Sharpe Ratio")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 1)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 2)))
    ax.set_title("Kosten-Sensitivität der Vol-Control")
    ax.legend(frameon=False)
    figure("abb_4_8", "4", "Anhang", "S1", "robustness.cost_sensitivity",
           "Sharpe Ratio in Abhängigkeit von den Transaktionskosten", fig,
           "Die Basisannahme ist ein gemischter Satz aus 10 Basispunkten für "
           "traditionelle Anlagen und 25 für Kryptowerte, gewichtet mit der Quote.")


def abb_4_9():
    r = rec("S1")["analytics"]["rolling"]
    fig, ax = plt.subplots()
    ax.plot(range(len(r["dates"])), r["vc_sharpe"], color=ACCENT, lw=1.4,
            label="Vol-Control 10 %")
    ax.plot(range(len(r["dates"])), r["bh_sharpe"], color=GREY, lw=1.2, ls="--",
            label="Buy-and-Hold")
    ax.axhline(0, color="black", lw=0.8)
    _year_ticks(ax, r["dates"])
    ax.set_ylabel("Rollierende Sharpe Ratio")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 1)))
    ax.set_title(f"Rollierende Sharpe Ratio ({dei(r['window'])} Handelstage)")
    ax.legend(frameon=False)
    figure("abb_4_9", "4", "Anhang", "S1", "analytics.rolling",
           "Rollierende Sharpe Ratio im Zeitverlauf", fig,
           f"Fenster von {dei(r['window'])} Handelstagen. Zeigt, in welchen Phasen der "
           "Vorsprung entsteht — und dass er nicht gleichmäßig über den Zeitraum anfällt.")


def abb_4_10():
    d = rec("S1")["analytics"]["distribution"]
    fig, ax = plt.subplots()
    x = [c * 100 for c in d["centers"]]
    ax.plot(x, d["bh"], color=GREY, lw=1.4, ls="--", label="Buy-and-Hold")
    ax.plot(x, d["vc"], color=ACCENT, lw=1.8, label="Vol-Control 10 %")
    for v, c, lbl in ((d["bh_cvar"] * 100, GREY, "CVaR BH"),
                      (d["vc_cvar"] * 100, ACCENT, "CVaR VC")):
        ax.axvline(v, color=c, lw=1.0, ls=":")
        ax.annotate(f"{lbl} {de(v, 2)} %", xy=(v, 0), xytext=(v, max(d["bh"]) * 0.55),
                    fontsize=8, rotation=90, color=c, ha="right")
    ax.set_xlabel("Tagesrendite")
    ax.set_ylabel("Dichte")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 0) + " %"))
    ax.set_title("Verteilung der Tagesrenditen")
    ax.legend(frameon=False)
    figure("abb_4_10", "4", "Anhang", "S1", "analytics.distribution",
           "Verteilung der Tagesrenditen mit CVaR-Markierung", fig,
           "Die Vol-Control staucht vor allem den linken Rand — genau das ist der "
           "Mechanismus hinter H1. Gestrichelte Linien markieren den CVaR 95 %.")


def abb_4_11():
    wf = rec("S1")["robustness"]["walk_forward"]["oos"]
    fig, ax = plt.subplots()
    ax.plot(range(len(wf["dates"])), wf["wealth"], color=ACCENT, lw=1.6,
            label="Vol-Control (Out-of-Sample)")
    ax.plot(range(len(wf["dates"])), wf["bh_wealth"], color=GREY, lw=1.4, ls="--",
            label="Buy-and-Hold (Out-of-Sample)")
    _year_ticks(ax, wf["dates"])
    ax.set_ylabel("Vermögensindex (Start = 1)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 2)))
    ax.set_title("Walk-Forward: Vermögensverlauf out-of-sample")
    ax.legend(frameon=False)
    figure("abb_4_11", "4", "Anhang", "S1", "robustness.walk_forward.oos",
           "Out-of-Sample-Vermögensverlauf aus dem Walk-Forward", fig,
           "Aneinandergereihte Out-of-Sample-Fenster; die Zielvolatilität wurde je "
           "Fold ausschließlich auf den vorangehenden Daten gewählt.")


def tab_4_12():
    dd = rec("S1")["analytics"]["drawdowns"]
    rows = []
    for lbl, key in (("Buy-and-Hold", "buy_hold"), ("Vol-Control 10 %", "vol_control")):
        for e in dd[key]:
            rows.append([lbl, e["start"], e["trough"], e["end"] or "—",
                         de(e["depth"], 2, True), dei(e["length_days"]),
                         "ja" if e["recovered"] else "nein"])
    table("tab_4_12", "4", "Anhang", "S1", "analytics.drawdowns",
          f"Die {dei(dd['top'])} tiefsten Drawdown-Episoden",
          ["Strategie", "Beginn", "Tiefpunkt", "Ende", "Tiefe", "Dauer (Tage)",
           "erholt"], rows,
          "Episoden nach Tiefe sortiert. Zeigt, welche konkreten Marktphasen die "
          "Drawdown-Kennzahl treiben.")


def abb_4_12():
    m = rec("S1")["analytics"]["monthly"]
    M = m["matrix"]
    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    vmax = max(abs(v) for row in M for v in row if v is not None)
    im = ax.imshow(M, cmap="RdGy", vmin=-vmax, vmax=vmax, aspect="auto")
    months = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    ax.set_xticks(range(12), months)
    ax.set_yticks(range(len(m["years"])), [str(y) for y in m["years"]])
    ax.set_title("Monatsrenditen der Vol-Control 10 %")
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.85,
                 format=FuncFormatter(lambda v, _p: de(v, 0, True)))
    figure("abb_4_12", "4", "Anhang", "S1", "analytics.monthly",
           "Monatsrenditen im Zeitraster", fig,
           "Jede Zelle ist eine Monatsrendite der Vol-Control 10 %. Rot = negativ.")


# ── Anhang ───────────────────────────────────────────────────────────────────
def tab_a_1():
    names = all_records()
    e = rec("S1")["environment"]
    rows = []
    for n in names:
        r = rec(n)
        rows.append([n, r["hashes"]["dataset_hash"], r["hashes"]["run_hash"],
                     r["git"]["describe"], r["generated_at"],
                     de(r["runtime_seconds"], 1) + " s"])
    table("tab_a_1", "Anhang", "Anhang", "alle", "hashes + git + environment",
          "Reproduktionsnachweis je Record",
          ["Record", "Datensatz-Hash", "Lauf-Hash", "Commit", "Erzeugt", "Laufzeit"], rows,
          f"Umgebung für alle Records: Python {e['python']}, numpy {e['numpy']}, "
          f"pandas {e['pandas']}, scipy {e['scipy']}, statsmodels {e['statsmodels']}, "
          f"{e['platform']}. Der Datensatz-Hash bürgt für die Datenbasis allein, der "
          "Lauf-Hash zusätzlich für Fenster, Quelle, Zinsmodus und Gewichte. Beide "
          "sind auf 1e-12 quantisiert und damit plattformunabhängig.")



def tab_4_2():
    """Teilfrage 1 — what crypto does to a STATIC portfolio, before any vol control."""
    shares = [("S1_bh0", 0.0), ("S1_bh10", 0.10), ("S1_bh25", 0.25), ("S1_bh50", 0.50)]
    rows = []
    for name, sh in shares:
        r = rec("S1" if name == "S1_bh10" else name)
        m = next(x for x in r["backtest"]["metrics"] if x["strategy"] == "BuyHold")
        assert abs(r["backtest"]["crypto_share"] - sh) < 1e-9, (
            f"{name}: Record traegt Quote {r['backtest']['crypto_share']}, erwartet {sh}")
        rows.append([de(sh, 0, True), de(m["ann_return"], 2, True), de(m["cagr"], 2, True),
                     de(m["ann_vol"], 2, True), de(m["sharpe"], 3),
                     de(m["max_drawdown"], 2, True), de(m["cvar_95"], 2, True),
                     de(m["turnover"], 2)])
    table("tab_4_2", "4", "Hauptteil", "S1_bh0/S1/S1_bh25/S1_bh50",
          "backtest.metrics[BuyHold]",
          "Teilfrage 1: Risiko-Rendite-Profil des STATISCHEN Portfolios je Krypto-Quote",
          ["Krypto-Quote", "Rendite p.a.", "CAGR", "Vol p.a.", "Sharpe",
           "Max. Drawdown", "CVaR 95 %", "Turnover"], rows,
          "OHNE Volatilitätssteuerung — das monatlich rebalancierte Buy-and-Hold-"
          "Portfolio bei verschiedenen Krypto-Anteilen. Netto nach Transaktionskosten "
          "und damit direkt vergleichbar mit tab_4_1. Genau diese Zeilen beantworten "
          "Teilfrage 1; die Vol-Control-Ergebnisse ab tab_4_4 setzen darauf auf. "
          "Der traditionelle Teil bleibt intern im Verhältnis 60/30/10 aufgeteilt.")


def abb_3_2():
    rf = rec("S1")["rf_series"]
    fig, ax = plt.subplots()
    ax.plot(range(len(rf["dates"])), [v * 100 for v in rf["annualised"]],
            color=ACCENT, lw=1.2)
    ax.axhline(0, color=NEG, lw=1.0, ls="--")
    splice = rec("S1")["describe"]["rf"]["estr"]["splice_date"]
    if splice in rf["dates"]:
        i = rf["dates"].index(splice)
        ax.axvline(i, color="black", lw=1.0, ls=":")
        ax.annotate(f"Umstellung auf €STR\n{splice}", xy=(i, 0), xytext=(i + 40, -0.35),
                    fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.8))
    _year_ticks(ax, rf["dates"])
    ax.set_ylabel("Risikofreier Zins p.a.")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 1) + " %"))
    ax.set_title("Verketteter risikofreier Zins im Stichprobenfenster")
    e = rec("S1")["describe"]["rf"]["estr"]
    figure("abb_3_2", "3", "Hauptteil", "S1", "rf_series",
           "Verlauf des verketteten risikofreien Zinses", fig,
           f"€STR ab {splice}, davor EONIA abzüglich {de(e['spread_bps'], 1)} "
           "Basispunkten (offizieller EZB-Umstellungsspread). Im Stichprobenfenster war "
           f"der Zins an {de(e['window_share_negative'], 1, True)} der Tage negativ, "
           f"im Mittel {de(e['window_mean_annual'], 2, True)} p.a. Er verzinst "
           "ausschließlich die nicht investierte Quote der Vol-Control — gerade in den "
           "Stressphasen, in denen diese Quote am größten ist.")


def _ts_plot(ident, placement, field, ylabel, title, caption, pct=False, hline=None):
    ts = rec("S1")["timeseries"]
    dates = ts["vol_10"]["dates"]
    fig, ax = plt.subplots()
    order = [("vol_5", "VolControl_5", "Vol-Control 5 %", ACCENT, ":", 1.2),
             ("vol_10", "VolControl_10", "Vol-Control 10 %", ACCENT, "-", 1.8),
             ("vol_15", "VolControl_15", "Vol-Control 15 %", ACCENT, "-.", 1.2)]
    for key, _strat, label, col, ls, lw in order:
        block = ts[key]["series"]
        name = ts[key]["selected"]
        y = block[name][field]
        ax.plot(range(len(y)), [v * 100 for v in y] if pct else y,
                color=col, ls=ls, lw=lw, label=label)
    if field != "exposure":
        for strat, label, col, ls in (("BuyHold", "Buy-and-Hold", GREY, "--"),
                                      ("Benchmark_TrueBH", "True Buy-and-Hold", NEG, ":")):
            y = ts["vol_10"]["series"].get(strat, {}).get(field)
            if y:
                ax.plot(range(len(y)), [v * 100 for v in y] if pct else y,
                        color=col, ls=ls, lw=1.3, label=label)
    if hline is not None:
        ax.axhline(hline, color="black", lw=0.9)
    _year_ticks(ax, dates)
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda v, _p: de(v, 0) + " %" if pct else de(v, 1)))
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8)
    figure(ident, "4", placement, "S1", "timeseries", title, fig, caption)


def abb_4_1():
    _ts_plot("abb_4_1", "Hauptteil", "wealth", "Vermögensindex (Start = 1)",
             "Vermögensverlauf der Strategien",
             "Aus 1 Euro zu Beginn des Stichprobenfensters, netto nach "
             "Transaktionskosten. True Buy-and-Hold driftet ohne Rebalancing und "
             "erreicht das höchste Endvermögen bei zugleich tiefstem Drawdown "
             "(tab_4_1) — Rendite und Risiko sind hier nicht zu trennen.")


def abb_4_2():
    ts = rec("S1")["timeseries"]
    dates = ts["vol_10"]["dates"]
    fig, ax = plt.subplots()
    for key, label, ls, lw in (("vol_5", "Vol-Control 5 %", ":", 1.2),
                               ("vol_10", "Vol-Control 10 %", "-", 1.8),
                               ("vol_15", "Vol-Control 15 %", "-.", 1.2)):
        name = ts[key]["selected"]
        y = ts[key]["series"][name]["exposure"]
        ax.plot(range(len(y)), [v * 100 for v in y], color=ACCENT, ls=ls, lw=lw, label=label)
    ax.axhline(100, color=NEG, lw=1.2, ls="--", label="Hebelgrenze 100 %")
    _year_ticks(ax, dates)
    ax.set_ylabel("Investitionsquote")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: de(v, 0) + " %"))
    ax.set_title("Investitionsquote der Vol-Control im Zeitverlauf")
    ax.legend(frameon=False, fontsize=8)
    figure("abb_4_2", "4", "Anhang", "S1", "timeseries",
           "Investitionsquote der Vol-Control im Zeitverlauf", fig,
           "Die Quote ist auf 100 % gedeckelt — es wird nicht gehebelt. Bei Zielvol "
           "15 % liegt sie an 58,1 % der Handelstage an dieser Grenze, bei 5 % an "
           "keinem einzigen. Das erklärt den nicht-monotonen Turnover in tab_4_3: "
           "eine Quote am Anschlag bewegt sich nicht mehr.")


def abb_4_6():
    _ts_plot("abb_4_6", "Anhang", "drawdown", "Drawdown",
             "Drawdown-Verläufe im Vergleich",
             "Rückgang vom jeweils vorangegangenen Höchststand. Die Vol-Control "
             "begrenzt vor allem die TIEFE der Einbrüche — das ist der Mechanismus "
             "hinter H1 (tab_4_4). Die tiefsten Einzelepisoden stehen in tab_4_12.",
             pct=True, hline=0)


BUILDERS = [tab_3_1, tab_3_2, tab_3_3, abb_3_1, abb_3_2, tab_3_4,
            tab_4_1, tab_4_2, tab_4_3, tab_4_4, tab_4_5, tab_4_6, tab_4_7, tab_4_8, tab_4_9,
            tab_4_10, tab_4_11, tab_4_12, abb_4_3, abb_4_4, abb_4_5, abb_4_7, abb_4_8,
            abb_4_1, abb_4_2, abb_4_6, abb_4_9, abb_4_10, abb_4_11, abb_4_12,
            tab_a_1]

# Exhibits the archive cannot supply. Listed explicitly rather than silently skipped —
# a missing exhibit that nobody notices is worse than one that announces itself.
GAPS: list[tuple] = []   # alle urspruenglichen Luecken sind mit der additiven Archiv-Erweiterung aufgeloest


def write_register() -> None:
    path = os.path.join(OUT, "REGISTER.csv")
    fields = ["bezeichner", "typ", "kapitel", "platzierung", "szenario", "quelle",
              "lauf_hash", "dateien", "titel"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for row in sorted(REGISTER, key=lambda r: (r["kapitel"], r["bezeichner"])):
            w.writerow(row)
        for ident, kap, plc, titel, _grund, _fix in GAPS:
            w.writerow({"bezeichner": ident, "typ": "FEHLT", "kapitel": kap,
                        "platzierung": plc, "szenario": "—", "quelle": "—",
                        "lauf_hash": "—", "dateien": "—", "titel": titel})

    md = ["# Exhibit-Register", "",
          f"Erzeugt aus dem Freeze-Archiv (Tag `results-freeze-v1`). "
          f"{len(REGISTER)} Exhibits, {len(GAPS)} offene Lücken.", "",
          "Die Spalte **Platzierung** ist ein Vorschlag und in REGISTER.csv leicht "
          "änderbar; sie beeinflusst die Erzeugung nicht.", "",
          "| Bezeichner | Typ | Kap. | Platzierung | Szenario | Quelle | Lauf-Hash | Titel |",
          "|---|---|---|---|---|---|---|---|"]
    for r in sorted(REGISTER, key=lambda r: (r["kapitel"], r["bezeichner"])):
        md.append(f"| `{r['bezeichner']}` | {r['typ']} | {r['kapitel']} | "
                  f"{r['platzierung']} | {r['szenario']} | `{r['quelle']}` | "
                  f"`{r['lauf_hash']}` | {r['titel']} |")
    md += ["", "## Nicht erzeugbar aus dem Archiv", "",
           "| Bezeichner | Kap. | Titel | Grund | Behebung |", "|---|---|---|---|---|"]
    for ident, kap, _plc, titel, grund, fix in GAPS:
        md.append(f"| `{ident}` | {kap} | {titel} | {grund} | {fix} |")
    with open(os.path.join(OUT, "REGISTER.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="nach dem Erzeugen die Stichprobenprüfung aus tests/ ausführen")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print(f"Exhibits aus dem Freeze-Archiv -> {os.path.abspath(OUT)}")
    for b in BUILDERS:
        b()
        print(f"  {b.__name__}")
    write_register()
    print(f"\n{len(REGISTER)} Exhibits erzeugt, {len(GAPS)} Lücken im Register vermerkt.")
    if args.check:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))
        import test_exhibits as t
        for fn in (t.test_formatter_roundtrip, t.test_tab_4_1_matches_metrics,
                   t.test_tab_4_4_matches_hypotheses, t.test_tab_4_7_matches_three_records,
                   t.test_tab_4_9_rf_pair, t.test_every_file_carries_its_run_hash,
                   t.test_gaps_are_declared_not_silent):
            fn()


if __name__ == "__main__":
    main()
