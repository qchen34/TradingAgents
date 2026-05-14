"use client";

import type { TaReportMeta } from "@/lib/api";

const ANALYST_BADGE: Record<string, string> = {
  market: "M",
  social: "S",
  news: "N",
  fundamentals: "F",
};

export function HistoryList({
  items,
  activeId,
  loading,
  onSelect,
}: {
  items: TaReportMeta[];
  activeId: string | null;
  loading?: boolean;
  onSelect: (reportId: string) => void;
}) {
  if (loading) {
    return (
      <div className="rounded border border-[#2B2F36] bg-[#0f1318] p-4 text-center text-[12px] text-[#8d90a2]">
        加载历史报告中…
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="rounded border border-[#2B2F36] bg-[#0f1318] p-4 text-center text-[12px] text-[#8d90a2]">
        本地 reports/ 目录暂无报告
      </div>
    );
  }
  return (
    <ul className="space-y-1.5">
      {items.map((m) => {
        const active = m.report_id === activeId;
        const dateOnly = m.generated_at.slice(0, 10);
        return (
          <li key={m.report_id}>
            <button
              type="button"
              onClick={() => onSelect(m.report_id)}
              className={`w-full rounded border px-3 py-2 text-left transition ${
                active
                  ? "border-[#2962FF] bg-[#0c1e3a] text-white"
                  : "border-[#2B2F36] bg-[#0f1318] text-[#d4d6e0] hover:border-[#3a4055] hover:bg-[#161A1F]"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[13px] font-semibold">
                  {m.ticker}
                </span>
                <span className="font-mono text-[11px] text-[#8d90a2]">
                  {dateOnly}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between text-[11px] text-[#a8acc0]">
                <span className="font-mono">{m.report_id}</span>
                <div className="flex gap-1">
                  {m.analysts.map((a) => (
                    <span
                      key={a}
                      className="rounded bg-[#1e232b] px-1.5 py-0.5 font-mono text-[10px] text-[#cbd0dc]"
                      title={a}
                    >
                      {ANALYST_BADGE[a] ?? a[0]?.toUpperCase()}
                    </span>
                  ))}
                </div>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
