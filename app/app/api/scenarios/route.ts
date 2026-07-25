import { NextResponse } from "next/server";
import { engineScenarios } from "@/lib/engine";

export const runtime = "nodejs";
export const maxDuration = 60;

// Proxy the engine's scenario catalogue so the configurator never redefines specs.
export async function GET() {
  try {
    const res = await engineScenarios();
    if (!res.ok) {
      return NextResponse.json({ error: `Engine /scenarios ${res.status}` }, { status: 502 });
    }
    return NextResponse.json(await res.json());
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
