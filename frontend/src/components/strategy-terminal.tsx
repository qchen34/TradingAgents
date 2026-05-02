"use client";

import { useEffect, useState } from "react";
import {
  askLrs,
  createBacktestJob,
  evaluateWheel,
  getBacktestJob,
  getBacktestPeriods,
  getStrategyMetadata,
  getWheelProfiles,
  WheelEvaluation,
  WheelProfile,
} from "@/lib/api";
import { useUiStore } from "@/store/uiStore";

type LrsMainTab = "doc" | "dashboard" | "backtest";
type LrsDashTab = "macro" | "base" | "validation" | "risk" | "exec";
type WheelTab = "aggressive" | "neutral" | "conservative" | "history";

const LRS_DASH_TABS: Array<{ id: LrsDashTab; label: string }> = [
  { id: "macro", label: "1) 宏观经济分析（优先）" },
  { id: "base", label: "2) 基础信号" },
  { id: "validation", label: "3) 入场模式判断" },
  { id: "risk", label: "4) 风控层（资金分配）" },
  { id: "exec", label: "5) 执行层（下单）" },
];

const WHEEL_TABS: Array<{ id: WheelTab; label: string }> = [
  { id: "aggressive", label: "激进" },
  { id: "neutral", label: "中性" },
  { id: "conservative", label: "保守" },
  { id: "history", label: "历史报告" },
];

