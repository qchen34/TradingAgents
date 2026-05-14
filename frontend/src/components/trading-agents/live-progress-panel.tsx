"use client";

import { useEffect, useRef } from "react";
import type { TaAgentStatus, TaJob } from "@/lib/api";
import { Md } from "./markdown";

const TEAMS: Array<{ name: string; agents: string[] }> = [
  {
    name: "Analyst Team",
    agents: [
      "Market Analyst",
      "Social Analyst",
      "News Analyst",
      "Fundamentals Analyst",
    ],
  },
  { name: "Research Team", agents: ["Bull Researcher", "Bear Researcher", "Research Manager"] },
  { name: "Trading Team", agents: ["Trader"] },
  {
    name: "Risk Management",
    agents: ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
  },
  { name: "Portfolio Management", agents: ["Portfolio Manager"] },
];

const SECTION_TITLES: Record<string, string> = {
  market_report: "Market Analysis",
  sentiment_report: "Social Sentiment",
  news_report: "News Analysis",
  fundamentals_report: "Fundamentals Analysis",
  investment_plan: "Research Team Decision",
  trader_investment_plan: "Trading Team Plan",
  final_trade_decision: "Portfolio Management Decision",
};

function fmtMmSs(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const mm = Math.floor(s / 60)
    .toString()
    .padStart(2, "0");
  const ss = (s % 60).toString().padStart(2, "0");
  return `${mm}:${ss}`;
}

function fmtTokens(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

const STATUS_STYLE: Record<TaAgentStatus, { dot: string; text: string; label: string }> = {
  pending: { dot: "bg-[#3a4055]", text: "text-[#8d90a2]", label: "pending" },
  in_progress: { dot: "bg-[#fbbf24] animate-pulse", text: "text-[#fbbf24]", label: "in_progress" },
  completed: { dot: "bg-[#22c55e]", text: "text-[#22c55e]", label: "completed" },
  error: { dot: "bg-[#f87171]", text: "text-[#f87171]", label: "error" },
};

const MSG_TYPE_STYLE: Record<string, string> = {
  Agent: "text-[#a3e635]",
  Tool: "text-[#60a5fa]",
  Data: "text-[#60a5fa]",
  User: "text-[#cbd0dc]",
  System: "text-[#8d90a2]",
  Control: "text-[#8d90a2]",
};

function AgentRow({
  agent,
  status,
  isCurrent,
}: {
  agent: string;
  status: TaAgentStatus;
  isCurrent: boolean;
}) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.pending;
  return (
    <div
      className={`flex items-center justify-between rounded px-2 py-1 text-[12px] ${
        isCurrent ? "bg-[#0c1e3a]" : ""
      }`}
    >
      <div className="flex items-center gap-2 truncate">
        <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
        <span
          className={`truncate ${
            isCurrent ? "font-semibold text-white" : "text-[#d4d6e0]"
          }`}
        >
          {agent}
        </span>
      </div>
      <span className={`font-mono text-[10px] uppercase tracking-wide ${s.text}`}>
        {s.label}
      </span>
    </div>
  );
}

