"""
个股追踪后端服务
- yfinance 基本面数据拉取
- Weinstein 技术指标计算（MA/RSI/RS vs QQQ/OBV/Score）
- matplotlib 技术图表生成（PNG）
- Thinking LLM 结构化分析（阶段/买点/催化剂）
- 异步 Job 管理（镜像 backtesting_core 风格）
"""
from __future__ import annotations

import io
import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from langchain_core.messages import HumanMessage

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.base_client import normalize_content
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

# ──────────────────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────────────────

# 核心追踪标的（可持续扩充）
CORE_TICKERS: list[str] = [
    "NVDA", "AVGO", "MU", "VRT", "GEV",
    "ETN", "ANET", "MRVL", "TER", "COHR",
    "ONTO", "AMKR", "ALAB", "AMD", "RKLB",
    "IREN", "CRWV", "LITE", "MSFT", "AMZN", "GOOGL", "CRCL",
]

# 向后兼容别名（部分老代码仍引用 CORE_13）
CORE_13 = CORE_TICKERS

# 行业代理 ETF：用其 trailingPE 作为「行业平均 PE」基准
# - 半导体 / GPU / HBM / 封测 / 互连：SOXX
# - 电气基础设施 / 工业 / 航天：XLI
# - 网络通信硬件：XLK（科技板块兜底）
INDUSTRY_PROXY_MAP: dict[str, str] = {
    "NVDA": "SOXX",
    "AVGO": "SOXX",
    "MU": "SOXX",
    "MRVL": "SOXX",
    "TER": "SOXX",
    "COHR": "SOXX",
    "ONTO": "SOXX",
    "AMKR": "SOXX",
    "ALAB": "SOXX",
    "AMD": "SOXX",
    "VRT": "XLI",
    "GEV": "XLI",
    "ETN": "XLI",
    "RKLB": "XLI",
    "IREN": "XLI",
    "ANET": "XLK",
    "CRWV": "XLK",
    "LITE": "SOXX",
    "MSFT": "XLK",
    "AMZN": "XLK",
    "GOOGL": "XLK",
    "CRCL": "XLK",
}

INDUSTRY_PROXY_LABEL: dict[str, str] = {
    "SOXX": "半导体 (SOXX)",
    "XLI": "工业 / 航天 (XLI)",
    "XLK": "信息技术 (XLK)",
}

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "stock_tracker"
LATEST_JSON = DATA_DIR / "latest.json"
CHARTS_DIR = DATA_DIR / "charts"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

_DEEP_PROVIDER = "siliconflow"
_DEEP_MODEL = MODEL_OPTIONS[_DEEP_PROVIDER]["deep"][0][1]
_PROVIDER_URL = "https://api.siliconflow.cn/v1"

# ──────────────────────────────────────────────────────────────────────────────
# Job 管理
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TrackerJob:
    job_id: str
    status: str          # running / completed / failed
    created_at: str
    updated_at: str = field(default_factory=lambda: _now_iso())
    progress: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None


_JOBS: dict[str, TrackerJob] = {}
_JOB_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# 通用标量提取工具（防止 yfinance 返回 Series/DataFrame）
# ──────────────────────────────────────────────────────────────────────────────

def _to_scalar(v: Any) -> Any:
    """将 pandas Series / DataFrame / numpy 数组强制取第一个标量值。"""
    if isinstance(v, pd.DataFrame):
        if v.empty:
            return None
        v = v.iloc[0, 0]
    if isinstance(v, pd.Series):
        if v.empty:
            return None
        v = v.iloc[0]
    if isinstance(v, (np.ndarray,)):
        if v.size == 0:
            return None
        v = v.flat[0]
    # numpy 标量
    if isinstance(v, (np.integer, np.floating)):
        v = v.item()
    return v


def _safe_float(v: Any) -> float | None:
    v = _to_scalar(v)
    if v is None:
        return None
    try:
        f = float(v)
        return None if (f != f) else f   # nan → None
    except (TypeError, ValueError):
        return None


def _pct(v: Any) -> float | None:
    """将 0-1 小数转为百分比（×100）。"""
    v = _safe_float(v)
    if v is None:
        return None
    return round(v * 100, 2)


def _cagr_pct(values: list[float]) -> float | None:
    """基于新->旧序列计算 CAGR 百分比。"""
    if len(values) < 2:
        return None
    newest = values[0]
    oldest = values[-1]
    if newest <= 0 or oldest <= 0:
        return None
    years = len(values) - 1
    if years <= 0:
        return None
    try:
        return round(((newest / oldest) ** (1 / years) - 1) * 100, 2)
    except Exception:
        return None


def _pick_fin_row(df: pd.DataFrame, row_candidates: list[str]) -> pd.Series | None:
    for idx_name in row_candidates:
        if idx_name in df.index:
            raw_row = df.loc[idx_name]
            if isinstance(raw_row, pd.DataFrame):
                raw_row = raw_row.iloc[0]
            if isinstance(raw_row, pd.Series):
                return raw_row
    return None


def _annual_cagr(
    t: yf.Ticker,
    row_candidates: list[str],
    years: int = 5,
) -> float | None:
    try:
        stmt = t.income_stmt
        if stmt is None or stmt.empty:
            return None
        row = _pick_fin_row(stmt, row_candidates)
        if row is None:
            return None
        cols = sorted(row.index, reverse=True)
        values: list[float] = []
        for col in cols:
            v = _safe_float(_to_scalar(row[col]))
            if v is not None:
                values.append(v)
            if len(values) >= years:
                break
        return _cagr_pct(values)
    except Exception:
        return None


def _quarterly_qoq_pct(t: yf.Ticker, row_candidates: list[str]) -> float | None:
    try:
        stmt = t.quarterly_income_stmt
        if stmt is None or stmt.empty:
            return None
        row = _pick_fin_row(stmt, row_candidates)
        if row is None:
            return None
        cols = sorted(row.index, reverse=True)[:2]
        if len(cols) < 2:
            return None
        curr = _safe_float(_to_scalar(row[cols[0]]))
        prev = _safe_float(_to_scalar(row[cols[1]]))
        if curr is None or prev is None or prev == 0:
            return None
        return round((curr / prev - 1) * 100, 2)
    except Exception:
        return None


