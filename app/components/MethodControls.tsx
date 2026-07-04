"use client";

import type { EngineParams } from "@/lib/types";

interface Props {
  params: EngineParams;
  onChange: (next: Partial<EngineParams>) => void;
}

function Segmented<T extends string>({
  value,
  options,
  onSelect,
}: {
  value: T;
  options: { id: T; label: string }[];
  onSelect: (v: T) => void;
}) {
  return (
    <div className="inline-flex border border-hairline-strong">
      {options.map((o, i) => (
        <button
          key={o.id}
          onClick={() => onSelect(o.id)}
          className={`px-4 py-1.5 text-sm nums transition-colors ${i > 0 ? "border-l border-hairline-strong" : ""} ${
            value === o.id ? "bg-ink text-paper" : "text-muted hover:text-ink"
          }`}
          aria-pressed={value === o.id}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function LimitInput({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  hint: string;
}) {
  return (
    <div>
      <label className="text-sm font-medium block mb-2">{label}</label>
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={value !== null}
            onChange={(e) => onChange(e.target.checked ? -0.2 : null)}
          />
          aktiv
        </label>
        {value !== null && (
          <div className="flex items-center border border-hairline-strong bg-paper">
            <input
              type="number"
              step={0.01}
              max={0}
              value={value}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (Number.isFinite(v)) onChange(Math.min(0, v));
              }}
              className="w-24 px-3 py-1.5 text-sm nums bg-transparent outline-none"
            />
            <span className="px-2 text-muted text-sm nums border-l border-hairline">
              {(value * 100).toFixed(0)} %
            </span>
          </div>
        )}
      </div>
      <p className="text-faint text-xs mt-1.5 leading-snug">{hint}</p>
    </div>
  );
}

// Methodology levers (vol estimator, rebalancing frequency) + treasury risk
// limits. These drive the robustness story and the policy/limit view.
export default function MethodControls({ params, onChange }: Props) {
  return (
    <div className="space-y-6">
      <div className="grid sm:grid-cols-2 gap-6">
        <div>
          <label className="text-sm font-medium block mb-2">Volatilitäts-Schätzer</label>
          <Segmented
            value={params.vol_method}
            options={[
              { id: "rolling", label: "Rolling" },
              { id: "ewma", label: "EWMA" },
            ]}
            onSelect={(v) => onChange({ vol_method: v })}
          />
          <p className="text-faint text-xs mt-1.5 leading-snug">
            EWMA reagiert schneller auf Volatilitäts-Cluster (RiskMetrics-Stil).
          </p>
        </div>
        <div>
          <label className="text-sm font-medium block mb-2">Rebalancing</label>
          <Segmented
            value={params.rebalance}
            options={[
              { id: "daily", label: "Täglich" },
              { id: "weekly", label: "Wöchentl." },
              { id: "monthly", label: "Monatl." },
            ]}
            onSelect={(v) => onChange({ rebalance: v })}
          />
          <p className="text-faint text-xs mt-1.5 leading-snug">
            Seltener rebalancen senkt Turnover &amp; Kosten (realistischer fürs Treasury).
          </p>
        </div>
        <div>
          <label className="text-sm font-medium block mb-2">Exposure-Totband</label>
          <Segmented
            value={String(params.dead_band) as "0" | "0.05" | "0.1"}
            options={[
              { id: "0", label: "Aus" },
              { id: "0.05", label: "±5 Pp" },
              { id: "0.1", label: "±10 Pp" },
            ]}
            onSelect={(v) => onChange({ dead_band: Number(v) })}
          />
          <p className="text-faint text-xs mt-1.5 leading-snug">
            Erst handeln, wenn das Ziel-Exposure um mehr als das Band abweicht — No-Trade-Zone
            gegen Turnover.
          </p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-6 border-t border-hairline pt-5">
        <LimitInput
          label="Max-Drawdown-Limit"
          value={params.mdd_limit}
          onChange={(v) => onChange({ mdd_limit: v })}
          hint="Policy-Grenze; Überschreitungen werden in der Kennzahlentabelle rot markiert."
        />
        <LimitInput
          label="CVaR-95-Limit"
          value={params.cvar_limit}
          onChange={(v) => onChange({ cvar_limit: v })}
          hint="Tagesbezogenes Expected-Shortfall-Limit als Risikoappetit-Grenze."
        />
      </div>
    </div>
  );
}
