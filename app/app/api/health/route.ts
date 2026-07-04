import { NextResponse } from "next/server";
import { engineHealth } from "@/lib/engine";

export const runtime = "nodejs";

// Proxy the engine's /health probe so the browser can show a live status dot
// without ever learning the engine URL.
export async function GET() {
  try {
    const res = await engineHealth();
    if (!res.ok) {
      return NextResponse.json({ error: `Engine /health ${res.status}` }, { status: 502 });
    }
    return NextResponse.json(await res.json());
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
