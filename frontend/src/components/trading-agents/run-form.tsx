"use client";

import { useEffect, useMemo, useState } from "react";
import type { TaOptions, TaRunPayload } from "@/lib/api";

const todayStr = (): string => {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
};

function Label({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div
      className="mb-1 text-[11px] font-medium uppercase tracking-wide text-[#a8acc0]"
      title={hint}
    >
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded border border-[#2B2F36] bg-[#0f1318] px-2 py-1.5 text-[13px] text-white outline-none focus:border-[#2962FF]";

export function RunForm({
  options,
  disabled,
  onSubmit,
}: {
  options: TaOptions;
  disabled?: boolean;
  onSubmit: (payload: TaRunPayload) => void;
}) {
  const defaults = options.defaults;
  const [ticker, setTicker] = useState("NVDA");
  const [date, setDate] = useState(todayStr());
  const [language, setLanguage] = useState(defaults.language);
  const [analysts, setAnalysts] = useState<string[]>(defaults.analysts);
  const [depth, setDepth] = useState<number>(defaults.depth);
  const [provider, setProvider] = useState(defaults.provider);
  const [shallow, setShallow] = useState("");
  const [deep, setDeep] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState(
    defaults.openai_reasoning_effort,
  );
  const [anthropicEffort, setAnthropicEffort] = useState(defaults.anthropic_effort);
  const [googleThinking, setGoogleThinking] = useState(
    defaults.google_thinking_level,
  );
  const [error, setError] = useState<string | null>(null);

  const providerInfo = useMemo(
    () => options.providers.find((p) => p.id === provider) ?? options.providers[0],
    [options.providers, provider],
  );
  const modelLists = options.models[provider];

  useEffect(() => {
    const ml = options.models[provider];
    if (!ml) return;
    if (ml.quick.length > 0) setShallow(ml.quick[0].value);
    if (ml.deep.length > 0) setDeep(ml.deep[0].value);
  }, [provider, options.models]);

  function toggleAnalyst(id: string) {
    setAnalysts((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  function submit() {
    setError(null);
    if (!ticker.trim()) {
      setError("请填写 ticker");
      return;
    }
    if (analysts.length === 0) {
      setError("至少选择一名分析师");
      return;
    }
    if (!shallow || !deep) {
      setError("请选择 Quick 与 Deep 模型");
      return;
    }
    const payload: TaRunPayload = {
      ticker: ticker.trim().toUpperCase(),
      analysis_date: date,
      analysts,
      research_depth: depth,
      llm_provider: provider,
      backend_url: providerInfo?.backend_url,
      shallow_thinker: shallow,
      deep_thinker: deep,
      output_language: language,
      openai_reasoning_effort:
        providerInfo?.thinking === "reasoning_effort" ? reasoningEffort : null,
      anthropic_effort:
        providerInfo?.thinking === "effort" ? anthropicEffort : null,
      google_thinking_level:
        providerInfo?.thinking === "thinking_level" ? googleThinking : null,
    };
    onSubmit(payload);
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <Label>Ticker</Label>
          <input
            className={inputCls}
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="NVDA / 0700.HK / 7203.T"
          />
        </div>
        <div>
          <Label>Analysis Date</Label>
          <input
            className={inputCls}
            type="date"
            value={date}
            max={todayStr()}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
      </div>

      <div>
        <Label>Output Language</Label>
        <select
          className={inputCls}
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          {options.languages.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <Label hint="至少选择一名分析师">Analysts Team</Label>
        <div className="grid grid-cols-2 gap-1.5">
          {options.analysts.map((a) => {
            const active = analysts.includes(a.id);
            return (
              <button
                type="button"
                key={a.id}
                onClick={() => toggleAnalyst(a.id)}
                className={`rounded border px-2 py-1.5 text-left text-[12px] transition ${
                  active
                    ? "border-[#2962FF] bg-[#0c1e3a] text-white"
                    : "border-[#2B2F36] bg-[#0f1318] text-[#a8acc0] hover:border-[#3a4055]"
                }`}
              >
                <span className="material-symbols-outlined mr-1 align-middle text-[14px]">
                  {active ? "check_box" : "check_box_outline_blank"}
                </span>
                {a.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <Label>Research Depth</Label>
        <div className="grid grid-cols-3 gap-1.5">
          {options.depths.map((d) => {
            const active = d.value === depth;
            return (
              <button
                type="button"
                key={d.value}
                onClick={() => setDepth(d.value)}
                className={`rounded border px-2 py-1.5 text-center text-[12px] transition ${
                  active
                    ? "border-[#2962FF] bg-[#0c1e3a] text-white"
                    : "border-[#2B2F36] bg-[#0f1318] text-[#a8acc0] hover:border-[#3a4055]"
                }`}
                title={d.label}
              >
                {d.label.split(" - ")[0]}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <Label>LLM Provider</Label>
        <select
          className={inputCls}
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {options.providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 gap-2">
        <div>
          <Label>Quick-Thinking Model</Label>
          <select
            className={inputCls}
            value={shallow}
            onChange={(e) => setShallow(e.target.value)}
          >
            {(modelLists?.quick ?? []).map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label>Deep-Thinking Model</Label>
          <select
            className={inputCls}
            value={deep}
            onChange={(e) => setDeep(e.target.value)}
          >
            {(modelLists?.deep ?? []).map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {providerInfo?.thinking === "reasoning_effort" && (
        <div>
          <Label>Reasoning Effort</Label>
          <select
            className={inputCls}
            value={reasoningEffort}
            onChange={(e) => setReasoningEffort(e.target.value)}
          >
            {(options.thinking_configs.openai ?? []).map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
      )}
      {providerInfo?.thinking === "effort" && (
        <div>
          <Label>Effort Level</Label>
          <select
            className={inputCls}
            value={anthropicEffort}
            onChange={(e) => setAnthropicEffort(e.target.value)}
          >
            {(options.thinking_configs.anthropic ?? []).map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
      )}
      {providerInfo?.thinking === "thinking_level" && (
        <div>
          <Label>Thinking Mode</Label>
          <select
            className={inputCls}
            value={googleThinking}
            onChange={(e) => setGoogleThinking(e.target.value)}
          >
            {(options.thinking_configs.google ?? []).map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <div className="rounded border border-[#7a1f1f] bg-[#2a0e0e] px-3 py-2 text-[12px] text-[#f87171]">
          {error}
        </div>
      )}

      <button
        type="button"
        onClick={submit}
        disabled={disabled}
        className={`flex w-full items-center justify-center gap-2 rounded border px-3 py-2 text-[13px] font-semibold transition ${
          disabled
            ? "cursor-not-allowed border-[#2B2F36] bg-[#1a1d22] text-[#5E6673]"
            : "border-[#2962FF] bg-[#0c1e3a] text-white hover:bg-[#13294e]"
        }`}
      >
        <span className="material-symbols-outlined text-[18px]">play_arrow</span>
        Run Analysis
      </button>
    </div>
  );
}
