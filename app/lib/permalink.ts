"use client";

import type { EngineParams } from "./types";

// Citable configuration permalink: the full parameter set is base64-encoded into
// ?cfg=… so any result can be reproduced from a link (thesis appendix, examiner).
// Compact and forward-tolerant: unknown fields are ignored on decode.

export function encodeParams(p: EngineParams): string {
  const json = JSON.stringify(p);
  // UTF-8-safe base64 (asset names are ASCII, but stay safe)
  return btoa(unescape(encodeURIComponent(json)));
}

export function decodeParams(s: string): Partial<EngineParams> | null {
  try {
    const json = decodeURIComponent(escape(atob(s)));
    const obj = JSON.parse(json);
    if (typeof obj !== "object" || obj === null) return null;
    return migrate(obj as Record<string, unknown>);
  } catch {
    return null;
  }
}

// Links minted before the reproducibility fix carry a rolling `years` window, the
// retired "synthetic" source and the old rf-mode names. Map them onto the current
// schema so an already-cited link still opens instead of erroring out.
function migrate(o: Record<string, unknown>): Partial<EngineParams> {
  const out = { ...o } as Record<string, unknown>;
  if ("years" in out) {
    delete out.years; // rolling window replaced by explicit calendar bounds
  }
  if (out.source === "synthetic") out.source = "frozen";
  if (out.rf_mode === "manual") out.rf_mode = "constant";
  if (out.rf_mode === "estr") out.rf_mode = "estr_chained";
  // Same defect class as the /dataset export: a link minted before sample designs
  // existed carries a basket but no `scenario`, so it merged onto the default
  // `scenario: "S1"` — and the scenario effect then OVERWROTE the link's own
  // assets and window with S1's. The cited link silently opened a different sample
  // than it encoded. A link that names its own basket is by definition custom.
  if (!out.scenario && Array.isArray(out.assets) && out.assets.length > 0) {
    out.scenario = "custom";
  }
  return out as Partial<EngineParams>;
}

/** Write the current config into the URL (replaceState — no history spam). */
export function syncUrl(p: EngineParams, step: string) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (step === "results") {
    url.searchParams.set("cfg", encodeParams(p));
  } else {
    url.searchParams.delete("cfg");
  }
  window.history.replaceState(null, "", url.toString());
}

/** Read a config from the URL on first load (returns null if none/invalid). */
export function readUrlConfig(): Partial<EngineParams> | null {
  if (typeof window === "undefined") return null;
  const s = new URLSearchParams(window.location.search).get("cfg");
  return s ? decodeParams(s) : null;
}
