"use client";

import { useEffect, useMemo, useState } from "react";
import { getXBriefLatest, refreshXBrief, XBriefData } from "@/lib/api";

type TweetItem = { handle: string; title: string; title_zh?: string; url: string; published_at: string };

export default function XBriefPage() {
  const [data, setData] = useState<XBriefData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState("");
  const [openTopics, setOpenTopics] = useState<Record<string, boolean>>({});
  const [openSilent, setOpenSilent] = useState(false);
  const [openGaps, setOpenGaps] = useState(false);

  useEffect(() => {
    getXBriefLatest()
      .then((d) => setData(d))
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function onRefresh() {
    setRefreshing(true);
    setErr("");
    try {
      const d = await refreshXBrief();
      setData(d);
    } catch (e) {
      setErr(String(e));
    } finally {
      setRefreshing(false);
    }
  }

  const tweets = ((data as XBriefData & { tweets?: TweetItem[] })?.tweets ?? []) as TweetItem[];
  const failedAccounts = useMemo(() => (data?.accounts ?? []).filter((x) => x.status !== "ok"), [data?.accounts]);
  const silentAccounts = useMemo(
    () => (data?.accounts ?? []).filter((x) => (x.tweets_count ?? 0) === 0),
    [data?.accounts],
  );

  const tweetByUrl = useMemo(() => {
    const m = new Map<string, TweetItem>();
    tweets.forEach((t) => t.url && m.set(t.url, t));
    return m;
  }, [tweets]);

  const tweetById = useMemo(() => {
    const m = new Map<string, TweetItem>();
    tweets.forEach((t) => {
      const match = t.url?.match(/\/status\/(\d+)/);
      if (match) m.set(match[1], t);
    });
    return m;
  }, [tweets]);

  const findTweet = (url?: string): TweetItem | null => {
    if (url && tweetByUrl.has(url)) return tweetByUrl.get(url)!;
    if (url) {
      const match = url.match(/\/status\/(\d+)/);
      if (match && tweetById.has(match[1])) return tweetById.get(match[1])!;
    }
    return null;
  };

  const topicCards = useMemo(() => {
    return (data?.modules?.themes ?? []).slice(0, 3).map((t) => ({
      id: t.id,
      title: t.title,
      priority: (t.priority ?? "P1") as "P0" | "P1" | "P2",
      tags: [t.subtitle || "重点主题"].filter(Boolean),
      insight: (t.bullets || []).slice(0, 2).join("；") || "暂无洞见",
      actionSuggestion: (t.bullets || [])[2] || "把这条主线加入下一期重点跟踪清单。",
      sources:
        t.samples?.map((s, i) => ({
          id: `${t.id}-${i}`,
          url: s.url || "",
          text: s.text || "",
          handle: s.handle || "",
          publishedAt: s.date || "",
        })) ?? [],
    }));
  }, [data?.modules?.themes]);

  const usedUrls = useMemo(() => {
    const set = new Set<string>();
    topicCards.forEach((c) => c.sources.forEach((s) => s.url && set.add(s.url)));
    return set;
  }, [topicCards]);

  const quickReads = useMemo(() => {
    const fromP0 =
      data?.modules?.p0_events?.map((x) => ({
        id: x.id,
        url: x.url || "",
        summary: x.summary || x.title || "",
        meta: x.meta || "",
      })) ?? [];
    const filtered = fromP0.filter((x) => !usedUrls.has(x.url)).slice(0, 8);
    if (filtered.length) return filtered;
    return tweets
      .filter((t) => !usedUrls.has(t.url))
      .slice(0, 8)
      .map((t, i) => ({
        id: `q-${i}`,
        url: t.url,
        summary: (t.title_zh || t.title).slice(0, 60),
        meta: `@${t.handle} · ${t.published_at.slice(0, 10)}`,
      }));
  }, [data?.modules?.p0_events, tweets, usedUrls]);


  const actionItems = useMemo(() => {
    const fromTopics = topicCards.slice(0, 3).map((c, i) => ({
      id: `a-${i}`,
      text: c.actionSuggestion,
    }));
    return fromTopics.length ? fromTopics : [{ id: "a-0", text: "今日无重点主题，建议先按快速扫读筛出3条候选研究线索。" }];
  }, [topicCards]);

  const headline = useMemo(() => {
    if (data?.headline) return data.headline;
    if (topicCards.length) return `30秒总览：${topicCards[0].title}`;
    return "30秒总览：今日无明显主线，市场信息偏分散。";
  }, [data?.headline, topicCards]);

  const dateLabel = useMemo(() => {
    const d = data?.generated_at || data?.period?.end_utc;
    return d ? d.slice(0, 10) : "N/A";
  }, [data?.generated_at, data?.period?.end_utc]);

  return (
    <div className="h-full overflow-y-auto bg-[#0B0E11]">
      <div className="min-h-full w-full space-y-3 p-3 text-[#e1e2e7]">
        <section className="border border-[#2B2F36] bg-[#161A1E] p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#5E6673]">AI & 投资日报</p>
          <h1 className="mt-2 text-3xl font-semibold text-[#f2f4ff]">{headline}</h1>
          <p className="mt-2 text-sm text-[#8d90a2]">
            日期 {dateLabel} · 抓取 {data?.overview?.total_tweets ?? 0} 条 · 保留 {data?.overview?.tweets_kept ?? "—"} 条 · 活跃账号 {data?.overview?.active_accounts ?? 0}
          </p>
          <div className="mt-4">
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              className="rounded border border-blue-400/60 bg-blue-600 px-3 py-1.5 text-sm font-semibold text-blue-50 hover:bg-blue-500 disabled:opacity-60"
            >
              {refreshing ? "刷新中..." : "刷新简报"}
            </button>
          </div>
        </section>

        {(data?.trending_keywords ?? []).length > 0 && (
          <section className="flex flex-wrap items-center gap-2 px-1">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-[#5E6673]">热词</span>
            {(data?.trending_keywords ?? []).map((kw, i) => (
              <span key={i} className="rounded border border-[#3a3f49] bg-[#161A1E] px-2 py-0.5 text-[11px] text-[#aeb8cc]">
                {kw}
              </span>
            ))}
          </section>
        )}

        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[#5E6673]">今日主题卡片</h2>
          {topicCards.length === 0 && (
            <div className="border border-[#2B2F36] bg-[#161A1E] p-4 text-sm text-[#8d90a2]">今日无重点主题，请见快速扫读。</div>
          )}
          {topicCards.map((card) => (
            <article key={card.id} className="border border-[#2B2F36] bg-[#161A1E] p-4">
              <div className="flex items-center gap-2">
                {card.priority === "P0" && (
                  <span className="rounded border border-[#da2237]/45 bg-[#da2237]/10 px-1.5 py-0.5 text-[10px] font-bold text-[#ffb3b0]">P0</span>
                )}
                {card.priority === "P1" && (
                  <span className="rounded border border-[#d97706]/40 bg-[#d97706]/12 px-1.5 py-0.5 text-[10px] font-bold text-[#fcd34d]">P1</span>
                )}
                {card.priority === "P2" && (
                  <span className="rounded border border-[#3a3f49] bg-[#111417] px-1.5 py-0.5 text-[10px] font-bold text-[#8d90a2]">P2</span>
                )}
                <h3 className="text-lg font-semibold text-[#eef1ff]">{card.title}</h3>
                {card.tags.map((tag, idx) => (
                  <span key={`${card.id}-tag-${idx}`} className="rounded border border-[#3a3f49] bg-[#111417] px-2 py-0.5 text-[10px] text-[#aeb8cc]">
                    {tag}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-sm leading-7 text-[#d5d9e6]">{card.insight}</p>
              <div className="mt-3 rounded border border-blue-500/40 bg-blue-500/10 p-3 text-sm text-blue-100">
                <strong className="mr-2">你可以做什么：</strong>
                {card.actionSuggestion}
              </div>
              {card.sources.length > 0 && (
                <div className="mt-3">
                  <button
                    className="text-xs text-[#8ea0be] hover:text-[#dfeaff]"
                    onClick={() => setOpenTopics((prev) => ({ ...prev, [card.id]: !prev[card.id] }))}
                  >
                    {openTopics[card.id] ? "收起推文证据" : "展开推文证据"}
                  </button>
                  {openTopics[card.id] && (
                    <ul className="mt-2 space-y-2">
                      {card.sources.map((s) => {
                        const hit = findTweet(s.url);
                        return (
                          <li key={s.id} className="rounded border border-[#2B2F36] bg-[#111417] p-2">
                            <p className="mb-1 text-xs text-[#8d90a2]">{hit ? `@${hit.handle} · ${hit.published_at.slice(0, 10)}` : s.handle || "来源待补充"}</p>
                            <p className="text-sm leading-7 text-[#cdd1df]">{hit?.title_zh || hit?.title || s.text}</p>
                            {s.url && (
                              <a className="mt-1 inline-block text-xs text-blue-400 hover:underline" href={s.url} target="_blank" rel="noreferrer">
                                查看原文 ↗
                              </a>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              )}
            </article>
          ))}
        </section>

        <section className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[#5E6673]">快速扫读</h2>
          <div className="border border-[#2B2F36] bg-[#161A1E]">
            {quickReads.map((x) => (
              <div key={x.id} className="border-t border-[#2B2F36] px-3 py-2 first:border-t-0">
                <p className="text-sm text-[#e2e5ef]">{x.summary}</p>
                <p className="mt-1 text-xs text-[#8d90a2]">{x.meta}</p>
                {x.url && (
                  <a className="mt-1 inline-block text-xs text-blue-400 hover:underline" href={x.url} target="_blank" rel="noreferrer">
                    原文 ↗
                  </a>
                )}
              </div>
            ))}
            {quickReads.length === 0 && <p className="px-3 py-3 text-sm text-[#8d90a2]">暂无快速扫读内容。</p>}
          </div>
        </section>


        <section className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[#5E6673]">本期可做的事</h2>
          <div className="border border-[#2B2F36] bg-[#161A1E] p-3">
            <ul className="space-y-2">
              {actionItems.map((a) => (
                <li key={a.id} className="rounded border border-emerald-500/40 bg-emerald-500/10 p-2 text-sm text-emerald-100">
                  {a.text}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="overflow-hidden border border-[#2B2F36] bg-[#161A1E]">
          <button className="flex w-full items-center justify-between px-3 py-3 text-left hover:bg-[#2B2F36]" onClick={() => setOpenSilent((v) => !v)}>
            <h2 className="text-sm font-semibold text-[#e1e2e7]">沉默账号</h2>
            <span className="text-xs text-[#5E6673]">{openSilent ? "▴" : "▾"}</span>
          </button>
          {openSilent && (
            <div className="border-t border-[#2B2F36] px-3 py-3">
              {silentAccounts.length > 0 ? (
                <ul className="space-y-2">
                  {silentAccounts.map((a) => (
                    <li key={a.handle} className="rounded border border-[#2B2F36] bg-[#111417] px-3 py-2 text-sm text-[#b6bfd2]">
                      @{a.handle}（{a.name}）
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-[#8d90a2]">本期没有沉默账号。</p>
              )}
            </div>
          )}
        </section>

        <section className="overflow-hidden border border-[#2B2F36] bg-[#161A1E]">
          <button className="flex w-full items-center justify-between px-3 py-3 text-left hover:bg-[#2B2F36]" onClick={() => setOpenGaps((v) => !v)}>
            <h2 className="text-sm font-semibold text-[#e1e2e7]">数据缺口说明</h2>
            <span className="text-xs text-[#5E6673]">{openGaps ? "▴" : "▾"}</span>
          </button>
          {openGaps && (
            <div className="border-t border-[#2B2F36] px-3 py-3">
              {failedAccounts.length > 0 ? (
                <ul className="space-y-2">
                  {failedAccounts.map((a) => (
                    <li key={a.handle} className="rounded border border-[#da2237]/45 bg-[#da2237]/10 px-3 py-2 text-xs text-[#ffb3b0]">
                      <p>
                        <strong>@{a.handle}</strong>（{a.name}）
                      </p>
                      <p className="mt-1">{a.error || "抓取失败"}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-[#8d90a2]">本次刷新无账号抓取失败。</p>
              )}
            </div>
          )}
        </section>

        {(loading || err) && (
          <section className="border border-[#2B2F36] bg-[#161A1E] p-3 text-xs">
            {loading && <p className="text-[#8d90a2]">正在加载 X 资讯简报...</p>}
            {err && <p className="text-[#ffb3b0]">{err}</p>}
          </section>
        )}

        <section className="pt-2 text-center text-[11px] text-[#5E6673]">
          <p>X资讯简报 · 手动刷新模式 · 基于多源抓取与双阶段 LLM 处理</p>
        </section>
      </div>
    </div>
  );
}
