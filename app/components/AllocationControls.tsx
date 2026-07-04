"use client";

import type { EngineParams } from "@/lib/types";
import { BASE_TRAD_WEIGHTS } from "@/lib/types";

interface Props {
  value: EngineParams["trad_weights"];
  onChange: (next: EngineParams["trad_weights"]) => void;
}

const ROWS: { key: keyof EngineParams["trad_weights"]; label: string }[] = [
  { key: "MSCI_World", label: "MSCI World (Aktien)" },
  { key: "Global_Bonds", label: "Global Bonds (Anleihen)" },
  { key: "Gold", label: "Gold" },
];

// Optional sensitivity control for the traditional-sleeve base allocation.
// Defaults to the documented 60/30/10 thesis base case; any deviation is flagged.
export default function AllocationControls({ value, onChange }: Props) {
  const sum = value.MSCI_World + value.Global_Bonds + value.Gold || 1;
  const norm = (k: keyof EngineParams["trad_weights"]) => value[k] / sum;
  const isBase =
    Math.abs(norm("MSCI_World") - BASE_TRAD_WEIGHTS.MSCI_World) < 1e-4 &&
    Math.abs(norm("Global_Bonds") - BASE_TRAD_WEIGHTS.Global_Bonds) < 1e-4 &&
    Math.abs(norm("Gold") - BASE_TRAD_WEIGHTS.Gold) < 1e-4;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="eyebrow">Basis-Allokation · traditioneller Topf</span>
        {isBase ? (
          <span className="text-xs px-2 py-0.5 border border-hairline-strong text-muted">Thesis-Basisfall</span>
        ) : (
          <span className="text-xs px-2 py-0.5 border border-neg text-neg">≠ Thesis-Basisfall</span>
        )}
      </div>
      <p className="text-faint text-xs mb-3 leading-snug">
        Aufteilung <em>innerhalb</em> des traditionellen Topfs (wird auf 100 % normiert). Standard 60/30/10.
        Nur für Sensitivitäts-/Robustheitsanalysen ändern — der Basisfall ist die berichtete Grundlage.
      </p>

      <div className="space-y-3">
        {ROWS.map((r) => (
          <div key={r.key}>
            <div className="flex items-baseline justify-between mb-1">
              <label className="text-sm">{r.label}</label>
              <span className="nums text-sm tabular-nums">{(norm(r.key) * 100).toFixed(0)} %</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={value[r.key]}
              onChange={(e) => onChange({ ...value, [r.key]: Number(e.target.value) })}
              aria-label={r.label}
            />
          </div>
        ))}
      </div>

      {!isBase && (
        <button
          onClick={() => onChange({ ...BASE_TRAD_WEIGHTS })}
          className="mt-3 text-xs text-accent hover:underline"
        >
          Auf 60/30/10 zurücksetzen
        </button>
      )}
    </div>
  );
}
