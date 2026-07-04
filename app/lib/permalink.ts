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
    return typeof obj === "object" && obj !== null ? (obj as Partial<EngineParams>) : null;
  } catch {
    return null;
  }
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