export function StrategyTerminal({ initialSub }: { initialSub: "LRS TQQQ策略" | "Wheel策略" }) {
  const [docMd, setDocMd] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [askBusy, setAskBusy] = useState(false);
  const [lrsTab, setLrsTab] = useState<LrsMainTab>("doc");
  const [lrsDashTab, setLrsDashTab] = useState<LrsDashTab>("macro");
  const [wheelTab, setWheelTab] = useState<WheelTab>("aggressive");
  const [subOptions, setSubOptions] = useState<string[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [metaErr, setMetaErr] = useState("");
  const [periods, setPeriods] = useState<Array<{ key: string; label: string }>>([]);
  const [periodKey, setPeriodKey] = useState("2y");
  const [jobId, setJobId] = useState("");
  const [jobStatus, setJobStatus] = useState("-");
  const [jobError, setJobError] = useState("");
  const [jobResult, setJobResult] = useState<string>("");
  const [runBusy, setRunBusy] = useState(false);
  const [wheelProfiles, setWheelProfiles] = useState<WheelProfile[]>([]);
  const [wheelUnderlying, setWheelUnderlying] = useState("TQQQ");
  const [wheelSignal, setWheelSignal] = useState("QQQ");
  const [wheelBusy, setWheelBusy] = useState(false);
  const [wheelError, setWheelError] = useState("");
  const [wheelEval, setWheelEval] = useState<WheelEvaluation | null>(null);

  const strategySubMenu = initialSub;
  const strategySubMenuFromStore = useUiStore((s) => s.strategySubMenu);
  const setStrategySubMenu = useUiStore((s) => s.setStrategySubMenu);

  useEffect(() => {
    Promise.all([getStrategyMetadata(), getBacktestPeriods(), getWheelProfiles()])
      .then(([meta, p, wp]) => {
        setSubOptions(meta.sub_strategies);
        setDocMd(meta.lrs_doc_md);
        setPeriods(p);
        setWheelProfiles(wp);
        if (p.length > 0) setPeriodKey(p[0].key);
      })
      .catch((e) => setMetaErr(String(e)))
      .finally(() => setLoadingMeta(false));
  }, []);

  useEffect(() => {
    if (strategySubMenuFromStore !== strategySubMenu) {
      setStrategySubMenu(strategySubMenu);
    }
  }, [setStrategySubMenu, strategySubMenu, strategySubMenuFromStore]);

  async function onAsk() {
    if (!question.trim()) return;
    setAskBusy(true);
    try {
      const res = await askLrs(question.trim());
      setAnswer(res.answer);
    } catch (e) {
      setAnswer(`请求失败：${String(e)}`);
    } finally {
      setAskBusy(false);
    }
  }

  async function onRunBacktest() {
    setRunBusy(true);
    setJobError("");
    setJobResult("");
    try {
      const job = await createBacktestJob(periodKey);
      setJobId(job.job_id);
      setJobStatus(job.status);
    } catch (e) {
      setJobError(String(e));
    } finally {
      setRunBusy(false);
    }
  }

  async function onRefreshJob() {
    if (!jobId) return;
    try {
      const job = await getBacktestJob(jobId);
      setJobStatus(job.status);
      setJobError(job.error ?? "");
      setJobResult(job.result ? JSON.stringify(job.result, null, 2) : "");
    } catch (e) {
      setJobError(String(e));
    }
  }

  async function onEvaluateWheel(styleKey: "aggressive" | "neutral" | "conservative") {
    setWheelBusy(true);
    setWheelError("");
    try {
      const res = await evaluateWheel({
        style_key: styleKey,
        underlying_ticker: wheelUnderlying.trim().toUpperCase(),
        signal_ticker: wheelSignal.trim().toUpperCase(),
      });
      setWheelEval(res);
    } catch (e) {
      setWheelError(String(e));
    } finally {
      setWheelBusy(false);
    }
  }

  const isWheel = strategySubMenu === "Wheel策略";
  const activeWheelStyle =
    wheelTab === "aggressive" || wheelTab === "neutral" || wheelTab === "conservative" ? wheelTab : "neutral";

  const tabClass = (active: boolean) =>
    `rounded-lg px-3 py-2 text-xs font-semibold ${
      active
        ? "border border-blue-500/60 bg-blue-600 text-blue-50"
        : "border border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-600"
    }`;

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="m-0 text-xl font-semibold tracking-tight text-slate-100">策略</h1>
            <p className="mt-1 text-xs text-slate-400">当前子策略：{strategySubMenu}</p>
          </div>
          <span className="inline-flex rounded-full border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] text-slate-300">
            ACTIVE: {strategySubMenu}
          </span>
        </div>
      </section>

      {loadingMeta && <p className="text-sm text-slate-400">正在加载策略配置...</p>}
      {metaErr && <p className="text-sm text-rose-400">策略数据加载失败：{metaErr}</p>}

      {!loadingMeta && !isWheel && (
        <>
          <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
            <div className="flex flex-wrap gap-2">
              <button className={tabClass(lrsTab === "doc")} onClick={() => setLrsTab("doc")} type="button">
                策略文档
              </button>
              <button className={tabClass(lrsTab === "dashboard")} onClick={() => setLrsTab("dashboard")} type="button">
                策略仪表盘
              </button>
              <button className={tabClass(lrsTab === "backtest")} onClick={() => setLrsTab("backtest")} type="button">
                策略回测
              </button>
            </div>
          </section>

          {lrsTab === "doc" && (
            <section className="grid grid-cols-1 gap-3 xl:grid-cols-[1.45fr_1fr]">
              <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                <h3 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">LRS 策略文档</h3>
                <div className="rounded-lg border border-blue-900/60 bg-slate-950 p-3">
                  <div className="whitespace-pre-wrap text-sm leading-7 text-slate-200">{docMd || "暂无文档内容"}</div>
                </div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                <h3 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">LRS 策略问答（LLM）</h3>
                <textarea
                  rows={5}
                  className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="输入你的策略问题..."
                />
                <div className="mt-2">
                  <button
                    onClick={onAsk}
                    disabled={askBusy}
                    className="inline-flex items-center rounded-lg border border-blue-500/60 bg-blue-600 px-3 py-2 text-xs font-semibold text-blue-50 hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {askBusy ? "生成中..." : "发送指令"}
                  </button>
                </div>
                <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <pre className="whitespace-pre-wrap font-mono text-xs leading-6 text-slate-300">
                    {answer || "[assistant] 等待提问..."}
                  </pre>
                </div>
              </div>
            </section>
          )}

          {lrsTab === "dashboard" && (
            <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <h3 className="text-sm font-semibold tracking-wide text-slate-100">LRS TQQQ 策略仪表盘</h3>
              <p className="mt-1 text-xs text-slate-400">基于“当日开仓决策”框架。当前采用子 Tab 架构，优先展示宏观层。</p>
              <div className="mt-3 grid grid-cols-2 gap-2 xl:grid-cols-4">
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  <p className="text-xs text-slate-400">策略模式</p>
                  <p className="mt-1 font-mono text-lg text-slate-100">LRS</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  <p className="text-xs text-slate-400">标的</p>
                  <p className="mt-1 font-mono text-lg text-slate-100">TQQQ</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  <p className="text-xs text-slate-400">决策状态</p>
                  <p className="mt-1 font-mono text-lg text-slate-100">待运行</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  <p className="text-xs text-slate-400">建议仓位</p>
                  <p className="mt-1 font-mono text-lg text-slate-100">N/A</p>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {LRS_DASH_TABS.map((t) => (
                  <button
                    key={t.id}
                    className={tabClass(lrsDashTab === t.id)}
                    onClick={() => setLrsDashTab(t.id)}
                    type="button"
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
                <pre className="whitespace-pre-wrap font-mono text-xs leading-6 text-slate-300">
                  {`[${lrsDashTab}] 该子模块已保留原 Streamlit 结构入口。
下一步可继续将 ${lrsDashTab} 的 Python 逻辑逐步 API 化并映射到本区块。`}
                </pre>
              </div>
            </section>
          )}

          {lrsTab === "backtest" && (
            <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <h3 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">策略回测</h3>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs text-slate-400">回测周期</p>
                  <select
                    className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                    value={periodKey}
                    onChange={(e) => setPeriodKey(e.target.value)}
                  >
                    {periods.map((p) => (
                      <option key={p.key} value={p.key}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-end gap-2">
                  <button
                    onClick={onRunBacktest}
                    disabled={runBusy}
                    className="inline-flex items-center rounded-lg border border-blue-500/60 bg-blue-600 px-3 py-2 text-xs font-semibold text-blue-50 hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {runBusy ? "提交中..." : "启动任务"}
                  </button>
                  <button
                    onClick={onRefreshJob}
                    disabled={!jobId}
                    className="inline-flex items-center rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-slate-600 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    刷新状态
                  </button>
                </div>
              </div>
              <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
                <pre className="whitespace-pre-wrap font-mono text-xs leading-6 text-slate-300">
                  {`job_id: ${jobId || "-"}
status: ${jobStatus}
error: ${jobError || "none"}`}
                </pre>
              </div>
              {jobResult && (
                <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <pre className="whitespace-pre-wrap font-mono text-xs leading-6 text-slate-300">{jobResult}</pre>
                </div>
              )}
            </section>
          )}
        </>
      )}

      {!loadingMeta && isWheel && (
        <>
          <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
            <div className="flex flex-wrap gap-2">
              {WHEEL_TABS.map((t) => (
                <button key={t.id} className={tabClass(wheelTab === t.id)} onClick={() => setWheelTab(t.id)} type="button">
                  {t.label}
                </button>
              ))}
            </div>
          </section>

          {wheelTab !== "history" && (
            <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <h3 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">
                Wheel 策略 - {WHEEL_TABS.find((x) => x.id === wheelTab)?.label}
              </h3>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  <p className="mb-2 text-xs text-slate-400">配置</p>
                  <select
                    className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                    value={activeWheelStyle}
                    onChange={(e) => setWheelTab(e.target.value as WheelTab)}
                  >
                    {wheelProfiles.map((p) => (
                      <option key={p.key} value={p.key}>
                        {p.label} ({p.key})
                      </option>
                    ))}
                  </select>
                  <input
                    className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                    value={wheelUnderlying}
                    onChange={(e) => setWheelUnderlying(e.target.value)}
                    placeholder="标的 Ticker"
                  />
                  <input
                    className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                    value={wheelSignal}
                    onChange={(e) => setWheelSignal(e.target.value)}
                    placeholder="信号 Ticker"
                  />
                  <button
                    onClick={() => onEvaluateWheel(activeWheelStyle)}
                    disabled={wheelBusy}
                    className="mt-2 inline-flex items-center rounded-lg border border-blue-500/60 bg-blue-600 px-3 py-2 text-xs font-semibold text-blue-50 hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {wheelBusy ? "评估中..." : "生成执行建议"}
                  </button>
                  {wheelError && <p className="mt-2 text-xs text-rose-400">{wheelError}</p>}
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  <p className="mb-2 text-xs text-slate-400">信号</p>
                  <pre className="whitespace-pre-wrap font-mono text-xs leading-6 text-slate-300">
                    {wheelEval
                      ? `underlying=${wheelEval.signal.underlying_ticker} ${wheelEval.signal.underlying_price.toFixed(2)}
signal=${wheelEval.signal.signal_ticker} ${wheelEval.signal.signal_price.toFixed(2)}
RSI14=${wheelEval.signal.rsi14.toFixed(2)}
IVR_est=${wheelEval.signal.ivr_est.toFixed(2)}
regime=${wheelEval.signal.regime}
put_entry_ok=${wheelEval.signal.put_entry_ok}`
                      : "等待评估..."}
                  </pre>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  <p className="mb-2 text-xs text-slate-400">执行建议</p>
                  <pre className="whitespace-pre-wrap font-mono text-xs leading-6 text-slate-300">
                    {wheelEval
                      ? `action=${wheelEval.execution_hint.suggested_action}
put_strike=${wheelEval.execution_hint.put_strike_hint}
call_strike=${wheelEval.execution_hint.call_strike_hint}
dte=${wheelEval.execution_hint.dte_hint}
tp_put=${(wheelEval.execution_hint.take_profit.put * 100).toFixed(0)}%
tp_call=${(wheelEval.execution_hint.take_profit.call * 100).toFixed(0)}%`
                      : "等待评估..."}
                  </pre>
                </div>
              </div>
            </section>
          )}

          {wheelTab === "history" && (
            <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <h3 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">Wheel 历史报告</h3>
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                <pre className="whitespace-pre-wrap font-mono text-xs leading-6 text-slate-300">
                  {"历史报告入口已保留（对应 Streamlit 历史报告 tab）。下一步可接入历史报告 API。"}
                </pre>
              </div>
            </section>
          )}
        </>
      )}

      {subOptions.length > 0 && <p className="text-[11px] text-slate-500">可用子策略：{subOptions.join(" / ")}</p>}
    </div>
  );
}

