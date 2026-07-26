// Client-side fetchers. They talk only to our own /api/* route handlers, which
// in turn proxy the Python engine. The browser therefore never needs to know
// the engine URL and we keep one same-origin surface.
import type {
  AnalyticsResponse,
  AssetInfo,
  ScenarioInfo,
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
async function postJson<T>(path: string, body: unknown, retries = 4,
                           timeoutMs = 75_000): Promise<T> {
  let lastErr = "";
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      // Without a client deadline a hung request waits forever and the UI keeps
      // claiming it is still computing. 75 s sits just past the route's own 60 s
      // budget, so a real gateway timeout still surfaces as a 504 first.
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeoutMs);
      let res: Response;
      try {
        res = await fetch(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: ctrl.signal,
        });
      } finally {
        clearTimeout(timer);
      }
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
      const err = e as Error;
      lastErr = err.name === "AbortError"
        ? `Zeitlimit überschritten (${Math.round(timeoutMs / 1000)} s) — die Berechnung ist auf dem Server länger gelaufen, als die Route warten darf.`
        : err.message;
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

/** Inference via the ASYNCHRONOUS job route.
 *
 *  A synchronous call cannot work in the deployment: measured 192–234 s on the free
 *  tier against a 60 s route budget, and an aborted request leaves nothing cached, so
 *  every retry restarts from zero. Starting a job and polling keeps every single HTTP
 *  request in the millisecond range, so no gateway limit is ever approached.
 *
 *  `onProgress` receives the elapsed seconds so the panel can show real progress
 *  instead of an unqualified spinner.
 */
export async function fetchHypotheses(
  p: EngineParams,
  onProgress?: (elapsedSeconds: number) => void,
  maxWaitMs = 420_000,
): Promise<HypothesesResponse> {
  const started = await postJson<{
    job_id: string | null; status: string; result?: HypothesesResponse;
  }>("/api/jobs/hypotheses", p, 2, 30_000);

  if (started.status === "done" && started.result) return started.result;   // precomputed
  if (!started.job_id) throw new Error("Engine lieferte keine Job-ID zurück.");

  const t0 = Date.now();
  while (Date.now() - t0 < maxWaitMs) {
    await sleep(1500);
    const res = await fetch(`/api/jobs/${started.job_id}`, { cache: "no-store" });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error("Der Rechen-Job ist verloren gegangen (Server neu gestartet). Bitte erneut starten.");
      }
      continue;                                   // transient gateway hiccup -> keep polling
    }
    const s = (await res.json()) as {
      status: string; result?: HypothesesResponse; error?: string; elapsed?: number;
    };
    if (s.status === "done" && s.result) return s.result;
    if (s.status === "error") throw new Error(s.error ?? "Berechnung fehlgeschlagen.");
    onProgress?.(s.elapsed ?? Math.round((Date.now() - t0) / 1000));
  }
  throw new Error(
    `Die Berechnung läuft seit über ${Math.round(maxWaitMs / 60_000)} Minuten. ` +
    "Sie läuft serverseitig weiter — ein erneuter Versuch trifft dann den Cache.",
  );
}

export const fetchDescribe = (p: EngineParams) =>
  postJson<DescribeResponse>("/api/describe", p);

export const fetchTimeSeries = (p: EngineParams) =>
  postJson<TimeSeriesResponse>("/api/timeseries", p);

export const fetchRobustness = (p: EngineParams) =>
  postJson<RobustnessResponse>("/api/robustness", p);

export const fetchAnalytics = (p: EngineParams) =>
  postJson<AnalyticsResponse>("/api/analytics", p);

/** Load the engine's scenario catalogue (single source of truth for sample designs). */
export async function fetchScenarios(): Promise<ScenarioInfo[]> {
  const res = await fetch("/api/scenarios");
  if (!res.ok) throw new Error(`Szenarien konnten nicht geladen werden (${res.status}).`);
  const data = (await res.json()) as { scenarios: ScenarioInfo[] };
  return data.scenarios;
}

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
