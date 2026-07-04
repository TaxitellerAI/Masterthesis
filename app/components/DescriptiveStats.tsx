"use client";

import type { DescribeResponse } from "@/lib/types";
import { pct, num, strategyLabel } from "@/lib/format";
import SectionPlaceholder from "./SectionPlaceholder";

interface Props {
  data: DescribeResponse | null;
  loading: boolean;
}

const COLS = [
  { key: "ann_return", label: "Rendite p.a.", fmt: (v: number) => pct(v) },
  { key: "ann_vol", label: "Vol p.a.", fmt: (v: number) => pct(v) },
  { key: "sharpe", label: "Sharpe", fmt: (v: number) => num(v, 3) },
  { key: "skew", label: "Schiefe", fmt: (v: number) => num(v, 2) },
  { key: "excess_kurtosis", label: "Kurtosis", fmt: (v: number) => num(v, 2) },
  { key: "max_drawdown", label: "Max DD", fmt: (v: number) => pct(v) },
  { key: "var_95", label: "VaR 95 %", fmt: (v: number) => pct(v) },
  { key: "cvar_95", label: "CVaR 95 %", fmt: (v: number) => pct(v) },
  { key: "pct_positive", label: "Pos. Tage", fmt: (v: number) => pct(v, 1) },
  { key: "trading_days", label: "Tage/J", fmt: (v: number) => String(v) },
  { key: "observations", label: "N", fmt: (v: number) => v.toLocaleString("de-DE") },
] as const;

// Greyscale shade for a correlation cell: |ρ| drives ink opacity, so structure
// reads at a glance without introducing a second colour.
function corrShade(v: number): string {
  const a = Math.min(Math.abs(v), 1) * 0.6;
  return `color-mix(in srgb, var(--color-ink) ${(a * 100).toFixed(0)}%, transparent)`;
}

export default function DescriptiveStats({ data, loading }: Props) {
  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">Deskriptive Statistik</h2>
        {data && (
          <span className="eyebrow">
            {data.source === "live" ? "Live · Yahoo Finance" : "Synthetisch"} · {data.base_currency}
          </span>
        )}
      </div>

      {!data && (
        <SectionPlaceholder loading={loading} label="Statistik wird berechnet…" height={220} />
      )}

      {data && (
        <div className="space-y-5">
          {/* Provenance / sample window */}
          <div className="flex flex-wrap gap-x-8 gap-y-1 text-xs text-muted nums border border-hairline bg-panel px-4 py-2.5">
            <span>
              Gemeinsames Fenster <span className="text-ink">{data.window.start ?? "—"}</span> –{" "}
              <span className="text-ink">{data.window.end ?? "—"}</span>
            </span>
            <span>
              Aligned N <span className="text-ink">{data.window.observations.toLocaleString("de-DE")}</span>
            </span>
            <span>
              Abgerufen{" "}
              <span className="text-ink">
                {new Date(data.fetched_at).toLocaleString("de-DE", {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
              </span>
            </span>
          </div>

          {/* Per-asset table */}
          <div className="border border-hairline bg-paper overflow-x-auto card-hover">
            <table className="w-full text-sm nums">
              <thead>
                <tr className="border-b border-hairline-strong text-muted">
                  <th className="text-left font-semibold px-4 py-2.5 eyebrow">Asset</th>
                  {COLS.map((c) => (
                    <th key={c.key} className="text-right font-semibold px-3 py-2.5 eyebrow whitespace-nowrap">
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.assets.map((a) => (
                  <tr key={a.asset} className="border-b border-hairline last:border-0 row-hover">
                    <td
                      className="px-4 py-2.5 text-left whitespace-nowrap font-medium"
                      title={`${a.first} – ${a.last}`}
                    >
                      {strategyLabel(a.asset)}
                    </td>
                    {COLS.map((c) => (
                      <td key={c.key} className="px-3 py-2.5 text-right tabular-nums">
                        {c.fmt(a[c.key] as number)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Calendar-year returns per asset */}
          {data.calendar?.yearly?.length > 0 && (
            <div>
              <div className="eyebrow mb-2">Jahresrenditen je Asset</div>
              <div className="border border-hairline bg-paper overflow-x-auto card-hover">
                <table className="text-xs nums w-full">
                  <thead>
                    <tr className="border-b border-hairline-strong text-muted">
                      <th className="px-3 py-2 text-left font-semibold eyebrow">Jahr</th>
                      {data.calendar.assets.map((a) => (
                        <th key={a} className="px-3 py-2 text-right font-semibold eyebrow whitespace-nowrap">
                          {strategyLabel(a)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.calendar.yearly.map((row) => (
                      <tr key={row.year} className="border-b border-hairline last:border-0 row-hover">
                        <td className="px-3 py-1.5 text-left text-faint font-semibold">{row.year}</td>
                        {data.calendar.assets.map((a) => {
                          const v = row[a] as number | null;
                          return (
                            <td
                              key={a}
                              className="px-3 py-1.5 text-right tabular-nums"
                              style={{
                                color:
                                  v == null
                                    ? "var(--color-faint)"
                                    : v < 0
                                      ? "var(--color-neg)"
                                      : undefined,
                              }}
                            >
                              {v == null ? "–" : `${(v * 100).toFixed(1)} %`}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-faint text-xs mt-1.5">
                Kompoundierte Kalenderjahr-Renditen je Asset (nativer Kalender); Grundlage auch für
                „seit Jahr X"-Fragen an The Desk.
              </p>
            </div>
          )}

          {/* Correlation matrix */}
          {data.correlation.assets.length > 1 && (
            <div>
              <div className="eyebrow mb-2">Korrelation der Tagesrenditen</div>
              <div className="border border-hairline bg-paper overflow-x-auto card-hover">
                <table className="text-sm nums border-collapse">
                  <thead>
                    <tr>
                      <th className="px-3 py-2"></th>
                      {data.correlation.assets.map((a) => (
                        <th key={a} className="px-3 py-2 text-faint text-xs font-semibold whitespace-nowrap">
                          {strategyLabel(a)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.correlation.matrix.map((row, i) => (
                      <tr key={i}>
                        <td className="px-3 py-2 text-faint text-xs font-semibold whitespace-nowrap text-right">
                          {strategyLabel(data.correlation.assets[i])}
                        </td>
                        {row.map((v, j) => (
                          <td
                            key={j}
                            className="px-3 py-2 text-center tabular-nums corr-cell"
                            style={{
                              color: Math.abs(v) > 0.5 ? "white" : "var(--color-ink)",
                              background: i === j ? "var(--color-panel)" : corrShade(v),
                            }}
                          >
                            {v.toFixed(2)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
      <p className="text-faint text-xs mt-2 leading-snug">
        Je Asset auf seinem <em>eigenen</em> Handelskalender: Krypto handelt ~365 Tage/Jahr,
        Aktien/Anleihen ~252 — daher unterschiedliche N und Annualisierung (Spalte „Tage/J").
        Korrelation und Backtest nutzen dagegen das gemeinsame, ausgerichtete Fenster (Aligned N);
        Feiertage werden nicht aufgefüllt. Werte aus <code>describe</code> der Engine.
      </p>
    </section>
  );
}
