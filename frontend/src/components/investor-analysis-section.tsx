"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getInvestorAnalysis,
  getInvestorAnalysisJob,
  triggerInvestorAnalysis,
  type InvestorAnalysis,
  type InvestorAnalysisMode,
  type InvestorAnalysisRecord,
  type InvestorAnalysisSummary,
  type InvestorFrameworkScore,
} from "@/lib/api";

type Verdict = "buy" | "watch" | "avoid";
type ViewMode = InvestorAnalysisMode;

function normalizeInvestorRecord(
  data: InvestorAnalysisRecord | InvestorAnalysis | null,
  ticker: string,
): InvestorAnalysisRecord {
  if (!data) return { ticker: ticker.toUpperCase(), quick: null, deep: null };
  if ("quick" in data || "deep" in data) {
    const rec = data as InvestorAnalysisRecord;
    return {
      ticker: rec.ticker || ticker.toUpperCase(),
      quick: rec.quick ?? null,
      deep: rec.deep ?? null,
    };
  }
  const flat = data as InvestorAnalysis;
  return { ticker: flat.ticker || ticker.toUpperCase(), quick: flat, deep: null };
}

function isV2Analysis(a: InvestorAnalysis): boolean {
  const v = a.framework_version ?? "";
  return (v === "2.0" || v.startsWith("2.1")) && !!a.summary;
}

function isDeepAnalysis(a: InvestorAnalysis): boolean {
  return a.analysis_mode === "deep" || a.framework_version === "2.1-deep";
}

function resolveSummary(a: InvestorAnalysis): InvestorAnalysisSummary | null {
  if (a.summary) return a.summary;
  if (!a.verdict) return null;
  return {
    verdict_mode: "legacy",
    verdict: a.verdict,
    verdict_counts: { buy: 0, watch: 0, avoid: 0 },
    verdict_summary: a.verdict_summary ?? "",
    ideal_price_median: toNum(a.entry?.ideal_price) ?? 0,
    ideal_price_range: [
      toNum(a.entry?.ideal_price) ?? 0,
      toNum(a.entry?.max_chase_price) ?? 0,
    ],
    key_risks: a.key_risks ?? [],
  };
}

function verdictLabel(v: Verdict | string | undefined): string {
  if (v === "buy") return "买入";
  if (v === "watch") return "观望";
  if (v === "avoid") return "回避";
  return String(v ?? "—");
}

function verdictClass(v: Verdict | string | undefined): string {
  if (v === "buy") return "bg-[#1a3a20] text-[#4ade80] border-[#22c55e]/40";
  if (v === "watch") return "bg-[#3a2a10] text-[#fbbf24] border-[#fbbf24]/40";
  return "bg-[#3a1a1a] text-[#f87171] border-[#f87171]/40";
}

function toNum(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function fmtUsd(v: unknown, digits = 2): string {
  const n = toNum(v);
  return n == null ? "—" : `$${n.toFixed(digits)}`;
}

function starCount(score: unknown): number {
  const n = toNum(score);
  if (n == null) return 0;
  return Math.max(0, Math.min(5, Math.round(n)));
}

function progressLabel(raw: string, status?: string): string {
  const t = (raw || status || "").trim();
  if (!t || t === "queued") return "排队中…";
  if (t.includes("加载") || t.startsWith("①")) return "① 读取追踪快照";
  const m = t.match(/②\s*(\d+)\/(\d+)/);
  if (m) return `② ${m[1]}/${m[2]} 位框架分析中`;
  if (t.startsWith("②") || t.includes("框架")) return t;
  if (t === "done" || t.startsWith("③") || t.includes("完成")) return "③ 写入结果";
  if (t === "running") return "分析进行中…";
  if (t === "failed") return "分析失败";
  return t.length > 56 ? `${t.slice(0, 56)}…` : t;
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
  } catch {
    return iso;
  }
}

function isStale(
  analysis: InvestorAnalysis | null,
  latestUpdatedAt: string | null | undefined,
): boolean {
  if (!analysis?.source_updated_at || !latestUpdatedAt) return false;
  return new Date(analysis.source_updated_at).getTime() < new Date(latestUpdatedAt).getTime();
}

