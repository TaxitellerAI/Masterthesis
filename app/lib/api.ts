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

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Wake the engine BEFORE firing the heavy compute burst. On the free tier the
// service sleeps after ~15 min idle and needs 30–60 s to boot; hitting it with
// several heavy POSTs at once means each races its own retry budget against the
// cold start and some give up first. A single cheap /health probe boots the
// engine and, once it answers 200, every following compute call lands on a warm
// instance — the same smooth run you get locally. Polls up to ~2 min, then lets
// the caller proceed (postJson's own retries remain the final safety net).
export async function ensureEngineAwake(
  onWaking?: (waking: boolean) => void,
  attempts = 24,
  perProbeTimeoutMs = 9000,
): Promise<void> {
  for (let i = 0; i < attempts; i++) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), perProbeTimeoutMs);
      const res = await fetch("/api/health", { cache: "no-store", signal: ctrl.signal });
      clearTimeout(t);
      if (res.ok) {
        onWaking?.(false);
        return; // warm
      }
    } catch {
      // network error / abort while the instance is still booting — keep polling
    }
    onWaking?.(true); // first miss ⇒ we are cold-starting; surface it to the UI
    await sleep(2500);
  }
  onWaking?.(false); // give up gating; proceed and let per-request retries handle it
}

// The compute engine runs on a free tier that sleeps when idle; even after the
// wake probe, a gateway hiccup can surface a 502/503/504. We retry a few times
// on gateway/timeout/network errors before giving up, so a cold engine self-heals
// instead of surfacing an error to the user.
async function postJson<T>(path: string, body: unknown, retries = 4): Promise<T> {
  let lastErr = "";
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) return (await res.json()) as T;
      // 502/503/504 → engine waking or gateway timeout → worth retrying
      if ([502, 503, 504].includes(res.status) && attempt < retries) {
        lastErr = `Engine wird aufgeweckt… (${res.status})`;
        await sleep(4000 + attempt * 3000);
        continue;
      }
      const data = await res.json().catch(() => ({}) as { error?: string });
      throw new Error(data.error ?? `Anfrage fehlgeschlagen (${res.status}).`);
    } catch (e) {
      lastErr = (e as Error).message;
      // network error (fetch reject) → also retry
      if (attempt < retries && !/fehlgeschlagen \(4/.test(lastErr)) {
        await sleep(4000 + attempt * 3000);
        continue;
      }
      throw new Error(lastErr);
    }
  }
  throw new Error(lastErr || "Anfrage fehlgeschlagen.");
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
