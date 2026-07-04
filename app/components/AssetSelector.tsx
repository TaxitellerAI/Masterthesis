"use client";

import type { AssetInfo } from "@/lib/types";

interface Props {
  catalog: AssetInfo[];
  selected: string[];
  onChange: (names: string[]) => void;
}

const CLASS_LABEL: Record<string, string> = {
  equity: "Aktien",
  bond: "Anleihen",
  commodity: "Rohstoffe",
  crypto: "Krypto",
};

// Checkbox grid over the curated universe, grouped by asset class. The selection
// defines the common sample the engine works on (canonical names map 1:1 to the
// engine's weighting logic, so any subset just works).
export default function AssetSelector({ catalog, selected, onChange }: Props) {
  const toggle = (name: string) => {
    onChange(selected.includes(name) ? selected.filter((n) => n !== name) : [...selected, name]);
  };

  const groups = Array.from(new Set(catalog.map((a) => a.asset_class)));

  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <span className="eyebrow">Anlageuniversum</span>
        <span className="text-faint text-xs nums">{selected.length} ausgewählt</span>
      </div>

      <div className="grid sm:grid-cols-2 gap-x-8 gap-y-5">
        {groups.map((g) => (
          <div key={g}>
            <div className="text-xs font-semibold text-muted mb-2">{CLASS_LABEL[g] ?? g}</div>
            <div className="space-y-1.5">
              {catalog
                .filter((a) => a.asset_class === g)
                .map((a) => {
                  const on = selected.includes(a.name);
                  return (
                    <label
                      key={a.name}
                      className="flex items-center gap-2.5 cursor-pointer group"
                    >
                      <span
                        className="w-3.5 h-3.5 border flex items-center justify-center shrink-0"
                        style={{
                          borderColor: on ? "var(--color-accent)" : "var(--color-hairline-strong)",
                          background: on ? "var(--color-accent)" : "transparent",
                        }}
                      >
                        {on && (
                          <svg width="9" height="9" viewBox="0 0 10 10" aria-hidden>
                            <path d="M1 5l2.5 2.5L9 2" fill="none" stroke="white" strokeWidth="1.6" />
                          </svg>
                        )}
                      </span>
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={on}
                        onChange={() => toggle(a.name)}
                      />
                      <span className="text-sm group-hover:text-ink">{a.label}</span>
                    </label>
                  );
                })}
            </div>
          </div>
        ))}
      </div>
      {selected.length === 0 && (
        <p className="text-neg text-xs mt-3">Mindestens ein Asset auswählen.</p>
      )}
    </div>
  );
}