function MetricCell({
  label,
  value,
  valueClass = "text-white",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-md border border-[#2B2F36] bg-[#0f1318]/80 px-3 py-2.5">
      <p className="text-[12px] font-medium uppercase tracking-wide text-[#8d94a8]">
        {label}
      </p>
      <p className={`mt-1 font-mono text-[15px] font-semibold tabular-nums ${valueClass}`}>
        {value}
      </p>
    </div>
  );
}

function InvestorCard({
  row,
  showDeepFields,
}: {
  row: InvestorFrameworkScore;
  showDeepFields?: boolean;
}) {
  const v = row.verdict as Verdict;
  const filled = starCount(row.score);

  return (
    <article
      className="flex flex-col rounded-lg border border-[#2B2F36] bg-[#14181c] p-4 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)] transition-colors hover:border-[#3d4a5c]"
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-[#252a32] pb-3">
        <h3 className="text-[17px] font-bold tracking-tight text-[#eef0ff]">
          {row.investor}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <div
            className="flex gap-0.5 text-[18px] leading-none text-[#fbbf24]"
            aria-label={`评分 ${filled} / 5`}
          >
            {Array.from({ length: 5 }, (_, i) => (
              <span key={i} className={i < filled ? "opacity-100" : "opacity-25"}>
                ★
              </span>
            ))}
          </div>
          <span
            className={`rounded-md border px-2.5 py-1 text-[13px] font-semibold ${verdictClass(v)}`}
          >
            {verdictLabel(v)}
          </span>
        </div>
      </header>

      <div className="mt-3 space-y-2 text-[14px] leading-relaxed text-[#d1d5e3]">
        <p>
          <span className="font-medium text-[#9aa3b5]">理由 · </span>
          {row.key_reason || "—"}
        </p>
        {row.concern ? (
          <p className="text-[#a8b0c4]">
            <span className="font-medium text-[#8d94a8]">顾虑 · </span>
            {row.concern}
          </p>
        ) : null}
      </div>

      {row.entry ? (
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <MetricCell label="理想买入" value={fmtUsd(row.entry.ideal_price, 0)} />
          <MetricCell label="最高追价" value={fmtUsd(row.entry.max_chase_price, 0)} />
          <MetricCell
            label="止损"
            value={fmtUsd(row.stop_loss?.price, 0)}
            valueClass="text-[#f87171]"
          />
          <MetricCell
            label="建议持有"
            value={row.holding_period?.range ?? "—"}
            valueClass="text-[#c4c9e0] font-sans text-[14px]"
          />
        </div>
      ) : null}

      {row.entry?.trigger_condition ? (
        <p className="mt-3 text-[13px] leading-snug text-[#9aa3b5]">
          <span className="font-medium text-[#8d94a8]">触发 · </span>
          {row.entry.trigger_condition}
        </p>
      ) : null}

      {showDeepFields && row.investment_thesis ? (
        <div className="mt-4 space-y-3 border-t border-[#252a32] pt-3 text-[14px] leading-relaxed">
          <p>
            <span className="font-semibold text-[#9aa3b5]">投资论点 · </span>
            {row.investment_thesis}
          </p>
          {row.bull_case ? (
            <p className="text-[#86efac]/90">
              <span className="font-semibold text-[#6ee7a0]">看多 · </span>
              {row.bull_case}
            </p>
          ) : null}
          {row.bear_case ? (
            <p className="text-[#fca5a5]/90">
              <span className="font-semibold text-[#f87171]">看空 · </span>
              {row.bear_case}
            </p>
          ) : null}
          {row.catalysts && row.catalysts.length > 0 ? (
            <div>
              <p className="mb-1 font-semibold text-[#8d94a8]">催化剂</p>
              <ul className="list-inside list-disc space-y-1 text-[#d1d5e3]">
                {row.catalysts.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {row.position_sizing ? (
            <p className="text-[#c4c9e0]">
              <span className="font-semibold text-[#8d94a8]">仓位 · </span>
              {row.position_sizing}
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

type Props = {
  ticker: string;
  latestUpdatedAt?: string | null;
  onAnalysisChange?: (analysis: InvestorAnalysis | null) => void;
};

export function InvestorAnalysisSection({
  ticker,
  latestUpdatedAt,
  onAnalysisChange,
}: Props) {
  const [record, setRecord] = useState<InvestorAnalysisRecord>({
    ticker: ticker.toUpperCase(),
    quick: null,
    deep: null,
  });
  const [viewMode, setViewMode] = useState<ViewMode>("quick");
  const [loadingCache, setLoadingCache] = useState(true);
  const [running, setRunning] = useState(false);
  const [runningMode, setRunningMode] = useState<ViewMode | null>(null);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const analysis = viewMode === "deep" ? record.deep : record.quick;

  const loadCache = useCallback(async () => {
    setLoadingCache(true);
    try {
      const data = await getInvestorAnalysis(ticker);
      const rec = normalizeInvestorRecord(data, ticker);
      setRecord(rec);
      onAnalysisChange?.(rec.quick ?? rec.deep);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingCache(false);
    }
  }, [ticker, onAnalysisChange]);

  useEffect(() => {
    loadCache();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadCache]);

  function pollJob(jobId: string) {
    if (pollRef.current) clearInterval(pollRef.current);

    const tick = async () => {
      try {
        const job = await getInvestorAnalysisJob(jobId);
        setProgress(progressLabel(job.progress, job.status));
        if (job.status === "completed") {
          if (pollRef.current) clearInterval(pollRef.current);
          setRunning(false);
          setRunningMode(null);
          setProgress("");
          await loadCache();
        } else if (job.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          setRunning(false);
          setRunningMode(null);
          setProgress("");
          setError(job.error ?? "分析失败");
        }
      } catch (e) {
        if (pollRef.current) clearInterval(pollRef.current);
        setRunning(false);
        setError(String(e));
      }
    };

    void tick();
    pollRef.current = setInterval(tick, 2000);
  }

  async function handleRun(mode: ViewMode) {
    if (running) return;
    setRunning(true);
    setRunningMode(mode);
    setViewMode(mode);
    setError(null);
    setProgress("排队中…");
    try {
      const job = await triggerInvestorAnalysis(ticker, mode);
      setProgress(progressLabel(job.progress, job.status));
      pollJob(job.job_id);
    } catch (e) {
      setRunning(false);
      setRunningMode(null);
      setProgress("");
      setError(String(e));
    }
  }

  const stale = isStale(analysis, latestUpdatedAt);
  const legacy = analysis != null && !isV2Analysis(analysis);
  const summary = analysis ? resolveSummary(analysis) : null;
  const scores = analysis?.framework_scores ?? [];
  const risks = summary?.key_risks ?? analysis?.key_risks ?? [];
  const showDeepFields = viewMode === "deep" || (analysis != null && isDeepAnalysis(analysis));
  const hasQuick = record.quick != null;
  const hasDeep = record.deep != null;
  const modeLabel = viewMode === "deep" ? "深度" : "快速";

  if (loadingCache && !analysis && !running && !hasQuick && !hasDeep) {
    return (
      <div className="rounded-lg border border-[#2B2F36] bg-[#1a1f24]/50 px-4 py-10 text-center text-[15px] text-[#9aa3b5]">
        加载大佬框架分析缓存…
      </div>
    );
  }

  return (
    <div className="md:col-span-2 xl:col-span-3">
      <div className="rounded-lg border border-[#2B2F36] bg-[#1a1f24] p-5 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)] sm:p-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-[#2B2F36] pb-4">
          <div>
            <p className="text-[13px] font-semibold tracking-wide text-[#8d94a8]">
              13 位框架 · 逐人独立分析（v2.1 快速 / 深度）
            </p>
            {analysis && (
              <p className="mt-1 text-[14px] text-[#9aa3b5]">
                {modeLabel} · 分析于 {fmtTime(analysis.analyzed_at)}
                {analysis.framework_version ? ` · ${analysis.framework_version}` : ""}
              </p>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            <div
              className="inline-flex rounded-md border border-[#2B2F36] p-0.5"
              role="tablist"
              aria-label="结论模式"
            >
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "quick"}
                disabled={running}
                onClick={() => setViewMode("quick")}
                className={`rounded px-3 py-1.5 text-[13px] font-semibold transition ${
                  viewMode === "quick"
                    ? "bg-[#2962FF] text-white"
                    : "text-[#9aa3b5] hover:text-white"
                }`}
              >
                快速结论{hasQuick ? "" : ""}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "deep"}
                disabled={running}
                onClick={() => setViewMode("deep")}
                className={`rounded px-3 py-1.5 text-[13px] font-semibold transition ${
                  viewMode === "deep"
                    ? "bg-[#7c3aed] text-white"
                    : "text-[#9aa3b5] hover:text-white"
                }`}
              >
                深度结论{hasDeep ? "" : ""}
              </button>
            </div>
            {running && progress && (
              <span className="max-w-[280px] text-right text-[13px] font-medium text-[#fbbf24]">
                {progress}
              </span>
            )}
            <div className="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => handleRun("quick")}
                disabled={running}
                className="rounded-md bg-[#2962FF] px-4 py-2.5 text-[14px] font-semibold text-white transition hover:bg-[#1d4ed8] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {running && runningMode === "quick"
                  ? "快速分析中…"
                  : record.quick
                    ? "重新快速"
                    : "快速结论"}
              </button>
              <button
                type="button"
                onClick={() => handleRun("deep")}
                disabled={running}
                title="基于独立 Playbook + 数据预计算"
                className="rounded-md border border-[#7c3aed]/60 bg-[#2e1064]/40 px-4 py-2.5 text-[14px] font-semibold text-[#e9d5ff] transition hover:bg-[#4c1d95]/60 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {running && runningMode === "deep"
                  ? "深度分析中…"
                  : record.deep
                    ? "重新深度"
                    : "深度结论"}
              </button>
            </div>
            {viewMode === "deep" && !running && (
              <p className="max-w-[260px] text-right text-[12px] leading-snug text-[#6b7288]">
                独立 Playbook + 预计算，约 8–15 分钟
              </p>
            )}
          </div>
        </div>

        {legacy && analysis && !running && (
          <div
            className="mb-4 rounded-md border border-[#fbbf24]/35 bg-[#3a2a10]/50 px-4 py-3 text-[14px] text-[#fde68a]"
            role="status"
          >
            当前为旧版（v1.0）缓存，无逐人买卖价。请点击「重新分析」生成 v2.0 结果。
          </div>
        )}

        {stale && analysis && (
          <div
            className="mb-4 rounded-md border border-[#fbbf24]/35 bg-[#3a2a10]/50 px-4 py-3 text-[14px] leading-relaxed text-[#fde68a]"
            role="status"
          >
            追踪数据已更新（{fmtTime(latestUpdatedAt)}），当前结论基于{" "}
            {fmtTime(analysis.source_updated_at)} 快照，建议重新分析。
          </div>
        )}

        {error && (
          <div
            className="mb-4 rounded-md border border-[#f87171]/35 bg-[#2a1518] px-4 py-3 text-[14px] text-[#fca5a5]"
            role="alert"
          >
            {error}
          </div>
        )}

        {running && (
          <div
            className="mb-4 rounded-md border border-[#2962FF]/30 bg-[#14181c] px-4 py-5"
            role="status"
            aria-live="polite"
          >
            <div className="flex items-center gap-3">
              <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-[#2962FF] border-t-transparent" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-medium text-[#c4c9e0]">
                  13 次独立 LLM · {runningMode === "deep" ? "深度" : "快速"}分析进行中
                </p>
                <p className="mt-1 text-[14px] text-[#fbbf24]">
                  {progress || "① 读取追踪快照"}
                </p>
                <p className="mt-1 text-[13px] text-[#6b7288]">
                  仅分析 {ticker}，不刷新全站 ·{" "}
                  {runningMode === "deep" ? "约 8–15 分钟" : "约 3–8 分钟"}（并发 2）
                </p>
              </div>
            </div>
          </div>
        )}

        {!analysis && !running && !error && (
          <div className="rounded-md border border-dashed border-[#3d4450] bg-[#14181c]/60 px-4 py-12 text-center">
            <p className="text-[16px] font-medium text-[#c4c9e0]">
              尚未运行{modeLabel}大佬框架分析
            </p>
            <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-[#8d94a8]">
              {viewMode === "deep"
                ? "深度模式按每位大佬 Playbook 分步分析，并注入预计算价位/PE 等事实；顶部仍为计票与中位数参考。"
                : "快速模式：每位大佬单独 Agent，给出买卖价与持有建议；顶部仅为计票与中位数参考。"}
            </p>
          </div>
        )}

        {analysis && summary && !running && (
          <div className="space-y-6">
            <div className={`rounded-lg border px-5 py-4 ${verdictClass(summary.verdict)}`}>
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-[22px] font-bold">
                  {verdictLabel(summary.verdict)}
                </span>
                {summary.verdict_counts && isV2Analysis(analysis) && (
                  <span className="text-[14px] opacity-90">
                    买入 {summary.verdict_counts.buy} · 观望 {summary.verdict_counts.watch} · 回避{" "}
                    {summary.verdict_counts.avoid}
                  </span>
                )}
              </div>
              <p className="mt-3 text-[15px] leading-relaxed">{summary.verdict_summary}</p>
              {isV2Analysis(analysis) && summary.ideal_price_median > 0 && (
                <p className="mt-2 text-[13px] text-[#9aa3b5]">
                  13 人理想买入中位数 {fmtUsd(summary.ideal_price_median, 0)}，区间{" "}
                  {fmtUsd(summary.ideal_price_range[0], 0)} –{" "}
                  {fmtUsd(summary.ideal_price_range[1], 0)}
                  <span className="text-[#6b7288]">（统计参考，非推荐仓位）</span>
                </p>
              )}
            </div>

            <div>
              <h2 className="mb-3 text-[14px] font-semibold tracking-wide text-[#8d94a8]">
                各框架独立建议（{scores.length} 位）
              </h2>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {scores.map((row) => (
                  <InvestorCard
                    key={row.investor}
                    row={row}
                    showDeepFields={showDeepFields}
                  />
                ))}
              </div>
            </div>

            {risks.length > 0 && (
              <div>
                <h2 className="mb-3 text-[14px] font-semibold text-[#8d94a8]">
                  主要风险（来自各框架 concern）
                </h2>
                <ul className="space-y-2 rounded-lg border border-[#2B2F36] bg-[#14181c] p-4">
                  {risks.map((r, i) => (
                    <li key={i} className="flex gap-2 text-[14px] leading-relaxed text-[#e8eaf0]">
                      <span className="text-[#fbbf24]">·</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
