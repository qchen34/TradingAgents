"""Step 5A — Direct Buy Execution.

UX pattern:
  - Page load: show last cached pre-order check results
  - "更新判断" (Pre-Order Check) button: fetch live data, save, display
  - Phase 2 (Order Placement) & Phase 3 (Entry Log) always visible
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import streamlit as st
import yfinance as yf

from web.pages.lrs import strategy_cache as sc
from web.pages.lrs.strategy_shared import render_score_card

_CACHE_KEY = "execution"
_SKEY      = "lrs_step5"

_NY_OFFSET = timedelta(hours=-5)  # UTC-5 (EST); adjust for DST manually if needed


@st.cache_data(ttl=60, show_spinner=False)
def _live_qqq_vs_ma200() -> tuple[float, float, bool]:
    import pandas as pd
    df = yf.download("QQQ", period="1y", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close  = df["Close"].dropna()
    ma200  = close.rolling(200).mean()
    price  = float(close.iloc[-1])
    ma_val = float(ma200.iloc[-1])
    return price, ma_val, price > ma_val


@st.cache_data(ttl=60, show_spinner=False)
def _tqqq_bid_ask() -> tuple[float | None, float | None, float | None]:
    ticker = yf.Ticker("TQQQ")
    info   = ticker.fast_info
    bid    = getattr(info, "bid",  None)
    ask    = getattr(info, "ask",  None)
    last   = getattr(info, "last_price", None)
    if bid and ask and bid > 0 and ask > 0:
        spread = ask - bid
        return float(bid), float(ask), float(spread)
    return None, None, None


def _market_hours_check() -> tuple[int, str, str]:
    now_ny = datetime.now(timezone.utc) + _NY_OFFSET
    h, m   = now_ny.hour, now_ny.minute
    is_open = (9, 30) <= (h, m) <= (16, 0)
    time_str = now_ny.strftime("%H:%M ET")
    if is_open:
        return 1, time_str, "常规交易时段 — 订单可立即执行。"
    return 0, time_str, "市场已收盘或盘前/盘后 — 限价单可能无法按预期成交。"


def _spread_assessment(spread) -> tuple[int, str, str]:
    if spread is None:
        return -1, "N/A", "无法获取买卖价，请检查数据源。"
    if spread <= 0.02:
        return 1, f"${spread:.3f}", f"价差紧窄 ${spread:.3f} — 成交质量优秀。"
    if spread <= 0.05:
        return -1, f"${spread:.3f}", f"价差适中 ${spread:.3f} — 建议使用限价单。"
    return 0, f"${spread:.3f}", f"价差偏宽 ${spread:.3f} — 建议等待 5 分钟后重查，或以中间价限价下单。"


def _to_cache(qqq_price, ma200_val, qqq_above, market_time, market_ok,
              bid, ask, spread) -> dict:
    return {
        "qqq_price": float(qqq_price), "ma200_val": float(ma200_val),
        "qqq_above": bool(qqq_above),
        "market_time": str(market_time), "market_ok": bool(market_ok),
        "bid":  float(bid)  if bid  else None,
        "ask":  float(ask)  if ask  else None,
        "spread": float(spread) if spread else None,
    }


def _render_check_results(data: dict) -> None:
    with st.container(border=True):
        st.markdown("#### 第一阶段 — 下单前检查")

        qqq   = data.get("qqq_price", 0)
        ma200 = data.get("ma200_val", 0)
        above = data.get("qqq_above", False)
        render_score_card(
            label="检查 1 — QQQ 仍在 MA200 之上",
            score=1 if above else 0,
            metric=f"QQQ = {qqq:.2f}  |  MA200 = {ma200:.2f}  |  Above = {above}",
            verdict=("QQQ 位于 MA200 之上，信号维持有效。" if above else
                     "QQQ 已跌破 MA200，不可入场，请返回 Step 2。"),
        )
        mkt_time = data.get("market_time", "N/A")
        mkt_ok   = data.get("market_ok", False)
        render_score_card(
            label="检查 2 — 美股常规交易时间",
            score=1 if mkt_ok else 0,
            metric=f"当前时间：{mkt_time}",
            verdict=("常规交易时段 — 订单可立即执行。"
                     if mkt_ok else
                     "市场已收盘或处于盘前/盘后 — 限价单可能无法按预期成交。"),
        )
        spread = data.get("spread")
        s_score, s_metric, s_verdict = _spread_assessment(spread)
        render_score_card(
            label="检查 3 — TQQQ 买卖价差",
            score=s_score, metric=s_metric, verdict=s_verdict,
        )
        if data.get("bid") and data.get("ask"):
            col1, col2, col3 = st.columns(3)
            col1.metric("买价",    f"${data['bid']:.2f}")
            col2.metric("卖价",    f"${data['ask']:.2f}")
            col3.metric("价差", f"${spread:.3f}" if spread else "N/A")


def render_tab_execution() -> None:
    st.markdown("### Step 5A — 直接买入执行")

    st.markdown(
        '<div style="border-left:4px solid #ef4444;padding:10px 16px;'
        'background:rgba(239,68,68,.1);border-radius:6px;margin-bottom:16px;">'
        '<b style="color:#ef4444;">LRS 离场规则</b><br>'
        '<span style="color:#fca5a5;">QQQ 连续 2 日收盘低于 MA200 → 次日开盘卖出全部 TQQQ 仓位。</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    cached = sc.load(_CACHE_KEY)

    col1, col2 = st.columns([4, 1])
    with col1:
        if cached:
            st.caption(f"上次检查：{cached.get('_updated_at', '—')}  |  点击「更新判断」重新检查实时数据")
        else:
            st.caption("暂无历史检查数据，请点击「更新判断」执行前置检查")
    with col2:
        update = st.button("🔄 更新判断", key=f"{_SKEY}_update",
                           type="primary", use_container_width=True)

    if update:
        try:
            with st.spinner("正在获取实时数据…"):
                _live_qqq_vs_ma200.clear()
                _tqqq_bid_ask.clear()
                qqq_price, ma200_val, qqq_above = _live_qqq_vs_ma200()
                bid, ask, spread                = _tqqq_bid_ask()
                market_ok, market_time, _       = _market_hours_check()
        except Exception as exc:
            st.error(f"数据获取失败：{exc}")
            return

        cache_data = _to_cache(qqq_price, ma200_val, qqq_above,
                                market_time, market_ok, bid, ask, spread)
        sc.save(_CACHE_KEY, cache_data)
        st.session_state[f"{_SKEY}_check_data"] = cache_data
        all_pass = qqq_above and bool(market_ok) and (spread is not None and spread <= 0.05)
        if all_pass:
            st.success("所有前置检查通过 — 可以下单。")
        else:
            st.warning("部分检查未通过，请查看下方详情。")

    check_data = st.session_state.get(f"{_SKEY}_check_data")
    if check_data is None and cached:
        check_data = cached
    if check_data is None:
        st.info("点击「更新判断」执行实时前置检查（QQQ vs MA200 / 交易时间 / 买卖价差）。")
    else:
        _render_check_results(check_data)

    # Phase 2 — Order Placement (always visible)
    with st.container(border=True):
        st.markdown("#### 第二阶段 — 下单参考")
        st.markdown("""
