import { NextResponse } from "next/server";
import { engineAssets } from "@/lib/engine";

export const runtime = "nodejs";

// Proxy the engine's curated asset universe to the configurator.
export async function GET() {
  try {
    const res = await engineAssets();
    if (!res.ok) {
      return NextResponse.json({ error: `Engine /assets ${res.status}` }, { status: 502 });
    }
    return NextResponse.json(await res.json());
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
