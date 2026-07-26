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
  "EZB: EONIA, Serie EON.D.EONIA_TO.RATE, ECB Data Portal (ab 01.10.2019 = €STR + 8,5 bp).",
];

// Methodological & Controlling context. These are DECISION/DISCUSSION pointers
// for the written thesis — not computed results — surfaced so the tool and the
// text stay consistent about assumptions and limitations.
function buildNotes(negTxt: string | null): { title: string; body: string }[] { return [
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
    title: "Risikofreier Zins (tagesgenau, verkettet)",
    body:
      "Der risikofreie Zins ist KEINE Konstante, sondern die realisierte Tagesreihe: €STR ab 01.10.2019, davor EONIA − 8,5 bp (offizieller EZB-Umstellungsspread; im Überlappungsfenster gilt er an jedem Tag exakt, die Verkettung ist also bruchfrei). Das ist ergebniskritisch, nicht kosmetisch: Die Vol-Control verzinst ihre nicht investierte Quote mit (1 − Exposure) · rf, und " +
      (negTxt ? `in ${negTxt} der Tage des AKTIVEN Fensters` : "in weiten Teilen des Fensters") +
      " war der Zins negativ — gerade in den Stressphasen mit niedrigem Exposure. Eine feste Konstante würde der Cash-Quote einen Ertrag gutschreiben, den sie nie verdient hat, während Buy-and-Hold (voll investiert, keine Cash-Quote) unberührt bleibt. Umrechnung p. a. → täglich nach Geldmarktkonvention act/360 über die tatsächlichen Kalendertage. Der Modus 'Konstant' bleibt für die Sensitivitätsanalyse erhalten.",
  },
  {
    title: "Untersuchungszeitraum & Reproduzierbarkeit",
    body:
      "Das Datenfenster ist mit festen Kalendergrenzen definiert (01.01.2018 – 31.12.2025, acht volle Jahre), nicht als rollierendes 'letzte N Jahre' — sonst lieferte jeder Abruf einen anderen Datenstand und keine berichtete Zahl wäre zitierfähig. 2018 ist zugleich das erste Jahr mit vollständiger Historie aller Default-Kryptowerte. Kurse und Zinsreihe sind als Snapshot eingefroren. Ausgewiesen werden ZWEI Anker: der Datensatz-Hash bürgt für die Datenbasis allein, der Lauf-Hash zusätzlich für Fenstergrenzen, Datenquelle, Zinsmodus und Gewichte — zwei Läufe mit unterschiedlichen Annahmen können also nie denselben Lauf-Hash tragen. Beide sind auf 1e-12 quantisiert und damit plattformunabhängig reproduzierbar (der byte-exakte Digest unterscheidet sich zwischen macOS und Linux um ein letztes Bit und taugt deshalb nicht als zitierfähiger Wert).",
  },
  {
    title: "Survivorship-Bias im Krypto-Universum",
    body:
      "BTC/ETH/XRP/BNB/SOL sind die heutigen großen Coins — die Auswahl ist rückschauend verzerrt. Sauber wäre ein zum Startzeitpunkt investierbares Universum. Die Verzerrung ist zu benennen und in der Interpretation zu berücksichtigen.",
  },
  {
    title: "Annualisierung (Kalender)",
    body:
      "Deskriptive Kennzahlen nutzen den nativen Kalender je Asset (Krypto ~365, Aktien ~252 Tage/Jahr; der tatsächliche Wert je Asset steht in der Spalte 'Tage/J'). Der Portfolio-Backtest samplet auf dem gemeinsamen Handelskalender — bewusste, konsistente Annahme für die tägliche Portfoliobildung. Die ausgewiesene Wölbung ist die EXZESS-Kurtosis (Normalverteilung = 0, nicht 3); positive Werte bedeuten fettere Ränder als die Normalverteilung.",
  },
];
}

export default function InfoNotes({
  fingerprint,
  source,
  tradWeights,
  rf,
  onDownloadDataset,
  downloadingDataset,
}: Props) {
  const negShare = rf?.estr?.window_share_negative;
  const NOTES = buildNotes(negShare != null ? `${(negShare * 100).toFixed(0)} %` : null);
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
              {rf.mode === "estr_chained" && rf.estr && !rf.estr.error
                ? "(€STR/EONIA real, Ø)"
                : "(konstant)"}
            </span>
          </span>
        )}
        {fingerprint && (
          <>
            {/* TWO distinct anchors, distinctly named. A report that calls two
                different values "Hash" is an open flank in the colloquium. Both are
                environment-stable; the byte-exact digest is machine-dependent and is
                therefore no longer shown as the citable value. */}
            <span>
              Datensatz-Hash{" "}
              <span className="text-ink" title="Bürgt für die Datenbasis allein (Kurse/Renditen).">
                {fingerprint.dataset_hash ?? "—"}
              </span>
            </span>
            <span>
              Lauf-Hash{" "}
              <span className="text-ink" title="Bürgt für Datenbasis UND Konfiguration (Szenario, Fenster, Zinsmodus …).">
                {fingerprint.run_hash ?? fingerprint.hash}
              </span>
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
        Ergebnisse. Der <strong>Datensatz-Hash</strong> bürgt für die Datenbasis allein, der{" "}
        <strong>Lauf-Hash</strong> zusätzlich für die Konfiguration (Szenario, Fenster,
        Zinsmodus, Gewichte). Beide sind plattformunabhängig reproduzierbar; der{" "}
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
