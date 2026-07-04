"use client";

import type { TimeSeriesResponse } from "@/lib/types";
import { strategyLabel, pct, num } from "@/lib/format";
import TimeSeriesChart, { type TSeries } from "./TimeSeriesChart";
import SectionPlaceholder from "./SectionPlaceholder";

interface Props {
  data: TimeSeriesResponse | null;
  loading: boolean;
}

// Stable colours per strategy. Selected vol-control = accent; BH grey; benchmarks muted.
const COLORS: Record<string, string> = {
  BuyHold: "var(--color-faint)",
  Benchmark_TrueBH: "var(--color-neg)",
  Benchmark_6040: "var(--color-bench-gold)",
  Benchmark_RiskParity: "var(--color-bench-green)",
};
const ACCENT = "var(--color-accent)";

function orderKeys(data: TimeSeriesResponse): string[] {
  const keys = Object.keys(data.series);
  // selected first so it draws on top of benchmarks in the legend
  return [data.selected, ...keys.filter((k) => k !== data.selected)];
}

function Frame({
  title,
  caption,
  legend,
  children,
}: {
  title: string;
  caption: string;
  legend: { label: string; color: string; dashed?: boolean }[];
  children: React.ReactNode;
}) {
  return (
    <div className="border border-hairline bg-paper p-4 card-hover">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="flex flex-wrap gap-4 my-2 text-xs text-muted nums">
        {legend.map((l) => (
          <span key={l.label} className="inline-flex items-center gap-1.5">
            <svg width="16" height="6">
              <line x1="0" y1="3" x2="16" y2="3" stroke={l.color} strokeWidth="1.5" strokeDasharray={l.dashed ? "4 3" : undefined} />
            </svg>
            {l.label}
          </span>
        ))}
      </div>
      {children}
      <p className="text-faint text-xs mt-2 leading-snug">{caption}</p>
    </div>
  );
}

export default function TimeSeriesSection({ data, loading }: Props) {
  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">Zeitreihen</h2>
        <span className="eyebrow">Wealth · Drawdown · Exposure</span>
      </div>

      {!data && (
        <SectionPlaceholder loading={loading} label="Zeitreihen werden berechnet…" height={260} />
      )}

      {data && (
        <div className="space-y-5">
          {(() => {
            const keys = orderKeys(data);
            const color = (k: string) => (k === data.selected ? ACCENT : COLORS[k] ?? "var(--color-faint)");
            const dashed = (k: string) => k === "BuyHold";

            const wealth: TSeries[] = keys.map((k) => ({
              label: strategyLabel(k),
              color: color(k),
              dashed: dashed(k),
              values: data.series[k].wealth,
            }));
            const drawdown: TSeries[] = [data.selected, "BuyHold"]
              .filter((k) => data.series[k])
              .map((k) => ({
                label: strategyLabel(k),
                color: color(k),
                dashed: dashed(k),
                fill: k === data.selected,
                values: data.series[k].drawdown,
              }));
            const exp = data.series[data.selected]?.exposure;
            const exposure: TSeries[] = exp
              ? [{ label: `${strategyLabel(data.selected)} · Exposure`, color: ACCENT, values: exp }]
              : [];

            const legend = keys.map((k) => ({ label: strategyLabel(k), color: color(k), dashed: dashed(k) }));

            return (
              <>
                <Frame
                  title="Vermögensentwicklung (rebasiert = 1)"
                  caption="Kumulierte Wertentwicklung, alle Serien am gemeinsamen Start auf 1 normiert."
                  legend={legend}
                >
                  <TimeSeriesChart dates={data.dates} series={wealth} fmtY={(y) => num(y, 2)} height={230} />
                </Frame>

                <Frame
                  title="Drawdown-Verlauf"
                  caption="Peak-to-Trough-Verlust über die Zeit — die Verlust­dämpfung der Vol-Control wird hier sichtbar."
                  legend={drawdown.map((s) => ({ label: s.label, color: s.color, dashed: s.dashed }))}
                >
                  <TimeSeriesChart dates={data.dates} series={drawdown} fmtY={(y) => pct(y, 0)} zeroLine height={200} />
                </Frame>

                {exposure.length > 0 && (
                  <Frame
                    title="Exposure-Verlauf (Vol-Control)"
                    caption="Investitionsgrad der gewählten Vol-Control-Strategie; unter 1 = teilweise im risikofreien Zins geparkt."
                    legend={[{ label: "Exposure", color: ACCENT }]}
                  >
                    <TimeSeriesChart dates={data.dates} series={exposure} fmtY={(y) => num(y, 2)} height={160} />
                  </Frame>
                )}
              </>
            );
          })()}
        </div>
      )}
    </section>
  );
}
