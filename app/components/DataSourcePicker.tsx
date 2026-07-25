"use client";

import type { EngineParams } from "@/lib/types";

interface Props {
  source: EngineParams["source"];
  start: string;
  end: string;
  onSource: (s: EngineParams["source"]) => void;
}

// Data source for the run. The default is the FROZEN snapshot: the reported
// thesis figures must not move because Yahoo Finance revised a price or the
// defence happens to run on a day with a rate limit. Live stays available to
// show the tool works against current quotes.
export default function DataSourcePicker({ source, start, end, onSource }: Props) {
  return (
    <div>
      <span className="eyebrow">Datenquelle</span>
      <div className="grid sm:grid-cols-2 gap-3 mt-3">
        {(
          [
            {
              id: "frozen",
              title: "Eingefroren · real",
              desc: "Fixierter Marktdaten-Abzug (EUR). Zitierfähig, reproduzierbar, netzunabhängig.",
            },
            {
              id: "live",
              title: "Live · Yahoo Finance",
              desc: "Aktuelle Kurse im selben Fenster — zeigt, dass das Werkzeug live läuft.",
            },
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

      {/* Fixed study window — stated, not choosable, because it defines the result. */}
      <div className="mt-4 border border-hairline bg-panel px-4 py-3">
        <div className="flex items-baseline justify-between gap-4">
          <span className="eyebrow">Untersuchungszeitraum</span>
          <span className="text-sm nums tabular-nums">
            {start} — {end}
          </span>
        </div>
        <p className="text-faint text-xs mt-1.5 leading-snug">
          Feste Kalendergrenzen (acht volle Jahre) statt eines rollierenden Fensters — sonst
          lieferte jeder Abruf einen anderen Datenstand und kein Ergebnis wäre zitierfähig.
        </p>
      </div>
    </div>
  );
}
