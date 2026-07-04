"use client";

import type {
  AnalyticsResponse,
  BacktestResponse,
  DescribeResponse,
  EngineParams,
  HypothesesResponse,
  ResultSnapshot,
  RobustnessResponse,
  SweepResponse,
  TimeSeriesResponse,
} from "@/lib/types";
import { THESIS } from "@/lib/thesis";
import HfwuLogo from "./HfwuLogo";
import ThemeToggle from "./ThemeToggle";
import ControlPanel from "./ControlPanel";
import DescriptiveStats from "./DescriptiveStats";
import MetricsTable from "./MetricsTable";
import TimeSeriesSection from "./TimeSeriesSection";
import SweepCharts from "./SweepCharts";
import RobustnessSection from "./RobustnessSection";
import AnalyticsSection from "./AnalyticsSection";
import HypothesesPanel from "./HypothesesPanel";
import InfoNotes from "./InfoNotes";
import AiExplainer from "./AiExplainer";

interface Props {
  params: EngineParams;
  onChange: (next: Partial<EngineParams>) => void;
  backtest: BacktestResponse | null;
  sweep: SweepResponse | null;
  hypotheses: HypothesesResponse | null;
  describe: DescribeResponse | null;
  timeseries: TimeSeriesResponse | null;
  robustness: RobustnessResponse | null;
  analytics: AnalyticsResponse | null;
  loadingFast: boolean;
  loadingHyp: boolean;
  loadingSlow: boolean;
  error: string | null;
  exporting: boolean;
  exportingExcel: boolean;
  downloadingDataset: boolean;
  onExportPdf: () => void;
  onExportExcel: () => void;
  onDownloadDataset: () => void;
  onReconfigure: () => void;
  getSnapshot: () => ResultSnapshot;
}

// Step 3 — the auswertung. Compact masthead + live-tuning sidebar + all exhibits.
export default function ResultsView({
  params,
  onChange,
  backtest,
  sweep,
  hypotheses,
  describe,
  timeseries,
  robustness,
  analytics,
  loadingFast,
  loadingHyp,
  loadingSlow,
  error,
  exporting,
  exportingExcel,
  downloadingDataset,
  onExportPdf,
  onExportExcel,
  onDownloadDataset,
  onReconfigure,
  getSnapshot,
}: Props) {
  const ready = Boolean(backtest || hypotheses);

  return (
    <main className="min-h-screen">
      <header className="border-b border-hairline-strong">
        <div className="mx-auto max-w-[1240px] px-8 py-5 flex items-end justify-between gap-6">
          <div className="flex items-center gap-4">
            <HfwuLogo height={34} />
            <div className="border-l border-hairline-strong pl-4">
              <div className="eyebrow">Volatility-Control Treasury · Auswertung</div>
              <h1 className="display text-[1.7rem] leading-tight mt-1">Risk Terminal</h1>
            </div>
          </div>
          <div className="flex items-end gap-4 shrink-0">
          <div className="text-right shrink-0 text-xs text-muted nums">
            <div className="eyebrow">Datensatz</div>
            <div className="mt-1">
              {describe?.source === "live" ? "Live · Yahoo Finance" : "Synthetisch"} ·{" "}
              {params.base_currency}
            </div>
            <div className="text-faint mt-0.5">
              {params.assets.length} Assets
              {describe?.window?.observations
                ? ` · ${describe.window.observations.toLocaleString("de-DE")} Tage`
                : ""}
            </div>
          </div>
          <ThemeToggle className="mb-0.5" />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1240px] px-8 py-8">
        {error && (
          <div className="mb-6 border border-neg/40 bg-paper px-4 py-3 text-sm text-neg">{error}</div>
        )}

        <div className="grid lg:grid-cols-[300px_1fr] gap-8">
          <ControlPanel
            params={params}
            onChange={onChange}
            onExportPdf={onExportPdf}
            onExportExcel={onExportExcel}
            onReconfigure={onReconfigure}
            exporting={exporting}
            exportingExcel={exportingExcel}
            busy={loadingFast || loadingHyp}
          />

          <div className="space-y-10 min-w-0">
            <MetricsTable data={backtest} loading={loadingFast} selectedTargetVol={params.target_vol} />
            <TimeSeriesSection data={timeseries} loading={loadingFast} />
            <SweepCharts data={sweep} loading={loadingFast} />
            <RobustnessSection data={robustness} loading={loadingSlow} selectedTargetVol={params.target_vol} />
            <AnalyticsSection data={analytics} loading={loadingSlow} />
            <DescriptiveStats data={describe} loading={loadingFast} />
            <HypothesesPanel data={hypotheses} loading={loadingHyp} />
            <InfoNotes
              fingerprint={backtest?.fingerprint ?? null}
              source={params.source}
              tradWeights={params.trad_weights}
              rf={backtest?.rf ?? null}
              onDownloadDataset={onDownloadDataset}
              downloadingDataset={downloadingDataset}
            />
            <AiExplainer getSnapshot={getSnapshot} ready={ready} />
          </div>
        </div>

        <footer className="mt-14 pt-5 border-t border-hairline text-faint text-xs leading-relaxed">
          Single source of truth: alle Kennzahlen, Sweeps, Tests und deskriptiven Statistiken
          werden von der Python-Engine (<code>volcontrol</code>) berechnet. {THESIS.examiners[0].name}{" "}
          (Erstprüfer), {THESIS.examiners[1].name} (Zweitprüferin). Kein Anlageratschlag.
        </footer>
      </div>
    </main>
  );
}
