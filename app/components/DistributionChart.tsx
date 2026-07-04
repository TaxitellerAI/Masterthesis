"use client";

import type { AnalyticsResponse } from "@/lib/types";
import { useContainerWidth } from "@/lib/useContainerWidth";

interface Props {
  data: AnalyticsResponse["distribution"];
  height?: number;
  width?: number;
}

const PAD = { top: 12, right: 14, bottom: 26, left: 40 };
const ACCENT = "var(--color-accent)";
const GREY = "var(--color-faint)";

// Overlaid daily-return densities (BH vs. vol-control) with VaR markers — the
// tail-risk story: vol-control compresses the left tail.
export default function DistributionChart({ data, height = 220, width: propWidth = 460 }: Props) {
  const [boxRef, width] = useContainerWidth<HTMLDivElement>(propWidth);
  const { centers, bh, vc } = data;
  if (!centers.length)
    return <div ref={boxRef} className="text-faint text-sm py-10 text-center">Keine Daten</div>;

  const xMin = centers[0];
  const xMax = centers[centers.length - 1];
  const yMax = Math.max(...bh, ...vc) * 1.05 || 1;

  const innerW = width - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const sx = (x: number) => PAD.left + ((x - xMin) / (xMax - xMin)) * innerW;
  const sy = (y: number) => PAD.top + (1 - y / yMax) * innerH;

  const area = (vals: number[]) => {
    const top = vals.map((v, i) => `${i === 0 ? "M" : "L"} ${sx(centers[i]).toFixed(1)} ${sy(v).toFixed(1)}`).join(" ");
    return `${top} L ${sx(xMax).toFixed(1)} ${sy(0).toFixed(1)} L ${sx(xMin).toFixed(1)} ${sy(0).toFixed(1)} Z`;
  };
  const line = (vals: number[]) =>
    vals.map((v, i) => `${i === 0 ? "M" : "L"} ${sx(centers[i]).toFixed(1)} ${sy(v).toFixed(1)}`).join(" ");

  const xTicks = [xMin, xMin / 2, 0, xMax / 2, xMax];

  const marker = (x: number, color: string, label: string) => (
    <g>
      <line x1={sx(x)} x2={sx(x)} y1={PAD.top} y2={height - PAD.bottom} stroke={color} strokeWidth={1} strokeDasharray="3 2" />
      <text x={sx(x)} y={PAD.top + 8} fontSize={8} fill={color} textAnchor="middle">
        {label}
      </text>
    </g>
  );

  return (
    <div ref={boxRef} className="w-full">
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} className="nums block" role="img" preserveAspectRatio="xMidYMid meet">
      {xTicks.map((v, i) => (
        <text key={i} x={sx(v)} y={height - 8} textAnchor="middle" fontSize={9} fill="var(--color-muted)">
          {(v * 100).toFixed(1)}%
        </text>
      ))}
      <line x1={PAD.left} x2={width - PAD.right} y1={height - PAD.bottom} y2={height - PAD.bottom} stroke="var(--color-hairline-strong)" strokeWidth={1} />

      {/* Vol-control filled, Buy-and-Hold outline */}
      <path d={area(vc)} fill={ACCENT} opacity={0.14} stroke="none" />
      <path d={line(vc)} fill="none" stroke={ACCENT} strokeWidth={1.5} />
      <path d={line(bh)} fill="none" stroke={GREY} strokeWidth={1.5} strokeDasharray="4 3" />

      {marker(data.vc_var, ACCENT, "VaR VC")}
      {marker(data.bh_var, GREY, "VaR BH")}
    </svg>
    </div>
  );
}
