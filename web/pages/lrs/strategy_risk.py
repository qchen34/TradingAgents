"""Step 4 — Capital Allocation Calculator.

UX pattern:
  - Page load: show last cached calculation
  - User enters total_cash (input persists via session_state)
  - "更新判断" button: fetch fresh TQQQ price, run 8-step calc, save, display
"""
from __future__ import annotations

import math
import streamlit as st
import yfinance as yf

from web.pages.lrs import strategy_cache as sc

_CACHE_KEY = "risk"
_SKEY      = "lrs_step4"

_MACRO_CEILING: dict[int, float] = {5: 1.00, 4: 1.00, 3: 0.80, 2: 0.60, 1: 0.00, 0: 0.00}


@st.cache_data(ttl=60, show_spinner=False)
def _tqqq_price() -> float:
    ticker = yf.Ticker("TQQQ")
    info   = ticker.fast_info
    return float(getattr(info, "last_price", None) or info.get("regularMarketPrice", 0))


def _row(label: str, value: str, formula: str = "", highlight: bool = False) -> None:
    bg    = "rgba(56,189,248,.15)" if highlight else "transparent"
    color = "#38bdf8" if highlight else "#e2e8f0"
    weight = "700" if highlight else "400"
    formula_html = (
        f'<span style="color:#64748b;font-size:11px;margin-left:8px;">{formula}</span>'
        if formula else ""
    )
    st.markdown(
        f'''<div style="display:flex;justify-content:space-between;align-items:baseline;
padding:6px 12px;background:{bg};border-radius:6px;margin:2px 0;">
<span style="color:#94a3b8;font-size:13px;">{label}</span>
<span style="color:{color};font-weight:{weight};font-size:14px;">{value}</span>
{formula_html}
</div>''',
        unsafe_allow_html=True,
    )

def _run_calc(total_cash: float, tqqq_price: float,
              macro_score: int, entry_mode: str, signal_quality: str) -> dict:
    ceiling_pct    = _MACRO_CEILING.get(macro_score, 0.60)
    deployable     = total_cash * ceiling_pct
    quality_adj    = 0.75 if signal_quality == "Weak" else 1.0
    deployable_adj = deployable * quality_adj

    if entry_mode.startswith("Direct Buy"):
        direct_alloc = deployable_adj * (2 / 3)
        wheel_margin = deployable_adj * (1 / 3)
    else:
        direct_alloc = deployable_adj * (1 / 3)
        wheel_margin = deployable_adj * (1 / 3)

    shares       = math.floor(direct_alloc / tqqq_price) if tqqq_price > 0 else 0
    actual_cost  = shares * tqqq_price
    put_contracts = math.floor(wheel_margin / (100 * tqqq_price)) if tqqq_price > 0 else 0
    reserve_cash = total_cash - actual_cost - (put_contracts * 100 * tqqq_price)

    return dict(
        total_cash=total_cash, tqqq_price=tqqq_price,
        macro_score=macro_score, ceiling_pct=ceiling_pct,
        deployable=deployable, quality_adj=quality_adj,
        deployable_adj=deployable_adj, direct_alloc=direct_alloc,
        wheel_margin=wheel_margin, shares=shares,
        actual_cost=actual_cost, put_contracts=put_contracts,
        reserve_cash=reserve_cash, entry_mode=entry_mode,
        signal_quality=signal_quality,
    )


