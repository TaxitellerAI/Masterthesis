"use client";

import type { EngineParams } from "@/lib/types";

interface Props {
  source: EngineParams["source"];
  years: number;
  onSource: (s: EngineParams["source"]) => void;
  onYears: (y: number) => void;
}

const YEAR_OPTIONS = [3, 5, 8, 10];

// Data source for the run: instant synthetic fixture vs. a live Yahoo Finance
// pull (current quotes, fetched fresh per configurator run, EUR-converted).
export default function DataSourcePicker({ source, years, onSource, onYears }: Props) {
  return (
    <div>
      <span className="eyebrow">Datenquelle</span>
      <div className="grid sm:grid-cols-3 gap-3 mt-3">
        {(
          [
            { id: "synthetic", title: "Synthetisch", desc: "Reproduzierbare Fixture-Daten, sofort verfügbar." },
            { id: "frozen", title: "Eingefroren · real", desc: "Fixierter Marktdaten-Abzug (EUR), zitierfähig & stabil." },
            { id: "live", title: "Live · Yahoo Finance", desc: "Aktuelle Kurse, bei jedem Lauf neu gezogen." },
          ] as const
        ).map((opt) => {
          const active = source === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onSource(opt.id)}
              className="text-left border p-3 transition-colors"
              style={{
                borderColor: active ? "var(--color-accent)" : "var(--color-hairline)",
                background: active ? "var(--color-accent-soft)" : "transparent",
              }}
              aria-pressed={active}
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full border"
                  style={{
                    borderColor: active ? "var(--color-accent)" : "var(--color-hairline-strong)",
                    background: active ? "var(--color-accent)" : "transparent",
                  }}
                />
                <span className="text-sm font-medium">{opt.title}</span>
              </div>
              <p className="text-faint text-xs mt-1.5 leading-snug">{opt.desc}</p>
            </button>
          );
        })}
      </div>

      {/* History length — only meaningful for the live pull. */}
      <div className={`mt-4 transition-opacity ${source === "live" ? "" : "opacity-40 pointer-events-none"}`}>
        <div className="flex items-baseline justify-between mb-2">
          <label className="text-sm font-medium">Historie</label>
          <span className="text-faint text-xs">Live-Fenster wird durch jüngstes Asset begrenzt</span>
        </div>
        <div className="inline-flex border border-hairline-strong">
          {YEAR_OPTIONS.map((y) => {
            const active = years === y;
            return (
              <button
                key={y}
                onClick={() => onYears(y)}
                className={`px-4 py-1.5 text-sm nums border-l first:border-l-0 border-hairline-strong transition-colors ${
                  active ? "bg-ink text-paper" : "text-muted hover:text-ink"
                }`}
                aria-pressed={active}
              >
                {y} J
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
