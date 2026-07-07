"use client";

import { useState } from "react";
import type { EngineParams, Fingerprint, RfInfo } from "@/lib/types";
import { BASE_TRAD_WEIGHTS } from "@/lib/types";
import { sourceLabel } from "@/lib/format";

interface Props {
  fingerprint: Fingerprint | null;
  source: string;
  tradWeights: EngineParams["trad_weights"];
  rf: RfInfo | null;
  onDownloadDataset: () => void;
  downloadingDataset: boolean;
}

// Citable method references for the statistical machinery used by the engine.
const REFERENCES: string[] = [
  "Politis, D. N. / Romano, J. P. (1994): The Stationary Bootstrap. JASA 89(428).",
  "Bailey, D. H. / López de Prado, M. (2014): The Deflated Sharpe Ratio. Journal of Portfolio Management 40(5).",
  "Newey, W. K. / West, K. D. (1987): A Simple, Positive Semi-definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix. Econometrica 55(3).",
  "Efron, B. (1987): Better Bootstrap Confidence Intervals (BCa). JASA 82(397).",
  "Mann, H. B. (1945): Nonparametric Tests Against Trend. Econometrica 13(3); Kendall, M. G. (1975): Rank Correlation Methods.",
  "Holm, S. (1979): A Simple Sequentially Rejective Multiple Test Procedure. Scandinavian Journal of Statistics 6(2).",
  "Moreira, A. / Muir, T. (2017): Volatility-Managed Portfolios. Journal of Finance 72(4).",
  "EZB: Euro Short-Term Rate (€STR), Serie EST.B.EU000A2X2A25.WT, ECB Data Portal.",
];

// Methodological & Controlling context. These are DECISION/DISCUSSION pointers
// for the written thesis — not computed results — surfaced so the tool and the
// text stay consistent about assumptions and limitations.
const NOTES: { title: string; body: string }[] = [
  {
    title: "Einordnung ins Corporate Treasury",
    body:
      "Ein Treasury hebelt und shortet nicht (Exposure-Cap = 1). Relevante Steuerungsgrößen sind Risikoappetit (CVaR-/Drawdown-Limits als Policy), Liquiditätsbedarf und die Anbindung an wertorientierte Steuerung (RAROC/ökonomisches Kapital). Die Kennzahlen sind Input für die Treasury-Richtlinie, nicht für ein Handelsdesk.",
  },
  {
    title: "Bilanzielle & steuerliche Behandlung von Krypto",
    body:
      "Nach IFRS werden Kryptowerte i. d. R. als immaterielle Vermögenswerte oder (bei Handelsabsicht) zum Fair Value bilanziert; nach HGB gilt strenges Niederstwertprinzip (Impairment-only). Das verzerrt die ökonomische 'Halten'-Perspektive gegenüber der reinen Kursbetrachtung und gehört in die Diskussion.",
  },
  {
    title: "Währungs-Restrisiko",
    body:
      "Live-Kurse werden über EURUSD nach EUR umgerechnet. Ein EUR-Treasury trägt beim Halten USD-denominierter Krypto/ETFs ein FX-Exposure, das hier in der EUR-Sicht enthalten, aber nicht separat gehedged ist — ein eigenständiges Risiko- und Hedging-Thema.",
  },
  {
    title: "Zins-Annahme",
    body:
      "Der risikofreie Zins ist konstant angesetzt. Über 2018–2024 verlief €STR/3M-EURIBOR von negativ zu ~4 %; eine Zeitreihe würde Sharpe und Überschussrendite spürbar verändern. Als bewusste Vereinfachung dokumentiert.",
  },
  {
    title: "Survivorship-Bias im Krypto-Universum",
    body:
      "BTC/ETH/XRP/BNB/SOL sind die heutigen großen Coins — die Auswahl ist rückschauend verzerrt. Sauber wäre ein zum Startzeitpunkt investierbares Universum. Die Verzerrung ist zu benennen und in der Interpretation zu berücksichtigen.",
  },
  {
    title: "Annualisierung (Kalender)",
    body:
      "Deskriptive Kennzahlen nutzen den nativen Kalender je Asset (Krypto ~365, Aktien ~252 Tage/Jahr). Der Portfolio-Backtest samplet auf dem gemeinsamen Handelskalender (~252) — bewusste, konsistente Annahme für die tägliche Portfoliobildung.",
  },
];

