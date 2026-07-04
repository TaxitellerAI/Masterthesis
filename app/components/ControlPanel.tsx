"use client";

import type { EngineParams } from "@/lib/types";
import ParamControls from "./ParamControls";

interface Props {
  params: EngineParams;
  onChange: (next: Partial<EngineParams>) => void;
  onExportPdf: () => void;
  onExportExcel: () => void;
  onReconfigure: () => void;
  exporting: boolean;
  exportingExcel: boolean;
  /** True while any engine call is in flight (drives the subtle status text). */
  busy: boolean;
}

// Results sidebar: live re-tuning of the strategy/market parameters (asset
// selection + data source stay fixed for the session — change them via the
// configurator), plus PDF export and a way back to the configurator.
export default function ControlPanel({
  params,
  onChange,
  onExportPdf,
  onExportExcel,
  onReconfigure,
  exporting,
  exportingExcel,
  busy,
}: Props) {
  return (
    <aside className="lg:sticky lg:top-6 self-start">
      <div className="border border-hairline bg-panel">
        <div className="px-5 py-4 border-b border-hairline flex items-center justify-between">
          <span className="eyebrow">Steuerung</span>
          {busy && <span className="text-faint text-xs nums">rechnet…</span>}
        </div>

        <div className="px-5 py-5">
          <ParamControls params={params} onChange={onChange} />
        </div>

        <div className="px-5 py-4 border-t border-hairline space-y-2">
          <button
            onClick={onExportPdf}
            disabled={exporting}
            className="w-full py-2 text-sm border border-ink bg-ink text-paper hover:bg-transparent hover:text-ink transition-colors disabled:opacity-40"
          >
            {exporting ? "PDF wird erzeugt…" : "PDF-Report exportieren"}
          </button>
          <button
            onClick={onExportExcel}
            disabled={exportingExcel}
            className="w-full py-2 text-sm border border-accent text-accent hover:bg-accent hover:text-paper transition-colors disabled:opacity-40"
          >
            {exportingExcel ? "Excel wird erzeugt…" : "Excel-Transparenz (.xlsx)"}
          </button>
          <button
            onClick={onReconfigure}
            className="w-full py-2 text-sm border border-hairline-strong text-muted hover:text-ink hover:border-ink transition-colors"
          >
            Neue Konfiguration
          </button>
          <p className="text-faint text-xs pt-1 leading-snug">
            PDF = Bericht. Excel = alle Kursdaten + jede Kennzahl als <em>lebende Formel</em> zum
            Nachvollziehen.
          </p>
        </div>
      </div>
    </aside>
  );
}
