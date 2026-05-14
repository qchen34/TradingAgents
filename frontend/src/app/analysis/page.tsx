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

// ─── 工具函数 ─────────────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, digits = 2, suffix = ""): string {
  if (v == null) return "—";
  return v.toFixed(digits) + suffix;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

function fmtPctColor(v: number | null | undefined): string {
  if (v == null) return "text-[#8d90a2]";
  return v >= 0 ? "text-[#22c55e]" : "text-[#f87171]";
}

function stageColor(label: string | undefined): string {
  if (!label) return "bg-[#2B2F36] text-[#8d90a2]";
  if (label.includes("Stage 2")) return "bg-[#1a3a20] text-[#4ade80]";
  if (label.includes("Stage 1")) return "bg-[#1a2e3a] text-[#60a5fa]";
  if (label.includes("Stage 3")) return "bg-[#3a2a10] text-[#fbbf24]";
  if (label.includes("Stage 4")) return "bg-[#3a1a1a] text-[#f87171]";
  return "bg-[#2B2F36] text-[#8d90a2]";
}

function scoreBar(score: number | null | undefined): string {
  if (score == null) return "—";
  const filled = Math.round(score);
  return "█".repeat(filled) + "░".repeat(Math.max(0, 9 - filled));
}

// ─── 主组件 ──────────────────────────────────────────────────────────────────

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
    <div className="h-full overflow-y-auto bg-[#161A1E] text-[#e8eaf0] font-mono">
      {/* ─── 顶部控制栏 ─────────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[#2B2F36] bg-[#161A1E]/95 px-5 py-3 backdrop-blur">
        <div>
          <span className="text-base font-semibold text-white">个股追踪</span>
          {data?.updated_at && (
            <span className="ml-4 text-[12px] text-[#a8acc0]">
              更新：{new Date(data.updated_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })}
            </span>
          )}
          {refreshing && (
            <span className="ml-4 text-[12px] text-[#fbbf24]">{refreshProgress}</span>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded border border-[#2B2F36] bg-[#1e232b] px-3.5 py-1.5 text-[12px] font-medium text-white transition hover:bg-[#2B2F36] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {refreshing ? "刷新中..." : "刷新数据"}
        </button>
      </div>

      {/* ─── 主体内容 ─────────────────────────────────────────────────────── */}
      <div className="p-5">
        {loading && (
          <div className="py-16 text-center text-[14px] text-[#a8acc0]">加载中...</div>
        )}
        {error && (
          <div className="mb-4 rounded border border-[#f87171]/30 bg-[#3a1a1a] p-3 text-[13px] text-[#f87171]">
            {error}
          </div>
        )}

        {!loading && tickers.length === 0 && (
          <div className="py-16 text-center text-[14px] text-[#a8acc0]">
            暂无数据，请点击「刷新数据」加载核心 13 只追踪指标。
          </div>
        )}

        {tickers.length > 0 && (
          <div className="overflow-x-auto">
            {/* ─── 表头 ──────────────────────────────────────────────────── */}
            <div className="mb-1.5 grid min-w-[1050px] grid-cols-[40px_140px_84px_80px_80px_80px_88px_90px_84px_172px_148px_64px] gap-x-2 px-3 text-[11px] font-medium uppercase tracking-wide text-[#a8acc0]">
              <span>#</span>
              <span>Ticker</span>
              <span className="text-right">收盘价</span>
              <span className="text-right">涨跌幅</span>
              <span className="text-right">PE(TTM)</span>
              <span className="text-right">行业PE</span>
              <span className="text-right">偏离MA150</span>
              <span className="text-right">MA150斜率</span>
              <span className="text-right">RS 3M</span>
              <span>Stage</span>
              <span>买点类型</span>
              <span className="text-right">评分</span>
            </div>

            {/* ─── 数据行 ─────────────────────────────────────────────────── */}
            <div className="min-w-[1050px] divide-y divide-[#2B2F36] rounded border border-[#2B2F36]">
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

// ─── 单行组件 ─────────────────────────────────────────────────────────────────

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

  return (
    <div
      onClick={onClick}
      className="grid min-w-[1050px] cursor-pointer grid-cols-[40px_140px_84px_80px_80px_80px_88px_90px_84px_172px_148px_64px] items-center gap-x-2 px-3 py-2.5 text-[13px] transition hover:bg-[#1e232b]"
    >
      {/* # */}
      <span className="text-[11px] text-[#a8acc0]">{rank}</span>

      {/* Ticker + name */}
      <div>
        <div className="text-[14px] font-semibold text-white">{item.ticker}</div>
        <div className="truncate text-[11px] text-[#a8acc0]">{item.name}</div>
      </div>

      {/* 收盘价 */}
      <span className="text-right font-mono text-white">
        {tech.close != null ? `$${tech.close.toFixed(2)}` : "—"}
      </span>

      {/* 涨跌幅 */}
      <span className={`text-right font-mono font-medium ${fmtPctColor(tech.change_pct)}`}>
        {fmtPct(tech.change_pct)}
      </span>

      {/* PE TTM */}
      <span className="text-right font-mono text-white">
        {fund.pe_ttm != null ? fund.pe_ttm.toFixed(1) + "x" : "—"}
      </span>

      {/* 行业PE */}
      <span
        className={`text-right font-mono ${peRatioColor}`}
        title={
          fund.industry_label
            ? `行业代理：${fund.industry_label}${peRatio != null ? `  ·  相对行业 ${peRatio.toFixed(2)}x` : ""}`
            : undefined
        }
      >
        {fund.industry_pe_avg != null ? fund.industry_pe_avg.toFixed(1) + "x" : "—"}
      </span>

      {/* 偏离MA150 */}
      <span className={`text-right font-mono font-medium ${fmtPctColor(tech.pct_vs_ma150)}`}>
        {fmtPct(tech.pct_vs_ma150)}
      </span>

      {/* MA150斜率 */}
      <span className={`text-right font-mono font-medium ${fmtPctColor(tech.ma150_slope_4w)}`}>
        {fmtPct(tech.ma150_slope_4w)}
      </span>

      {/* RS 3M */}
      <span className={`text-right font-mono ${fmtPctColor(tech.rs_slope_3m)}`}>
        {tech.rs_slope_3m != null ? (tech.rs_slope_3m >= 0 ? "+" : "") + tech.rs_slope_3m.toFixed(3) : "—"}
      </span>

      {/* Stage */}
      <span className={`truncate rounded px-2 py-0.5 text-[11px] font-medium ${stageColor(llm.stage_label)}`}>
        {llm.stage_label || "待分析"}
      </span>

      {/* 买点类型 */}
      <span className="truncate text-[12px] text-[#dce1ff]">
        {llm.action_type || "待分析"}
      </span>

      {/* 评分 */}
      <span className="text-right font-mono text-[13px] font-semibold text-[#fbbf24]">
        {tech.score != null ? `${tech.score}/9` : "—"}
      </span>
    </div>
  );
}
