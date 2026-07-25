"use client";

import type { ScenarioInfo } from "@/lib/types";

interface Props {
  scenarios: ScenarioInfo[];
  active: string;
  mismatch: boolean; // selected assets deviate from the named scenario
  onSelect: (name: string) => void;
}

// Step 2a — the sample design. This is the single most consequential choice in the
// tool: it fixes the window, the crypto basket and whether the sleeve is fixed or
// grows point-in-time. It used to be reachable only through the API, which made it
// possible to export a report that did not match the thesis specification without
// noticing. It is therefore shown first and always labelled.
export default function ScenarioPicker({ scenarios, active, mismatch, onSelect }: Props) {
  const primary = scenarios.filter((s) => s.primary);
  const sensitivity = scenarios.filter((s) => !s.primary);
  const current = scenarios.find((s) => s.name === active);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <span className="eyebrow">Sample-Design</span>
        {mismatch && (
          <span className="text-xs nums" style={{ color: "var(--color-neg)" }}>
            Asset-Auswahl weicht ab → custom
          </span>
        )}
      </div>

      <div className="grid sm:grid-cols-3 gap-3 mt-3">
        {primary.map((s) => {
          const isActive = active === s.name;
          return (
            <button
              key={s.name}
              onClick={() => onSelect(s.name)}
              className="text-left border p-3 transition-colors"
              style={{
                borderColor: isActive ? "var(--color-accent)" : "var(--color-hairline)",
                background: isActive ? "var(--color-accent-soft)" : "transparent",
              }}
              aria-pressed={isActive}
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full border shrink-0"
                  style={{
                    borderColor: isActive ? "var(--color-accent)" : "var(--color-hairline-strong)",
                    background: isActive ? "var(--color-accent)" : "transparent",
                  }}
                />
                <span className="text-sm font-medium">
                  {s.name}
                  {s.name === "S1" && <span className="text-faint font-normal"> · Haupt</span>}
                </span>
              </div>
              <p className="text-xs mt-1.5 leading-snug">{s.label}</p>
              <p className="text-faint text-xs mt-1 nums tabular-nums">
                {s.start.slice(0, 7)} – {s.end.slice(0, 7)} · {s.crypto_members.length} Coins ·{" "}
                {s.sleeve_mode === "point_in_time" ? "PIT" : "fest"}
              </p>
            </button>
          );
        })}
      </div>

      {/* S4 family + custom */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-faint text-xs mr-1">Startjahr-Sensitivität (S4):</span>
        {sensitivity.map((s) => {
          const isActive = active === s.name;
          return (
            <button
              key={s.name}
              onClick={() => onSelect(s.name)}
              className={`px-2.5 py-1 text-xs nums border transition-colors ${
                isActive ? "bg-ink text-paper border-ink" : "text-muted border-hairline-strong hover:text-ink"
              }`}
              aria-pressed={isActive}
            >
              {s.start.slice(0, 4)}
            </button>
          );
        })}
        <button
          onClick={() => onSelect("custom")}
          className={`px-2.5 py-1 text-xs border transition-colors ml-2 ${
            active === "custom"
              ? "bg-ink text-paper border-ink"
              : "text-muted border-hairline-strong hover:text-ink"
          }`}
          aria-pressed={active === "custom"}
        >
          custom
        </button>
      </div>

      {/* Rationale of the active scenario — this is what belongs in the thesis text. */}
      {current && (
        <p className="text-faint text-xs mt-3 leading-snug border-l-2 border-hairline pl-3">
          {current.rationale}
        </p>
      )}
      {active === "custom" && (
        <p className="text-faint text-xs mt-3 leading-snug border-l-2 pl-3"
           style={{ borderColor: "var(--color-neg)" }}>
          Freie Auswahl: Fenster und Assets bestimmst du selbst. Ergebnisse entsprechen dann
          <strong> nicht</strong> der Hauptspezifikation der Arbeit — im Kopfbereich und im PDF
          wird das als „custom“ ausgewiesen.
        </p>
      )}
    </div>
  );
}
