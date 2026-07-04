"use client";

import type { HypothesesResponse } from "@/lib/types";
import { pval, isSignificant, numSigned, pctSigned, num } from "@/lib/format";
import SectionPlaceholder from "./SectionPlaceholder";

interface Props {
  data: HypothesesResponse | null;
  loading: boolean;
}

// Flat significance tag driven by the FAMILY-WISE (Holm-adjusted) p-value.
function Tag({ p }: { p: number }) {
  const sig = isSignificant(p);
  return (
    <span
      className="text-xs px-2 py-0.5 border nums whitespace-nowrap"
      style={{
        borderColor: sig ? "var(--color-accent)" : "var(--color-hairline-strong)",
        color: sig ? "var(--color-accent)" : "var(--color-muted)",
      }}
    >
      {sig ? "signifikant" : "nicht signifikant"}
    </span>
  );
}

export default function HypothesesPanel({ data, loading }: Props) {
  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">Hypothesen &amp; Inferenz</h2>
        <span className="eyebrow">α = 5 % · Holm-korrigiert</span>
      </div>

      {!data && (
        <SectionPlaceholder loading={loading} label="Hypothesentests laufen (Bootstrap)…" height={220} />
      )}

      {data && (
        <div className="space-y-4">
          {/* Deflated / Probabilistic Sharpe callout */}
          <div className="border border-hairline bg-panel px-4 py-3 grid sm:grid-cols-3 gap-4 card-hover">
            <div>
              <div className="eyebrow">Deflated Sharpe</div>
              <div className="text-xl nums mt-1" style={{ color: data.deflated_sharpe.dsr > 0.95 ? "var(--color-accent)" : undefined }}>
                {num(data.deflated_sharpe.dsr, 3)}
              </div>
              <div className="text-faint text-xs nums">nach {data.deflated_sharpe.n_trials} Konfigurationen</div>
            </div>
            <div>
              <div className="eyebrow">Probabilistic Sharpe</div>
              <div className="text-xl nums mt-1">{num(data.probabilistic_sharpe.psr, 3)}</div>
              <div className="text-faint text-xs nums">P(SR &gt; 0)</div>
            </div>
            <div className="text-faint text-xs leading-snug self-center">
              DSR &gt; 0,95 = der Sharpe überlebt die Mehrfachauswahl (Data-Snooping-Korrektur nach
              Bailey/López de Prado).
            </div>
          </div>

          {/* H1 / H2 */}
          <div className="border border-hairline bg-paper divide-y divide-hairline card-hover">
            {[
              {
                id: "H1",
                title: "Drawdown-Reduktion",
                detail: "Max Drawdown, Vol-Control vs. Buy-and-Hold (paired block bootstrap)",
                effectLabel: "ΔMDD",
                effect: pctSigned(data.H1_max_drawdown.observed_diff),
                bca: `BCa [${pctSigned(data.H1_max_drawdown.ci_low_bca)}, ${pctSigned(data.H1_max_drawdown.ci_high_bca)}]`,
                rawP: data.H1_max_drawdown.p_value,
                holmP: data.holm_adjusted["H1_max_drawdown"],
              },
              {
                id: "H2",
                title: "Sharpe-Differenz",
                detail: "Sharpe, Vol-Control vs. Buy-and-Hold (paired block bootstrap)",
                effectLabel: "ΔSharpe",
                effect: numSigned(data.H2_sharpe.observed_diff, 3),
                bca: `BCa [${numSigned(data.H2_sharpe.ci_low_bca, 3)}, ${numSigned(data.H2_sharpe.ci_high_bca, 3)}]`,
                rawP: data.H2_sharpe.p_value,
                holmP: data.holm_adjusted["H2_sharpe"],
              },
            ].map((r) => (
              <div key={r.id} className="px-4 py-3.5 grid grid-cols-[auto_1fr_auto] gap-4 items-center row-hover">
                <div className="display text-base text-accent w-9">{r.id}</div>
                <div className="min-w-0">
                  <div className="text-sm font-medium">{r.title}</div>
                  <div className="text-faint text-xs mt-0.5">{r.detail}</div>
                  <div className="text-faint text-xs mt-0.5 nums">{r.bca}</div>
                </div>
                <div className="text-right nums">
                  <div className="text-sm tabular-nums">
                    <span className="text-faint text-xs mr-2">{r.effectLabel}</span>
                    {r.effect}
                  </div>
                  <div className="flex items-center gap-2 justify-end mt-1">
                    <span className="text-faint text-xs tabular-nums">
                      p {pval(r.rawP)} · Holm {pval(r.holmP)}
                    </span>
                    <Tag p={r.holmP} />
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* H3 — three inferences side by side */}
          <div className="border border-hairline bg-paper card-hover">
            <div className="px-4 py-2.5 border-b border-hairline flex items-baseline gap-3">
              <span className="display text-base text-accent">H3</span>
              <span className="text-sm font-medium">Effekt steigt mit der Krypto-Quote</span>
              <span className="text-faint text-xs">— drei unabhängige Inferenzwege</span>
            </div>
            {[
              {
                label: "ΔMDD ~ Quote",
                hac: data.H3_dMDD_vs_share,
                mk: data.H3_dMDD_mann_kendall,
                boot: data.H3_dMDD_boot_slope,
                holmP: data.holm_adjusted["H3_dMDD_vs_share"],
              },
              {
                label: "ΔCVaR ~ Quote",
                hac: data.H3_dCVaR_vs_share,
                mk: data.H3_dCVaR_mann_kendall,
                boot: data.H3_dCVaR_boot_slope,
                holmP: data.holm_adjusted["H3_dCVaR_vs_share"],
              },
            ].map((r) => (
              <div key={r.label} className="px-4 py-3 border-b border-hairline last:border-0 row-hover">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{r.label}</span>
                  <Tag p={r.holmP} />
                </div>
                <div className="grid sm:grid-cols-3 gap-x-6 gap-y-1 mt-2 text-xs nums">
                  <div>
                    <span className="text-faint">HAC-OLS Steigung</span>{" "}
                    <span className="tabular-nums">{num(r.hac.slope, 3)}</span>{" "}
                    <span className="text-faint">(R² {num(r.hac.r2, 2)}, p {pval(r.hac.p_value)})</span>
                  </div>
                  <div>
                    <span className="text-faint">Mann-Kendall τ</span>{" "}
                    <span className="tabular-nums">{num(r.mk.tau, 2)}</span>{" "}
                    <span className="text-faint">(p {pval(r.mk.p_value)})</span>
                  </div>
                  <div>
                    <span className="text-faint">Boot-Steigung 95% KI</span>{" "}
                    <span className="tabular-nums">
                      [{num(r.boot.ci_low, 3)}, {num(r.boot.ci_high, 3)}]
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Wilcoxon supporting line */}
          <div className="border border-hairline bg-paper px-4 py-2.5 flex items-center justify-between text-xs text-muted nums">
            <span>Wilcoxon (tägliche Renditen, gepaart)</span>
            <span className="tabular-nums">
              Statistik {data.wilcoxon_daily.statistic.toLocaleString("de-DE")} · p {pval(data.wilcoxon_daily.p_value)} ·
              Holm {pval(data.holm_adjusted["wilcoxon_daily"])}
            </span>
          </div>
        </div>
      )}
      <p className="text-faint text-xs mt-2 leading-snug">
        Signifikanz auf Basis der <strong>Holm-korrigierten</strong> p-Werte (family-wise error). H1/H2:
        stationärer Block-Bootstrap mit BCa-Intervall. H3 mit drei robusten Verfahren (HAC-OLS,
        Mann-Kendall-Trend, Pair-Resampling-Steigung). Werte aus <code>hypotheses</code> der Engine.
      </p>
    </section>
  );
}
