"use client";

import type { EngineParams } from "@/lib/types";

interface Props {
  params: EngineParams;
  onChange: (next: Partial<EngineParams>) => void;
}

// The engine only computes vol-control variants at 5/10/15 % and indexes them as
// VolControl_{int(target_vol*100)} — so the target-vol control snaps to exactly
// those three values. This keeps the engine untouched and avoids a KeyError.
const TARGET_VOLS = [0.05, 0.1, 0.15];

// The four strategy/market parameters, shared by the configurator and the
// results sidebar so the two never drift apart.
export default function ParamControls({ params, onChange }: Props) {
  return (
    <div className="space-y-7">
      {/* Zielvolatilität */}
      <div>
        <div className="flex items-baseline justify-between mb-2">
          <label className="text-sm font-medium">Zielvolatilität</label>
          <span className="nums text-sm">{(params.target_vol * 100).toFixed(0)} %</span>
        </div>
        <input
          type="range"
          min={0}
          max={2}
          step={1}
          value={TARGET_VOLS.indexOf(params.target_vol)}
          onChange={(e) => onChange({ target_vol: TARGET_VOLS[Number(e.target.value)] })}
          aria-label="Zielvolatilität"
        />
        <div className="flex justify-between text-faint text-xs nums mt-1.5">
          {TARGET_VOLS.map((v) => (
            <span key={v}>{v * 100} %</span>
          ))}
        </div>
        <p className="text-faint text-xs mt-2 leading-snug">
          Engine-Varianten 5/10/15 %. Bestimmt, welche Vol-Control-Strategie in den
          Hypothesentests (H1/H2) gegen Buy-and-Hold geprüft wird.
        </p>
      </div>

      {/* Krypto-Quote */}
      <div>
        <div className="flex items-baseline justify-between mb-2">
          <label className="text-sm font-medium">Krypto-Quote</label>
          <span className="nums text-sm">{(params.crypto_share * 100).toFixed(1)} %</span>
        </div>
        <input
          type="range"
          min={0}
          max={0.5}
          step={0.005}
          value={params.crypto_share}
          onChange={(e) => onChange({ crypto_share: Number(e.target.value) })}
          aria-label="Krypto-Quote"
        />
        <div className="flex justify-between text-faint text-xs nums mt-1.5">
          <span>0 %</span>
          <span>25 %</span>
          <span>50 %</span>
        </div>
      </div>

      {/* Währung */}
      <div>
        <label className="text-sm font-medium block mb-2">Basiswährung</label>
        <div className="inline-flex border border-hairline-strong">
          {(["EUR", "USD"] as const).map((c) => {
            const active = params.base_currency === c;
            return (
              <button
                key={c}
                onClick={() => onChange({ base_currency: c })}
                className={`px-5 py-1.5 text-sm nums transition-colors ${
                  active ? "bg-ink text-paper" : "bg-transparent text-muted hover:text-ink"
                } ${c === "USD" ? "border-l border-hairline-strong" : ""}`}
                aria-pressed={active}
              >
                {c}
              </button>
            );
          })}
        </div>
        <p className="text-faint text-xs mt-2 leading-snug">
          EUR + 3M-EURIBOR entspricht der Thesis. Bei Live-Daten werden die USD-Kurse
          via EURUSD nach EUR umgerechnet.
        </p>
      </div>

      {/* Risikofreier Zins */}
      <div>
        <label className="text-sm font-medium block mb-2" htmlFor="rf">
          Risikofreier Zins (p.a.)
        </label>
        <div className="inline-flex border border-hairline-strong mb-2">
          {(
            [
              { id: "manual", label: "Manuell" },
              { id: "estr", label: "€STR (ECB)" },
            ] as const
          ).map((o, i) => (
            <button
              key={o.id}
              onClick={() => onChange({ rf_mode: o.id })}
              className={`px-4 py-1.5 text-sm nums transition-colors ${i > 0 ? "border-l border-hairline-strong" : ""} ${
                params.rf_mode === o.id ? "bg-ink text-paper" : "text-muted hover:text-ink"
              }`}
              aria-pressed={params.rf_mode === o.id}
            >
              {o.label}
            </button>
          ))}
        </div>
        {params.rf_mode === "manual" ? (
          <div className="flex items-center border border-hairline-strong bg-paper">
            <input
              id="rf"
              type="number"
              min={0}
              max={0.2}
              step={0.0025}
              value={params.rf_annual}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (Number.isFinite(v)) onChange({ rf_annual: Math.max(0, Math.min(0.2, v)) });
              }}
              className="w-full px-3 py-1.5 text-sm nums bg-transparent outline-none"
            />
            <span className="px-3 text-muted text-sm nums border-l border-hairline">
              {(params.rf_annual * 100).toFixed(2)} %
            </span>
          </div>
        ) : (
          <p className="text-faint text-xs leading-snug">
            Realisierter €STR-Durchschnitt des Datenfensters (ECB SDMX, ab Okt 2019) — ersetzt die
            willkürliche Konstante durch das tatsächliche Zinsniveau der Stichprobe.
          </p>
        )}
      </div>
    </div>
  );
}
