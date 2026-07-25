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
  // Flag rows that do NOT span the full sample, so a shorter series is never
  // silently compared against the others.
  const maxN = Math.max(0, ...(data?.metrics ?? []).map((m) => m.observations ?? 0));
  const shortSample = (m: { observations?: number | null }) =>
    maxN > 0 && (m.observations ?? maxN) < maxN;

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
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap cursor-help"
                  title="Arithmetische annualisierte Durchschnittsrendite (Mittel der Tagesrenditen × Handelstage).">Rendite p.a.</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap cursor-help"
                  title="Compound Annual Growth Rate — geometrische, kompoundierte Jahresrendite aus dem Endvermögen.">CAGR</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap cursor-help"
                  title="Annualisierte Volatilität — Standardabweichung der Tagesrenditen × √Handelstage.">Vol</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap cursor-help"
                  title="Sharpe Ratio — Überrendite über den risikofreien Zins je Einheit Volatilität (annualisiert).">Sharpe</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap cursor-help"
                  title="Maximum Drawdown — größter Rückgang vom Höchststand zum darauffolgenden Tief.">Max DD</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap cursor-help"
                  title="Conditional Value-at-Risk (95 %) — erwarteter Verlust in den schlechtesten 5 % der Tage.">CVaR 95 %</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap cursor-help"
                  title="Turnover — kumulierte Σ|Δ Gewicht| bzw. Σ|Δ Exposure|. Constant-Mix und Risk-Parity handeln tatsächlich; nur True BH (Drift) hat echte Null.">Turnover</th>
              <th className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap cursor-help"
                  title="Anzahl Handelstage dieser Strategie. Risk-Parity verwirft eine Warm-up-Phase und läuft daher auf einem kürzeren Sample.">n</th>
            </tr>
          </thead>
          <tbody>
            {!data && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-faint">
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
                  <td className="px-3 py-2.5 text-right tabular-nums text-faint"
                      title={m.sharpe_gross != null ? `Sharpe brutto (ohne Kosten): ${num(m.sharpe_gross, 3)}` : undefined}>
                    {m.turnover > 0 ? num(m.turnover, 1) : "0,0"}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-faint"
                      style={shortSample(m) ? { color: "var(--color-warn, #b8843f)" } : undefined}
                      title={m.start && m.end ? `${m.start} – ${m.end}` : undefined}>
                    {m.observations != null ? m.observations.toLocaleString("de-DE") : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-faint text-xs mt-2">
        <strong>Turnover</strong> ist für alle gewichtsbasierten Strategien real gerechnet (Σ|Δ Gewicht|)
        und mit denselben Kostensätzen belastet wie die Vol-Control; nur <strong>True BH (Drift)</strong>
        hat echte Null. Ausgewiesen sind Netto-Kennzahlen — die Brutto-Sharpe (ohne Kosten) steht im
        Tooltip der Turnover-Spalte. <strong>n</strong> = Handelstage je Strategie; orange markierte
        Zeilen laufen auf einem <em>kürzeren</em> Fenster (Risk-Parity verwirft eine Warm-up-Phase)
        und sind daher nur eingeschränkt direkt vergleichbar.
        <br />
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
