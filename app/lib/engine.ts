// Server-side helper: the ONLY place that knows the engine URL. Route handlers
// import this; the browser never sees ENGINE_URL. This keeps a single origin
// for the client and keeps the compute host private.
import "server-only";
import type { EngineParams } from "./types";

// Default engine host: local uvicorn in development, the Render deployment in
// production. An explicit ENGINE_URL env var overrides both.
const DEFAULT_ENGINE =
  process.env.NODE_ENV === "production"
    ? "https://treasury-volcontrol-engine.onrender.com"
    : "http://localhost:8000";
const ENGINE_URL = (process.env.ENGINE_URL ?? DEFAULT_ENGINE).replace(/\/$/, "");

export class EngineError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "EngineError";
  }
}

/** POST a parameter set to one of the engine's compute endpoints. */
export async function callEngine<T>(
  endpoint: "backtest" | "sweep" | "hypotheses" | "describe" | "timeseries" | "robustness" | "analytics",
  params: EngineParams,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${ENGINE_URL}/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
      cache: "no-store",
    });
  } catch (e) {
    // Network-level failure: engine not running / unreachable.
    throw new EngineError(
      `Engine nicht erreichbar unter ${ENGINE_URL}. Läuft uvicorn? (${(e as Error).message})`,
      502,
    );
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new EngineError(`Engine ${endpoint} fehlgeschlagen (${res.status}). ${detail}`, res.status);
  }
  return (await res.json()) as T;
}

/** GET the engine health probe (used by the status bar). */
export async function engineHealth(): Promise<Response> {
  return fetch(`${ENGINE_URL}/health`, { cache: "no-store" });
}

/** GET the curated asset universe (used by the configurator's selector). */
export async function engineAssets(): Promise<Response> {
  return fetch(`${ENGINE_URL}/assets`, { cache: "no-store" });
}

/** POST to an engine endpoint that returns a binary payload (e.g. the .xlsx). */
export async function callEngineRaw(endpoint: "workbook" | "dataset", params: EngineParams): Promise<Response> {
  try {
    return await fetch(`${ENGINE_URL}/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
      cache: "no-store",
    });
  } catch (e) {
    throw new EngineError(`Engine nicht erreichbar unter ${ENGINE_URL}. (${(e as Error).message})`, 502);
  }
}