def _estimate_growth_pct(t: yf.Ticker, period: str) -> float | None:
    try:
        ee = t.get_earnings_estimate()
        if ee is None or ee.empty or period not in ee.index:
            return None
        growth = _safe_float(_to_scalar(ee.loc[period].get("growth")))
        return _pct(growth)
    except Exception:
        return None


def _ltg_growth_pct(t: yf.Ticker) -> float | None:
    try:
        ge = t.get_growth_estimates()
        if ge is None or ge.empty or "LTG" not in ge.index:
            return None
        val = _safe_float(_to_scalar(ge.loc["LTG"].get("stockTrend")))
        return _pct(val)
    except Exception:
        return None


def _to_series(s: pd.Series | pd.DataFrame) -> pd.Series:
    """确保返回 1D Series，兼容 yfinance 新版多级列名。"""
    if isinstance(s, pd.DataFrame):
        return s.iloc[:, 0]
    return s


# ──────────────────────────────────────────────────────────────────────────────
# Weinstein 技术指标计算
# ──────────────────────────────────────────────────────────────────────────────

def _calc_rsi(closes: pd.Series, period: int = 14) -> float | None:
    if len(closes) < period + 5:
        return None
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = _to_scalar(rsi.iloc[-1])
    if val is None or (isinstance(val, float) and val != val):
        return None
    return round(float(val), 2)


