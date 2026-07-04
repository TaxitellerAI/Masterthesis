import { NextRequest, NextResponse } from "next/server";
import { callEngineRaw, EngineError } from "@/lib/engine";
import type { EngineParams } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 60;

// Streams the frozen dataset CSV (exact aligned prices + hash in filename).
export async function POST(req: NextRequest) {
  try {
    const params = (await req.json()) as EngineParams;
    const res = await callEngineRaw("dataset", params);
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      return NextResponse.json({ error: `Dataset fehlgeschlagen (${res.status}). ${detail}` }, { status: res.status });
    }
    const buf = await res.arrayBuffer();
    return new NextResponse(Buffer.from(buf), {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": res.headers.get("content-disposition") ?? 'attachment; filename="treasury-dataset.csv"',
      },
    });
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json({ error: (e as Error).message }, { status });
  }
}
