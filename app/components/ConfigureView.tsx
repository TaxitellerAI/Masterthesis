"use client";

import type { AssetInfo, EngineParams } from "@/lib/types";
import HfwuLogo from "./HfwuLogo";
import ThemeToggle from "./ThemeToggle";
import AssetSelector from "./AssetSelector";
import DataSourcePicker from "./DataSourcePicker";
import ParamControls from "./ParamControls";
import MethodControls from "./MethodControls";
import AllocationControls from "./AllocationControls";

interface Props {
  catalog: AssetInfo[];
  catalogLoading: boolean;
  params: EngineParams;
  onChange: (next: Partial<EngineParams>) => void;
  onBack: () => void;
  onRun: () => void;
  running: boolean;
  error: string | null;
}

// Step 2 — the configurator. Pick the universe, the data source, and the
// strategy parameters, then trigger the computation.
export default function ConfigureView({
  catalog,
  catalogLoading,
  params,
  onChange,
  onBack,
  onRun,
  running,
  error,
}: Props) {
  const canRun = params.assets.length > 0 && !running;

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-[1000px] px-8 py-12">
        <div className="flex items-center justify-between gap-4">
          <button onClick={onBack} className="text-muted text-sm hover:text-ink transition-colors">
            ← Übersicht
          </button>
          <span className="flex items-center gap-3">
            <HfwuLogo height={34} />
            <ThemeToggle />
          </span>
        </div>

        <div className="mt-5 mb-9">
          <div className="eyebrow">Schritt 2 von 3</div>
          <h1 className="display text-3xl mt-2">Konfiguration</h1>
          <p className="text-muted text-sm mt-2 max-w-2xl">
            Anlageuniversum, Datenquelle und Parameter festlegen. Die Auswahl bestimmt das
            gemeinsame Datenfenster; bei Live-Daten werden aktuelle Kurse gezogen.
          </p>
        </div>

        <div className="space-y-9">
          {/* Universe */}
          <section className="border border-hairline bg-paper p-6 card-hover">
            {catalogLoading ? (
              <div className="text-faint text-sm py-6 text-center">Universum wird geladen…</div>
            ) : (
              <AssetSelector
                catalog={catalog}
                selected={params.assets}
                onChange={(assets) => onChange({ assets })}
              />
            )}
          </section>

          {/* Data source */}
          <section className="border border-hairline bg-paper p-6 card-hover">
            <DataSourcePicker
              source={params.source}
              years={params.years}
              onSource={(source) => onChange({ source })}
              onYears={(years) => onChange({ years })}
            />
          </section>

          {/* Parameters */}
          <section className="border border-hairline bg-paper p-6 card-hover">
            <span className="eyebrow">Parameter</span>
            <div className="mt-4 max-w-md">
              <ParamControls params={params} onChange={onChange} />
            </div>
          </section>

          {/* Methodology & risk limits */}
          <section className="border border-hairline bg-paper p-6 card-hover">
            <span className="eyebrow">Methodik &amp; Risiko-Limits</span>
            <div className="mt-4">
              <MethodControls params={params} onChange={onChange} />
            </div>
          </section>

          {/* Optional base-allocation sensitivity */}
          <section className="border border-hairline bg-paper p-6 card-hover">
            <div className="max-w-md">
              <AllocationControls
                value={params.trad_weights}
                onChange={(trad_weights) => onChange({ trad_weights })}
              />
            </div>
          </section>
        </div>

        {error && (
          <div className="mt-6 border border-neg/40 bg-paper px-4 py-3 text-sm text-neg">
            {error}
          </div>
        )}

        <div className="mt-8 flex items-center gap-4">
          <button
            onClick={onRun}
            disabled={!canRun}
            className="px-7 py-2.5 text-sm border border-ink bg-ink text-paper hover:bg-transparent hover:text-ink transition-colors disabled:opacity-40 disabled:hover:bg-ink disabled:hover:text-paper"
          >
            {running
              ? params.source === "live"
                ? "Kurse werden gezogen & berechnet…"
                : "Wird berechnet…"
              : "Daten laden & berechnen →"}
          </button>
          {params.source === "live" && (
            <span className="text-faint text-xs">Live-Abruf kann einige Sekunden dauern.</span>
          )}
        </div>
      </div>
    </main>
  );
}
