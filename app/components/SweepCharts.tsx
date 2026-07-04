"use client";

import type { SweepResponse } from "@/lib/types";
import LineChart, { type Series } from "./LineChart";
import SectionPlaceholder from "./SectionPlaceholder";

interface Props {
  data: SweepResponse | null;
  loading: boolean;
}

const ACCENT = "var(--color-accent)";
const INK = "var(--color-ink)";
const GREY = "var(--color-faint)";

const fmtShare = (x: number) => `${(x * 100).toFixed(0)}%`;
const fmtPct = (y: number) => `${(y * 100).toFixed(1)}%`;
const fmtNum = (y: number) => y.toFixed(2);

function ChartFrame({
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
      <div className="flex items-baseline justify-between mb-1">
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <div className="flex gap-4 mb-2 text-xs text-muted nums">
        {legend.map((l) => (
          <span key={l.label} className="inline-flex items-center gap-1.5">
            <svg width="16" height="6">
              <line
                x1="0"
                y1="3"
                x2="16"
                y2="3"
                stroke={l.color}
                strokeWidth="1.5"
                strokeDasharray={l.dashed ? "4 3" : undefined}
              />
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

export default function SweepCharts({ data, loading }: Props) {
  const pts = data?.points ?? [];

  const deltaSeries: Series[] = [
    { label: "ΔMDD", color: ACCENT, points: pts.map((p) => ({ x: p.crypto_share, y: p.d_mdd })) },
    { label: "ΔCVaR", color: INK, dashed: true, points: pts.map((p) => ({ x: p.crypto_share, y: p.d_cvar })) },
  ];

  const sharpeSeries: Series[] = [
    { label: "Buy-and-Hold", color: GREY, dashed: true, points: pts.map((p) => ({ x: p.crypto_share, y: p.sharpe_bh })) },
    { label: "Vol-Control", color: ACCENT, points: pts.map((p) => ({ x: p.crypto_share, y: p.sharpe_vc })) },
  ];

  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">Krypto-Quoten-Sweep</h2>
        <span className="eyebrow">
          Zielvolatilität {data ? `${(data.target_vol * 100).toFixed(0)} %` : "—"}
        </span>
      </div>

      {!data && (
        <SectionPlaceholder loading={loading} label="Sweep wird berechnet…" height={240} />
      )}

      {data && (
        <div className="grid md:grid-cols-2 gap-5">
          <ChartFrame
            title="Risiko-Effekt der Vol-Control über die Krypto-Quote"
            caption="ΔMDD und ΔCVaR = Vol-Control minus Buy-and-Hold. Positiv = mildere Verlustkennzahl."
            legend={[
              { label: "ΔMDD", color: ACCENT },
              { label: "ΔCVaR", color: INK, dashed: true },
            ]}
          >
            <LineChart series={deltaSeries} fmtX={fmtShare} fmtY={fmtPct} />
          </ChartFrame>

          <ChartFrame
            title="Sharpe-Verläufe über die Krypto-Quote"
            caption="Sharpe der statischen und der volatilitätsgesteuerten Variante je Krypto-Anteil."
            legend={[
              { label: "Vol-Control", color: ACCENT },
              { label: "Buy-and-Hold", color: GREY, dashed: true },
            ]}
          >
            <LineChart series={sharpeSeries} fmtX={fmtShare} fmtY={fmtNum} />
          </ChartFrame>
        </div>
      )}
    </section>
  );
}
