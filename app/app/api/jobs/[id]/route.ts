import { NextRequest, NextResponse } from "next/server";
import { engineJobStatus } from "@/lib/engine";

export const runtime = "nodejs";
export const maxDuration = 60;

// Polls a running inference job. Cheap and fast — the long computation happens in
// the engine's own thread, not inside this request.
export async function GET(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await ctx.params;
    const res = await engineJobStatus(id);
    if (!res.ok) {
      return NextResponse.json({ error: `Engine /jobs ${res.status}` }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
