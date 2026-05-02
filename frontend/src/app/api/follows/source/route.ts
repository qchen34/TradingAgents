import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

type FutuWatchlistRow = {
  group_name: string;
  code: string;
  name: string;
};

export async function GET() {
  try {
    const scriptsDir = path.resolve(process.cwd(), "../scripts");
    const files = await fs.readdir(scriptsDir);
    const candidates = files
      .filter((f) => /^futu_watchlist_full_.*\.json$/i.test(f))
      .sort((a, b) => b.localeCompare(a));

    if (candidates.length === 0) {
      return NextResponse.json([] as FutuWatchlistRow[]);
    }

    const latest = candidates[0];
    const fullPath = path.join(scriptsDir, latest);
    const raw = await fs.readFile(fullPath, "utf-8");
    const parsed = JSON.parse(raw) as Array<Record<string, unknown>>;

    const rows: FutuWatchlistRow[] = parsed.map((x) => ({
      group_name: String(x.group_name ?? ""),
      code: String(x.code ?? ""),
      name: String(x.name ?? ""),
    }));
    return NextResponse.json(rows);
  } catch {
    return NextResponse.json([] as FutuWatchlistRow[]);
  }
}

