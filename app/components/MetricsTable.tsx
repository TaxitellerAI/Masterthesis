"use client";

import type { BacktestResponse } from "@/lib/types";
import { pct, num, strategyLabel, isBenchmark } from "@/lib/format";

interface Props {
  data: BacktestResponse | null;
  loading: boolean;
  /** Currently selected target vol, to highlight the matching row. */
  selectedTargetVol: number;
}

export default function MetricsTable({ data, loading, selectedTargetVol }: Props) {
  const selectedKey = `VolControl_${Math.round(selectedTargetVol * 100)}`;

  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">Kennzahlen</h2>
        <span className="eyebrow">Buy-and-Hold · Vol-Control · Benchmarks</span>
      </div>

      <div className="border border-hairline bg-paper overflow-x-auto card-hover">
        <table className="w-full text-sm nums">
          <thead>
            <tr className="border-b border-hairline-strong text-muted">
              <th className="text-left font-semibold px-4 py-2.5 eyebrow">Strategie</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap">Rendite p.a.</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap">CAGR</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap">Vol</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap">Sharpe</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap">Max DD</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap">CVaR 95 %</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap">Turnover</th>
            </tr>
          </thead>
          <tbody>
            {!data && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-faint">
                  {loading ? "Berechnung läuft…" : "Keine Daten."}
                </td>
              </tr>
            )}
            {data?.metrics.map((m) => {
              const selected = m.strategy === selectedKey;
              const bench = isBenchmark(m.strategy);
              return (
                <tr
                  key={m.strategy}
                  className={`border-b border-hairline last:border-0 row-hover ${
                    selected ? "bg-accent-soft" : ""
                  } ${bench ? "text-muted" : ""}`}
                >
                  <td className="px-4 py-2.5 text-left whitespace-nowrap">
                    <span className={selected ? "text-accent font-semibold" : bench ? "italic" : "font-medium"}>
                      {strategyLabel(m.strategy)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{pct(m.ann_return)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{pct(m.cagr)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{pct(m.ann_vol)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{num(m.sharpe, 3)}</td>
                  <td
                    className="px-3 py-2.5 text-right tabular-nums"
                    style={m.mdd_breach ? { color: "var(--color-neg)", fontWeight: 600 } : undefined}
                    title={m.mdd_breach ? "Limit überschritten" : undefined}
                  >
                    {pct(m.max_drawdown)}
                  </td>
                  <td
                    className="px-3 py-2.5 text-right tabular-nums"
                    style={m.cvar_breach ? { color: "var(--color-neg)", fontWeight: 600 } : undefined}
                    title={m.cvar_breach ? "Limit überschritten" : undefined}
                  >
                    {pct(m.cvar_95)}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-faint">
                    {m.turnover > 0 ? num(m.turnover, 1) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-faint text-xs mt-2">
        Blau = gewählte Zielvolatilität; kursiv = alternative Benchmarks. Rot = gesetztes Risiko-Limit
        überschritten. <strong>Buy-and-Hold</strong> ist als Constant-Mix implementiert (feste Gewichte
        ≙ tägliches Rebalancing auf die Zielallokation); <strong>True BH (Drift)</strong> = einmalige
        Anlage ohne Rebalancing, Gewichte driften. <strong>Rendite p.a.</strong> arithmetisch,{" "}
        <strong>CAGR</strong> geometrisch (kompoundiert). Turnover = Σ|Δ Exposure|. Werte aus{" "}
        <code>backtest</code> der Engine.
      </p>
    </section>
  );
}
