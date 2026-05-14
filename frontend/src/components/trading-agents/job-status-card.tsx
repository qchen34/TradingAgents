"use client";

import type { TaJob } from "@/lib/api";

function fmtMmSs(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const mm = Math.floor(s / 60).toString().padStart(2, "0");
  const ss = (s % 60).toString().padStart(2, "0");
  return `${mm}:${ss}`;
}

const STAGES = [
  { key: "init", label: "Initializing", match: /init/i },
  { key: "graph", label: "Running multi-agent graph", match: /running/i },
  { key: "done", label: "Completed", match: /complete/i },
];

export function JobStatusCard({ job }: { job: TaJob }) {
  const isRunning = job.status === "queued" || job.status === "running";
  const isFailed = job.status === "failed";
  const isDone = job.status === "completed";

  const stageIdx = STAGES.findIndex((s) => s.match.test(job.progress));

  return (
    <div className="rounded border border-[#2B2F36] bg-[#0f1318] p-3">
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
                  : "Running TradingAgents"}
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

      {isRunning && (
        <div className="mt-3 flex items-center gap-1.5">
          {STAGES.map((s, idx) => {
            const reached = idx <= Math.max(stageIdx, 0);
            return (
              <div
                key={s.key}
                className={`h-1 flex-1 rounded ${
                  reached ? "bg-[#2962FF]" : "bg-[#2B2F36]"
                }`}
                title={s.label}
              />
            );
          })}
        </div>
      )}

      {job.progress && (
        <div className="mt-2 text-[11px] text-[#a8acc0]">
          <span className="text-[#5E6673]">stage:</span> {job.progress}
        </div>
      )}

      {isFailed && job.error && (
        <div className="mt-2 rounded border border-[#7a1f1f] bg-[#2a0e0e] px-3 py-2 text-[12px] text-[#f87171]">
          {job.error}
        </div>
      )}
    </div>
  );
}
