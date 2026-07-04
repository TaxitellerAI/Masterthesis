import { NextRequest, NextResponse } from "next/server";
import { callEngineRaw, EngineError } from "@/lib/engine";
import type { EngineParams } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 60;

// Streams the engine's transparency workbook (.xlsx) through to the browser.
export async function POST(req: NextRequest) {
  try {
    const params = (await req.json()) as EngineParams;
    const res = await callEngineRaw("workbook", params);
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      return NextResponse.json({ error: `Workbook fehlgeschlagen (${res.status}). ${detail}` }, { status: res.status });
    }
    const buf = await res.arrayBuffer();
    return new NextResponse(Buffer.from(buf), {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": 'attachment; filename="treasury-transparenz.xlsx"',
      },
    });
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json({ error: (e as Error).message }, { status });
  }
}
