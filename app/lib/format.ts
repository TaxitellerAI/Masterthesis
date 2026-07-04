// Number formatting for a research terminal: deterministic, tabular, signed
// where it matters. All formatters tolerate null/NaN so the UI never crashes
// on a partial result.

const isNum = (x: unknown): x is number =>
  typeof x === "number" && Number.isFinite(x);

// Non-breaking space before the percent sign so "−20.66 %" never wraps onto
// two lines inside a tight table column.
const NBSP = " ";

/** Percent with fixed decimals, e.g. 0.0722 -> "7.22 %". */
export function pct(x: number | null | undefined, decimals = 2): string {
  if (!isNum(x)) return "—";
  return `${(x * 100).toFixed(decimals)}${NBSP}%`;
}

/** Signed percent, e.g. 0.0195 -> "+1.95 %", -0.01 -> "−1.00 %". */
export function pctSigned(x: number | null | undefined, decimals = 2): string {
  if (!isNum(x)) return "—";
  const v = x * 100;
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}${Math.abs(v).toFixed(decimals)}${NBSP}%`;
}

/** Plain number with fixed decimals (e.g. Sharpe). */
export function num(x: number | null | undefined, decimals = 2): string {
  if (!isNum(x)) return "—";
  return x.toFixed(decimals);
}

/** Signed plain number. */
export function numSigned(x: number | null | undefined, decimals = 2): string {
  if (!isNum(x)) return "—";
  const sign = x > 0 ? "+" : x < 0 ? "−" : "";
  return `${sign}${Math.abs(x).toFixed(decimals)}`;
}

/**
 * p-value with the conventions a thesis reader expects: very small values are
 * shown as "< 0.001", everything else to three decimals.
 */
export function pval(p: number | null | undefined): string {
  if (!isNum(p)) return "—";
  if (p < 0.001) return "< 0.001";
  return p.toFixed(3);
}

/** Significance verdict at a given alpha (default 5 %). */
export function isSignificant(p: number | null | undefined, alpha = 0.05): boolean {
  return isNum(p) && p < alpha;
}

/** Map a raw strategy key to a human label. */
export function strategyLabel(key: string): string {
  if (key === "BuyHold") return "Buy-and-Hold";
  if (key === "Benchmark_TrueBH") return "True BH (Drift)";
  if (key === "Benchmark_6040") return "60/40";
  if (key === "Benchmark_RiskParity") return "Risk-Parity";
  const m = key.match(/^VolControl_(\d+)$/);
  if (m) return `Vol-Control ${m[1]} %`;
  return key;
}

/** Is this strategy key an alternative benchmark (vs. BH / vol-control)? */
export function isBenchmark(key: string): boolean {
  return key.startsWith("Benchmark_");
}

/** Currency symbol for the active base currency. */
export function currencySymbol(c: string): string {
  return c === "USD" ? "$" : "€";
}
