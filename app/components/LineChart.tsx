"use client";

import { useRef, useState } from "react";
import { useContainerWidth } from "@/lib/useContainerWidth";

// A minimal, dependency-free SVG line chart. Hairline axes, tabular tick labels,
// a single muted accent for the primary series — reads like a printed exhibit.
// On hover it comes alive: a baby-blue guide line, the marked points grow, and a
// compact readout shows the values at the cursor.

export interface Series {
  label: string;
  points: { x: number; y: number }[];
  color: string;
  dashed?: boolean;
}

interface Props {
  series: Series[];
  width?: number;
  height?: number;
  fmtX?: (x: number) => string;
  fmtY?: (y: number) => string;
  zeroLine?: boolean;
  xTicks?: number;
  yTicks?: number;
}

const PAD = { top: 12, right: 14, bottom: 26, left: 52 };

export default function LineChart({
  series,
  width: propWidth = 460,
  height = 240,
  fmtX = (x) => `${x}`,
  fmtY = (y) => `${y}`,
  zeroLine = true,
  xTicks = 5,
  yTicks = 4,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  // Render the viewBox at the container's real width so labels stay a constant size.
  const [boxRef, width] = useContainerWidth<HTMLDivElement>(propWidth);

  const all = series.flatMap((s) => s.points);
  if (all.length === 0) {
    return <div ref={boxRef} className="text-faint text-sm py-10 text-center">Keine Daten</div>;
  }

  const xs = all.map((p) => p.x);
  const ys = all.map((p) => p.y);
  let xMin = Math.min(...xs);
  let xMax = Math.max(...xs);
  let yMin = Math.min(...ys);
  let yMax = Math.max(...ys);
  if (zeroLine) {
    yMin = Math.min(yMin, 0);
    yMax = Math.max(yMax, 0);
  }
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  const yPad = (yMax - yMin) * 0.08;
  yMin -= yPad;
  yMax += yPad;
  if (xMin === xMax) {
    xMin -= 1;
    xMax += 1;
  }

  const innerW = width - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const sx = (x: number) => PAD.left + ((x - xMin) / (xMax - xMin)) * innerW;
  const sy = (y: number) => PAD.top + (1 - (y - yMin) / (yMax - yMin)) * innerH;

  const xTickVals = Array.from({ length: xTicks }, (_, i) => xMin + ((xMax - xMin) * i) / (xTicks - 1));
  const yTickVals = Array.from({ length: yTicks }, (_, i) => yMin + ((yMax - yMin) * i) / (yTicks - 1));

  // Shared x grid (all series share the same x positions here).
  const grid = series[0].points;

  // Map a pointer event to the nearest data index along x.
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const vbx = ((e.clientX - rect.left) / rect.width) * width;
    let best = 0;
    let bestD = Infinity;
    grid.forEach((p, i) => {
      const d = Math.abs(sx(p.x) - vbx);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    setHover(best);
  };

  const hx = hover != null ? sx(grid[hover].x) : 0;
  // Readout box geometry (clamped inside the plot).
  const boxW = 124;
  const boxX = hover != null ? Math.min(Math.max(hx + 8, PAD.left), width - boxW - 4) : 0;

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
      {/* y gridlines + labels */}
      {yTickVals.map((v, i) => (
        <g key={`y${i}`}>
          <line x1={PAD.left} x2={width - PAD.right} y1={sy(v)} y2={sy(v)} stroke="var(--color-hairline)" strokeWidth={0.75} />
          <text x={PAD.left - 8} y={sy(v) + 3} textAnchor="end" fontSize={9} fill="var(--color-muted)">
            {fmtY(v)}
          </text>
        </g>
      ))}

      {/* zero reference line */}
      {zeroLine && yMin < 0 && yMax > 0 && (
        <line x1={PAD.left} x2={width - PAD.right} y1={sy(0)} y2={sy(0)} stroke="var(--color-hairline-strong)" strokeWidth={1} />
      )}

      {/* x labels */}
      {xTickVals.map((v, i) => (
        <text key={`x${i}`} x={sx(v)} y={height - 8} textAnchor="middle" fontSize={9} fill="var(--color-muted)">
          {fmtX(v)}
        </text>
      ))}

      {/* axis */}
      <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={height - PAD.bottom} stroke="var(--color-ink)" strokeWidth={1} />

      {/* hover guide line */}
      {hover != null && (
        <line x1={hx} x2={hx} y1={PAD.top} y2={height - PAD.bottom} stroke="var(--color-sky-strong)" strokeWidth={1} strokeDasharray="3 2" />
      )}

      {/* series */}
      {series.map((s, si) => {
        const d = s.points.map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p.x).toFixed(2)} ${sy(p.y).toFixed(2)}`).join(" ");
        return (
          <g key={si}>
            <path d={d} fill="none" stroke={s.color} strokeWidth={hover != null ? 2 : 1.5} strokeDasharray={s.dashed ? "4 3" : undefined} style={{ transition: "stroke-width 0.12s ease" }} />
            {s.points.map((p, i) => (
              <circle key={i} className="spark-dot" cx={sx(p.x)} cy={sy(p.y)} r={hover === i ? 4 : 1.6} fill={s.color} stroke={hover === i ? "var(--color-paper)" : "none"} strokeWidth={hover === i ? 1.2 : 0} />
            ))}
          </g>
        );
      })}

      {/* hover readout */}
      {hover != null && (
        <g pointerEvents="none">
          <rect x={boxX} y={PAD.top + 2} width={boxW} height={16 + series.length * 13} fill="var(--color-paper)" stroke="var(--color-sky)" strokeWidth={0.75} />
          <text x={boxX + 8} y={PAD.top + 15} fontSize={9} fill="var(--color-muted)">
            {fmtX(grid[hover].x)}
          </text>
          {series.map((s, i) => (
            <g key={i}>
              <rect x={boxX + 8} y={PAD.top + 22 + i * 13} width={8} height={2} fill={s.color} />
              <text x={boxX + 20} y={PAD.top + 26 + i * 13} fontSize={9} fill="var(--color-ink)">
                {s.label}
              </text>
              <text x={boxX + boxW - 8} y={PAD.top + 26 + i * 13} fontSize={9} textAnchor="end" fill="var(--color-ink)">
                {fmtY(s.points[hover].y)}
              </text>
            </g>
          ))}
        </g>
      )}
    </svg>
    </div>
  );
}
