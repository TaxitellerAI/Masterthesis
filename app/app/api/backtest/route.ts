import { NextRequest, NextResponse } from "next/server";
import { callEngine, EngineError } from "@/lib/engine";
import type { BacktestResponse, EngineParams } from "@/lib/types";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  try {
    const params = (await req.json()) as EngineParams;
    const data = await callEngine<BacktestResponse>("backtest", params);
    return NextResponse.json(data);
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json({ error: (e as Error).message }, { status });
  }
}
