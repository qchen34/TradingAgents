import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

type AiComputeTicker = {
  ticker: string;
  name?: string;
  rank?: number;
  layer?: string;
  reason?: string;
  action?: string;
};

type AiComputeGroup = {
  id: string;
  label: string;
  order: number;
  description?: string;
  focus?: string;
  merged_from?: string[];
  tickers: AiComputeTicker[];
};

type AiComputeWatchlist = {
  schema_version: string;
  name: string;
  source_doc?: string;
  updated_at?: string;
  priority_legend?: Record<string, string>;
  groups: AiComputeGroup[];
};

export async function GET() {
  try {
    // 由 frontend/ 起向上一级取仓库根，统一指向 data/follows/ai_compute_watchlist.json。
    const filePath = path.resolve(
      process.cwd(),
      "../data/follows/ai_compute_watchlist.json",
    );
    const raw = await fs.readFile(filePath, "utf-8");
    const data = JSON.parse(raw) as AiComputeWatchlist;
    data.groups = [...(data.groups ?? [])].sort(
      (a, b) => (a.order ?? 0) - (b.order ?? 0),
    );
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { groups: [] as AiComputeGroup[], error: String(err) },
      { status: 200 },
    );
  }
}
