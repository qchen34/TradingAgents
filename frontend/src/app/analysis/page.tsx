"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getStockTrackerLatest,
  refreshStockTracker,
  getStockTrackerJob,
  type StockTrackerItem,
  type StockTrackerLatest,
} from "@/lib/api";

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

function fmtPctColor(v: number | null | undefined): string {
  if (v == null) return "text-[#8d90a2]";
  return v >= 0 ? "text-[#22c55e]" : "text-[#f87171]";
}

function stageColor(label: string | undefined): string {
  if (!label) return "bg-[#2B2F36] text-[#9aa3b5]";
  if (label.includes("Stage 2")) return "bg-[#1a3a20] text-[#4ade80]";
  if (label.includes("Stage 1")) return "bg-[#1a2e3a] text-[#60a5fa]";
  if (label.includes("Stage 3")) return "bg-[#3a2a10] text-[#fbbf24]";
  if (label.includes("Stage 4")) return "bg-[#3a1a1a] text-[#f87171]";
  return "bg-[#2B2F36] text-[#9aa3b5]";
}

function trendBuyShort(verdict: string | undefined): string {
  if (!verdict) return "—";
  if (verdict === "at_buy") return "买点确认";
  if (verdict === "near_buy") return "近买点";
  if (verdict === "not_yet") return "未到";
  if (verdict === "avoid_chase") return "禁追";
  return verdict;
}

const NUM = "text-right font-mono text-[12px] tabular-nums";
const NUM_MAIN = "text-right font-mono text-[13px] tabular-nums";

