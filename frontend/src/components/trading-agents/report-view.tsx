"use client";

import { useState, type ReactNode } from "react";
import { Md } from "./markdown";
import type { TaReportDetail, TaReportDecision } from "@/lib/api";

const DECISION_STYLES: Record<
  TaReportDecision,
  { bg: string; border: string; text: string; label: string; icon: string }
> = {
  BUY: {
    bg: "bg-gradient-to-r from-[#0c2a16] to-[#0a1f12]",
    border: "border-[#1f7a3c]",
    text: "text-[#22c55e]",
    label: "BUY",
    icon: "trending_up",
  },
  HOLD: {
    bg: "bg-gradient-to-r from-[#1a1d22] to-[#161A1F]",
    border: "border-[#3a3f48]",
    text: "text-[#cbd0dc]",
    label: "HOLD",
    icon: "horizontal_rule",
  },
  SELL: {
    bg: "bg-gradient-to-r from-[#2a0e0e] to-[#1f0a0a]",
    border: "border-[#7a1f1f]",
    text: "text-[#f87171]",
    label: "SELL",
    icon: "trending_down",
  },
  UNKNOWN: {
    bg: "bg-[#161A1F]",
    border: "border-[#2B2F36]",
    text: "text-[#a8acc0]",
    label: "UNKNOWN",
    icon: "help",
  },
};

function Module({
  title,
  romanNumeral,
  count,
  defaultOpen = true,
  children,
}: {
  title: string;
  romanNumeral: string;
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="rounded border border-[#2B2F36] bg-[#0f1318]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-[#161A1F]"
      >
        <div className="flex items-center gap-2">
          <span className="rounded bg-[#1e232b] px-1.5 py-0.5 font-mono text-[11px] text-[#8d90a2]">
            {romanNumeral}
          </span>
          <span className="text-[13px] font-semibold text-white">{title}</span>
          {count != null && (
            <span className="text-[11px] text-[#8d90a2]">· {count} 段</span>
          )}
        </div>
        <span className="material-symbols-outlined text-[18px] text-[#8d90a2]">
          {open ? "expand_less" : "expand_more"}
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-[#2B2F36] px-3 py-3">
          {children}
        </div>
      )}
    </section>
  );
}

function SubCard({
  title,
  content,
  defaultOpen = true,
}: {
  title: string;
  content?: string | null;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!content || !content.trim()) return null;
  return (
    <div className="rounded border border-[#2B2F36] bg-[#161A1F]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-[#1a1f26]"
      >
        <span className="text-[12px] font-semibold uppercase tracking-wide text-[#a8acc0]">
          {title}
        </span>
        <span className="material-symbols-outlined text-[16px] text-[#8d90a2]">
          {open ? "expand_less" : "expand_more"}
        </span>
      </button>
      {open && (
        <div className="border-t border-[#1e232b] px-3 py-2">
          <Md text={content} />
        </div>
      )}
    </div>
  );
}

function countSections(obj: Record<string, string | null | undefined>): number {
  return Object.values(obj).filter((v) => v && v.trim()).length;
}

export function ReportView({ report }: { report: TaReportDetail }) {
  const decisionStyle = DECISION_STYLES[report.decision] ?? DECISION_STYLES.UNKNOWN;
  const { sections } = report;

  return (
    <div className="space-y-3">
      <div
        className={`rounded border ${decisionStyle.border} ${decisionStyle.bg} px-4 py-3`}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className={`material-symbols-outlined ${decisionStyle.text} text-[32px]`}
            >
              {decisionStyle.icon}
            </span>
            <div>
              <div className="font-mono text-[11px] uppercase tracking-widest text-[#8d90a2]">
                Portfolio Decision · {report.ticker}
              </div>
              <div
                className={`text-[26px] font-bold leading-tight ${decisionStyle.text}`}
              >
                {decisionStyle.label}
              </div>
            </div>
          </div>
          <div className="text-right font-mono text-[11px] text-[#8d90a2]">
            <div>{report.report_id}</div>
            <div>{report.generated_at.replace("T", " ").slice(0, 19)}</div>
          </div>
        </div>
        {report.decision_summary && (
          <div className="mt-2 border-t border-[#2B2F36] pt-2 text-[12px] leading-relaxed text-[#d4d6e0]">
            {report.decision_summary}
          </div>
        )}
      </div>

      <Module
        title="Analyst Team Reports"
        romanNumeral="I"
        count={countSections(sections.analysts)}
        defaultOpen={true}
      >
        <SubCard title="Market Analyst" content={sections.analysts.market} />
        <SubCard title="Social Media Analyst" content={sections.analysts.social} />
        <SubCard title="News Analyst" content={sections.analysts.news} />
        <SubCard
          title="Fundamentals Analyst"
          content={sections.analysts.fundamentals}
        />
        {countSections(sections.analysts) === 0 && (
          <div className="text-[12px] text-[#8d90a2]">本次未启用任何分析师</div>
        )}
      </Module>

      <Module
        title="Research Team Decision"
        romanNumeral="II"
        count={countSections(sections.research)}
        defaultOpen={false}
      >
        <SubCard title="Bull Researcher" content={sections.research.bull} />
        <SubCard title="Bear Researcher" content={sections.research.bear} />
        <SubCard title="Research Manager" content={sections.research.manager} />
      </Module>

      <Module
        title="Trading Team Plan"
        romanNumeral="III"
        count={countSections(sections.trading)}
        defaultOpen={false}
      >
        <SubCard title="Trader" content={sections.trading.trader} />
      </Module>

      <Module
        title="Risk Management Team Decision"
        romanNumeral="IV"
        count={countSections(sections.risk)}
        defaultOpen={false}
      >
        <SubCard title="Aggressive Analyst" content={sections.risk.aggressive} />
        <SubCard
          title="Conservative Analyst"
          content={sections.risk.conservative}
        />
        <SubCard title="Neutral Analyst" content={sections.risk.neutral} />
      </Module>

      <Module
        title="Portfolio Manager Decision"
        romanNumeral="V"
        count={countSections(sections.portfolio)}
        defaultOpen={true}
      >
        <SubCard
          title="Portfolio Manager"
          content={sections.portfolio.decision}
        />
      </Module>
    </div>
  );
}
