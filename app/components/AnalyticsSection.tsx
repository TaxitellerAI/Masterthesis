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
        </div>
      )}
    </section>
  );
}
