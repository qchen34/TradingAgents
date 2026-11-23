"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { InvestorAnalysisSection } from "@/components/investor-analysis-section";
import {
  getInvestorAnalysis,
  getStockTrackerLatest,
  getStockTrackerChartUrl,
  type InvestorAnalysis,
  type InvestorAnalysisRecord,
  type StockTrackerItem,
  type StockTechnical,
  type StockTrendBuy,
  type StockFundamental,
  type StockLlm,
  type EpsHistoryItem,
  type QuarterlyRevenueItem,
  type AnalystBreakdown,
} from "@/lib/api";

// ─── 工具函数 ─────────────────────────────────────────────────────────────────

function pickInvestorSummary(
  data: InvestorAnalysis | InvestorAnalysisRecord | null,
): InvestorAnalysis | null {
  if (!data) return null;
  if ("quick" in data || "deep" in data) {
    const rec = data as InvestorAnalysisRecord;
    return rec.quick ?? rec.deep;
  }
  return data as InvestorAnalysis;
}

function fmt(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—";
  return v.toFixed(digits);
}

function toNum(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function fmtPct(v: number | null | undefined, alwaysSign = true): string {
  if (v == null) return "—";
  const sign = alwaysSign ? (v >= 0 ? "+" : "") : "";
  return sign + v.toFixed(2) + "%";
}

function fmtMarketCap(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(0) + "M";
  return "$" + v.toFixed(0);
}

function fmtFreeCashflow(v: number | null | undefined): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (Math.abs(v) >= 1e6) return "$" + (v / 1e6).toFixed(0) + "M";
  return "$" + v.toFixed(0);
}

function colorVal(v: number | null | undefined): string {
  if (v == null) return "text-[#e8eaf0]";
  return v >= 0 ? "text-[#22c55e]" : "text-[#f87171]";
}

function stageColor(label: string | undefined): string {
  if (!label || label === "待分析") return "bg-[#2B2F36] text-[#8d90a2]";
  if (label.includes("Stage 2")) return "bg-[#1a3a20] text-[#4ade80]";
  if (label.includes("Stage 1")) return "bg-[#1a2e3a] text-[#60a5fa]";
  if (label.includes("Stage 3")) return "bg-[#3a2a10] text-[#fbbf24]";
  if (label.includes("Stage 4")) return "bg-[#3a1a1a] text-[#f87171]";
  return "bg-[#2B2F36] text-[#8d90a2]";
}

function confidenceColor(c: string | undefined): string {
  if (c === "high") return "text-[#22c55e]";
  if (c === "medium") return "text-[#fbbf24]";
  if (c === "low") return "text-[#f87171]";
  return "text-[#8d90a2]";
}

function trendBuyVerdictLabel(v: StockTrendBuy["verdict"] | undefined): string {
  if (v === "at_buy") return "买点确认";
  if (v === "near_buy") return "近买点";
  if (v === "not_yet") return "未到买点";
  if (v === "avoid_chase") return "禁追 / 等回撤";
  return "—";
}

function trendBuyVerdictClass(v: StockTrendBuy["verdict"] | undefined): string {
  if (v === "at_buy") return "text-[#22c55e]";
  if (v === "near_buy") return "text-[#38bdf8]";
  if (v === "avoid_chase") return "text-[#f87171]";
  return "text-[#a8acc0]";
}

function formatAnalystRating(rating: string | undefined): React.ReactNode {
  if (!rating) return "—";
  const key = rating.toLowerCase().replace(/\s+/g, "_");
  const labels: Record<string, string> = {
    strong_buy: "强烈买入",
    buy: "买入",
    hold: "持有",
    sell: "卖出",
    strong_sell: "强烈卖出",
  };
  const label = labels[key] ?? rating;
  const badgeClass =
    key === "strong_buy" || key === "buy"
      ? "bg-[#1a3a20] text-[#4ade80]"
      : key === "strong_sell" || key === "sell"
        ? "bg-[#3a1a1a] text-[#f87171]"
        : "bg-[#2B2F36] text-[#c4c9e0]";
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[12px] font-medium ${badgeClass}`}>
      {label}
    </span>
  );
}

// ─── 小指标行 ─────────────────────────────────────────────────────────────────

function Row({
  label,
  value,
  valueClass = "text-white",
  hint,
  valueHint,
}: {
  label: string;
  value: React.ReactNode;
  valueClass?: string;
  hint?: string;
  valueHint?: string;
}) {
  return (
    <div className="metric-row">
      <span className="text-[12px] leading-snug text-[#8d94a8]" title={hint}>
        {label}
      </span>
      <div className="min-w-0">
        <span className={`font-mono text-[13px] font-medium tabular-nums ${valueClass}`}>{value}</span>
        {valueHint && (
          <p className="mt-0.5 text-[11px] leading-snug text-[#6b7288]">{valueHint}</p>
        )}
      </div>
    </div>
  );
}

function MetricRows({ children }: { children: React.ReactNode }) {
  return <div className="metric-rows">{children}</div>;
}

// ─── 中卡片 ──────────────────────────────────────────────────────────────────

function MedCard({
  title,
  children,
  fullWidth = false,
}: {
  title: string;
  children: React.ReactNode;
  fullWidth?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border border-[#2B2F36] bg-[#1a1f24] p-5 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)] ${
        fullWidth ? "md:col-span-2" : ""
      }`}
    >
      <div className="mb-4 border-b border-[#2B2F36] pb-3 text-[12px] font-semibold text-[#c4c9e0]">
        {title}
      </div>
      {children}
    </div>
  );
}