export default function AnalysisPage() {
  const router = useRouter();
  const [data, setData] = useState<StockTrackerLatest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshProgress, setRefreshProgress] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadLatest();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function loadLatest() {
    setLoading(true);
    setError(null);
    try {
      const d = await getStockTrackerLatest();
      setData(d);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    if (refreshing) return;
    setRefreshing(true);
    setRefreshProgress("启动刷新...");
    try {
      const job = await refreshStockTracker();
      pollJob(job.job_id);
    } catch (e) {
      setRefreshing(false);
      setRefreshProgress("");
      setError(String(e));
    }
  }

  function pollJob(jobId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const job = await getStockTrackerJob(jobId);
        setRefreshProgress(job.progress ? `处理中：${job.progress}` : job.status);
        if (job.status === "completed") {
          clearInterval(pollRef.current!);
          setRefreshing(false);
          setRefreshProgress("");
          await loadLatest();
        } else if (job.status === "failed") {
          clearInterval(pollRef.current!);
          setRefreshing(false);
          setRefreshProgress("");
          setError(job.error ?? "刷新失败");
        }
      } catch {
        clearInterval(pollRef.current!);
        setRefreshing(false);
      }
    }, 2000);
  }

  const tickers = data?.tickers ?? [];

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#161A1E] font-sans text-[13px] leading-normal text-[#e8eaf0] antialiased">
      <div className="sticky top-0 z-10 flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-[#2B2F36] bg-[#161A1E]/95 px-5 py-3.5 shadow-[0_1px_0_0_rgba(0,0,0,0.25)] backdrop-blur-md">
        <div className="min-w-0 flex-1">
          <h1 className="text-[17px] font-semibold tracking-tight text-white">个股追踪</h1>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] text-[#9aa3b5]">
            {data?.updated_at && (
              <span>
                更新{" "}
                {new Date(data.updated_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })}
              </span>
            )}
            {refreshing && <span className="font-medium text-[#fbbf24]">{refreshProgress}</span>}
          </div>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="shrink-0 rounded-md bg-[#2962FF] px-4 py-2 text-[12px] font-semibold text-white shadow-sm transition hover:bg-[#1d4ed8] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {refreshing ? "刷新中…" : "刷新数据"}
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-5">
        {loading && (
          <div className="rounded-lg border border-[#2B2F36] bg-[#1a1f24]/50 py-20 text-center text-[13px] text-[#9aa3b5]">
            加载中…
          </div>
        )}
        {error && (
          <div
            className="mb-4 rounded-lg border border-[#f87171]/35 bg-[#2a1518] px-4 py-3 text-[13px] leading-relaxed text-[#fca5a5]"
            role="alert"
          >
            {error}
          </div>
        )}

        {!loading && tickers.length === 0 && (
          <div className="rounded-lg border border-dashed border-[#3d4450] bg-[#1a1f24]/40 px-6 py-16 text-center">
            <p className="text-[14px] font-medium text-[#c4c9e0]">暂无追踪数据</p>
            <p className="mx-auto mt-2 max-w-md text-[12px] leading-relaxed text-[#8d94a8]">
              请点击右上角「刷新数据」从后端拉取核心标的。
            </p>
          </div>
        )}

        {tickers.length > 0 && (
          <div className="w-full overflow-x-auto rounded-lg border border-[#2B2F36] bg-[#14181c] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)] custom-scrollbar">
            <div className="tracker-grid tracker-grid-header" role="row">
              <span className="tracker-sticky-rank tabular-nums">#</span>
              <span className="tracker-sticky-ticker">标的</span>
              <span className={NUM_MAIN}>收盘</span>
              <span className={NUM_MAIN}>涨跌</span>
              <span className={NUM}>RSI</span>
              <span className={NUM}>量/MA20</span>
              <span className={NUM}>MACD</span>
              <span>金叉</span>
              <span>趋势买点</span>
              <span className={`${NUM} tracker-col-group-valuation`}>PE</span>
              <span className={NUM}>行业PE</span>
              <span className={`${NUM} tracker-col-group-growth`}>PEG</span>
              <span className={NUM}>EPS 5Y</span>
              <span className={NUM}>EPS N.Y</span>
              <span className={NUM}>D/E</span>
              <span className={NUM}>偏离MA150</span>
              <span className={NUM}>MA150斜</span>
              <span className={NUM}>RS 3M</span>
              <span>Stage</span>
              <span>买点类型</span>
              <span className={NUM}>评分</span>
            </div>

            <div className="divide-y divide-[#252a32]">
              {tickers.map((item, idx) => (
                <TickerRow
                  key={item.ticker}
                  item={item}
                  rank={idx + 1}
                  onClick={() => router.push(`/stock-detail?ticker=${item.ticker}`)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TickerRow({
  item,
  rank,
  onClick,
}: {
  item: StockTrackerItem;
  rank: number;
  onClick: () => void;
}) {
  const tech = item.technical ?? {};
  const fund = item.fundamental ?? {};
  const llm = item.llm ?? {};
  const tb = tech.trend_buy;

  const peRatio =
    fund.pe_ttm != null && fund.industry_pe_avg != null && fund.industry_pe_avg > 0
      ? fund.pe_ttm / fund.industry_pe_avg
      : null;
  const peRatioColor =
    peRatio == null
      ? "text-[#a8acc0]"
      : peRatio > 1.5
        ? "text-[#fbbf24]"
        : peRatio < 0.8
          ? "text-[#4ade80]"
          : "text-[#e8eaf0]";
  const deColor =
    fund.debt_to_equity == null
      ? "text-[#8d90a2]"
      : fund.debt_to_equity > 2
        ? "text-[#f87171]"
        : fund.debt_to_equity > 1
          ? "text-[#fbbf24]"
          : "text-[#22c55e]";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className="tracker-grid tracker-grid-row cursor-pointer outline-none transition-colors hover:bg-[#1c2229] focus-visible:ring-2 focus-visible:ring-[#2962FF]/50 focus-visible:ring-inset"
    >
      <span className={`tracker-sticky-rank tabular-nums text-[12px] text-[#8d94a8]`}>{rank}</span>

      <div className="tracker-sticky-ticker min-w-0 pr-1">
        <div className="font-mono text-[14px] font-semibold tracking-tight text-white">{item.ticker}</div>
        <div className="truncate text-[12px] leading-snug text-[#a8b4c8]" title={item.name}>
          {item.name}
        </div>
      </div>

      <span className={`${NUM_MAIN} text-white`}>
        {tech.close != null ? `$${tech.close.toFixed(2)}` : "—"}
      </span>

      <span className={`${NUM_MAIN} font-medium ${fmtPctColor(tech.change_pct)}`}>
        {fmtPct(tech.change_pct)}
      </span>

      <span
        className={`${NUM} ${
          tech.rsi14 == null
            ? "text-[#8d90a2]"
            : tech.rsi14 > 70
              ? "text-[#f87171]"
              : tech.rsi14 > 50
                ? "text-[#22c55e]"
                : "text-[#fbbf24]"
        }`}
      >
        {tech.rsi14 != null ? tech.rsi14.toFixed(0) : "—"}
      </span>

      <span className={`${NUM} text-[#e2e6ef]`}>
        {tech.volume_vs_ma20 != null ? tech.volume_vs_ma20.toFixed(2) : "—"}
      </span>

      <span
        className={`${NUM} ${
          tech.macd_hist == null
            ? "text-[#8d90a2]"
            : tech.macd_hist >= 0
              ? "text-[#22c55e]"
              : "text-[#f87171]"
        }`}
      >
        {tech.macd_hist != null ? tech.macd_hist.toFixed(3) : "—"}
      </span>

      <div className="min-w-0 text-[11px] leading-snug text-[#c8d0e0]" title={tech.golden_cross_label ?? ""}>
        <div className="truncate">{tech.golden_cross_label ?? "—"}</div>
      </div>

      <span
        className={`min-w-0 truncate text-[11px] font-medium leading-snug ${
          tb?.verdict === "at_buy"
            ? "text-[#22c55e]"
            : tb?.verdict === "near_buy"
              ? "text-[#38bdf8]"
              : tb?.verdict === "avoid_chase"
                ? "text-[#f87171]"
                : "text-[#9aa3b5]"
        }`}
        title={(tb as { one_liner?: string } | undefined)?.one_liner}
      >
        {trendBuyShort(tb?.verdict)}
      </span>

      <span className={`${NUM} tracker-col-group-valuation text-white`}>
        {fund.pe_ttm != null ? fund.pe_ttm.toFixed(1) + "x" : "—"}
      </span>

      <span
        className={`${NUM} ${peRatioColor}`}
        title={
          fund.industry_label
            ? `行业：${fund.industry_label}${peRatio != null ? ` · 相对 ${peRatio.toFixed(2)}x` : ""}`
            : undefined
        }
      >
        {fund.industry_pe_avg != null ? fund.industry_pe_avg.toFixed(1) + "x" : "—"}
      </span>

      <span className={`${NUM} tracker-col-group-growth text-white`}>
        {fund.peg_ratio != null ? fund.peg_ratio.toFixed(2) : "—"}
      </span>

      <span className={`${NUM} font-medium ${fmtPctColor(fund.eps_growth_5y_pct)}`}>
        {fmtPct(fund.eps_growth_5y_pct)}
      </span>

      <span className={`${NUM} font-medium ${fmtPctColor(fund.eps_growth_next_y_pct)}`}>
        {fmtPct(fund.eps_growth_next_y_pct)}
      </span>

      <span className={`${NUM} ${deColor}`}>
        {fund.debt_to_equity != null ? fund.debt_to_equity.toFixed(2) : "—"}
      </span>

      <span className={`${NUM} font-medium ${fmtPctColor(tech.pct_vs_ma150)}`}>
        {fmtPct(tech.pct_vs_ma150)}
      </span>

      <span className={`${NUM} font-medium ${fmtPctColor(tech.ma150_slope_4w)}`}>
        {fmtPct(tech.ma150_slope_4w)}
      </span>

      <span className={`${NUM} ${fmtPctColor(tech.rs_slope_3m)}`}>
        {tech.rs_slope_3m != null ? (tech.rs_slope_3m >= 0 ? "+" : "") + tech.rs_slope_3m.toFixed(3) : "—"}
      </span>

      <span
        className={`justify-self-center inline-block max-w-full truncate text-center rounded-md px-2 py-0.5 text-[11px] font-medium ${stageColor(llm.stage_label)}`}
        title={llm.stage_label}
      >
        {llm.stage_label || "待分析"}
      </span>

      <span className="min-w-0 truncate text-[11px] leading-snug text-[#d8deeb]" title={llm.action_type}>
        {llm.action_type || "待分析"}
      </span>

      <span className={`${NUM_MAIN} font-semibold text-[#fbbf24]`}>
        {tech.score != null ? `${tech.score}/9` : "—"}
      </span>
    </div>
  );
}