**时机指引：**
- 最佳时段：美东 9:45–10:30 AM（开盘波动平息后）
- 第二窗口：美东 2:00–3:30 PM

**限价单规则（TQQQ）：**
- 以卖价（Ask）下限价单；若 3 分钟内未成交 → 每次上移 $0.05，最多操作 3 次
- 禁止使用市价单买 TQQQ（日内价差风险较大）

**价差指引：**
- 价差 <= $0.02：以 Ask 价积极下单
- 价差 $0.02–$0.05：以中间价（bid+ask）/2 限价
- 价差 > $0.05：等待 5 分钟后重新查看
""")

    # Phase 3 — Entry Log
    with st.container(border=True):
        st.markdown("#### 第三阶段 — 入场记录与离场提醒设置")
        with st.form(key="lrs_entry_log_form"):
            st.markdown("**订单成交后填写入场记录：**")
            c1, c2, c3 = st.columns(3)
            entry_price = c1.text_input("成交价格（$）", placeholder="如 73.45")
            entry_shares = c2.text_input("成交股数", placeholder="如 90")
            entry_date  = c3.text_input("成交日期", placeholder="YYYY-MM-DD")
            notes = st.text_input("备注（可选）", placeholder="如 跳空高开，以 Ask 成交")
            submitted = st.form_submit_button("保存入场记录")
            if submitted and entry_price:
                sc.save("execution_log", {
                    "entry_price": entry_price, "shares": entry_shares,
                    "date": entry_date, "notes": notes,
                })
                st.success("入场记录已保存。")

        st.markdown("""
**TradingView 离场提醒设置：**
1. 打开 QQQ 图表 → 添加 200 日均线（EMA 或 SMA）指标
2. 提醒条件：`QQQ 收盘价 < MA200`
3. 提醒消息："LRS 离场：QQQ 收盘跌破 MA200 — 次日注意操作"
4. 设置为每根 K 线收盘触发（日线图）
5. 开启手机 + 邮件通知
""")

    with st.container(border=True):
        st.markdown("#### 执行完成清单")
        checks = [
            "下单前三项检查均已通过（QQQ > MA200 / 交易时间 / 买卖价差）",
            "Step 4 计算的买入股数已确认",
            "限价单已按正确价格下单",
            "订单已成交 — 截图已保存",
            "入场记录已填写（第三阶段）",
            "TradingView 离场提醒已配置",
            "心理止损已设定：连续 2 日 QQQ 收盘跌破 MA200 时离场",
        ]
        for i, item in enumerate(checks):
            st.checkbox(item, key=f"lrs_exec_check_{i}")
