"use client";

import { useEffect, useState } from "react";
import { createBacktestJob, getBacktestJob, getBacktestPeriods } from "@/lib/api";

type PeriodItem = { key: string; label: string };

export default function BacktestingPage() {
  const [periods, setPeriods] = useState<PeriodItem[]>([]);
  const [periodKey, setPeriodKey] = useState("2y");
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getBacktestPeriods().then((res) => {
      setPeriods(res);
      if (res.length > 0) setPeriodKey(res[0].key);
    });
  }, []);

  async function runBacktest() {
    setError("");
    setResult(null);
    const job = await createBacktestJob(periodKey);
    setJobId(job.job_id);
    setStatus(job.status);
  }

  async function refreshJob() {
    if (!jobId) return;
    const job = await getBacktestJob(jobId);
    setStatus(job.status);
    setResult(job.result ?? null);
    setError(job.error ?? "");
  }

  return (
    <div>
      <h1>回测执行终端</h1>
      <div className="card">
        <div className="metric-label">回测周期</div>
        <select value={periodKey} onChange={(e) => setPeriodKey(e.target.value)}>
          {periods.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
            </option>
          ))}
        </select>
        <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
          <button onClick={runBacktest}>启动回测任务</button>
          <button onClick={refreshJob} disabled={!jobId}>
            刷新状态
          </button>
        </div>
      </div>

      <div className="card">
        <h3 className="panel-title">任务状态面板</h3>
        <div className="mono-block">
          {`job_id: ${jobId || "-"}
status: ${status || "-"}
error: ${error || "none"}`}
        </div>
        {error && <div>错误：{error}</div>}
      </div>

      {result !== null && (
        <div className="card">
          <h3 className="panel-title">结果快照</h3>
          <div className="mono-block">{JSON.stringify(result, null, 2)}</div>
        </div>
      )}
    </div>
  );
}