export function LiveProgressPanel({ job }: { job: TaJob }) {
  const messagesRef = useRef<HTMLDivElement>(null);

  // Auto-scroll messages to bottom on new messages
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [job.messages.length, job.tool_calls.length]);

  const isFailed = job.status === "failed";
  const isDone = job.status === "completed";
  const isRunning = job.status === "queued" || job.status === "running";

  const currentSection = job.current_section;
  const currentSectionContent =
    currentSection && job.report_sections[currentSection]
      ? job.report_sections[currentSection]
      : null;
  const currentSectionTitle =
    (currentSection && SECTION_TITLES[currentSection]) ||
    (currentSection ?? "Waiting for analyst output");

  return (
    <div className="space-y-3">
      <div className="rounded border border-[#2B2F36] bg-[#0f1318] px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className={`material-symbols-outlined text-[24px] ${
                isFailed
                  ? "text-[#f87171]"
                  : isDone
                    ? "text-[#22c55e]"
                    : "text-[#fbbf24] animate-pulse"
              }`}
            >
              {isFailed ? "error" : isDone ? "check_circle" : "progress_activity"}
            </span>
            <div>
              <div className="text-[13px] font-semibold text-white">
                {isFailed
                  ? "Analysis Failed"
                  : isDone
                    ? "Analysis Completed"
                    : `Running ${job.current_agent ?? "TradingAgents"}`}
              </div>
              <div className="font-mono text-[11px] text-[#8d90a2]">
                {job.ticker} · {job.analysis_date} · {job.job_id.slice(0, 8)}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-[22px] font-semibold text-white">
              {fmtMmSs(job.elapsed_seconds)}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#8d90a2]">
              elapsed
            </div>
          </div>
        </div>

        {/* Footer stats */}
        <div className="mt-3 grid grid-cols-2 gap-2 border-t border-[#2B2F36] pt-2 text-[11px] sm:grid-cols-4">
          <Stat
            label="Agents"
            value={`${job.stats.agents_completed}/${job.stats.agents_total}`}
          />
          <Stat
            label="Reports"
            value={`${job.stats.reports_completed}/${job.stats.reports_total}`}
          />
          <Stat label="LLM" value={String(job.stats.llm_calls)} />
          <Stat label="Tools" value={String(job.stats.tool_calls)} />
          <Stat
            label="Tokens In"
            value={fmtTokens(job.stats.tokens_in)}
            valueClass="text-[#60a5fa]"
          />
          <Stat
            label="Tokens Out"
            value={fmtTokens(job.stats.tokens_out)}
            valueClass="text-[#a3e635]"
          />
          <Stat
            label="Stage"
            value={job.progress || "—"}
            valueClass="font-mono text-[10px]"
          />
          <Stat
            label="Current"
            value={job.current_agent ?? "—"}
            valueClass="text-[#fbbf24]"
          />
        </div>

        {isFailed && job.error && (
          <div className="mt-3 rounded border border-[#7a1f1f] bg-[#2a0e0e] px-3 py-2 text-[12px] text-[#f87171]">
            {job.error}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[280px_minmax(0,1fr)]">
        {/* Left: Agent progress + Messages */}
        <div className="space-y-3">
          <section className="rounded border border-[#2B2F36] bg-[#0f1318]">
            <header className="border-b border-[#2B2F36] px-3 py-2 text-[11px] font-semibold uppercase tracking-widest text-[#a8acc0]">
              Progress
            </header>
            <div className="space-y-2 p-2">
              {TEAMS.map((team) => {
                const activeAgents = team.agents.filter(
                  (a) => a in job.agent_statuses,
                );
                if (activeAgents.length === 0) return null;
                return (
                  <div key={team.name}>
                    <div className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-[#5E6673]">
                      {team.name}
                    </div>
                    <div className="space-y-0.5">
                      {activeAgents.map((a) => (
                        <AgentRow
                          key={a}
                          agent={a}
                          status={job.agent_statuses[a] ?? "pending"}
                          isCurrent={a === job.current_agent && isRunning}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        {/* Right: Messages stream + Current report */}
        <div className="space-y-3">
          <section className="rounded border border-[#2B2F36] bg-[#0f1318]">
            <header className="flex items-center justify-between border-b border-[#2B2F36] px-3 py-2 text-[11px] font-semibold uppercase tracking-widest text-[#a8acc0]">
              <span>Messages &amp; Tools</span>
              <span className="font-mono text-[10px] text-[#5E6673]">
                {job.messages.length} msg · {job.tool_calls.length} tool
              </span>
            </header>
            <div
              ref={messagesRef}
              className="max-h-[220px] space-y-1 overflow-y-auto p-2 text-[11px]"
            >
              {job.messages.length === 0 && job.tool_calls.length === 0 && (
                <div className="px-2 py-1 text-[#5E6673]">
                  Waiting for agent activity…
                </div>
              )}
              {(() => {
                const all: Array<
                  | { kind: "msg"; ts: string; type: string; content: string }
                  | { kind: "tool"; ts: string; name: string; args: string }
                > = [
                  ...job.messages.map((m) => ({
                    kind: "msg" as const,
                    ts: m.timestamp,
                    type: m.type,
                    content: m.content,
                  })),
                  ...job.tool_calls.map((t) => ({
                    kind: "tool" as const,
                    ts: t.timestamp,
                    name: t.tool_name,
                    args: t.args_preview,
                  })),
                ].sort((a, b) => a.ts.localeCompare(b.ts));
                return all.map((row, idx) => {
                  if (row.kind === "tool") {
                    return (
                      <div key={idx} className="flex gap-2 px-2 py-0.5">
                        <span className="shrink-0 font-mono text-[10px] text-[#5E6673]">
                          {row.ts}
                        </span>
                        <span className="shrink-0 rounded bg-[#1e232b] px-1 text-[10px] uppercase tracking-wide text-[#60a5fa]">
                          Tool
                        </span>
                        <span className="truncate text-[#a8acc0]">
                          <span className="font-mono text-[#cbd0dc]">{row.name}</span>
                          <span className="text-[#5E6673]"> · {row.args}</span>
                        </span>
                      </div>
                    );
                  }
                  return (
                    <div key={idx} className="flex gap-2 px-2 py-0.5">
                      <span className="shrink-0 font-mono text-[10px] text-[#5E6673]">
                        {row.ts}
                      </span>
                      <span
                        className={`shrink-0 rounded bg-[#1e232b] px-1 text-[10px] uppercase tracking-wide ${
                          MSG_TYPE_STYLE[row.type] ?? "text-[#cbd0dc]"
                        }`}
                      >
                        {row.type}
                      </span>
                      <span className="break-words text-[#d4d6e0]">{row.content}</span>
                    </div>
                  );
                });
              })()}
            </div>
          </section>

          <section className="rounded border border-[#2B2F36] bg-[#0f1318]">
            <header className="border-b border-[#2B2F36] px-3 py-2 text-[11px] font-semibold uppercase tracking-widest text-[#a8acc0]">
              Current Report · {currentSectionTitle}
            </header>
            <div className="max-h-[420px] overflow-y-auto p-3">
              {currentSectionContent ? (
                <Md text={currentSectionContent} />
              ) : (
                <div className="text-[12px] italic text-[#5E6673]">
                  Waiting for analysis report…
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  valueClass = "text-white",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex flex-col">
      <span className="font-mono text-[9px] uppercase tracking-widest text-[#5E6673]">
        {label}
      </span>
      <span className={`truncate text-[13px] font-semibold ${valueClass}`} title={value}>
        {value}
      </span>
    </div>
  );
}
