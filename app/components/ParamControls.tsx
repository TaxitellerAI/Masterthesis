"use client";

import type { EngineParams, RfInfo } from "@/lib/types";

interface Props {
  params: EngineParams;
  onChange: (next: Partial<EngineParams>) => void;
  /** Live rf facts from the engine — never hard-code window-dependent numbers. */
  rf?: RfInfo | null;
}

// The engine only computes vol-control variants at 5/10/15 % and indexes them as
// VolControl_{int(target_vol*100)} — so the target-vol control snaps to exactly
// those three values. This keeps the engine untouched and avoids a KeyError.
const TARGET_VOLS = [0.05, 0.1, 0.15];

// The four strategy/market parameters, shared by the configurator and the
// results sidebar so the two never drift apart.
export default function ParamControls({ params, onChange, rf = null }: Props) {
  const negShare = rf?.estr?.window_share_negative;
  const negTxt = negShare != null ? `${(negShare * 100).toFixed(0)} %` : null;
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
            // The frozen snapshot exists only in EUR. Offering USD there would
            // produce EUR figures under a USD label — disable it and say why.
            const blocked = c === "USD" && params.source === "frozen";
            return (
              <button
                key={c}
                disabled={blocked}
                title={blocked
                  ? "Der eingefrorene Datensatz liegt nur in EUR vor. Für USD die Live-Datenquelle wählen."
                  : undefined}
                onClick={() => !blocked && onChange({ base_currency: c })}
                className={`px-5 py-1.5 text-sm nums transition-colors ${
                  active ? "bg-ink text-paper" : "bg-transparent text-muted hover:text-ink"
                } ${c === "USD" ? "border-l border-hairline-strong" : ""} ${blocked ? "opacity-40 cursor-not-allowed" : ""}`}
                aria-pressed={active}
              >
                {c}
              </button>
            );
          })}
        </div>
        <p className="text-faint text-xs mt-2 leading-snug">
          EUR ist die Basiswährung der Thesis; der risikofreie Zins ist die realisierte
          €STR/EONIA-Tagesreihe (siehe unten), nicht der 3M-EURIBOR. Live-Kurse werden über
          EURUSD nach EUR umgerechnet.
          {params.source === "frozen" && (
            <> Der <strong>eingefrorene</strong> Datensatz liegt ausschließlich in EUR vor —
            USD ist hier deaktiviert, weil sonst EUR-Zahlen unter USD-Etikett erschienen.</>
          )}
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
              { id: "estr_chained", label: "€STR/EONIA (real)" },
              { id: "constant", label: "Konstant" },
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
        {params.rf_mode === "constant" ? (
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
            Tagesgenaue realisierte Zinsreihe: €STR ab Okt 2019, davor EONIA − 8,5 bp (ECB SDMX,
            eingefroren).{" "}
            {negTxt ? (
              <>
                In <span className="nums tabular-nums">{negTxt}</span> der Tage{" "}
                <em>dieses</em> Fensters war der Zins negativ
              </>
            ) : (
              <>In weiten Teilen des Fensters war der Zins negativ</>
            )}{" "}
            — eine feste Konstante würde der Cash-Quote der Vol-Control einen Ertrag
            gutschreiben, den sie nie verdient hat. „Konstant“ bleibt für die Sensitivitätsanalyse.
          </p>
        )}
      </div>
    </div>
  );
}
