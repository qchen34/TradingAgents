"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getTaOptions,
  getTaJob,
  getTaReport,
  listTaReports,
  runTradingAgents,
  type TaJob,
  type TaOptions,
  type TaReportDetail,
  type TaReportMeta,
  type TaRunPayload,
} from "@/lib/api";
import { ReportView } from "@/components/trading-agents/report-view";
import { RunForm } from "@/components/trading-agents/run-form";
import { LiveProgressPanel } from "@/components/trading-agents/live-progress-panel";
import { HistoryList } from "@/components/trading-agents/history-list";

type TabKey = "run" | "history";

export default function TradingAgentsPage() {
  const [tab, setTab] = useState<TabKey>("run");
  const [options, setOptions] = useState<TaOptions | null>(null);
  const [optionsErr, setOptionsErr] = useState<string | null>(null);

  const [activeJob, setActiveJob] = useState<TaJob | null>(null);
  const [runReport, setRunReport] = useState<TaReportDetail | null>(null);
  const [runErr, setRunErr] = useState<string | null>(null);

  const [history, setHistory] = useState<TaReportMeta[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyErr, setHistoryErr] = useState<string | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [historyReport, setHistoryReport] = useState<TaReportDetail | null>(null);
  const [historyReportLoading, setHistoryReportLoading] = useState(false);
  const [historyReportErr, setHistoryReportErr] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getTaOptions()
      .then(setOptions)
      .catch((err) => setOptionsErr(String(err)));
  }, []);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryErr(null);
    try {
      const { reports } = await listTaReports();
      setHistory(reports);
    } catch (err) {
      setHistoryErr(String(err));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "history" && history.length === 0 && !historyLoading) {
      loadHistory();
    }
  }, [tab, history.length, historyLoading, loadHistory]);

  const stopPoll = useCallback(() => {
    if (pollRef.current != null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPoll, [stopPoll]);

  const startPoll = useCallback(
    (jobId: string) => {
      stopPoll();
      pollRef.current = setInterval(async () => {
        try {
          const job = await getTaJob(jobId);
          setActiveJob(job);
          if (job.status === "completed" || job.status === "failed") {
            stopPoll();
            if (job.status === "completed" && job.report_id) {
              try {
                const detail = await getTaReport(job.report_id);
                setRunReport(detail);
                loadHistory();
              } catch (err) {
                setRunErr(String(err));
              }
            }
          }
        } catch (err) {
          setRunErr(String(err));
          stopPoll();
        }
      }, 1500);
    },
    [stopPoll, loadHistory],
  );

  const handleSubmit = useCallback(
    async (payload: TaRunPayload) => {
      setRunErr(null);
      setRunReport(null);
      try {
        const job = await runTradingAgents(payload);
        setActiveJob(job);
        startPoll(job.job_id);
      } catch (err) {
        setRunErr(String(err));
      }
    },
    [startPoll],
  );

  const selectHistory = useCallback(async (reportId: string) => {
    setSelectedReportId(reportId);
    setHistoryReportLoading(true);
    setHistoryReportErr(null);
    setHistoryReport(null);
    try {
      const detail = await getTaReport(reportId);
      setHistoryReport(detail);
    } catch (err) {
      setHistoryReportErr(String(err));
    } finally {
      setHistoryReportLoading(false);
    }
  }, []);

  const submitting =
    activeJob?.status === "queued" || activeJob?.status === "running";

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#0B0E11]">
      <div className="flex items-center justify-between border-b border-[#2B2F36] px-3 py-2">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-[20px] text-[#cbd0dc]">
            psychology
          </span>
          <span className="text-[14px] font-semibold uppercase tracking-wide text-white">
            TradingAgents
          </span>
          <span className="hidden text-[11px] text-[#8d90a2] md:inline">
            多 Agent LLM 金融交易分析框架
          </span>
        </div>
        <div className="flex items-center gap-1">
          <TabButton
            active={tab === "run"}
            onClick={() => setTab("run")}
            icon="play_circle"
            label="运行分析"
          />
          <TabButton
            active={tab === "history"}
            onClick={() => setTab("history")}
            icon="history"
            label="历史报告"
          />
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {tab === "run" ? (
          <RunTab
            options={options}
            optionsErr={optionsErr}
            activeJob={activeJob}
            submitting={!!submitting}
            runReport={runReport}
            runErr={runErr}
            onSubmit={handleSubmit}
          />
        ) : (
          <HistoryTab
            history={history}
            loading={historyLoading}
            err={historyErr}
            selectedId={selectedReportId}
            report={historyReport}
            reportLoading={historyReportLoading}
            reportErr={historyReportErr}
            onSelect={selectHistory}
            onReload={loadHistory}
          />
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: string;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1 rounded px-3 py-1 text-[12px] transition ${
        active
          ? "bg-[#2962FF] text-white"
          : "text-[#8d90a2] hover:bg-[#1e232b] hover:text-white"
      }`}
    >
      <span className="material-symbols-outlined text-[14px]">{icon}</span>
      {label}
    </button>
  );
}

function RunTab({
  options,
  optionsErr,
  activeJob,
  submitting,
  runReport,
  runErr,
  onSubmit,
}: {
  options: TaOptions | null;
  optionsErr: string | null;
  activeJob: TaJob | null;
  submitting: boolean;
  runReport: TaReportDetail | null;
  runErr: string | null;
  onSubmit: (p: TaRunPayload) => void;
}) {
  return (
    <div className="flex h-full overflow-hidden">
      <aside className="w-[340px] shrink-0 overflow-y-auto border-r border-[#2B2F36] p-3">
        <div className="mb-2 text-[11px] uppercase tracking-widest text-[#5E6673]">
          analysis configuration
        </div>
        {optionsErr && (
          <div className="rounded border border-[#7a1f1f] bg-[#2a0e0e] px-3 py-2 text-[12px] text-[#f87171]">
            {optionsErr}
          </div>
        )}
        {!options && !optionsErr && (
          <div className="text-[12px] text-[#8d90a2]">加载选项中…</div>
        )}
        {options && (
          <RunForm options={options} disabled={submitting} onSubmit={onSubmit} />
        )}
      </aside>
      <main className="flex-1 overflow-y-auto p-3">
        {!activeJob && !runReport && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <span className="material-symbols-outlined text-[48px] text-[#3a4055]">
                rocket_launch
              </span>
              <div className="mt-2 text-[13px] text-[#8d90a2]">
                填写左侧表单并点击 Run Analysis 开始一次新分析。
              </div>
              <div className="mt-1 text-[11px] text-[#5E6673]">
                完整流程包括 Analyst → Research → Trader → Risk → Portfolio 五大阶段。
              </div>
            </div>
          </div>
        )}

        {activeJob && !runReport && (
          <div className="mb-3">
            <LiveProgressPanel job={activeJob} />
          </div>
        )}

        {runErr && (
          <div className="mb-3 rounded border border-[#7a1f1f] bg-[#2a0e0e] px-3 py-2 text-[12px] text-[#f87171]">
            {runErr}
          </div>
        )}

        {runReport && <ReportView report={runReport} />}
      </main>
    </div>
  );
}

function HistoryTab({
  history,
  loading,
  err,
  selectedId,
  report,
  reportLoading,
  reportErr,
  onSelect,
  onReload,
}: {
  history: TaReportMeta[];
  loading: boolean;
  err: string | null;
  selectedId: string | null;
  report: TaReportDetail | null;
  reportLoading: boolean;
  reportErr: string | null;
  onSelect: (id: string) => void;
  onReload: () => void;
}) {
  return (
    <div className="flex h-full overflow-hidden">
      <aside className="w-[320px] shrink-0 overflow-y-auto border-r border-[#2B2F36] p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-[11px] uppercase tracking-widest text-[#5E6673]">
            local reports/
          </div>
          <button
            type="button"
            onClick={onReload}
            className="flex items-center gap-1 rounded border border-[#2B2F36] px-1.5 py-0.5 text-[11px] text-[#a8acc0] hover:border-[#3a4055] hover:text-white"
          >
            <span className="material-symbols-outlined text-[12px]">refresh</span>
            刷新
          </button>
        </div>
        {err && (
          <div className="mb-2 rounded border border-[#7a1f1f] bg-[#2a0e0e] px-3 py-2 text-[12px] text-[#f87171]">
            {err}
          </div>
        )}
        <HistoryList
          items={history}
          activeId={selectedId}
          loading={loading}
          onSelect={onSelect}
        />
      </aside>
      <main className="flex-1 overflow-y-auto p-3">
        {!selectedId && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <span className="material-symbols-outlined text-[48px] text-[#3a4055]">
                folder_open
              </span>
              <div className="mt-2 text-[13px] text-[#8d90a2]">
                请选择左侧任一历史报告查看详情。
              </div>
            </div>
          </div>
        )}
        {selectedId && reportLoading && (
          <div className="text-[12px] text-[#8d90a2]">加载报告中…</div>
        )}
        {selectedId && reportErr && (
          <div className="rounded border border-[#7a1f1f] bg-[#2a0e0e] px-3 py-2 text-[12px] text-[#f87171]">
            {reportErr}
          </div>
        )}
        {report && <ReportView report={report} />}
      </main>
    </div>
  );
}
