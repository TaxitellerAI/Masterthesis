"use client";

import { useRef, useState } from "react";
import { useContainerWidth } from "@/lib/useContainerWidth";

// Index-based multi-series chart for time paths (wealth/drawdown/exposure).
// Handles null gaps (a series that starts later), a sparse date axis, and the
// same baby-blue hover readout as the sweep charts.

export interface TSeries {
  label: string;
  color: string;
  values: (number | null)[];
  dashed?: boolean;
  fill?: boolean; // shade to zero (used for drawdown)
}

interface Props {
  dates: string[];
  series: TSeries[];
  height?: number;
  width?: number;
  fmtY?: (y: number) => string;
  zeroLine?: boolean;
  yTicks?: number;
}

const PAD = { top: 12, right: 14, bottom: 26, left: 54 };

export default function TimeSeriesChart({
  dates,
  series,
  height = 240,
  width: propWidth = 900,
  fmtY = (y) => `${y}`,
  zeroLine = false,
  yTicks = 4,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [boxRef, width] = useContainerWidth<HTMLDivElement>(propWidth);

  const n = dates.length;
  const flat = series.flatMap((s) => s.values.filter((v): v is number => v != null));
  if (flat.length === 0)
    return <div ref={boxRef} className="text-faint text-sm py-10 text-center">Keine Daten</div>;

  let yMin = Math.min(...flat);
  let yMax = Math.max(...flat);
  if (zeroLine) {
    yMin = Math.min(yMin, 0);
    yMax = Math.max(yMax, 0);
  }
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  const pad = (yMax - yMin) * 0.06;
  yMin -= pad;
  yMax += pad;

  const innerW = width - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const sx = (i: number) => PAD.left + (n <= 1 ? 0 : (i / (n - 1)) * innerW);
  const sy = (y: number) => PAD.top + (1 - (y - yMin) / (yMax - yMin)) * innerH;

  const yTickVals = Array.from({ length: yTicks }, (_, i) => yMin + ((yMax - yMin) * i) / (yTicks - 1));
  const xTickIdx = [0, Math.round((n - 1) * 0.25), Math.round((n - 1) * 0.5), Math.round((n - 1) * 0.75), n - 1];

  // Build a path string that breaks across null gaps.
  const pathFor = (vals: (number | null)[]) => {
    let d = "";
    let pen = false;
    vals.forEach((v, i) => {
      if (v == null) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"} ${sx(i).toFixed(2)} ${sy(v).toFixed(2)} `;
      pen = true;
    });
    return d.trim();
  };

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const vbx = ((e.clientX - rect.left) / rect.width) * width;
    const i = Math.round(((vbx - PAD.left) / innerW) * (n - 1));
    setHover(Math.min(Math.max(i, 0), n - 1));
  };

  const hx = hover != null ? sx(hover) : 0;
  const boxW = 150;
  const boxX = hover != null ? Math.min(Math.max(hx + 8, PAD.left), width - boxW - 4) : 0;
  const visible = series.filter((s) => hover != null && s.values[hover] != null);

  return (
    <div ref={boxRef} className="w-full">
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      className="nums select-none block"
      role="img"
      preserveAspectRatio="xMidYMid meet"
      onPointerMove={onMove}
      onPointerLeave={() => setHover(null)}
    >
      {yTickVals.map((v, i) => (
        <g key={i}>
          <line x1={PAD.left} x2={width - PAD.right} y1={sy(v)} y2={sy(v)} stroke="var(--color-hairline)" strokeWidth={0.75} />
          <text x={PAD.left - 8} y={sy(v) + 3} textAnchor="end" fontSize={9} fill="var(--color-muted)">
            {fmtY(v)}
          </text>
        </g>
      ))}
      {zeroLine && yMin < 0 && yMax > 0 && (
        <line x1={PAD.left} x2={width - PAD.right} y1={sy(0)} y2={sy(0)} stroke="var(--color-hairline-strong)" strokeWidth={1} />
      )}
      {xTickIdx.map((i, k) => (
        <text key={k} x={sx(i)} y={height - 8} textAnchor="middle" fontSize={9} fill="var(--color-muted)">
          {dates[i]?.slice(0, 7)}
        </text>
      ))}
      <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={height - PAD.bottom} stroke="var(--color-ink)" strokeWidth={1} />

      {/* optional fill to zero (drawdown) */}
      {series.map((s, si) =>
        s.fill ? (
          <path
            key={`f${si}`}
            d={`${pathFor(s.values)} L ${sx(n - 1)} ${sy(0)} L ${sx(0)} ${sy(0)} Z`}
            fill={s.color}
            opacity={0.08}
            stroke="none"
          />
        ) : null,
      )}

      {hover != null && (
        <line x1={hx} x2={hx} y1={PAD.top} y2={height - PAD.bottom} stroke="var(--color-sky-strong)" strokeWidth={1} strokeDasharray="3 2" />
      )}

      {series.map((s, si) => (
        <path key={si} d={pathFor(s.values)} fill="none" stroke={s.color} strokeWidth={1.5} strokeDasharray={s.dashed ? "4 3" : undefined} />
      ))}

      {hover != null &&
        visible.map((s, i) => {
          const v = s.values[hover] as number;
          return <circle key={i} cx={hx} cy={sy(v)} r={3} fill={s.color} stroke="var(--color-paper)" strokeWidth={1} />;
        })}

      {hover != null && visible.length > 0 && (
        <g pointerEvents="none">
          <rect x={boxX} y={PAD.top + 2} width={boxW} height={16 + visible.length * 13} fill="var(--color-paper)" stroke="var(--color-sky)" strokeWidth={0.75} />
          <text x={boxX + 8} y={PAD.top + 15} fontSize={9} fill="var(--color-muted)">
            {dates[hover]}
          </text>
          {visible.map((s, i) => (
            <g key={i}>
              <rect x={boxX + 8} y={PAD.top + 22 + i * 13} width={8} height={2} fill={s.color} />
              <text x={boxX + 20} y={PAD.top + 26 + i * 13} fontSize={9} fill="var(--color-ink)">
                {s.label}
              </text>
              <text x={boxX + boxW - 8} y={PAD.top + 26 + i * 13} fontSize={9} textAnchor="end" fill="var(--color-ink)">
                {fmtY(s.values[hover] as number)}
              </text>
            </g>
          ))}
        </g>
      )}
    </svg>
    </div>
  );
}
