"use client";

import { useEffect, useState } from "react";
import { BatchQuote, DashboardSnapshot, getBatchQuotes, getDashboard, getDefaultState, refreshDashboard } from "@/lib/api";
import { useUiStore } from "@/store/uiStore";

type FollowsTab = "watchlist" | "positions";

type FollowRow = {
  ticker: string;
  note: string;
  sourceCode?: string;
};

type FutuWatchlistRow = {
  group_name: string;
  code: string;
  name: string;
};

export default function DashboardPage() {
  const hydrate = useUiStore((s) => s.hydrateFromApi);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState("");
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [followsTab, setFollowsTab] = useState<FollowsTab>("watchlist");
  const [watchlistRows, setWatchlistRows] = useState<FollowRow[]>([]);
  const [watchlistByGroup, setWatchlistByGroup] = useState<Record<string, FollowRow[]>>({});
  const [watchlistGroups, setWatchlistGroups] = useState<string[]>([]);
  const [activeWatchlistGroup, setActiveWatchlistGroup] = useState("");
  const [positionsRows, setPositionsRows] = useState<FollowRow[]>([]);
  const [followsQuoteMap, setFollowsQuoteMap] = useState<Record<string, BatchQuote>>({});

  useEffect(() => {
    Promise.all([getDefaultState(), getDashboard()])
      .then(([state, dash]) => {
        hydrate(state);
        setSnapshot(dash);
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [hydrate]);

  useEffect(() => {
    const savedWatch = localStorage.getItem("ta_follows_watchlist");
    const savedPos = localStorage.getItem("ta_follows_positions");
    const savedQuotes = localStorage.getItem("ta_follows_quotes");
    const defaults: FollowRow[] = [
      { ticker: "QQQ", note: "纳指ETF" },
      { ticker: "TQQQ", note: "三倍做多纳指" },
      { ticker: "SOXX", note: "半导体ETF" },
      { ticker: "SPY", note: "标普ETF" },
      { ticker: "NVDA", note: "AI龙头" },
      { ticker: "AAPL", note: "权重股" },
    ];
    setWatchlistRows(savedWatch ? (JSON.parse(savedWatch) as FollowRow[]) : defaults);
    setPositionsRows(savedPos ? (JSON.parse(savedPos) as FollowRow[]) : []);
    setFollowsQuoteMap(savedQuotes ? (JSON.parse(savedQuotes) as Record<string, BatchQuote>) : {});
  }, []);

  useEffect(() => {
    fetch("/api/follows/source")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((rows: FutuWatchlistRow[]) => {
        const grouped: Record<string, FollowRow[]> = {};
        rows.forEach((r) => {
          const group = (r.group_name || "未分组").trim();
          const ticker = normalizeFutuCode(r.code);
          const note = (r.name || r.code || "").trim();
          if (!ticker) return;
          if (!grouped[group]) grouped[group] = [];
          grouped[group].push({ ticker, note, sourceCode: r.code });
        });
        const groups = Object.keys(grouped);
        if (groups.length === 0) return;
        setWatchlistByGroup(grouped);
        setWatchlistGroups(groups);
        setActiveWatchlistGroup((prev) => (prev && grouped[prev] ? prev : groups[0]));
      })
      .catch(() => {
        // 保留本地默认 watchlist，避免 API 未就绪时页面报错
      });
  }, []);

  async function onRefreshMarket() {
    setRefreshing(true);
    setErr("");
    try {
      const dash = await refreshDashboard(10);
      setSnapshot(dash);
      const allRows = [
        ...watchlistRows,
        ...Object.values(watchlistByGroup).flat(),
        ...positionsRows,
      ];
      const queryCodes = Array.from(
        new Set(allRows.map((x) => (x.sourceCode || x.ticker || "").toUpperCase()).filter(Boolean)),
      ).slice(0, 200);
      if (queryCodes.length > 0) {
        const rows = await getBatchQuotes(queryCodes);
        const m: Record<string, BatchQuote> = {};
        rows.forEach((q) => {
          m[(q.request_code || "").toUpperCase()] = q;
          m[(q.normalized_code || "").toUpperCase()] = q;
        });
        setFollowsQuoteMap(m);
        localStorage.setItem("ta_follows_quotes", JSON.stringify(m));
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setRefreshing(false);
    }
  }

  function pct(value: number | null | undefined): string {
    if (value === null || value === undefined) return "-";
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  }

  function num(value: number | null | undefined): string {
    if (value === null || value === undefined) return "N/A";
    return value.toFixed(2);
  }

  function clsByPct(value: number | null | undefined): string {
    if (value === null || value === undefined) return "text-[#c3c5d8]";
    if (value < 0) return "text-[#ffb3b0]";
    return "text-[#44e092]";
  }

  function heatBgByPct(value: number | null | undefined): string {
    if (value === null || value === undefined) return "bg-[#111417]";
    if (value < 0) return "bg-[#da2237]/12";
    return "bg-[#03c177]/12";
  }

  function stanceMeta(stance: string | undefined): { label: string; cls: string } {
    if (stance === "bullish") return { label: "看多", cls: "border-[#03c177]/50 bg-[#03c177]/15 text-[#66fdac]" };
    if (stance === "bearish") return { label: "看空", cls: "border-[#da2237]/50 bg-[#da2237]/15 text-[#ffb3b0]" };
    return { label: "中性", cls: "border-[#434656] bg-[#272a2e] text-[#c3c5d8]" };
  }

  const digestText = snapshot?.market_digest_md?.trim() || "暂无总结内容";
  const digestLines = digestText.split("\n").filter(Boolean);
  const heatmapCards = (snapshot?.top6_sectors ?? [])
    .map((x) => ({
      key: `sector-${x.ticker}`,
      name: x.ticker,
      price: x.price,
      change_pct: x.change_pct,
    }))
    .sort((a, b) => (b.change_pct ?? -Infinity) - (a.change_pct ?? -Infinity))
    .slice(0, 6);

  function onImportFutuCsv(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      const lines = text
        .split(/\r?\n/)
        .map((x) => x.trim())
        .filter(Boolean);
      if (lines.length < 2) return;
      const delimiter = lines[0].includes("\t") ? "\t" : ",";
      const headers = lines[0].split(delimiter).map((x) => x.trim().toLowerCase());
      const codeIdx = headers.findIndex((h) => ["code", "ticker", "symbol", "代码", "股票代码"].includes(h));
      const nameIdx = headers.findIndex((h) => ["name", "名称", "股票名称"].includes(h));
      const rows: FollowRow[] = lines.slice(1).map((line) => {
        const cols = line.split(delimiter).map((x) => x.trim());
        const ticker = (codeIdx >= 0 ? cols[codeIdx] : cols[0] || "").toUpperCase();
        const note = nameIdx >= 0 ? cols[nameIdx] || "富途导入" : "富途导入";
        return { ticker, note, sourceCode: ticker };
      });
      const cleaned = rows.filter((r) => r.ticker.length > 0);
      setPositionsRows(cleaned);
      localStorage.setItem("ta_follows_positions", JSON.stringify(cleaned));
      setFollowsTab("positions");
    };
    reader.readAsText(file, "utf-8");
  }

  function normalizeFutuCode(code: string): string {
    const c = (code || "").trim().toUpperCase();
    if (!c) return "";
    if (c.startsWith("US..")) return `^${c.slice(4)}`;
    if (c.startsWith("US.")) return c.slice(3);
    return c;
  }

  const displayedRows =
    followsTab === "watchlist"
      ? watchlistGroups.length > 0 && activeWatchlistGroup
        ? watchlistByGroup[activeWatchlistGroup] ?? []
        : watchlistRows
      : positionsRows;

  return (
    <div className="grid h-full grid-cols-12 gap-2 overflow-hidden">
      <div className="col-span-3 flex h-full flex-col gap-2 overflow-hidden">
        <section className="flex h-1/2 flex-col overflow-hidden border border-[#2B2F36] bg-[#161A1E]">
          <header className="flex items-center justify-between border-b border-[#2B2F36] bg-[#1d2023] p-2">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-[#5E6673]">Sector Strength Heatmap</h2>
            <span className="material-symbols-outlined text-[14px] text-[#5E6673]">grid_view</span>
          </header>
          <div className="grid flex-1 grid-cols-2 gap-1 overflow-y-auto p-2 custom-scrollbar">
            {heatmapCards.map((x) => (
              <div className={`flex flex-col justify-between border border-[#2B2F36] p-2 ${heatBgByPct(x.change_pct)}`} key={x.key}>
                <span className="text-[10px] text-[#5E6673]">{x.name}</span>
                <span className="font-mono text-[13px] text-[#e1e2e7]">{num(x.price)}</span>
                <span className={`font-mono text-lg ${clsByPct(x.change_pct)}`}>{pct(x.change_pct)}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="flex h-1/2 flex-col overflow-hidden border border-[#2B2F36] bg-[#161A1E]">
          <header className="border-b border-[#2B2F36] bg-[#1d2023] p-2">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-[#5E6673]">Macro Index</h2>
          </header>
          <div className="grid grid-cols-1 gap-1 border-b border-[#2B2F36] p-2">
            {(snapshot?.macro_strip ?? []).map((m) => (
              <div
                className={`flex items-center justify-between border border-[#2B2F36] px-2 py-1 ${heatBgByPct(m.change_pct ?? null)}`}
                key={`macro-index-${m.ticker}`}
              >
                <div className="min-w-0 w-[46%]">
                  <div className="font-mono text-[10px] text-[#e1e2e7]">{m.ticker}</div>
                  <div className="truncate text-[10px] text-[#8d90a2]">{m.label}</div>
                </div>
                <span className="w-[24%] text-right font-mono text-[10px] text-[#c3c5d8]">{m.display_value ?? "N/A"}</span>
                <span className={`w-[30%] text-right font-mono text-[10px] ${clsByPct(m.change_pct ?? null)}`}>
                  {pct(m.change_pct ?? null)}
                </span>
              </div>
            ))}
          </div>
          <div className="custom-scrollbar flex-1 space-y-1 overflow-y-auto p-2">
            {(snapshot?.indexes ?? []).map((x) => (
              <div
                className={`flex items-center justify-between border border-[#2B2F36] px-2 py-1 ${heatBgByPct(x.change_pct)}`}
                key={`macro-idx-${x.ticker}`}
              >
                <div className="min-w-0 w-[46%]">
                  <div className="font-mono text-[10px] text-[#e1e2e7]">{x.ticker}</div>
                  <div className="truncate text-[10px] text-[#8d90a2]">{x.label}</div>
                </div>
                <span className="w-[24%] text-right font-mono text-[10px] text-[#c3c5d8]">{num(x.price)}</span>
                <span className={`w-[30%] text-right font-mono text-[10px] ${clsByPct(x.change_pct)}`}>{pct(x.change_pct)}</span>
              </div>
            ))}
            {loading && <div className="px-1 py-1 font-mono text-[10px] text-[#5E6673]">[SYNC] loading market snapshot...</div>}
            {err && <div className="px-1 py-1 font-mono text-[10px] text-[#ffb3b0]">{err}</div>}
          </div>
        </section>
      </div>

      <div className="col-span-6 flex h-full flex-col gap-2 overflow-hidden">
        <article className="relative h-[42%] shrink-0 overflow-hidden border border-[#2962ff] bg-[#1a2a53]/60 p-3">
          <div className="mb-2 flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-[#dce1ff]">bolt</span>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#dce1ff]">LLM Alpha Summary</h2>
          </div>
          <div className="max-h-[calc(100%-56px)] overflow-y-auto custom-scrollbar rounded border border-[#2B2F36] bg-[#111417]/70 p-3">
            {digestLines.length === 0 && <p className="text-sm leading-relaxed text-[#e1e2e7]">暂无总结内容</p>}
            {digestLines.map((line, idx) => {
              const t = line.trim();
              if (t.startsWith("#####")) {
                return (
                  <h3 className="mt-3 text-sm font-semibold text-[#dce1ff] first:mt-0" key={`h-${idx}`}>
                    {t.replace(/^#####\s*/, "")}
                  </h3>
                );
              }
              if (t.startsWith("-")) {
                return (
                  <p className="mt-1 text-xs leading-relaxed text-[#c3c5d8]" key={`li-${idx}`}>
                    {t}
                  </p>
                );
              }
              return (
                <p className="mt-1 text-sm leading-relaxed text-[#e1e2e7] first:mt-0" key={`p-${idx}`}>
                  {t}
                </p>
              );
            })}
          </div>
          <div className="mt-2 flex gap-2">
            <span className="rounded border border-[#2962ff] bg-[#2962ff]/20 px-2 py-0.5 text-[10px] font-bold text-[#dce1ff]">
              {snapshot?.market_status || "MARKET"}
            </span>
            <span className="rounded border border-[#2B2F36] px-2 py-0.5 text-[10px] font-bold text-[#c3c5d8]">
              {snapshot?.last_updated_et || "N/A"}
            </span>
            <button
              onClick={onRefreshMarket}
              disabled={refreshing}
              className="rounded border border-[#2B2F36] px-2 py-0.5 text-[10px] font-bold text-[#c3c5d8] hover:bg-[#2B2F36] disabled:opacity-60"
            >
              {refreshing ? "刷新中" : "刷新"}
            </button>
          </div>
        </article>

        <section className="flex h-[58%] flex-col overflow-hidden border border-[#2B2F36] bg-[#161A1E]">
          <header className="flex items-center justify-between border-b border-[#2B2F36] bg-[#1d2023] p-2">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-[#5E6673]">Real-time News Feed</h2>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[#44e092]" />
              <span className="text-[9px] uppercase text-[#5E6673]">Live Stream</span>
            </div>
          </header>
          <div className="flex-1 space-y-1 overflow-y-auto p-1 custom-scrollbar">
            {(snapshot?.news ?? []).slice(0, 10).map((n, i) => (
              <div className="flex gap-3 border-b border-[#2B2F36] p-2 transition-colors hover:bg-[#2B2F36]" key={`${n.title}-${i}`}>
                <div className="pt-1 font-mono text-[10px] text-[#5E6673]">{n.published_at?.slice(11, 16) || "--:--"}</div>
                <div>
                  <h3 className="text-sm font-semibold leading-tight text-[#e1e2e7]">{n.title}</h3>
                  <div className="mt-1">
                    {(() => {
                      const meta = stanceMeta(n.stance);
                      return (
                        <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-semibold ${meta.cls}`}>
                          {meta.label}
                        </span>
                      );
                    })()}
                  </div>
                  {n.llm_summary && <p className="mt-1 text-[11px] text-[#9ea7b8]">{n.llm_summary}</p>}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="col-span-3 flex h-full flex-col gap-2 overflow-hidden">
        <section className="flex h-3/4 flex-col overflow-hidden border border-[#2B2F36] bg-[#161A1E]">
          <header className="border-b border-[#2B2F36] bg-[#1d2023] p-2">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-[#5E6673]">Follows</h2>
            <div className="mt-2 flex items-center justify-between gap-2">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setFollowsTab("watchlist")}
                  className={`rounded px-2 py-1 text-[10px] ${followsTab === "watchlist" ? "bg-[#2B2F36] text-white" : "text-[#8d90a2]"}`}
                >
                  自选
                </button>
                <button
                  type="button"
                  onClick={() => setFollowsTab("positions")}
                  className={`rounded px-2 py-1 text-[10px] ${followsTab === "positions" ? "bg-[#2B2F36] text-white" : "text-[#8d90a2]"}`}
                >
                  持仓
                </button>
              </div>
              <label className="cursor-pointer rounded border border-[#2B2F36] px-2 py-1 text-[10px] text-[#c3c5d8] hover:bg-[#2B2F36]">
                富途导入
                <input
                  type="file"
                  accept=".csv,.txt"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) onImportFutuCsv(file);
                    e.currentTarget.value = "";
                  }}
                />
              </label>
            </div>
          </header>
          <div className="flex items-center border-b border-[#2B2F36] px-2 py-1 text-[10px] text-[#8d90a2]">
            <div className="w-[42%]">名称代码</div>
            <div className="w-[20%] text-right">最新价</div>
            <div className="w-[18%] text-right">涨跌额</div>
            <div className="w-[20%] text-right">涨跌幅</div>
          </div>
          <div className="custom-scrollbar flex-1 overflow-y-auto">
            {followsTab === "watchlist" && watchlistGroups.length > 0 && (
              <div className="flex items-center gap-1 border-b border-[#2B2F36] px-2 py-1">
                {watchlistGroups.map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setActiveWatchlistGroup(g)}
                    className={`max-w-[88px] truncate rounded px-2 py-0.5 text-[10px] ${
                      g === activeWatchlistGroup ? "bg-[#2B2F36] text-white" : "text-[#8d90a2] hover:bg-[#252a33]"
                    }`}
                    title={g}
                  >
                    {g}
                  </button>
                ))}
              </div>
            )}
            {displayedRows.map((f) => {
              const mapHit = followsQuoteMap[(f.sourceCode || f.ticker).toUpperCase()] || followsQuoteMap[f.ticker.toUpperCase()];
              const hit =
                mapHit ||
                (snapshot?.indexes ?? []).find((x) => x.ticker === f.ticker) ||
                (snapshot?.top6_sectors ?? []).find((x) => x.ticker === f.ticker);
              return (
                <div
                  className={`flex items-center border-b border-[#2B2F36] px-2 py-1.5 ${heatBgByPct(hit?.change_pct)}`}
                  key={`${followsTab}-${f.ticker}`}
                >
                  <div className="w-[42%]">
                    <div className="truncate text-[11px] font-semibold text-[#f0f2ff]">{f.note}</div>
                    <div className="font-mono text-[10px] text-[#8d90a2]">{f.ticker}</div>
                  </div>
                  <div className="w-[20%] text-right font-mono text-[12px] text-[#e1e2e7]">{num(hit?.price)}</div>
                  <div className={`w-[18%] text-right font-mono text-[12px] ${clsByPct(hit?.change_pct)}`}>
                    {hit?.change === null || hit?.change === undefined ? "-" : `${hit.change >= 0 ? "+" : ""}${hit.change.toFixed(2)}`}
                  </div>
                  <div className={`w-[20%] text-right font-mono text-[12px] font-semibold ${clsByPct(hit?.change_pct)}`}>
                    {pct(hit?.change_pct)}
                  </div>
                </div>
              );
            })}
            {followsTab === "positions" && positionsRows.length === 0 && (
              <div className="px-2 py-3 text-[11px] text-[#8d90a2]">暂无持仓，点击右上角“富途导入”导入 CSV。</div>
            )}
          </div>
        </section>

        <section className="flex h-1/4 flex-col overflow-hidden border border-[#2B2F36] bg-[#161A1E]">
          <header className="border-b border-[#2B2F36] bg-[#1d2023] p-2">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-[#5E6673]">NPM Runtime Logs</h2>
          </header>
          <div className="custom-scrollbar flex-1 space-y-1 overflow-y-auto p-2 font-mono text-[10px] text-[#c3c5d8]">
            <div>[npm] next dev -p 3000</div>
            <div className="text-[#44e092]">[ready] dev server running</div>
            <div>[api] GET /api/v1/dashboard</div>
            <div>[api] POST /api/v1/dashboard/refresh</div>
            {refreshing ? <div className="text-[#44e092]">[refresh] market data updating...</div> : <div>[refresh] idle</div>}
            {err ? <div className="text-[#ffb3b0]">[error] {err}</div> : <div className="text-[#44e092]">[status] no runtime error</div>}
          </div>
        </section>
      </div>
    </div>
  );
}

