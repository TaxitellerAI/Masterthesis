"use client";

import type { AnalyticsResponse } from "@/lib/types";

interface Props {
  data: AnalyticsResponse["monthly"];
}

const MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

// Diverging shade: blue for gains, muted red for losses, intensity by magnitude.
function shade(v: number | null): string {
  if (v == null) return "transparent";
  const t = Math.min(Math.abs(v) / 0.15, 1); // 15% monthly = full intensity
  const color = v >= 0 ? "var(--color-accent)" : "var(--color-neg)";
  return `color-mix(in srgb, ${color} ${(t * 82 + 4).toFixed(0)}%, var(--color-paper))`;
}

// Calendar of monthly returns for the selected vol-control strategy.
export default function MonthlyHeatmap({ data }: Props) {
  if (!data.years.length) return <div className="text-faint text-sm py-8 text-center">Keine Daten</div>;

  return (
    <div className="overflow-x-auto">
      <table className="text-xs nums border-collapse">
        <thead>
          <tr>
            <th className="px-2 py-1 text-faint font-semibold text-left">Jahr</th>
            {MONTHS.map((m, i) => (
              <th key={i} className="px-1.5 py-1 text-faint font-semibold text-center w-7">
                {m}
              </th>
            ))}
            <th className="px-2 py-1 text-faint font-semibold text-right">Jahr Σ</th>
          </tr>
        </thead>
        <tbody>
          {data.years.map((y, ri) => (
            <tr key={y}>
              <td className="px-2 py-1 text-faint font-semibold text-right">{y}</td>
              {data.matrix[ri].map((v, ci) => (
                <td
                  key={ci}
                  className="px-1 py-1 text-center tabular-nums"
                  style={{
                    background: shade(v),
                    color: v != null && Math.abs(v) > 0.09 ? "white" : "var(--color-ink)",
                  }}
                  title={v != null ? `${(v * 100).toFixed(1)} %` : ""}
                >
                  {v != null ? (v * 100).toFixed(0) : ""}
                </td>
              ))}
              <td
                className="px-2 py-1 text-right tabular-nums font-medium"
                style={{ color: data.annual[ri] >= 0 ? "var(--color-accent)" : "var(--color-neg)" }}
              >
                {(data.annual[ri] * 100).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