export default function InfoNotes({
  fingerprint,
  source,
  tradWeights,
  rf,
  onDownloadDataset,
  downloadingDataset,
}: Props) {
  const s = tradWeights.MSCI_World + tradWeights.Global_Bonds + tradWeights.Gold || 1;
  const split = {
    MSCI_World: tradWeights.MSCI_World / s,
    Global_Bonds: tradWeights.Global_Bonds / s,
    Gold: tradWeights.Gold / s,
  };
  const isBase =
    Math.abs(split.MSCI_World - BASE_TRAD_WEIGHTS.MSCI_World) < 1e-4 &&
    Math.abs(split.Global_Bonds - BASE_TRAD_WEIGHTS.Global_Bonds) < 1e-4 &&
    Math.abs(split.Gold - BASE_TRAD_WEIGHTS.Gold) < 1e-4;
  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">Methodik &amp; Einordnung</h2>
        <span className="eyebrow">Diskussion / Annahmen</span>
      </div>

      <div className="border border-hairline bg-paper divide-y divide-hairline">
        {NOTES.map((n) => (
          <details key={n.title} className="group">
            <summary className="px-4 py-3 cursor-pointer text-sm font-medium flex items-center justify-between hover:text-accent transition-colors list-none">
              {n.title}
              <span className="text-faint text-xs group-open:rotate-90 transition-transform">›</span>
            </summary>
            <p className="px-4 pb-3.5 -mt-1 text-sm text-muted leading-relaxed">{n.body}</p>
          </details>
        ))}
      </div>

      {/* Method references */}
      <details className="mt-3 border border-hairline bg-paper group">
        <summary className="px-4 py-3 cursor-pointer text-sm font-medium flex items-center justify-between hover:text-accent transition-colors list-none">
          Methoden-Referenzen (zitierfähig)
          <span className="text-faint text-xs group-open:rotate-90 transition-transform">›</span>
        </summary>
        <ol className="px-4 pb-3.5 -mt-1 text-xs text-muted leading-relaxed list-decimal list-inside space-y-1">
          {REFERENCES.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ol>
      </details>

      {/* Reproducibility fingerprint + actions */}
      <div className="mt-3 border border-hairline bg-panel px-4 py-2.5 text-xs text-muted nums flex flex-wrap items-center gap-x-6 gap-y-2">
        <span className="eyebrow">Reproduzierbarkeit</span>
        <span>
          Datenquelle <span className="text-ink">{sourceLabel(source)}</span>
        </span>
        <span>
          Basis-Allokation{" "}
          <span className={isBase ? "text-ink" : "text-neg"}>
            {(split.MSCI_World * 100).toFixed(0)}/{(split.Global_Bonds * 100).toFixed(0)}/
            {(split.Gold * 100).toFixed(0)}
            {isBase ? " (Basisfall)" : " (≠ Basisfall)"}
          </span>
        </span>
        {rf && (
          <span>
            rf{" "}
            <span className="text-ink">
              {(rf.effective_annual * 100).toFixed(2)} %{" "}
              {rf.mode === "estr" && rf.estr && !rf.estr.error ? "(€STR Ø, ECB)" : "(manuell)"}
            </span>
          </span>
        )}
        {fingerprint && (
          <>
            <span>
              Daten-Hash <span className="text-ink">{fingerprint.hash}</span>
            </span>
            <span>
              Fenster <span className="text-ink">{fingerprint.start}</span> – <span className="text-ink">{fingerprint.end}</span>
            </span>
          </>
        )}
        <span className="flex items-center gap-2 ml-auto">
          <button
            onClick={onDownloadDataset}
            disabled={downloadingDataset}
            className="px-3 py-1 border border-hairline-strong text-muted hover:text-ink hover:border-ink transition-colors disabled:opacity-40"
          >
            {downloadingDataset ? "Lädt…" : "Datensatz (.csv)"}
          </button>
          <CopyLinkButton />
        </span>
      </div>
      <p className="text-faint text-xs mt-2 leading-snug">
        Diese Punkte sind Diskussions-/Annahme-Hinweise für die schriftliche Arbeit — keine berechneten
        Ergebnisse. Der Daten-Hash bindet einen Report an den exakten Datensatz; der{" "}
        <strong>Datensatz-Export</strong> friert die verwendeten Kurse als CSV ein (Hash im Dateinamen)
        und der <strong>Konfigurations-Link</strong> stellt genau diese Auswertung wieder her. Für die
        vollständige Nachvollziehbarkeit steht zudem der <strong>Excel-Export</strong> bereit: alle
        Kursdaten plus jede Kennzahl als lebende Formel (Kurse → Renditen → Portfolio → Kennzahlen).
      </p>
    </section>
  );
}

// Copies the current (config-encoded) URL — the citable permalink to this result.
function CopyLinkButton() {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(window.location.href);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch {}
      }}
      className="px-3 py-1 border border-accent text-accent hover:bg-accent hover:text-paper transition-colors"
    >
      {copied ? "Kopiert ✓" : "Konfigurations-Link"}
    </button>
  );
}