def _render_all(result: dict) -> None:
    with st.container(border=True):
        st.markdown("#### 八步资金分配计算")
        _row("步骤 1 — 可用总资金", f"${result['total_cash']:,.0f}")
        _row("步骤 2 — 宏观仓位上限",
             f"{result['ceiling_pct']*100:.0f}%  →  ${result['deployable']:,.0f}",
             f"宏观评分 = {result['macro_score']}")
        _row("步骤 3 — 弱信号调整",
             f"x{result['quality_adj']:.2f}  →  ${result['deployable_adj']:,.0f}",
             f"信号质量 = {result['signal_quality']}")
        _row("步骤 4 — 直接买入资金",
             f"${result['direct_alloc']:,.0f}",
             f"入场模式 = {result['entry_mode']}")
        _row("步骤 5 — 买入股数",
             f"{result['shares']} shares  @  ${result['tqqq_price']:.2f}",
             formula="floor(直接买入金额 / TQQQ 价格)")
        _row("步骤 6 — 实际购买成本",
             f"${result['actual_cost']:,.2f}",
             formula="股数 x 价格", highlight=True)
        _row("步骤 7 — Wheel 保证金预留",
             f"${result['wheel_margin']:,.0f}")
        _row("步骤 8 — Sell Put 合约数",
             f"{result['put_contracts']} contracts",
             formula="floor(Wheel 保证金 / (100 x 价格))", highlight=True)
        _row("未使用现金",
             f"${result['reserve_cash']:,.2f}", highlight=True)

    with st.container(border=True):
        st.markdown("#### 汇总")
        c1, c2, c3 = st.columns(3)
        c1.metric("买入 TQQQ 股数", f"{result['shares']} 股",
                  f"${result['actual_cost']:,.0f}")
        c2.metric("Sell Put 合约数", f"{result['put_contracts']} 张",
                  f"${result['wheel_margin']:,.0f} 保证金")
        c3.metric("预留现金", f"${result['reserve_cash']:,.0f}")

    with st.expander("保证金说明"):
        st.markdown("""
**Sell Put 保证金规则：**
- 每张合约对应 100 股 TQQQ
- 券商通常要求约 20% 名义价值作为现金担保保证金
- 本计算器为安全起见使用 100% 名义价值（全额现金担保）
- 盈透证券 RegT 保证金可能允许更低要求，下单前请确认
""")


def render_tab_risk() -> None:
    st.markdown("### Step 4 — 资金分配计算器")

    cached = sc.load(_CACHE_KEY)

    col1, col2 = st.columns([4, 1])
    with col1:
        if cached:
            st.caption(f"上次更新：{cached.get('_updated_at', '—')}  |  点击「更新判断」刷新 TQQQ 价格并重算")
        else:
            st.caption("暂无历史数据，请填写总资金后点击「更新判断」")
    with col2:
        update = st.button("🔄 更新判断", key=f"{_SKEY}_update",
                           type="primary", use_container_width=True)

    st.info(
        f"**入场模式**（来自 Step 3）：`{st.session_state.get('lrs_step3_entry_mode', '未设置')}`  \n"
        f"**信号质量**（来自 Step 2）：`{st.session_state.get('lrs_step2_signal_quality', '未设置')}`  \n"
        "如需修改，请先到对应 tab 重新运行「更新判断」。"
    )

    with st.container(border=True):
        st.markdown("#### 输入参数")
        default_cash = float(cached.get("total_cash", 10000.0)) if cached else 10000.0
        total_cash = st.number_input("可用总资金（$）",
                                      min_value=1000.0, max_value=10_000_000.0,
                                      value=default_cash, step=1000.0,
                                      key=f"{_SKEY}_total_cash")

    if update:
        try:
            with st.spinner("正在获取 TQQQ 实时价格…"):
                _tqqq_price.clear()
                price = _tqqq_price()
        except Exception as exc:
            st.error(f"价格获取失败：{exc}")
            return

        macro_score    = int(round(float(st.session_state.get("macro_score_total", 3))))
        entry_mode     = st.session_state.get("lrs_step3_entry_mode", "Direct Buy")
        signal_quality = st.session_state.get("lrs_step2_signal_quality", "Valid")

        result = _run_calc(total_cash, price, macro_score, entry_mode, signal_quality)
        sc.save(_CACHE_KEY, result)
        st.session_state[f"{_SKEY}_result"] = result
        st.success(f"已更新  |  TQQQ 价格: ${price:.2f}  |  买入: {result['shares']} 股  |  保留: ${result['reserve_cash']:,.0f}")

    display_result = st.session_state.get(f"{_SKEY}_result")
    if display_result is None and cached:
        display_result = cached

    if display_result is None:
        st.info("请填写总资金后点击「更新判断」开始计算。")
        return

    _render_all(display_result)
