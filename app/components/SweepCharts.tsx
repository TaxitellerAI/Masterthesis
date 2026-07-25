"use client";

import type { SweepBootstrap, SweepResponse } from "@/lib/types";
import LineChart, { type Band, type Series } from "./LineChart";
import SectionPlaceholder from "./SectionPlaceholder";

interface Props {
  data: SweepResponse | null;
  loading: boolean;
  /** Data-level sweep bootstrap — supplies the confidence bands. */
  boot?: SweepBootstrap | null;
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

export default function SweepCharts({ data, loading, boot = null }: Props) {
  const pts = data?.points ?? [];

  /** Build a band from the bootstrap result. `kind` picks pointwise vs simultaneous. */
  const band = (key: string, kind: "pointwise" | "simultaneous", color: string,
                opacity: number): Band | null => {
    const b = boot?.bands?.[key];
    if (!b) return null;
    const lo = kind === "pointwise" ? b.pointwise_low : b.simultaneous_low;
    const hi = kind === "pointwise" ? b.pointwise_high : b.simultaneous_high;
    const points = boot!.shares
      .map((x, i) => ({ x, lo: lo[i], hi: hi[i] }))
      .filter((p): p is { x: number; lo: number; hi: number } => p.lo != null && p.hi != null);
    return points.length > 1 ? { label: `${key}-${kind}`, color, opacity, points } : null;
  };

  // Simultaneous band drawn first (wider), pointwise on top — the visual point is
  // that the simultaneous band still covers zero at low crypto shares while the
  // pointwise one does not.
  const deltaBands = [
    band("d_mdd", "simultaneous", ACCENT, 0.10),
    band("d_mdd", "pointwise", ACCENT, 0.20),
  ].filter((b): b is Band => b !== null);
  const sharpeBands = [
    band("sharpe_vc", "simultaneous", ACCENT, 0.10),
    band("sharpe_vc", "pointwise", ACCENT, 0.20),
  ].filter((b): b is Band => b !== null);

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
            caption={
              deltaBands.length
                ? "ΔMDD und ΔCVaR = Vol-Control minus Buy-and-Hold. Positiv = mildere Verlustkennzahl. " +
                  `Flächen = Bootstrap-Konfidenz für ΔMDD (B = ${boot!.n_boot.toLocaleString("de-DE")}): ` +
                  "dunkler = punktweise 95 %, heller = SIMULTAN über alle Quoten " +
                  `(Faktor ${boot!.bands.d_mdd.simultaneous_factor.toFixed(2)} statt 1,96). ` +
                  "Das simultane Band enthält bei niedrigen Quoten die Null, das punktweise nicht — " +
                  "die Gesamtunsicherheit über die Kurve ist deutlich größer als je Einzelpunkt."
                : "ΔMDD und ΔCVaR = Vol-Control minus Buy-and-Hold. Positiv = mildere Verlustkennzahl."
            }
            legend={[
              { label: "ΔMDD", color: ACCENT },
              { label: "ΔCVaR", color: INK, dashed: true },
            ]}
          >
            <LineChart series={deltaSeries} bands={deltaBands} fmtX={fmtShare} fmtY={fmtPct} />
          </ChartFrame>

          <ChartFrame
            title="Sharpe-Verläufe über die Krypto-Quote"
            caption="Sharpe der statischen und der volatilitätsgesteuerten Variante je Krypto-Anteil."
            legend={[
              { label: "Vol-Control", color: ACCENT },
              { label: "Buy-and-Hold", color: GREY, dashed: true },
            ]}
          >
            <LineChart series={sharpeSeries} bands={sharpeBands} fmtX={fmtShare} fmtY={fmtNum} />
          </ChartFrame>
        </div>
      )}
    </section>
  );
}