def _calc_rsi_series(closes: pd.Series, period: int = 14) -> pd.Series:
    """与 _calc_rsi 同源，返回对齐 closes 索引的 RSI 序列（前段 NaN）。"""
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _calc_macd(closes: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD(12,26,9)：返回 (macd_line, signal, histogram)，与 closes 索引对齐。"""
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return macd_line, signal, hist


def _macd_hist_slope_sign(hist: pd.Series, bars: int = 5) -> str | None:
    tail = hist.dropna().iloc[-bars:]
    if len(tail) < 3:
        return None
    x = np.arange(len(tail))
    try:
        slope = float(np.polyfit(x, tail.values.astype(float), 1)[0])
    except Exception:
        return None
    if slope > 1e-8:
        return "up"
    if slope < -1e-8:
        return "down"
    return "flat"


def _ma50_ma200_cross_info(ma50_s: pd.Series, ma200_s: pd.Series) -> dict[str, Any]:
    """
    最近一次 MA50 与 MA200 交叉：金叉 = MA50 从下穿上穿 MA200；死叉相反。
    返回 golden_cross_state（bull/bear/insufficient）、last_cross_event、bars_since_cross、last_cross_date。
    """
    out: dict[str, Any] = {
        "ma50_above_ma200": None,
        "golden_cross_state": "insufficient",
        "last_cross_event": None,
        "bars_since_cross": None,
        "last_cross_date": None,
    }
    diff = (ma50_s - ma200_s).dropna()
    if len(diff) < 2:
        return out
    last = diff.iloc[-1]
    ma50_above = bool(last > 0)
    out["ma50_above_ma200"] = ma50_above
    out["golden_cross_state"] = "bull" if ma50_above else "bear"
    vals = diff.values.astype(float)
    idx = diff.index
    for i in range(len(vals) - 1, 0, -1):
        a, b = vals[i - 1], vals[i]
        if (a <= 0 < b) or (a < 0 <= b):
            out["last_cross_event"] = "golden"
            out["bars_since_cross"] = int(len(vals) - 1 - i)
            out["last_cross_date"] = str(idx[i].date()) if hasattr(idx[i], "date") else str(idx[i])
            return out
        if (a >= 0 > b) or (a > 0 >= b):
            out["last_cross_event"] = "death"
            out["bars_since_cross"] = int(len(vals) - 1 - i)
            out["last_cross_date"] = str(idx[i].date()) if hasattr(idx[i], "date") else str(idx[i])
            return out
    return out


def _trend_buy_assessment(
    *,
    pct_vs_ma150: float | None,
    ma150_slope_4w: float | None,
    rsi14: float | None,
    ma50_above_ma150: bool,
    ma150_above_ma200: bool,
    ma50_above_ma200: bool | None,
    macd_hist: float | None,
    macd_hist_slope: str | None,
    volume_vs_ma20: float | None,
    extension_label: str,
    last_cross_event: str | None,
    bars_since_cross: int | None,
    pullback_from_52w: float | None,
) -> dict[str, Any]:
    """
    规则化趋势买点结论（与 docs/strategy/buy_point_methodology_v1 对齐的简化实现）。
    verdict: at_buy | near_buy | not_yet | avoid_chase
    """
    tags: list[str] = []
    conditions: list[str] = []

    ext = extension_label or ""
    p150 = pct_vs_ma150
    rsi = rsi14
    slope150 = ma150_slope_4w

    if ma50_above_ma150 and ma150_above_ma200:
        tags.append("MA多头排列")
    if rsi is not None and rsi < 70:
        tags.append("RSI未极端超买")
    if rsi is not None and rsi >= 50:
        tags.append("RSI偏强")
    if macd_hist is not None and macd_hist > 0:
        tags.append("MACD柱为正")
    if macd_hist_slope == "up":
        tags.append("MACD动能改善")
    if volume_vs_ma20 is not None and volume_vs_ma20 >= 1.0:
        tags.append("量能不低于20日均")

    # 禁追：延伸 / 过度延伸 / 超买
    over_extended = ext in ("延伸区", "过度延伸") or (p150 is not None and p150 > 28)
    rsi_bubble = rsi is not None and rsi >= 78
    chase_pullback = pullback_from_52w is not None and pullback_from_52w > -8 and (p150 is not None and p150 > 35)

    if over_extended or rsi_bubble or chase_pullback:
        verdict = "avoid_chase"
        one = "当前价格结构偏延伸或情绪过热，不宜追高，宜等回撤或事件后再评估。"
        conditions = [
            "价格回到健康偏离区（约 MA150 上方 +5%～+25%）且 MA150 维持上行",
            "RSI 回落至 40～60 区间并伴随缩量回踩",
            "MACD 柱由正转负后再度翻红且站上零轴更佳",
            "若属延伸博弈，参考财报/事件后 -15%～-25% 级别回调再议（见方法论 C 类）",
        ]
        return {
            "verdict": verdict,
            "one_liner": one,
            "supporting_tags": tags[:6],
            "conditions_if_not_buy": conditions,
        }

    # 趋势买点（健康区 + 结构 + 动能不过热）
    healthy_pullback = p150 is not None and 3 <= p150 <= 22
    ma150_up = slope150 is not None and slope150 > 0
    rsi_ok = rsi is not None and 42 <= rsi <= 72
    macd_ok = (macd_hist is not None and macd_hist > 0) or macd_hist_slope == "up"

    if healthy_pullback and ma50_above_ma150 and ma150_above_ma200 and ma150_up and rsi_ok and macd_ok:
        verdict = "at_buy"
        one = "结构与偏离度处于健康趋势买点区间，可关注回踩不破关键均线后的机会。"
        conditions = [
            "守住 MA50，收盘不破则持有逻辑延续",
            "若放量跌破 MA50，降至「观察」并等待 MA150 附近再评估",
        ]
        return {
            "verdict": verdict,
            "one_liner": one,
            "supporting_tags": tags[:6],
            "conditions_if_not_buy": conditions,
        }

    # 近买点：贴近 MA150、刚金叉不久、或 RSI 超卖修复初期
    near_ma = p150 is not None and -5 <= p150 < 8
    recent_golden = last_cross_event == "golden" and bars_since_cross is not None and bars_since_cross <= 25
    rsi_recover = rsi is not None and 30 <= rsi < 48 and macd_hist_slope == "up"

    if (near_ma and ma150_up) or recent_golden or rsi_recover:
        verdict = "near_buy"
        one = "接近趋势买点：均线结构或动能出现积极信号，可等待确认信号再行动。"
        conditions = [
            "收盘站上 MA150 且 MA150 斜率维持为正",
            "放量突破近 20 日震荡上沿，或缩量回踩 MA50 不破",
            "MACD 柱持续走高或上穿零轴",
            "RSI 回到 45～60 并配合成交量温和放大",
        ]
        return {
            "verdict": verdict,
            "one_liner": one,
            "supporting_tags": tags[:6],
            "conditions_if_not_buy": conditions,
        }

    verdict = "not_yet"
    one = "尚未满足趋势买点核心条件，建议继续跟踪均线结构与量能。"
    conditions = [
        "MA150 拐头向上且价格站上 MA150",
        "MA50 上穿 MA150 形成中期多头排布",
        "RSI 脱离弱势区（>45）且 MACD 柱翻红",
        "回调时量能萎缩、上攻时量能放大",
    ]
    return {
        "verdict": verdict,
        "one_liner": one,
        "supporting_tags": tags[:6],
        "conditions_if_not_buy": conditions,
    }


def _calc_obv_trend(closes: pd.Series, volumes: pd.Series, lookback: int = 60) -> str:
    if len(closes) < lookback:
        return "无数据"
    c = closes.iloc[-lookback:].values
    v = volumes.iloc[-lookback:].values
    direction = np.sign(np.diff(c))
    obv = np.concatenate([[0], np.cumsum(direction * v[1:])])
    x = np.arange(len(obv))
    try:
        slope = np.polyfit(x, obv, 1)[0]
    except Exception:
        return "无数据"
    return "上升" if slope > 0 else "下降"


def _monthly_highs_trend(highs: pd.Series) -> str:
    if len(highs) < 40:
        return "无数据"
    try:
        # pandas 2.2+ 用 "ME"，旧版用 "M"
        try:
            monthly = highs.resample("ME").max().dropna()
        except Exception:
            monthly = highs.resample("M").max().dropna()
        if len(monthly) < 3:
            return "无数据"
        last3 = monthly.iloc[-3:].values
        if last3[2] > last3[1] > last3[0]:
            return "上升"
        elif last3[2] < last3[1] < last3[0]:
            return "下降"
        return "震荡"
    except Exception:
        return "无数据"


def _extension_label(pct_vs_ma150: float | None) -> str:
    if pct_vs_ma150 is None:
        return "无数据"
    v = pct_vs_ma150
    if v < -5:
        return "超跌区"
    elif v < 5:
        return "贴近区"
    elif v < 15:
        return "健康区"
    elif v < 30:
        return "延伸区"
    return "过度延伸"


def _weinstein_score(
    pct_vs_ma150: float | None,
    ma150_slope: float | None,
    rsi14: float | None,
    rs_slope_3m: float | None,
    vol_ratio: float | None,
    ma50_above_ma150: bool,
    ma150_above_ma200: bool,
) -> int:
    score = 0
    if pct_vs_ma150 is not None and pct_vs_ma150 > 0:
        score += 1
    if ma150_slope is not None and ma150_slope > 0:
        score += 1
    if rsi14 is not None and rsi14 > 50:
        score += 1
    if rsi14 is not None and rsi14 < 80:
        score += 1
    if rs_slope_3m is not None and rs_slope_3m > 0:
        score += 1
    if vol_ratio is not None and vol_ratio > 1.0:
        score += 1
    if ma50_above_ma150:
        score += 1
    if ma150_above_ma200:
        score += 1
    if pct_vs_ma150 is not None and 5 <= pct_vs_ma150 <= 25:
        score += 1
    return score


def _calc_rs_slope(closes: pd.Series, ref_closes: pd.Series, days: int = 63) -> float | None:
    """RS vs 参考指数 slope（3M）。对齐时重命名，避免同名列合并为 DataFrame。"""
    s1 = closes.rename("ticker")
    s2 = ref_closes.rename("ref")
    aligned = pd.concat([s1, s2], axis=1, join="inner").dropna()
    if len(aligned) < days + 5:
        return None
    rs = aligned["ticker"] / aligned["ref"]
    rs_recent = rs.iloc[-days:]
    if len(rs_recent) < 5:
        return None
    x = np.arange(len(rs_recent))
    first_val = _safe_float(rs_recent.iloc[0])
    if not first_val:
        return None
    try:
        slope_pct = np.polyfit(x, rs_recent.values.astype(float), 1)[0] / first_val * 100
        return round(float(slope_pct), 3)
    except Exception:
        return None


def _calc_vol_ratio(closes: pd.Series, volumes: pd.Series, lookback: int = 20) -> float | None:
    if len(closes) < lookback + 1:
        return None
    diff = closes.diff().iloc[-lookback:]
    vol = volumes.iloc[-lookback:]
    up_vol = float(vol[diff > 0].sum())
    down_vol = float(vol[diff < 0].sum())
    if down_vol == 0:
        return 9.99
    return round(up_vol / down_vol, 2)


def _last_change_pct(closes: pd.Series) -> float | None:
    if len(closes) < 2:
        return None
    prev = _safe_float(closes.iloc[-2])
    curr = _safe_float(closes.iloc[-1])
    if prev is None or curr is None or prev == 0:
        return None
    return round((curr / prev - 1) * 100, 2)


def fetch_technical(ticker: str, qqq_hist: pd.DataFrame | None = None) -> dict[str, Any]:
    """拉取并计算 Weinstein 技术指标。qqq_hist 传入可复用，避免重复请求。"""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y", interval="1d", auto_adjust=True)
        if hist.empty:
            return {"error": "no data"}

        hist.index = pd.to_datetime(hist.index)

        # 确保 1D Series，防止 yfinance 新版返回多级列 DataFrame
        closes = _to_series(hist["Close"]).dropna()
        volumes = _to_series(hist["Volume"]).dropna()
        highs = _to_series(hist["High"]).dropna()

        if len(closes) < 30:
            return {"error": "insufficient data"}

        close = _safe_float(closes.iloc[-1])

        # 移动平均
        ma50_s = closes.rolling(50).mean()
        ma150_s = closes.rolling(150).mean()
        ma200_s = closes.rolling(200).mean()
        ma50 = _safe_float(ma50_s.iloc[-1]) if len(closes) >= 50 else None
        ma150 = _safe_float(ma150_s.iloc[-1]) if len(closes) >= 150 else None
        ma200 = _safe_float(ma200_s.iloc[-1]) if len(closes) >= 200 else None

        # MACD(12,26,9)
        macd_line_s, macd_signal_s, macd_hist_s = _calc_macd(closes)
        macd_line = _safe_float(macd_line_s.iloc[-1])
        macd_signal = _safe_float(macd_signal_s.iloc[-1])
        macd_hist = _safe_float(macd_hist_s.iloc[-1])
        macd_hist_slope = _macd_hist_slope_sign(macd_hist_s, bars=5)

        # 量能 vs 20 日均量（与收盘价日期对齐）
        vol_aligned = volumes.reindex(closes.index, method="ffill")
        vol_ma20 = vol_aligned.rolling(20).mean()
        vol_last = _safe_float(vol_aligned.iloc[-1]) if len(vol_aligned) else None
        vol_ma20_last = _safe_float(vol_ma20.iloc[-1]) if len(vol_aligned) >= 20 else None
        volume_vs_ma20 = (
            round(vol_last / vol_ma20_last, 2) if (vol_last and vol_ma20_last and vol_ma20_last > 0) else None
        )

        # MA50 vs MA200 金叉语义
        cross50_200 = _ma50_ma200_cross_info(ma50_s, ma200_s)
        ma50_above_ma200 = cross50_200.get("ma50_above_ma200")

        # 52w high
        high_52w = _safe_float(closes.iloc[-252:].max()) if len(closes) >= 10 else close
        pullback = round((close / high_52w - 1) * 100, 2) if (high_52w and close) else None

        # MA150 偏离 & 斜率
        pct_vs_ma150 = round((close / ma150 - 1) * 100, 2) if (ma150 and close) else None
        ma150_slope_4w = None
        if ma150 and len(closes) >= 170:
            ma150_20ago = _safe_float(closes.rolling(150).mean().iloc[-21])
            if ma150_20ago and ma150_20ago != 0:
                ma150_slope_4w = round((ma150 / ma150_20ago - 1) * 100, 2)

        # RSI
        rsi14 = _calc_rsi(closes, 14)

        # RS vs QQQ
        rs_slope_3m = None
        if qqq_hist is not None and not qqq_hist.empty:
            qqq_closes = _to_series(qqq_hist["Close"]).dropna()
            rs_slope_3m = _calc_rs_slope(closes, qqq_closes, days=63)

        # 涨跌量比
        vol_ratio = _calc_vol_ratio(closes, volumes, lookback=20)

        # OBV 趋势
        obv_trend = _calc_obv_trend(closes, volumes, lookback=60)

        # 月度高点趋势
        monthly_highs_trend = _monthly_highs_trend(highs)

        # 均线交叉
        ma50_above_ma150 = bool(ma50 and ma150 and ma50 > ma150)
        ma150_above_ma200 = bool(ma150 and ma200 and ma150 > ma200)

        ext_label = _extension_label(pct_vs_ma150)
        trend_buy = _trend_buy_assessment(
            pct_vs_ma150=pct_vs_ma150,
            ma150_slope_4w=ma150_slope_4w,
            rsi14=rsi14,
            ma50_above_ma150=ma50_above_ma150,
            ma150_above_ma200=ma150_above_ma200,
            ma50_above_ma200=bool(ma50_above_ma200) if ma50_above_ma200 is not None else None,
            macd_hist=macd_hist,
            macd_hist_slope=macd_hist_slope,
            volume_vs_ma20=volume_vs_ma20,
            extension_label=ext_label,
            last_cross_event=cross50_200.get("last_cross_event"),
            bars_since_cross=cross50_200.get("bars_since_cross"),
            pullback_from_52w=pullback,
        )

        # 3月振幅
        range_3m_pct = None
        if len(closes) >= 63:
            last63 = closes.iloc[-63:]
            lo = _safe_float(last63.min())
            hi = _safe_float(last63.max())
            if lo and hi and lo != 0:
                range_3m_pct = round((hi / lo - 1) * 100, 2)

        score = _weinstein_score(
            pct_vs_ma150, ma150_slope_4w, rsi14, rs_slope_3m,
            vol_ratio, ma50_above_ma150, ma150_above_ma200,
        )

        golden_label = "—"
        if cross50_200.get("last_cross_event") == "golden":
            b = cross50_200.get("bars_since_cross")
            golden_label = f"金叉≈{b}日前" if b is not None else "金叉(近期)"
        elif cross50_200.get("last_cross_event") == "death":
            b = cross50_200.get("bars_since_cross")
            golden_label = f"死叉≈{b}日前" if b is not None else "死叉(近期)"
        elif ma50_above_ma200 is True:
            golden_label = "MA50>MA200"
        elif ma50_above_ma200 is False:
            golden_label = "MA50<MA200"

        return {
            "close": round(close, 2) if close else None,
            "change_pct": _last_change_pct(closes),
            "high_52w": round(high_52w, 2) if high_52w else None,
            "pullback_from_52w_high": pullback,
            "ma50": round(ma50, 2) if ma50 else None,
            "ma150": round(ma150, 2) if ma150 else None,
            "ma200": round(ma200, 2) if ma200 else None,
            "pct_vs_ma150": pct_vs_ma150,
            "ma150_slope_4w": ma150_slope_4w,
            "rsi14": rsi14,
            "rs_slope_3m": rs_slope_3m,
            "vol_ratio": vol_ratio,
            "volume_vs_ma20": volume_vs_ma20,
            "macd_line": round(macd_line, 4) if macd_line is not None else None,
            "macd_signal": round(macd_signal, 4) if macd_signal is not None else None,
            "macd_hist": round(macd_hist, 4) if macd_hist is not None else None,
            "macd_hist_slope": macd_hist_slope,
            "golden_cross_label": golden_label,
            "obv_trend": obv_trend,
            "monthly_highs_trend": monthly_highs_trend,
            "ma_cross": {
                "ma50_above_ma150": ma50_above_ma150,
                "ma150_above_ma200": ma150_above_ma200,
                "ma50_above_ma200": ma50_above_ma200,
                "golden_cross_state": cross50_200.get("golden_cross_state"),
                "last_cross_event": cross50_200.get("last_cross_event"),
                "bars_since_cross": cross50_200.get("bars_since_cross"),
                "last_cross_date": cross50_200.get("last_cross_date"),
            },
            "range_3m_pct": range_3m_pct,
            "score": score,
            "extension_label": ext_label,
            "trend_buy": trend_buy,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────────
# yfinance 基本面数据
# ──────────────────────────────────────────────────────────────────────────────

def fetch_industry_pe_map(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """一次性拉取所需行业代理 ETF 的 trailingPE，返回 ticker → {proxy, label, pe}。"""
    proxies_needed = {INDUSTRY_PROXY_MAP[t] for t in tickers if t in INDUSTRY_PROXY_MAP}
    proxy_pe: dict[str, float | None] = {}
    for proxy in proxies_needed:
        try:
            info = yf.Ticker(proxy).info or {}
            proxy_pe[proxy] = _safe_float(info.get("trailingPE"))
        except Exception:
            proxy_pe[proxy] = None
    result: dict[str, dict[str, Any]] = {}
    for tk in tickers:
        proxy = INDUSTRY_PROXY_MAP.get(tk)
        result[tk] = {
            "industry_proxy": proxy,
            "industry_label": INDUSTRY_PROXY_LABEL.get(proxy or "", proxy or ""),
            "industry_pe_avg": proxy_pe.get(proxy) if proxy else None,
        }
    return result


def fetch_fundamental(ticker: str, industry_info: dict[str, Any] | None = None) -> dict[str, Any]:
    t = yf.Ticker(ticker)
    info: dict[str, Any] = {}
    try:
        raw = t.info
        if isinstance(raw, dict):
            info = raw
    except Exception:
        pass

    industry_info = industry_info or {}
    result: dict[str, Any] = {
        "name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "industry_proxy": industry_info.get("industry_proxy"),
        "industry_label": industry_info.get("industry_label"),
        "industry_pe_avg": industry_info.get("industry_pe_avg"),
        "market_cap": _safe_float(info.get("marketCap")),
        "pe_ttm": _safe_float(info.get("trailingPE")),
        "pe_fwd": _safe_float(info.get("forwardPE")),
        "ps_ttm": _safe_float(info.get("priceToSalesTrailing12Months")),
        "peg_ratio": _safe_float(info.get("pegRatio")),
        "debt_to_equity": _safe_float(info.get("debtToEquity")),
        "ev_ebitda": _safe_float(info.get("enterpriseToEbitda")),
        "revenue_growth_yoy": _pct(info.get("revenueGrowth")),
        "eps_growth_5y_pct": None,
        "sales_growth_5y_pct": None,
        "eps_growth_this_y_pct": None,
        "eps_growth_next_y_pct": None,
        "eps_growth_next_5y_pct": None,
        "eps_growth_qoq_pct": None,
        "sales_growth_qoq_pct": None,
        "gross_margin": _pct(info.get("grossMargins")),
        "operating_margin": _pct(info.get("operatingMargins")),
        "free_cashflow": _safe_float(info.get("freeCashflow")),
        "analyst_target": _safe_float(info.get("targetMeanPrice")),
        "analyst_rating": info.get("recommendationKey"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "eps_history": [],
        "quarterly_revenue": [],
        "analyst_breakdown": None,
        "next_earnings_date": None,
        "eps_guidance_range": None,
        "revenue_guidance_range": None,
    }

    # ── EPS history（最近4季）─────────────────────────────────────────────
    try:
        eh = t.earnings_history
        if eh is not None and not isinstance(eh, type(None)) and len(eh) > 0:
            eh = eh.sort_index(ascending=False).head(4)
            rows = []
            for _, row in eh.iterrows():
                rows.append({
                    "date": str(row.name.date()) if hasattr(row.name, "date") else str(row.name),
                    "eps_actual": _safe_float(_to_scalar(row.get("epsActual"))),
                    "eps_estimate": _safe_float(_to_scalar(row.get("epsEstimate"))),
                    "surprise_pct": _safe_float(_to_scalar(row.get("surprisePercent"))),
                })
            result["eps_history"] = rows
    except Exception:
        pass

    # ── 分析师买卖分布 ─────────────────────────────────────────────────────
    try:
        rs = t.recommendations_summary
        if rs is not None and len(rs) > 0:
            latest = rs.sort_index(ascending=False).iloc[0]
            result["analyst_breakdown"] = {
                "strongBuy": int(_to_scalar(latest.get("strongBuy")) or 0),
                "buy": int(_to_scalar(latest.get("buy")) or 0),
                "hold": int(_to_scalar(latest.get("hold")) or 0),
                "sell": int(_to_scalar(latest.get("sell")) or 0),
                "strongSell": int(_to_scalar(latest.get("strongSell")) or 0),
            }
    except Exception:
        pass

    # ── 季度营收 ───────────────────────────────────────────────────────────
    try:
        stmt = t.quarterly_income_stmt
        if stmt is not None and not stmt.empty:
            rev_row = None
            for idx_name in ["Total Revenue", "TotalRevenue"]:
                if idx_name in stmt.index:
                    raw_row = stmt.loc[idx_name]
                    # 防止重复行返回 DataFrame
                    if isinstance(raw_row, pd.DataFrame):
                        raw_row = raw_row.iloc[0]
                    rev_row = raw_row
                    break
            if rev_row is not None:
                sorted_cols = sorted(rev_row.index, reverse=True)[:4]
                rev_rows = []
                for col in sorted_cols:
                    val = _safe_float(_to_scalar(rev_row[col]))
                    rev_rows.append({
                        "date": str(col.date()) if hasattr(col, "date") else str(col),
                        "revenue": val,
                        "qoq_pct": None,
                    })
                # 计算 QoQ
                for i in range(len(rev_rows) - 1):
                    curr = rev_rows[i]["revenue"]
                    prev = rev_rows[i + 1]["revenue"]
                    if curr and prev and prev != 0:
                        rev_rows[i]["qoq_pct"] = round((curr / prev - 1) * 100, 2)
                result["quarterly_revenue"] = rev_rows
                result["sales_growth_qoq_pct"] = rev_rows[0].get("qoq_pct") if rev_rows else None
    except Exception:
        pass

    # ── Finviz 风格成长/杠杆扩展指标 ───────────────────────────────────────
    result["eps_growth_5y_pct"] = _annual_cagr(t, ["Diluted EPS", "Basic EPS"])
    result["sales_growth_5y_pct"] = _annual_cagr(t, ["Total Revenue", "TotalRevenue"])
    result["eps_growth_this_y_pct"] = _estimate_growth_pct(t, "0y")
    result["eps_growth_next_y_pct"] = _estimate_growth_pct(t, "+1y")
    result["eps_growth_next_5y_pct"] = _ltg_growth_pct(t)
    result["eps_growth_qoq_pct"] = _quarterly_qoq_pct(t, ["Diluted EPS", "Basic EPS"])

    # ── 下次财报日 & EPS/Revenue 指引 ──────────────────────────────────────
    try:
        cal = t.calendar
        if cal is not None:
            # 处理 dict 和 DataFrame 两种返回格式
            if isinstance(cal, pd.DataFrame):
                cal = cal.to_dict()
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed is not None:
                    if isinstance(ed, (list, pd.Series, np.ndarray)):
                        dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in ed]
                        result["next_earnings_date"] = dates[0] if dates else None
                    else:
                        result["next_earnings_date"] = str(ed)
                result["eps_guidance_range"] = {
                    "low": _safe_float(_to_scalar(cal.get("Earnings Low"))),
                    "high": _safe_float(_to_scalar(cal.get("Earnings High"))),
                    "avg": _safe_float(_to_scalar(cal.get("Earnings Average"))),
                }
                result["revenue_guidance_range"] = {
                    "low": _safe_float(_to_scalar(cal.get("Revenue Low"))),
                    "high": _safe_float(_to_scalar(cal.get("Revenue High"))),
                    "avg": _safe_float(_to_scalar(cal.get("Revenue Average"))),
                }
    except Exception:
        pass

    return result


# ──────────────────────────────────────────────────────────────────────────────
# 图表生成（matplotlib Weinstein 风格）
# ──────────────────────────────────────────────────────────────────────────────

def generate_chart_png(ticker: str) -> bytes:
    """生成 Weinstein 技术图表 PNG，返回 bytes，并缓存到磁盘。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    t = yf.Ticker(ticker)
    hist = t.history(period="2y", interval="1d", auto_adjust=True)
    if hist.empty:
        raise ValueError(f"no data for {ticker}")

    hist.index = pd.to_datetime(hist.index)
    closes = _to_series(hist["Close"]).dropna()
    volumes = _to_series(hist["Volume"]).dropna()

    qqq = yf.Ticker("QQQ")
    qqq_hist = qqq.history(period="2y", interval="1d", auto_adjust=True)
    qqq_closes = _to_series(qqq_hist["Close"]).dropna() if not qqq_hist.empty else pd.Series(dtype=float)

    ma50 = closes.rolling(50).mean()
    ma150 = closes.rolling(150).mean()
    rsi_series = _calc_rsi_series(closes, 14)
    macd_line, macd_signal, macd_hist = _calc_macd(closes)

    fig, axes = plt.subplots(
        5, 1, figsize=(12, 11),
        sharex=True,
        gridspec_kw={"height_ratios": [3.0, 1.0, 1.0, 1.15, 1.0]},
        facecolor="#0e1117",
    )
    fig.suptitle(ticker, color="#dce1ff", fontsize=14, fontweight="bold")

    ax1 = axes[0]
    ax1.set_facecolor("#161A1E")
    ax1.plot(closes.index, closes.values, color="#8fb4f8", linewidth=1.2, label="Price")
    ax1.plot(ma50.index, ma50.values, color="#5bc8f5", linewidth=1.0, label="MA50", alpha=0.85)
    ax1.plot(ma150.index, ma150.values, color="#f97316", linewidth=1.2, label="MA150")
    ax1.set_ylabel("Price", color="#8d90a2")
    ax1.tick_params(colors="#8d90a2")
    ax1.legend(facecolor="#1e232b", labelcolor="#dce1ff", fontsize=8)
    ax1.grid(color="#2B2F36", linewidth=0.5, alpha=0.6)
    for spine in ax1.spines.values():
        spine.set_color("#2B2F36")

    ax2 = axes[1]
    ax2.set_facecolor("#161A1E")
    close_arr = closes.reindex(volumes.index, method="ffill")
    open_arr = _to_series(hist["Open"]).dropna().reindex(volumes.index, method="ffill")
    colors = [
        "#e74c3c" if (c < o) else "#2ecc71"
        for c, o in zip(close_arr.values, open_arr.values)
    ]
    ax2.bar(volumes.index, volumes.values, color=colors, alpha=0.7, width=1)
    ax2.set_ylabel("Volume", color="#8d90a2", fontsize=8)
    ax2.tick_params(colors="#8d90a2", labelsize=7)
    ax2.grid(color="#2B2F36", linewidth=0.5, alpha=0.6)
    for spine in ax2.spines.values():
        spine.set_color("#2B2F36")

    ax_rsi = axes[2]
    ax_rsi.set_facecolor("#161A1E")
    rsi_plot = rsi_series.dropna()
    if len(rsi_plot) > 0:
        ax_rsi.plot(rsi_plot.index, rsi_plot.values, color="#eab308", linewidth=1.0, label="RSI(14)")
    ax_rsi.axhline(70, color="#f87171", linewidth=0.6, linestyle="--", alpha=0.75)
    ax_rsi.axhline(30, color="#22c55e", linewidth=0.6, linestyle="--", alpha=0.75)
    ax_rsi.set_ylabel("RSI", color="#8d90a2", fontsize=8)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.tick_params(colors="#8d90a2", labelsize=7)
    ax_rsi.legend(facecolor="#1e232b", labelcolor="#dce1ff", fontsize=7, loc="upper left")
    ax_rsi.grid(color="#2B2F36", linewidth=0.5, alpha=0.6)
    for spine in ax_rsi.spines.values():
        spine.set_color("#2B2F36")

    ax_macd = axes[3]
    ax_macd.set_facecolor("#161A1E")
    mh = macd_hist.fillna(0)
    bar_colors = ["#2ecc71" if float(v) >= 0 else "#e74c3c" for v in mh.values]
    ax_macd.bar(mh.index, mh.values, color=bar_colors, alpha=0.55, width=1, label="Histogram")
    ax_macd.plot(macd_line.index, macd_line.values, color="#5bc8f5", linewidth=0.9, label="MACD")
    ax_macd.plot(macd_signal.index, macd_signal.values, color="#f97316", linewidth=0.9, label="Signal")
    ax_macd.axhline(0, color="#8d90a2", linewidth=0.5, alpha=0.6)
    ax_macd.set_ylabel("MACD", color="#8d90a2", fontsize=8)
    ax_macd.tick_params(colors="#8d90a2", labelsize=7)
    ax_macd.legend(facecolor="#1e232b", labelcolor="#dce1ff", fontsize=6, loc="upper left", ncol=3)
    ax_macd.grid(color="#2B2F36", linewidth=0.5, alpha=0.6)
    for spine in ax_macd.spines.values():
        spine.set_color("#2B2F36")

    ax5 = axes[4]
    ax5.set_facecolor("#161A1E")
    if not qqq_closes.empty:
        s1 = closes.rename("ticker")
        s2 = qqq_closes.rename("ref")
        aligned = pd.concat([s1, s2], axis=1, join="inner").dropna()
        if len(aligned) > 5:
            rs = aligned["ticker"] / aligned["ref"]
            ax5.plot(rs.index, rs.values, color="#a78bfa", linewidth=1.0, label="RS vs QQQ")
            ax5.set_ylabel("RS vs QQQ", color="#8d90a2", fontsize=8)
            ax5.legend(facecolor="#1e232b", labelcolor="#dce1ff", fontsize=7)
    ax5.tick_params(colors="#8d90a2", labelsize=7)
    ax5.grid(color="#2B2F36", linewidth=0.5, alpha=0.6)
    for spine in ax5.spines.values():
        spine.set_color("#2B2F36")

    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%y/%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, fontsize=7, color="#8d90a2")

    plt.tight_layout(rect=[0, 0, 1, 0.97])

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor="#0e1117", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img_bytes = buf.read()

    chart_path = CHARTS_DIR / f"{ticker}.png"
    chart_path.write_bytes(img_bytes)
    return img_bytes


