import { NextRequest, NextResponse } from "next/server";
import { engineStartJob, EngineError } from "@/lib/engine";
import type { EngineParams } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 60;

// Starts the inference job. Returns in milliseconds, so no gateway limit applies —
// a synchronous /hypotheses on the deployed host takes 192-234 s against a 60 s
// budget and could never complete.
export async function POST(req: NextRequest) {
  try {
    const params = (await req.json()) as EngineParams;
    const res = await engineStartJob(params);
    if (!res.ok) {
      return NextResponse.json({ error: `Engine /jobs/hypotheses ${res.status}` }, { status: 502 });
    }
    return NextResponse.json(await res.json());
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json({ error: (e as Error).message }, { status });
  }
}
