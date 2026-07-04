"use client";

import type { RobustnessResponse } from "@/lib/types";
import { num, pct } from "@/lib/format";
import LineChart, { type Series } from "./LineChart";
import TimeSeriesChart from "./TimeSeriesChart";
import SectionPlaceholder from "./SectionPlaceholder";

interface Props {
  data: RobustnessResponse | null;
  loading: boolean;
  selectedTargetVol: number;
  selectedLookback?: number;
}

const ACCENT = "var(--color-accent)";

// Heatmap cell colour: interpolate empty→accent by rank within the grid.
function cellBg(v: number, lo: number, hi: number): string {
  const t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
  return `color-mix(in srgb, var(--color-accent) ${(t * 78 + 6).toFixed(0)}%, var(--color-paper))`;
}

export default function RobustnessSection({ data, loading, selectedTargetVol }: Props) {
  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">Robustheit</h2>
        <span className="eyebrow">Parameter · Kosten · Regime</span>
      </div>

      {!data && (
        <SectionPlaceholder loading={loading} label="Robustheits-Analysen laufen…" height={260} />
      )}

      {data && (
        <div className="space-y-6">
          {/* Walk-forward out-of-sample */}
          {data.walk_forward?.folds?.length > 0 && (
            <div className="grid lg:grid-cols-2 gap-5">
              <div className="border border-hairline bg-paper p-4 card-hover">
                <h3 className="text-sm font-semibold mb-1">Walk-Forward — Out-of-Sample</h3>
                <p className="text-faint text-xs mb-2">
                  Zielvol je Fold in-sample gewählt, dann rein OOS gemessen (Overfit-Test). OOS-Sharpe
                  VC {num(data.walk_forward.oos_metrics.sharpe ?? NaN, 2)} vs. BH{" "}
                  {num(data.walk_forward.bh_oos_metrics.sharpe ?? NaN, 2)}; OOS-MaxDD VC{" "}
                  {pct(data.walk_forward.oos_metrics.max_drawdown ?? NaN)} vs. BH{" "}
                  {pct(data.walk_forward.bh_oos_metrics.max_drawdown ?? NaN)}.
                </p>
                <TimeSeriesChart
                  dates={data.walk_forward.oos.dates}
                  series={[
                    { label: "VC (OOS)", color: "var(--color-accent)", values: data.walk_forward.oos.wealth },
                    { label: "BH (OOS)", color: "var(--color-faint)", dashed: true, values: data.walk_forward.oos.bh_wealth },
                  ]}
                  fmtY={(y) => y.toFixed(2)}
                  height={200}
                />
              </div>
              <div className="border border-hairline bg-paper p-4 card-hover overflow-x-auto">
                <h3 className="text-sm font-semibold mb-2">Folds</h3>
                <table className="w-full text-xs nums">
                  <thead>
                    <tr className="text-faint">
                      <th className="text-left px-2 py-1 font-semibold">OOS-Fenster</th>
                      <th className="text-right px-2 py-1 font-semibold">Zielvol</th>
                      <th className="text-right px-2 py-1 font-semibold">IS-Sharpe</th>
                      <th className="text-right px-2 py-1 font-semibold">OOS-Sharpe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.walk_forward.folds.map((f, i) => (
                      <tr key={i} className="border-t border-hairline row-hover">
                        <td className="px-2 py-1.5 text-left whitespace-nowrap">
                          {f.test_start} – {f.test_end}
                        </td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{(f.chosen_target_vol * 100).toFixed(0)}%</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-faint">{num(f.is_sharpe, 2)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{num(f.oos_sharpe, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Parameter stability heatmap + cost sensitivity, side by side */}
          <div className="grid lg:grid-cols-2 gap-5">
            <div className="border border-hairline bg-paper p-4 card-hover">
              <h3 className="text-sm font-semibold mb-1">Parameter-Stabilität — Sharpe</h3>
              <p className="text-faint text-xs mb-3">Lookback (Zeilen) × Zielvolatilität (Spalten). Kein Klippeneffekt = nicht overfit.</p>
              {(() => {
                const flat = data.param_stability.sharpe.flat();
                const lo = Math.min(...flat);
                const hi = Math.max(...flat);
                return (
                  <div className="overflow-x-auto">
                    <table className="text-xs nums border-collapse">
                      <thead>
                        <tr>
                          <th className="px-2 py-1 text-faint font-semibold text-left">LB \ Vol</th>
                          {data.param_stability.target_vols.map((tv) => (
                            <th key={tv} className="px-2 py-1 text-faint font-semibold text-right">
                              {(tv * 100).toFixed(1)}%
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.param_stability.sharpe.map((row, i) => (
                          <tr key={i}>
                            <td className="px-2 py-1 text-faint font-semibold text-right">
                              {data.param_stability.lookbacks[i]}
                            </td>
                            {row.map((v, j) => {
                              const isSel =
                                Math.abs(data.param_stability.target_vols[j] - selectedTargetVol) < 1e-6;
                              return (
                                <td
                                  key={j}
                                  className="px-2 py-1 text-right tabular-nums"
                                  style={{
                                    background: cellBg(v, lo, hi),
                                    outline: isSel ? "1.5px solid var(--color-ink)" : "none",
                                    outlineOffset: "-1.5px",
                                  }}
                                  title={`Lookback ${data.param_stability.lookbacks[i]}, Vol ${(
                                    data.param_stability.target_vols[j] * 100
                                  ).toFixed(1)}% → Sharpe ${v}`}
                                >
                                  {v.toFixed(2)}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                );
              })()}
            </div>

            <div className="border border-hairline bg-paper p-4 card-hover">
              <h3 className="text-sm font-semibold mb-1">Kosten-Sensitivität</h3>
              <p className="text-faint text-xs mb-2">
                Netto-Sharpe der Vol-Control über die Transaktionskosten (Basis {data.cost_sensitivity.base_cost_bps}{" "}
                bps). Überlebt der Vorteil höhere Krypto-Kosten?
              </p>
              <LineChart
                series={[
                  {
                    label: "Sharpe",
                    color: ACCENT,
                    points: data.cost_sensitivity.points.map((p) => ({ x: p.cost_bps, y: p.sharpe })),
                  } as Series,
                ]}
                fmtX={(x) => `${x.toFixed(0)}bps`}
                fmtY={(y) => y.toFixed(2)}
                zeroLine={false}
                height={200}
              />
            </div>
          </div>

          {/* Regime / sub-period breakdown */}
          <div>
            <h3 className="text-sm font-semibold mb-2">Regime-Analyse — Buy-and-Hold vs. Vol-Control</h3>
            <div className="border border-hairline bg-paper overflow-x-auto card-hover">
              <table className="w-full text-sm nums">
                <thead>
                  <tr className="border-b border-hairline-strong text-muted">
                    <th className="text-left px-4 py-2.5 eyebrow">Periode</th>
                    <th className="text-right px-3 py-2.5 eyebrow whitespace-nowrap">CAGR BH</th>
                    <th className="text-right px-3 py-2.5 eyebrow whitespace-nowrap">CAGR VC</th>
                    <th className="text-right px-3 py-2.5 eyebrow whitespace-nowrap">MaxDD BH</th>
                    <th className="text-right px-3 py-2.5 eyebrow whitespace-nowrap">MaxDD VC</th>
                    <th className="text-right px-3 py-2.5 eyebrow whitespace-nowrap">Sharpe BH</th>
                    <th className="text-right px-3 py-2.5 eyebrow whitespace-nowrap">Sharpe VC</th>
                  </tr>
                </thead>
                <tbody>
                  {data.subperiods.map((r) => (
                    <tr key={r.period} className="border-b border-hairline last:border-0 row-hover">
                      <td className="px-4 py-2.5 text-left">
                        <div className="font-medium">{r.period}</div>
                        <div className="text-faint text-xs nums">
                          {r.start} – {r.end}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{pct(r.bh_cagr)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{pct(r.vc_cagr)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{pct(r.bh_max_drawdown)}</td>
                      <td
                        className="px-3 py-2.5 text-right tabular-nums"
                        style={{ color: r.vc_max_drawdown > r.bh_max_drawdown ? "var(--color-accent)" : undefined }}
                      >
                        {pct(r.vc_max_drawdown)}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{num(r.bh_sharpe, 2)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{num(r.vc_sharpe, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-faint text-xs mt-2 leading-snug">
              Blau = Vol-Control mit milderem Max Drawdown als Buy-and-Hold in dieser Phase. Werte aus{" "}
              <code>robustness</code> der Engine.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