def get_chart_png(ticker: str, force_regenerate: bool = False) -> bytes | None:
    chart_path = CHARTS_DIR / f"{ticker}.png"
    today = datetime.now().date()
    if not force_regenerate and chart_path.exists():
        mtime = datetime.fromtimestamp(chart_path.stat().st_mtime).date()
        if mtime == today:
            return chart_path.read_bytes()
    try:
        return generate_chart_png(ticker)
    except Exception:
        if chart_path.exists():
            return chart_path.read_bytes()
        return None


# ──────────────────────────────────────────────────────────────────────────────
# LLM 分析
# ──────────────────────────────────────────────────────────────────────────────

def _get_deep_llm():
    cfg = DEFAULT_CONFIG.copy()
    cfg["llm_provider"] = _DEEP_PROVIDER
    cfg["deep_think_llm"] = _DEEP_MODEL
    cfg["backend_url"] = _PROVIDER_URL
    client = create_llm_client(
        provider=cfg["llm_provider"],
        model=cfg["deep_think_llm"],
        base_url=cfg["backend_url"],
    )
    return client.get_llm()


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError("no JSON array in model output")


def _msg_text(resp: Any) -> str:
    if hasattr(resp, "content"):
        normalize_content(resp)
        c = resp.content
        return c if isinstance(c, str) else str(c)
    return str(resp)


