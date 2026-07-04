// Client-side fetchers. They talk only to our own /api/* route handlers, which
// in turn proxy the Python engine. The browser therefore never needs to know
// the engine URL and we keep one same-origin surface.
import type {
  AnalyticsResponse,
  AssetInfo,
  BacktestResponse,
  DescribeResponse,
  EngineParams,
  HypothesesResponse,
  ResultSnapshot,
  RobustnessResponse,
  SweepResponse,
  TimeSeriesResponse,
} from "./types";

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}) as { error?: string });
    throw new Error(data.error ?? `Anfrage fehlgeschlagen (${res.status}).`);
  }
  return (await res.json()) as T;
}

export const fetchBacktest = (p: EngineParams) =>
  postJson<BacktestResponse>("/api/backtest", p);

export const fetchSweep = (p: EngineParams) =>
  postJson<SweepResponse>("/api/sweep", p);

export const fetchHypotheses = (p: EngineParams) =>
  postJson<HypothesesResponse>("/api/hypotheses", p);

export const fetchDescribe = (p: EngineParams) =>
  postJson<DescribeResponse>("/api/describe", p);

export const fetchTimeSeries = (p: EngineParams) =>
  postJson<TimeSeriesResponse>("/api/timeseries", p);

export const fetchRobustness = (p: EngineParams) =>
  postJson<RobustnessResponse>("/api/robustness", p);

export const fetchAnalytics = (p: EngineParams) =>
  postJson<AnalyticsResponse>("/api/analytics", p);

/** Load the curated asset universe for the configurator. */
export async function fetchAssets(): Promise<AssetInfo[]> {
  const res = await fetch("/api/assets");
  if (!res.ok) throw new Error(`Asset-Universum konnte nicht geladen werden (${res.status}).`);
  const data = (await res.json()) as { assets: AssetInfo[] };
  return data.assets;
}

/** Ask "The Desk" (server-side, numbers-only context) — optional question + short history. */
export const fetchExplanation = (
  snapshot: ResultSnapshot,
  question?: string,
  history?: { role: "user" | "assistant"; content: string }[],
) => postJson<{ text: string; ok: boolean }>("/api/explain", { snapshot, question, history });

/** Request the server-rendered PDF for a snapshot; returns a Blob to download. */
export async function fetchPdf(snapshot: ResultSnapshot): Promise<Blob> {
  const res = await fetch("/api/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ snapshot }),
  });
  if (!res.ok) throw new Error(`PDF-Export fehlgeschlagen (${res.status}).`);
  return res.blob();
}

/** Request the transparency workbook (.xlsx) for the current parameters. */
export async function fetchWorkbook(p: EngineParams): Promise<Blob> {
  const res = await fetch("/api/workbook", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(p),
  });
  if (!res.ok) throw new Error(`Excel-Export fehlgeschlagen (${res.status}).`);
  return res.blob();
}

/** Download the frozen dataset CSV; returns { blob, filename } (hash in the name). */
export async function fetchDataset(p: EngineParams): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch("/api/dataset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(p),
  });
  if (!res.ok) throw new Error(`Dataset-Export fehlgeschlagen (${res.status}).`);
  const disp = res.headers.get("content-disposition") ?? "";
  const m = disp.match(/filename="?([^";]+)"?/);
  return { blob: await res.blob(), filename: m?.[1] ?? "treasury-dataset.csv" };
}
