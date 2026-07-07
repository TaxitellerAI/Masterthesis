"use client";

import type { AnalyticsResponse } from "@/lib/types";
import { pct } from "@/lib/format";
import TimeSeriesChart from "./TimeSeriesChart";
import DistributionChart from "./DistributionChart";
import MonthlyHeatmap from "./MonthlyHeatmap";
import SectionPlaceholder from "./SectionPlaceholder";

interface Props {
  data: AnalyticsResponse | null;
  loading: boolean;
}

const ACCENT = "var(--color-accent)";
const GREY = "var(--color-faint)";

// Restrained multi-series palette for the per-crypto correlation lines — muted
// institutional tones, accent blue leading.
const CORR_COLORS = ["#2b63b3", "#8a8f98", "#b8843f", "#4f7a5b", "#7a5b8a"];

function fmtDate(d: string) {
  return d.slice(0, 7); // YYYY-MM
}

export default function AnalyticsSection({ data, loading }: Props) {
  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">Analytik</h2>
        <span className="eyebrow">Rolling Sharpe · Verteilung · Monatskalender</span>
      </div>

      {!data && (
        <SectionPlaceholder loading={loading} label="Analytik wird berechnet…" height={240} />
      )}

      {data && (
        <div className="space-y-5">
          <div className="grid lg:grid-cols-2 gap-5">
            <div className="border border-hairline bg-paper p-4 card-hover">
              <h3 className="text-sm font-semibold mb-1">Rolling Sharpe ({data.rolling.window} Tage)</h3>
              <p className="text-faint text-xs mb-2">Stabilität über die Zeit — kein Einzelepisoden-Effekt.</p>
              <div className="flex gap-4 mb-1 text-xs text-muted nums">
                <span className="inline-flex items-center gap-1.5">
                  <svg width="16" height="6"><line x1="0" y1="3" x2="16" y2="3" stroke={ACCENT} strokeWidth="1.5" /></svg>
                  Vol-Control
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <svg width="16" height="6"><line x1="0" y1="3" x2="16" y2="3" stroke={GREY} strokeWidth="1.5" strokeDasharray="4 3" /></svg>
                  Buy-and-Hold
                </span>
              </div>
              <TimeSeriesChart
                dates={data.rolling.dates}
                series={[
                  { label: "Vol-Control", color: ACCENT, values: data.rolling.vc_sharpe },
                  { label: "Buy-and-Hold", color: GREY, dashed: true, values: data.rolling.bh_sharpe },
                ]}
                fmtY={(y) => y.toFixed(2)}
                zeroLine
                height={200}
              />
            </div>

            <div className="border border-hairline bg-paper p-4 card-hover">
              <h3 className="text-sm font-semibold mb-1">Verteilung der Tagesrenditen</h3>
              <p className="text-faint text-xs mb-2">
                Vol-Control komprimiert den linken Verlust-Tail. CVaR: BH {pct(data.distribution.bh_cvar)} · VC{" "}
                {pct(data.distribution.vc_cvar)}.
              </p>
              <DistributionChart data={data.distribution} />
            </div>
          </div>

          <div className="border border-hairline bg-paper p-4 card-hover">
            <h3 className="text-sm font-semibold mb-1">Monatsrenditen-Kalender — Vol-Control (%)</h3>
            <p className="text-faint text-xs mb-3">
              Blau = positiver Monat, rot = negativer. Rechte Spalte = Jahresrendite.
            </p>
            <MonthlyHeatmap data={data.monthly} />
          </div>

          {/* Rolling crypto–equity correlation: is the diversification premise stable? */}
          {data.correlation && Object.keys(data.correlation.series).length > 0 && (
            <div className="border border-hairline bg-paper p-4 card-hover">
              <h3 className="text-sm font-semibold mb-1">
                Rollierende Korrelation zu Aktien ({data.correlation.window} Tage)
              </h3>
              <p className="text-faint text-xs mb-2">
                Krypto vs. MSCI World. Steigt die Korrelation in Stressphasen gegen 1, bricht die
                Diversifikation genau dann weg, wenn sie gebraucht wird.
              </p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mb-1 text-xs text-muted nums">
                {Object.keys(data.correlation.series).map((name, i) => (
                  <span key={name} className="inline-flex items-center gap-1.5">
                    <svg width="16" height="6">
                      <line x1="0" y1="3" x2="16" y2="3" stroke={CORR_COLORS[i % CORR_COLORS.length]} strokeWidth="1.5" />
                    </svg>
                    {name}
                  </span>
                ))}
              </div>
              <TimeSeriesChart
                dates={data.correlation.dates}
                series={Object.entries(data.correlation.series).map(([name, values], i) => ({
                  label: name,
                  color: CORR_COLORS[i % CORR_COLORS.length],
                  values,
                }))}
                fmtY={(y) => y.toFixed(2)}
                zeroLine
                height={220}
              />
            </div>
          )}

          {/* Worst drawdown episodes side by side — the crisis-by-crisis evidence. */}
          {data.drawdowns && (
            <div className="border border-hairline bg-paper p-4 card-hover">
              <h3 className="text-sm font-semibold mb-1">
                Schwerste Drawdown-Episoden (Top {data.drawdowns.top})
              </h3>
              <p className="text-faint text-xs mb-3">
                Peak-zu-Tal je Strategie. Vol-Control sollte flachere, kürzere Einbrüche zeigen.
              </p>
              <div className="grid lg:grid-cols-2 gap-5">
                {(
                  [
                    { title: "Buy-and-Hold", rows: data.drawdowns.buy_hold },
                    { title: "Vol-Control", rows: data.drawdowns.vol_control },
                  ] as const
                ).map((tbl) => (
                  <div key={tbl.title}>
                    <div className="eyebrow mb-1.5">{tbl.title}</div>
                    <table className="w-full text-xs nums">
                      <thead>
                        <tr className="text-faint text-left">
                          <th className="font-medium pb-1">Tief</th>
                          <th className="font-medium pb-1 text-right">Tiefe</th>
                          <th className="font-medium pb-1 text-right">Dauer</th>
                          <th className="font-medium pb-1 text-right">Erholt</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tbl.rows.map((e) => (
                          <tr key={e.start} className="border-t border-hairline row-hover">
                            <td className="py-1 tabular-nums">{fmtDate(e.trough)}</td>
                            <td className="py-1 text-right tabular-nums" style={{ color: "var(--color-negative, #b3452b)" }}>
                              {pct(e.depth)}
                            </td>
                            <td className="py-1 text-right tabular-nums text-muted">{e.length_days} T</td>
                            <td className="py-1 text-right tabular-nums text-muted">
                              {e.recovered ? "✓" : "offen"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