def run_llm_analysis(ticker_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ticker_data:
        return []
    lines = []
    for d in ticker_data:
        tk = d.get("ticker", "")
        tech = d.get("technical", {})
        fund = d.get("fundamental", {})
        eps_h = (fund.get("eps_history") or [])[:4]
        eps_str = ", ".join(
            f"Q{i+1}: {e.get('surprise_pct', 'N/A')}%" for i, e in enumerate(eps_h)
        )
        qrev = (fund.get("quarterly_revenue") or [])[:4]
        qrev_str = ", ".join(
            f"Q{i+1}: {r.get('qoq_pct', 'N/A')}% QoQ" for i, r in enumerate(qrev)
        )
        tb = tech.get("trend_buy") if isinstance(tech.get("trend_buy"), dict) else {}
        tb_verdict = tb.get("verdict", "")
        tb_line = (tb.get("one_liner") or "").replace("\n", " ")[:120]
        conds = tb.get("conditions_if_not_buy") or []
        cond_str = "; ".join(str(c) for c in conds[:4]) if conds else ""
        lines.append(
            f"- {tk}: "
            f"close={tech.get('close')} ma50={tech.get('ma50')} ma150={tech.get('ma150')} "
            f"pct_vs_ma150={tech.get('pct_vs_ma150')}% ma150_slope={tech.get('ma150_slope_4w')}% "
            f"rsi14={tech.get('rsi14')} rs_3m={tech.get('rs_slope_3m')} score={tech.get('score')}/9 "
            f"macd_hist={tech.get('macd_hist')} macd_slope={tech.get('macd_hist_slope')} "
            f"vol_vs_ma20={tech.get('volume_vs_ma20')} golden={tech.get('golden_cross_label')} "
            f"rule_buy_verdict={tb_verdict} rule_summary={tb_line} "
            f"rule_if_not_buy=[{cond_str}] "
            f"pe_ttm={fund.get('pe_ttm')} rev_growth={fund.get('revenue_growth_yoy')}% "
            f"gross_margin={fund.get('gross_margin')}% eps_beats=[{eps_str}] "
            f"qrev_qoq=[{qrev_str}] next_earnings={fund.get('next_earnings_date')}"
        )

    block = "\n".join(lines)
    prompt = f"""你是专业的 Weinstein 趋势分析师，使用威科夫-韦恩斯坦阶段分析体系。

以下是 {len(ticker_data)} 只 AI 算力产业链核心股票的技术面与基本面数据：

{block}

每条数据中的 rule_buy_verdict / rule_summary / rule_if_not_buy 来自代码规则化「趋势买点」初判（含 MACD、量能、均线结构与延伸度）。请将其作为重要参考：
- 若你的阶段判断（stage_label）或买点类型（action_type）与规则化结论明显冲突，以价格/均线/RSI/MACD 等客观数据为准，并在 stage_narrative 中用一两句话解释差异原因。
- next_buy_guidance 应优先呼应 rule_if_not_buy 中的可验证条件（可改写得更具体），除非数据证明规则已失效。

请对每只股票输出一个 JSON 对象（严格数组），包含以下字段：
- ticker: 股票代码
- stage_label: 阶段判断（枚举：Stage 1 / Stage 2 早期 / Stage 2 中后期 / Stage 3 / Stage 4）
- stage_narrative: 不超过150字的中文阶段叙述
- action_type: 买点类型（枚举：买点A候选 / 买点A/B低偏离区 / 买点B等待区 / 延伸后等回踩 / 等待MA150上拐 / 禁追）
- next_buy_guidance: 买点价格指引（如"等回踩MA50-MA150×1.1区间，RS不破位"，简洁）
- stop_reference: 止损参考价格（数字，推荐MA150×0.92）
- catalysts: 关键催化剂数组（2-4条，结合财报日、行业事件）
- revenue_surprise_assessment: 收入超预期评估（1-2句中文，基于QoQ趋势）
- confidence: 分析置信度（high / medium / low）

要求：
1. 输出纯 JSON 数组，无 markdown 围栏，无额外文字
2. 严格遵守枚举约束
3. catalysts 数组包含下次财报日期
"""
    llm = _get_deep_llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    raw = _msg_text(resp)
    return _parse_json_array(raw)


# ──────────────────────────────────────────────────────────────────────────────
# 持久化
# ──────────────────────────────────────────────────────────────────────────────

def load_latest() -> dict[str, Any]:
    if LATEST_JSON.exists():
        try:
            return json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema_version": "1.0", "updated_at": None, "status": "empty", "tickers": []}


def save_latest(data: dict[str, Any]) -> None:
    LATEST_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# 刷新主流程
# ──────────────────────────────────────────────────────────────────────────────

def _run_refresh(job_id: str) -> None:
    """后台线程：拉取所有技术+基本面数据，生成图表，调用 LLM，写 JSON。"""
    try:
        qqq = yf.Ticker("QQQ")
        qqq_hist = qqq.history(period="2y", interval="1d", auto_adjust=True)

        # 行业代理 ETF 的 PE 一次性预取
        industry_map = fetch_industry_pe_map(CORE_TICKERS)

        collected: list[dict[str, Any]] = []

        for ticker in CORE_TICKERS:
            with _JOB_LOCK:
                if job_id in _JOBS:
                    _JOBS[job_id].progress = ticker
                    _JOBS[job_id].updated_at = _now_iso()

            tech = fetch_technical(ticker, qqq_hist=qqq_hist)
            fund = fetch_fundamental(ticker, industry_info=industry_map.get(ticker))

            try:
                generate_chart_png(ticker)
            except Exception:
                pass

            collected.append({
                "ticker": ticker,
                "technical": tech,
                "fundamental": fund,
            })

        # LLM 批量分析
        llm_results: list[dict[str, Any]] = []
        try:
            with _JOB_LOCK:
                if job_id in _JOBS:
                    _JOBS[job_id].progress = "LLM 分析中..."
                    _JOBS[job_id].updated_at = _now_iso()
            llm_results = run_llm_analysis(collected)
        except Exception as e:
            llm_results = [{"ticker": d["ticker"], "error": str(e)} for d in collected]

        llm_map = {r.get("ticker"): r for r in llm_results if isinstance(r, dict)}
        tickers_out = []
        for d in collected:
            ticker = d["ticker"]
            llm = llm_map.get(ticker, {})
            tickers_out.append({
                "ticker": ticker,
                "name": d["fundamental"].get("name", ticker),
                "technical": d["technical"],
                "fundamental": d["fundamental"],
                "llm": {
                    "stage_label": llm.get("stage_label", "待分析"),
                    "stage_narrative": llm.get("stage_narrative", ""),
                    "action_type": llm.get("action_type", "待分析"),
                    "next_buy_guidance": llm.get("next_buy_guidance", ""),
                    "stop_reference": llm.get("stop_reference"),
                    "catalysts": llm.get("catalysts", []),
                    "revenue_surprise_assessment": llm.get("revenue_surprise_assessment", ""),
                    "confidence": llm.get("confidence", "low"),
                    "error": llm.get("error"),
                },
            })

        payload = {
            "schema_version": "1.0",
            "updated_at": _now_iso(),
            "status": "ready",
            "tickers": tickers_out,
        }
        save_latest(payload)

        with _JOB_LOCK:
            if job_id in _JOBS:
                _JOBS[job_id].status = "completed"
                _JOBS[job_id].updated_at = _now_iso()
                _JOBS[job_id].progress = "done"
                _JOBS[job_id].result = {"updated_at": payload["updated_at"]}

    except Exception as exc:
        with _JOB_LOCK:
            if job_id in _JOBS:
                _JOBS[job_id].status = "failed"
                _JOBS[job_id].updated_at = _now_iso()
                _JOBS[job_id].error = str(exc)


def create_refresh_job() -> TrackerJob:
    job_id = uuid.uuid4().hex
    job = TrackerJob(
        job_id=job_id,
        status="running",
        created_at=_now_iso(),
        progress="starting",
    )
    with _JOB_LOCK:
        _JOBS[job_id] = job
    th = threading.Thread(target=_run_refresh, args=(job_id,), daemon=True)
    th.start()
    return job


def get_tracker_job(job_id: str) -> TrackerJob | None:
    with _JOB_LOCK:
        return _JOBS.get(job_id)