// ─── 大模块（accordion） ──────────────────────────────────────────────────────

function Module({
  title,
  summary,
  children,
  defaultOpen = true,
}: {
  title: string;
  summary: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="mb-5 overflow-hidden rounded-lg border border-[#2B2F36] bg-[#14181c] shadow-[0_1px_0_0_rgba(0,0,0,0.2)]">
      {/* 大模块 header */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left transition hover:bg-[#1c2229]"
      >
        <div className="flex min-w-0 items-center gap-3">
          <span
            className="shrink-0 text-[12px] text-[#8d94a8] transition-transform"
            style={{ display: "inline-block", transform: open ? "rotate(90deg)" : "rotate(0deg)" }}
          >
            ▶
          </span>
          <span className="text-[16px] font-semibold tracking-tight text-white">{title}</span>
        </div>
        {!open && (
          <span className="ml-2 min-w-0 flex-1 truncate text-[12px] leading-snug text-[#9aa3b5]">
            {summary}
          </span>
        )}
        <span className="ml-2 shrink-0 rounded border border-[#3d4450] px-2 py-0.5 text-[11px] text-[#9aa3b5]">
          {open ? "收起" : "展开"}
        </span>
      </button>

      {open && (
        <div className="border-t border-[#2B2F36] bg-[#161A1E]/80 px-4 pb-5 pt-4 sm:px-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">{children}</div>
        </div>
      )}
    </div>
  );
}

// ─── EPS 历史 ─────────────────────────────────────────────────────────────────

function EpsHistoryRows({ items }: { items: EpsHistoryItem[] }) {
  if (!items || items.length === 0)
    return <div className="text-[12px] text-[#a8acc0]">暂无数据</div>;
  return (
    <div className="space-y-0.5">
      {items.map((e, i) => (
        <div
          key={i}
          className="flex items-center justify-between border-b border-[#1e232b] py-1.5 text-[12px] last:border-0"
        >
          <span className="text-[#a8acc0]">{e.date ?? `Q${i + 1}`}</span>
          <span className="font-mono font-medium">
            {e.surprise_pct != null ? (
              <span className={e.surprise_pct >= 0 ? "text-[#4ade80]" : "text-[#f87171]"}>
                {e.surprise_pct >= 0 ? "+" : ""}
                {e.surprise_pct.toFixed(1)}% {e.surprise_pct >= 0 ? "✅" : "❌"}
              </span>
            ) : (
              <span className="text-[#a8acc0]">—</span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── 季度营收 ─────────────────────────────────────────────────────────────────

function QuarterlyRevenueRows({ items }: { items: QuarterlyRevenueItem[] }) {
  if (!items || items.length === 0)
    return <div className="text-[12px] text-[#a8acc0]">暂无数据</div>;
  return (
    <div className="space-y-0.5">
      {items.map((r, i) => (
        <div
          key={i}
          className="flex items-center justify-between border-b border-[#1e232b] py-1.5 text-[12px] last:border-0"
        >
          <span className="text-[#a8acc0]">{r.date ?? `Q${i + 1}`}</span>
          <span className="font-mono">
            {r.revenue != null ? (
              <span className="font-medium text-white">
                {r.revenue >= 1e9
                  ? "$" + (r.revenue / 1e9).toFixed(2) + "B"
                  : "$" + (r.revenue / 1e6).toFixed(0) + "M"}
              </span>
            ) : (
              "—"
            )}
            {r.qoq_pct != null && (
              <span
                className={`ml-2 font-medium ${
                  r.qoq_pct >= 0 ? "text-[#4ade80]" : "text-[#f87171]"
                }`}
              >
                {r.qoq_pct >= 0 ? "+" : ""}
                {r.qoq_pct.toFixed(1)}%
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── 分析师买卖分布 bar ────────────────────────────────────────────────────────

function AnalystBar({ b }: { b: AnalystBreakdown | null }) {
  if (!b) return <div className="text-[12px] text-[#a8acc0]">暂无数据</div>;
  const total = b.strongBuy + b.buy + b.hold + b.sell + b.strongSell || 1;
  const segments = [
    { label: "强买", count: b.strongBuy, color: "bg-[#16a34a]" },
    { label: "买", count: b.buy, color: "bg-[#22c55e]" },
    { label: "持", count: b.hold, color: "bg-[#6b7280]" },
    { label: "卖", count: b.sell, color: "bg-[#f87171]" },
    { label: "强卖", count: b.strongSell, color: "bg-[#dc2626]" },
  ];
  return (
    <div>
      <div className="flex h-5 w-full overflow-hidden rounded-md bg-[#0f1318]">
        {segments.map((s) =>
          s.count > 0 ? (
            <div
              key={s.label}
              className={`${s.color} min-w-[2px]`}
              style={{ width: `${(s.count / total) * 100}%` }}
              title={`${s.label}: ${s.count}`}
            />
          ) : null,
        )}
      </div>
      <div className="mt-3 grid grid-cols-5 gap-1 text-center text-[11px] text-[#9aa3b5]">
        {segments.map((s) => (
          <div key={s.label}>
            <div className="font-mono text-[13px] font-semibold tabular-nums text-white">{s.count}</div>
            <div className="mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── 详情页主组件（内部，需要 useSearchParams） ─────────────────────────────

function StockDetailInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const ticker = searchParams.get("ticker")?.toUpperCase() ?? "";

  const [item, setItem] = useState<StockTrackerItem | null>(null);
  const [latestUpdatedAt, setLatestUpdatedAt] = useState<string | null>(null);
  const [investorSummary, setInvestorSummary] = useState("尚未运行大佬分析");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    try {
      const d = await getStockTrackerLatest();
      setLatestUpdatedAt(d.updated_at ?? null);
      const found = d.tickers.find((t) => t.ticker === ticker) ?? null;
      setItem(found);
      if (!found && d.status === "empty") {
        setError("数据尚未加载，请先在「个股追踪」页面刷新数据。");
      } else if (!found) {
        setError(`未找到 ${ticker} 的追踪数据。`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [ticker]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const updateInvestorSummary = useCallback((a: Awaited<ReturnType<typeof getInvestorAnalysis>>) => {
    const row = pickInvestorSummary(a);
    if (!row) {
      setInvestorSummary("尚未运行大佬分析");
      return;
    }
    const fv = row.framework_version ?? "";
    const isV2 = (fv === "2.0" || fv.startsWith("2.1")) && row.summary;
    const verdict = isV2 ? row.summary!.verdict : row.verdict;
    const vLabel =
      verdict === "buy" ? "买入" : verdict === "watch" ? "观望" : verdict === "avoid" ? "回避" : "—";
    let idealStr = "—";
    if (isV2 && row.summary) {
      const med = row.summary.ideal_price_median;
      idealStr = Number.isFinite(med) ? `$${med.toFixed(0)}` : "—";
    } else if (row.entry?.ideal_price != null) {
      const n = Number(row.entry.ideal_price);
      idealStr = Number.isFinite(n) ? `$${n.toFixed(0)}` : "—";
    }
    const verTag = fv.startsWith("2.1") ? "深度" : isV2 ? "快速" : "v1↑";
    setInvestorSummary(`${vLabel} · 中位 ${idealStr} · 13位(${verTag})`);
  }, []);

  useEffect(() => {
    if (!ticker) return;
    getInvestorAnalysis(ticker)
      .then(updateInvestorSummary)
      .catch(() => setInvestorSummary("尚未运行大佬分析"));
  }, [ticker, updateInvestorSummary]);

  if (!ticker) {
    return (
      <div className="h-full overflow-y-auto bg-[#161A1E] font-sans text-[13px] leading-normal text-[#e8eaf0] antialiased">
        <div className="mx-auto max-w-md px-4 py-12 sm:px-5 sm:py-16">
          <div className="rounded-lg border border-dashed border-[#3d4450] bg-[#1a1f24]/50 px-6 py-10 text-center">
            <h1 className="text-[17px] font-semibold tracking-tight text-white">缺少股票代码</h1>
            <p className="mt-3 text-[13px] leading-relaxed text-[#9aa3b5]">
              请在「个股追踪」总表中点击一行进入详情；或在地址栏使用参数{" "}
              <code className="rounded bg-[#0f1318] px-1.5 py-0.5 font-mono text-[11px] text-[#a8b4c8]">
                ?ticker=NVDA
              </code>
              。
            </p>
            <button
              type="button"
              onClick={() => router.push("/analysis")}
              className="mt-6 rounded-md border border-[#3d4450] bg-[#222830] px-4 py-2.5 text-[12px] font-medium text-white shadow-sm transition hover:border-[#4a5568] hover:bg-[#2a313c] active:scale-[0.98]"
            >
              打开个股追踪
            </button>
          </div>
        </div>
      </div>
    );
  }

  const tech = (item?.technical ?? {}) as Partial<StockTechnical>;
  const fund = (item?.fundamental ?? {}) as Partial<StockFundamental>;
  const llm = (item?.llm ?? {}) as Partial<StockLlm>;

  // ─── 各模块摘要文本 ─────────────────────────────────────────────────────
  const fundSummary = [
    fund.pe_ttm != null ? `PE ${fund.pe_ttm.toFixed(0)}x` : null,
    fund.peg_ratio != null ? `PEG ${fund.peg_ratio.toFixed(2)}` : null,
    fund.eps_growth_next_y_pct != null
      ? `EPS N.Y ${fund.eps_growth_next_y_pct >= 0 ? "+" : ""}${fund.eps_growth_next_y_pct.toFixed(0)}%`
      : null,
    fund.revenue_growth_yoy != null ? `收入${fund.revenue_growth_yoy >= 0 ? "+" : ""}${fund.revenue_growth_yoy.toFixed(0)}%` : null,
    fund.gross_margin != null ? `毛利 ${fund.gross_margin.toFixed(0)}%` : null,
    fund.next_earnings_date ? `财报 ${fund.next_earnings_date.slice(5)}` : null,
  ]
    .filter(Boolean)
    .join("  ·  ");

  const techSummary = [
    tech.trend_buy?.verdict ? `规则: ${trendBuyVerdictLabel(tech.trend_buy.verdict)}` : null,
    tech.pct_vs_ma150 != null ? `偏离MA150 ${fmtPct(tech.pct_vs_ma150)}` : null,
    tech.rsi14 != null ? `RSI ${tech.rsi14.toFixed(0)}` : null,
    tech.rs_slope_3m != null ? `RS 3M ${tech.rs_slope_3m >= 0 ? "+" : ""}${tech.rs_slope_3m.toFixed(3)}` : null,
    tech.score != null ? `评分 ${tech.score}/9` : null,
    tech.extension_label ? tech.extension_label : null,
  ]
    .filter(Boolean)
    .join("  ·  ");

  const llmSummary = [
    llm.stage_label || null,
    llm.action_type || null,
    llm.confidence ? `置信度 ${llm.confidence}` : null,
  ]
    .filter(Boolean)
    .join("  ·  ");

  const chartUrl = getStockTrackerChartUrl(ticker);

  return (
    <div className="h-full overflow-y-auto bg-[#161A1E] font-sans text-[13px] leading-normal text-[#e8eaf0] antialiased">
      {/* ─── Sticky Header ──────────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 border-b border-[#2B2F36] bg-[#161A1E]/95 px-4 py-3.5 shadow-[0_1px_0_0_rgba(0,0,0,0.25)] backdrop-blur-md sm:px-5">
        {/* 面包屑 */}
        <button
          type="button"
          onClick={() => router.push("/analysis")}
          className="mb-2.5 flex items-center gap-1.5 text-[12px] font-medium text-[#9aa3b5] transition hover:text-white"
        >
          ← 个股追踪
        </button>

        {loading ? (
          <div className="rounded-md border border-[#2B2F36] bg-[#1a1f24]/40 px-4 py-6 text-[13px] text-[#9aa3b5]">
            加载中…
          </div>
        ) : error ? (
          <div
            className="rounded-lg border border-[#f87171]/35 bg-[#2a1518] px-4 py-3 text-[13px] leading-relaxed text-[#fca5a5]"
            role="alert"
          >
            {error}
          </div>
        ) : item ? (
          <>
            {/* 第一行：价格信息 */}
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1.5">
              <span className="font-mono text-[22px] font-bold tracking-tight text-white">{ticker}</span>
              <span className="max-w-full text-[14px] leading-snug text-[#b8c0d0]">{item.name}</span>
              {tech.close != null && (
                <span className="font-mono text-[19px] font-bold tabular-nums text-white">
                  ${tech.close.toFixed(2)}
                </span>
              )}
              {tech.change_pct != null && (
                <span className={`font-mono text-[16px] font-bold tabular-nums ${colorVal(tech.change_pct)}`}>
                  {fmtPct(tech.change_pct)}
                </span>
              )}
            </div>
            {/* 第二行：Stage / 买点 / 评分 / 行业 */}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {llm.stage_label && (
                <span
                  className={`rounded-md px-2.5 py-0.5 text-[12px] font-semibold ${stageColor(
                    llm.stage_label,
                  )}`}
                >
                  {llm.stage_label}
                </span>
              )}
              {llm.action_type && llm.action_type !== "待分析" && (
                <span className="rounded-md border border-[#2B2F36] bg-[#222830] px-2.5 py-0.5 text-[12px] font-medium text-[#dce1ff]">
                  买点：{llm.action_type}
                </span>
              )}
              {tech.score != null && (
                <span className="rounded-md border border-[#2B2F36] bg-[#222830] px-2.5 py-0.5 font-mono text-[12px] font-semibold tabular-nums text-[#fbbf24]">
                  评分 {tech.score}/9
                </span>
              )}
              {fund.industry_label && (
                <span className="rounded-md border border-[#2B2F36] bg-[#222830] px-2.5 py-0.5 text-[12px] text-[#c4c9e0]">
                  {fund.industry_label}
                </span>
              )}
            </div>
          </>
        ) : (
          <div className="text-[13px] text-[#fca5a5]">未找到 {ticker} 的数据</div>
        )}
      </div>

      {/* ─── 主体：三大模块 ──────────────────────────────────────────────── */}
      {item && (
        <div className="w-full px-4 py-5 sm:px-5">
          {/* ═══════════════════════════════════════════════════════════════ */}
          {/* 大模块 1：基本面分析 */}
          {/* ═══════════════════════════════════════════════════════════════ */}
          <Module title="基本面分析" summary={fundSummary}>
            {/* 1-A 估值指标 */}
            <MedCard title="估值指标">
              <Row label="PE TTM" value={fund.pe_ttm != null ? fund.pe_ttm.toFixed(1) + "x" : "—"} />
              <Row
                label={`行业PE${fund.industry_proxy ? ` (${fund.industry_proxy})` : ""}`}
                value={
                  fund.industry_pe_avg != null
                    ? `${fund.industry_pe_avg.toFixed(1)}x`
                    : "—"
                }
                valueClass="text-[#c4c9e0]"
                hint={fund.industry_label ?? undefined}
              />
              {(() => {
                const ratio =
                  fund.pe_ttm != null &&
                  fund.industry_pe_avg != null &&
                  fund.industry_pe_avg > 0
                    ? fund.pe_ttm / fund.industry_pe_avg
                    : null;
                const cls =
                  ratio == null
                    ? "text-[#a8acc0]"
                    : ratio > 1.5
                    ? "text-[#fbbf24]"
                    : ratio < 0.8
                    ? "text-[#4ade80]"
                    : "text-white";
                return (
                  <Row
                    label="PE/行业PE"
                    value={ratio != null ? ratio.toFixed(2) + "x" : "—"}
                    valueClass={cls}
                    hint="相对行业代理 ETF 的 PE 倍率"
                  />
                );
              })()}
              <Row label="PE Fwd" value={fund.pe_fwd != null ? fund.pe_fwd.toFixed(1) + "x" : "—"} />
              <Row label="PS TTM" value={fund.ps_ttm != null ? fund.ps_ttm.toFixed(1) + "x" : "—"} />
              <Row label="PEG" value={fund.peg_ratio != null ? fund.peg_ratio.toFixed(2) : "—"} />
              <Row
                label="EV/EBITDA"
                value={fund.ev_ebitda != null ? fund.ev_ebitda.toFixed(1) + "x" : "—"}
              />
              <Row label="市值" value={fmtMarketCap(fund.market_cap)} />
            </MedCard>

            {/* 1-B 盈利质量 */}
            <MedCard title="盈利质量">
              <Row
                label="毛利率"
                value={fmtPct(fund.gross_margin, false)}
                valueClass="text-[#e8eaf0]"
              />
              <Row
                label="营业利润率"
                value={fmtPct(fund.operating_margin, false)}
                valueClass="text-[#e8eaf0]"
              />
              <Row
                label="收入增速 YoY"
                value={fmtPct(fund.revenue_growth_yoy)}
                valueClass={colorVal(fund.revenue_growth_yoy)}
              />
              <Row label="自由现金流" value={fmtFreeCashflow(fund.free_cashflow)} />
            </MedCard>

            {/* 1-C 成长与杠杆 */}
            <MedCard title="成长与杠杆">
              <Row label="PEG 比率" value={fund.peg_ratio != null ? fund.peg_ratio.toFixed(2) : "—"} />
              <Row
                label="EPS Past 5Y%"
                value={fmtPct(fund.eps_growth_5y_pct)}
                valueClass={colorVal(fund.eps_growth_5y_pct)}
              />
              <Row
                label="Sales Past 5Y%"
                value={fmtPct(fund.sales_growth_5y_pct)}
                valueClass={colorVal(fund.sales_growth_5y_pct)}
              />
              <Row
                label="EPS This Y%"
                value={fmtPct(fund.eps_growth_this_y_pct)}
                valueClass={colorVal(fund.eps_growth_this_y_pct)}
              />
              <Row
                label="EPS Next Y%"
                value={fmtPct(fund.eps_growth_next_y_pct)}
                valueClass={colorVal(fund.eps_growth_next_y_pct)}
              />
              <Row
                label="EPS Next 5Y%"
                value={fmtPct(fund.eps_growth_next_5y_pct)}
                valueClass={colorVal(fund.eps_growth_next_5y_pct)}
              />
              <Row
                label="EPS Q/Q%"
                value={fmtPct(fund.eps_growth_qoq_pct)}
                valueClass={colorVal(fund.eps_growth_qoq_pct)}
              />
              <Row
                label="Sales Q/Q%"
                value={fmtPct(fund.sales_growth_qoq_pct)}
                valueClass={colorVal(fund.sales_growth_qoq_pct)}
              />
              <Row
                label="D/E"
                value={fund.debt_to_equity != null ? fund.debt_to_equity.toFixed(2) : "—"}
                valueClass={colorVal(
                  fund.debt_to_equity != null ? (fund.debt_to_equity > 1 ? -1 : 1) : null,
                )}
              />
            </MedCard>

            {/* 1-D 财报达标 */}
            <MedCard title="财报达标（最近4季）" fullWidth>
              <div className="grid grid-cols-1 gap-x-4 gap-y-2 md:grid-cols-2">
                <div>
                  <div className="mb-1.5 text-[11px] font-medium text-[#c4c9e0]">EPS 超预期</div>
                  <EpsHistoryRows items={fund.eps_history ?? []} />
                </div>
                <div>
                  <div className="mb-1.5 text-[11px] font-medium text-[#c4c9e0]">季度营收 QoQ</div>
                  <QuarterlyRevenueRows items={fund.quarterly_revenue ?? []} />
                </div>
              </div>
            </MedCard>

            {/* 1-E 分析师共识 */}
            <MedCard title="分析师共识" fullWidth>
              <div className="grid grid-cols-1 gap-x-4 gap-y-2 md:grid-cols-2">
                <div>
                  <Row label="综合评级" value={fund.analyst_rating ?? "—"} />
                  <Row
                    label="目标价"
                    value={
                      fund.analyst_target != null ? "$" + fund.analyst_target.toFixed(2) : "—"
                    }
                  />
                  <Row
                    label="分析师数"
                    value={fund.analyst_count != null ? fund.analyst_count + "人" : "—"}
                  />
                  <Row label="下次财报" value={fund.next_earnings_date ?? "—"} />
                  {fund.eps_guidance_range?.low != null && (
                    <Row
                      label="EPS 指引"
                      value={`$${fund.eps_guidance_range.low?.toFixed(2)} – $${fund.eps_guidance_range.high?.toFixed(
                        2,
                      )}`}
                    />
                  )}
                </div>
                <div>
                  <div className="mb-2 text-[11px] font-medium text-[#c4c9e0]">买/持/卖 分布</div>
                  <AnalystBar b={fund.analyst_breakdown ?? null} />
                </div>
              </div>
            </MedCard>
          </Module>

          {/* ═══════════════════════════════════════════════════════════════ */}
          {/* 大模块 2：技术面分析 */}
          {/* ═══════════════════════════════════════════════════════════════ */}
          <Module title="技术面分析" summary={techSummary}>
            {/* 2-A 趋势结构 */}
            <MedCard title="趋势结构">
              <Row label="收盘价" value={tech.close != null ? "$" + tech.close.toFixed(2) : "—"} />
              <Row label="MA50" value={tech.ma50 != null ? "$" + tech.ma50.toFixed(2) : "—"} />
              <Row label="MA150" value={tech.ma150 != null ? "$" + tech.ma150.toFixed(2) : "—"} />
              <Row label="MA200" value={tech.ma200 != null ? "$" + tech.ma200.toFixed(2) : "—"} />
              <Row
                label="偏离MA150"
                value={fmtPct(tech.pct_vs_ma150)}
                valueClass={colorVal(tech.pct_vs_ma150)}
              />
              <Row
                label="MA150斜率 4w"
                value={fmtPct(tech.ma150_slope_4w)}
                valueClass={colorVal(tech.ma150_slope_4w)}
              />
              <Row
                label="MA50 > MA150"
                value={tech.ma_cross?.ma50_above_ma150 ? "✅" : "❌"}
                valueClass={tech.ma_cross?.ma50_above_ma150 ? "text-[#22c55e]" : "text-[#f87171]"}
              />
              <Row
                label="MA150 > MA200"
                value={tech.ma_cross?.ma150_above_ma200 ? "✅" : "❌"}
                valueClass={tech.ma_cross?.ma150_above_ma200 ? "text-[#22c55e]" : "text-[#f87171]"}
              />
            </MedCard>

            {/* 2-A2 趋势买点（规则） */}
            <MedCard title="趋势买点（规则）">
              {tech.trend_buy ? (
                <>
                  <Row
                    label="结论"
                    value={trendBuyVerdictLabel(tech.trend_buy.verdict)}
                    valueClass={`font-semibold ${trendBuyVerdictClass(tech.trend_buy.verdict)}`}
                  />
                  <div className="mt-2 border-t border-[#1e232b] pt-2">
                    <span className="text-[11px] text-[#a8acc0]">摘要</span>
                    <p className="mt-1 text-[12px] leading-relaxed text-[#e8eaf0]">
                      {tech.trend_buy.one_liner || "—"}
                    </p>
                  </div>
                  {tech.trend_buy.supporting_tags && tech.trend_buy.supporting_tags.length > 0 && (
                    <div className="mt-2">
                      <span className="text-[11px] text-[#a8acc0]">标签</span>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {tech.trend_buy.supporting_tags.map((t, i) => (
                          <span
                            key={i}
                            className="rounded bg-[#1e232b] px-1.5 py-0.5 text-[10px] text-[#c4c9e0]"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {tech.trend_buy.conditions_if_not_buy && tech.trend_buy.conditions_if_not_buy.length > 0 && (
                    <div className="mt-2">
                      <span className="text-[11px] text-[#a8acc0]">若未到买点，可关注条件</span>
                      <ul className="mt-1 space-y-1">
                        {tech.trend_buy.conditions_if_not_buy.map((c, i) => (
                          <li key={i} className="text-[11px] leading-snug text-[#dce1ff]">
                            · {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-[12px] text-[#a8acc0]">暂无规则化买点数据，请刷新追踪。</div>
              )}
            </MedCard>

            {/* 2-B 动量与量能 */}
            <MedCard title="动量与量能">
              <Row
                label="RSI(14)"
                value={tech.rsi14 != null ? tech.rsi14.toFixed(1) : "—"}
                valueClass={
                  tech.rsi14 == null
                    ? "text-[#8d90a2]"
                    : tech.rsi14 > 70
                    ? "text-[#f87171]"
                    : tech.rsi14 > 50
                    ? "text-[#22c55e]"
                    : "text-[#fbbf24]"
                }
              />
              <Row
                label="RS vs QQQ 3M"
                value={tech.rs_slope_3m != null ? (tech.rs_slope_3m >= 0 ? "+" : "") + tech.rs_slope_3m.toFixed(3) : "—"}
                valueClass={colorVal(tech.rs_slope_3m)}
              />
              <Row label="涨跌量比" value={tech.vol_ratio != null ? tech.vol_ratio.toFixed(2) : "—"} />
              <Row
                label="量 / 20日均量"
                value={tech.volume_vs_ma20 != null ? tech.volume_vs_ma20.toFixed(2) : "—"}
                hint="当日成交量 ÷ 20日平均成交量"
              />
              <Row
                label="MACD 柱"
                value={tech.macd_hist != null ? tech.macd_hist.toFixed(4) : "—"}
                valueClass={
                  tech.macd_hist == null
                    ? "text-[#8d90a2]"
                    : tech.macd_hist >= 0
                      ? "text-[#22c55e]"
                      : "text-[#f87171]"
                }
              />
              <Row label="MACD 柱斜率" value={tech.macd_hist_slope ?? "—"} />
              <Row label="MACD / Signal" value={tech.macd_line != null && tech.macd_signal != null ? `${tech.macd_line.toFixed(3)} / ${tech.macd_signal.toFixed(3)}` : "—"} />
              <Row label="MA50·MA200" value={tech.golden_cross_label ?? "—"} />
              <Row label="OBV 趋势" value={tech.obv_trend ?? "—"} />
              <Row label="3月振幅" value={tech.range_3m_pct != null ? tech.range_3m_pct.toFixed(1) + "%" : "—"} />
              <Row label="月度高点" value={tech.monthly_highs_trend ?? "—"} />
              <Row
                label="综合评分"
                value={tech.score != null ? `${tech.score}/9` : "—"}
                valueClass="text-[#fbbf24]"
              />
              <Row
                label="偏离区间"
                value={tech.extension_label ?? "—"}
                valueClass={
                  tech.extension_label === "健康区"
                    ? "text-[#22c55e]"
                    : tech.extension_label === "延伸区" || tech.extension_label === "过度延伸"
                    ? "text-[#f87171]"
                    : "text-[#e8eaf0]"
                }
              />
            </MedCard>

            {/* 2-C Weinstein 图表（全宽） */}
            <MedCard title="Weinstein 技术图表" fullWidth>
              <div className="relative overflow-hidden rounded-md border border-[#2B2F36] bg-[#0e1117]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={chartUrl}
                  alt={`${ticker} Weinstein chart`}
                  className="w-full"
                  style={{ minHeight: 200, background: "#0e1117" }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
                <div className="border-t border-[#2B2F36] px-3 py-2 text-[11px] text-[#8d94a8]">
                  Price · MA50 · MA150 · Volume · RSI(14) · MACD · RS vs QQQ
                </div>
              </div>
            </MedCard>
          </Module>

          {/* ═══════════════════════════════════════════════════════════════ */}
          {/* 大模块 3：LLM 深度分析 */}
          {/* ═══════════════════════════════════════════════════════════════ */}
          <Module title="LLM 深度分析" summary={llmSummary}>
            {/* 3-A 阶段判断（全宽） */}
            <MedCard title="阶段判断" fullWidth>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span
                  className={`rounded px-2.5 py-0.5 text-[13px] font-semibold ${stageColor(
                    llm.stage_label,
                  )}`}
                >
                  {llm.stage_label || "待分析"}
                </span>
                <span className={`text-[12px] font-semibold ${confidenceColor(llm.confidence)}`}>
                  置信度：{llm.confidence || "—"}
                </span>
              </div>
              {llm.stage_narrative ? (
                <p className="text-[13px] leading-relaxed text-[#e8eaf0]">{llm.stage_narrative}</p>
              ) : (
                <p className="text-[12px] text-[#a8acc0]">
                  {llm.error ? `分析错误：${llm.error}` : "暂无 LLM 分析，请刷新数据。"}
                </p>
              )}
            </MedCard>

            {/* 3-B 买点指引 */}
            <MedCard title="买点指引">
              <Row label="买点类型" value={llm.action_type || "—"} />
              {(() => {
                const stop = toNum(llm.stop_reference);
                return (
                  <Row
                    label="止损参考"
                    value={stop != null ? "$" + stop.toFixed(2) : "—"}
                    valueClass="text-[#f87171]"
                  />
                );
              })()}
              {llm.next_buy_guidance && (
                <div className="mt-3 rounded bg-[#1e232b] p-2.5 text-[12px] leading-relaxed text-[#e8eaf0]">
                  {llm.next_buy_guidance}
                </div>
              )}
            </MedCard>

            {/* 3-C 催化剂监控 */}
            <MedCard title="催化剂监控">
              {llm.catalysts && llm.catalysts.length > 0 ? (
                <ul className="space-y-1.5">
                  {llm.catalysts.map((c, i) => (
                    <li key={i} className="flex items-start gap-2 text-[12px] text-[#e8eaf0]">
                      <span className="mt-0.5 text-[#fbbf24]">·</span>
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-[12px] text-[#a8acc0]">暂无数据</div>
              )}
            </MedCard>

            {/* 3-D 收入达标评估（全宽） */}
            <MedCard title="收入达标评估（LLM）" fullWidth>
              {llm.revenue_surprise_assessment ? (
                <p className="text-[13px] leading-relaxed text-[#e8eaf0]">
                  {llm.revenue_surprise_assessment}
                </p>
              ) : (
                <p className="text-[12px] text-[#a8acc0]">暂无 LLM 分析，请刷新数据。</p>
              )}
            </MedCard>
          </Module>

          <Module title="大佬框架分析" summary={investorSummary} defaultOpen={false}>
            <InvestorAnalysisSection
              ticker={ticker}
              latestUpdatedAt={latestUpdatedAt}
              onAnalysisChange={updateInvestorSummary}
            />
          </Module>
        </div>
      )}
    </div>
  );
}

// ─── 导出（包裹 Suspense，因为使用了 useSearchParams） ──────────────────────

export default function StockDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="h-full overflow-y-auto bg-[#161A1E] px-5 py-12 font-sans text-[13px] text-[#9aa3b5] antialiased">
          <div className="mx-auto max-w-sm rounded-lg border border-[#2B2F36] bg-[#1a1f24]/50 py-12 text-center">
            加载中…
          </div>
        </div>
      }
    >
      <StockDetailInner />
    </Suspense>
  );
}
