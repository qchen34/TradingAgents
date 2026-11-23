# 趋势框架回测规则手册 v1

> 创建：2026-05-14  
> 原则：每一条规则必须是可以从历史数据计算的，不能包含任何主观判断。  
> 对应框架：`trend_framework_learning_v1.md`  
> 回测语言：Python / pandas / yfinance

---

## 0. 核心设计原则（专业量化的标准）

在写任何规则之前，先理解规则设计的底线要求：

**① 无歧义（No Ambiguity）**  
"回踩 MA150 附近"不是规则。  
"`close` 在 `MA150 × 1.00` 到 `MA150 × 1.12` 之间"是规则。

**② 前视干净（No Look-Ahead Bias）**  
规则只能用"截止到当周收盘"已知的数据，不能用未来数据。  
滚动均线、ATR 等指标天然满足，但"下周还在涨"这种判断不满足。

**③ 完整闭环（Entry + Exit = Complete System）**  
只有买入规则没有卖出规则，不是策略，是赌博。  
每一条买入规则，必须配套止损规则和退出规则。

**④ 参数可变（Parameter Sensitivity）**  
规则里的每个数字（比如 `< 0.12`、`> 0.3`、`RSI < 55`）都是参数。  
回测后必须做敏感性测试：把参数各改 ±20%，如果结果崩了，说明过拟合。

**⑤ 样本够大（Statistical Significance）**  
单只股票的回测没有意义。需要跨多只股票、多个市场周期验证。  
目标：至少 30 笔以上的交易记录，才能开始谈胜率。

---

## 1. 数据准备规格

```python
# 数据频率：周线（weekly）
# 最少历史：5年（约 260 周）
# 必须字段：
#   close, high, low, open, volume
#   MA10w  = close.rolling(10).mean()   # 约 50 日均线
#   MA30w  = close.rolling(30).mean()   # 约 150 日均线（Weinstein 核心）
#   MA40w  = close.rolling(40).mean()   # 约 200 日均线
#   MA30_slope = MA30w.diff(4)          # 4 周斜率变化（判断阶段的关键）
#   ATR14  = 14 周平均真实波动幅度
#   RSI14  = 14 周 RSI
#   pct_vs_ma30 = (close / MA30w - 1) * 100
#   vol_ratio   = volume / volume.rolling(10).mean()
#   rs_line     = close / benchmark_close  # SPY 或 QQQ 作为基准

# 基准数据（用于市场环境 Layer 1）：
#   SPY 周线 close
#   SPY_MA40w = SPY.close.rolling(40).mean()
```

---

## 2. Layer 1：市场环境过滤器

**规则 M1（基础大盘过滤）：**
```
condition_M1 = SPY_close > SPY_MA40w
```
> 含义：S&P500 在 200 日均线以上，才允许建新仓。  
> 不满足时：现有持仓继续持有（不止损），但不开新仓。

**规则 M2（可选增强，需额外数据）：**
```
condition_M2 = new_highs_count > new_lows_count  # 需要市场广度数据
```
> 简化替代方案：用 SPY 的 MA10w > MA30w 作为代理指标。

**Layer 1 通过条件（二选一，简化版用 M1）：**
```python
market_ok = (SPY_close > SPY_MA40w)
```

---

## 3. Layer 2：个股阶段分类规则

每周对每只股票执行一次分类，输出 Stage 标签：

```python
def classify_stage(close, ma30, ma30_slope, ma10):
    """
    输入：当周数据（单行）
    输出：'Stage4' / 'Stage1' / 'Stage2' / 'Stage2_ext' / 'Stage3'
    """
    if pd.isna(ma30) or pd.isna(ma30_slope):
        return 'unknown'

    pct = (close / ma30 - 1) * 100

    # Stage 4：股价在 MA30 下方，且 MA30 斜率明显向下
    if close < ma30 and ma30_slope < -0.15:
        return 'Stage4'

    # Stage 3：MA30 斜率从正转负（曾经 > 0.5，现在 < 0），且股价在 MA30 附近或以下
    # (需要前几周数据，由调用方传入，此处简化)
    if close < ma30 * 1.05 and ma30_slope < 0:
        return 'Stage3'

    # Stage 1：MA30 斜率极小（趋于平稳），股价在 MA30 ±15% 内
    if abs(ma30_slope) < 0.15 and abs(pct) < 15:
        return 'Stage1'

    # Stage 2 延伸区：趋势向上但偏离过大
    if ma30_slope > 0.05 and close > ma30 and pct > 30:
        return 'Stage2_ext'

    # Stage 2 健康区：MA30 向上，股价在 MA30 上方，偏离合理
    if ma30_slope > 0.05 and close > ma30:
        return 'Stage2'

    # 其余情况归入 Stage1（过渡区）
    return 'Stage1'
```

---

## 4. Layer 3+4：买入信号规则

### 4.1 买点 A（趋势启动确认买点）

**触发条件（全部满足）：**

| 编号 | 条件 | 含义 |
|------|------|------|
| A1 | `ma30_slope > 0` 且上周 `ma30_slope_prev <= 0` | MA30 斜率本周首次转正 |
| A2 | `close > ma30` | 股价在 MA30 上方 |
| A3 | `pct_vs_ma30 < 30` | 偏离 MA30 不超过 30%（非过度延伸）|
| A4 | `RSI14 < 82` | 排除极度超买 |
| A5 | `vol_ratio >= 1.0` | 成交量不低于 10 周均量（无量突破不算）|
| A6 | `market_ok == True` | 大盘环境通过 Layer 1 |

```python
def signal_buy_a(row, prev_row, market_ok):
    if not market_ok: return False
    if pd.isna(row['ma30_slope']) or pd.isna(prev_row['ma30_slope']): return False
    A1 = row['ma30_slope'] > 0 and prev_row['ma30_slope'] <= 0
    A2 = row['close'] > row['ma30']
    A3 = row['pct_vs_ma30'] < 30
    A4 = row['rsi14'] < 82
    A5 = row['vol_ratio'] >= 1.0
    return A1 and A2 and A3 and A4 and A5
```

**预期特征：**
- 信号稀少（每只股票每次 Stage 1→2 转换只出现一次）
- 入场时价格可能已从底部涨 20-50%（正常，框架用安全换时机）
- 高 RSI 是正常的（突破往往伴随动能）

---

### 4.2 买点 B（趋势中期回踩买点）

**触发条件（全部满足）：**

| 编号 | 条件 | 含义 |
|------|------|------|
| B1 | `stage == 'Stage2'`（至少持续 8 周）| 确保是中期趋势，不是刚进 Stage2 |
| B2 | `ma30_slope > 0.3` | MA30 有实质向上斜率（不是刚转正）|
| B3 | `0 < pct_vs_ma30 < 12` | 股价回踩至 MA30 上方 0-12% 内 |
| B4 | `close > ma30` | 没有跌破 MA30 |
| B5 | `RSI14 < 55` | RSI 已经从高位回落 |
| B6 | `vol_ratio < 1.5` | 回踩时成交量不放大（不是恐慌性抛售）|
| B7 | `market_ok == True` | 大盘环境通过 Layer 1 |

```python
def signal_buy_b(row, stage2_weeks, market_ok):
    if not market_ok: return False
    if stage2_weeks < 8: return False  # 至少在 Stage2 里 8 周了
    if pd.isna(row['ma30_slope']) or pd.isna(row['pct_vs_ma30']): return False
    B1 = True  # stage2_weeks >= 8 已检查
    B2 = row['ma30_slope'] > 0.3
    B3 = 0 < row['pct_vs_ma30'] < 12
    B4 = row['close'] > row['ma30']
    B5 = row['rsi14'] < 55
    B6 = row['vol_ratio'] < 1.5
    return B2 and B3 and B4 and B5 and B6
```

**预期特征：**
- 买点 B 入场时情绪往往是"AI 热度消退了""横盘好久没动"
- 这正是框架的优势：在别人失去耐心时，规则告诉你结构完好

---

## 5. Layer 5：止损与退出规则

### 5.1 硬止损（Hard Stop）

```python
HARD_STOP_PCT = -0.08  # -8%

def check_hard_stop(current_close, entry_price):
    return (current_close / entry_price - 1) < HARD_STOP_PCT
```

> **为什么是 -8%？**  
> Minervini 和 O'Neil 都用 -7~-8%。原因：如果一个 Stage 2 趋势健康，正常回踩很少超过 -8%（除非叙事崩塌）。  
> 触发 -8% 止损，说明这次买点判断可能有误，必须出场等待重新评估。

### 5.2 趋势止损（Trend Stop）

```python
def check_trend_stop(current_close, ma30, ma30_slope):
    price_below_ma30 = current_close < ma30
    slope_turning_negative = ma30_slope < -0.1
    return price_below_ma30 and slope_turning_negative
```

> 含义：股价跌破 MA30 且 MA30 斜率转负，说明 Stage 2 可能结束，进入 Stage 3。

### 5.3 时间止损（Time Stop，可选）

```python
TIME_STOP_WEEKS = 13  # 3 个月内没有超过 10% 的盈利，考虑退出

def check_time_stop(weeks_held, current_gain_pct):
    return weeks_held > TIME_STOP_WEEKS and current_gain_pct < 0.10
```

> 含义：如果买入后 13 周（约 3 个月）仍然没有 10% 的盈利，说明这只股票的动能不足，资金可以移到更强的标的。

### 5.4 止损执行优先级

```
1. 硬止损（-8%）        → 当周收盘即执行，无条件
2. 趋势止损             → 当周收盘执行
3. 时间止损             → 下周开盘执行（不紧急）
```

---

## 6. 仓位管理规则

```python
# 单笔交易风险控制
MAX_RISK_PER_TRADE = 0.02   # 每笔交易最多亏损组合总值的 2%
HARD_STOP_PCT = 0.08

# 由此推导每笔仓位大小：
# position_size = portfolio_value × MAX_RISK_PER_TRADE / HARD_STOP_PCT
# 例：组合 $100,000，每笔最多亏 $2,000，止损 8%
#     position_size = 100000 × 0.02 / 0.08 = $25,000（占组合 25%）

# 最大同时持仓数
MAX_POSITIONS = 4

# 单只标的上限
MAX_SINGLE_POSITION_PCT = 0.30  # 单只不超过组合 30%

# 买点 A 仓位（首次建仓）
BUY_A_SIZE = 0.5   # 用上述计算出的仓位大小的 50%

# 买点 B 或突破确认后加仓
BUY_B_SIZE = 0.5   # 剩余 50%（仅当第一笔已经盈利 5%+ 才加）
```

---

## 7. 完整交易状态机（Python 伪代码）

```python
class Position:
    def __init__(self, ticker, entry_price, entry_date, signal_type, shares):
        self.ticker = ticker
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.signal_type = signal_type  # 'A' or 'B'
        self.shares = shares
        self.weeks_held = 0

class BacktestEngine:
    def __init__(self, initial_capital=100000):
        self.capital = initial_capital
        self.positions = {}   # {ticker: Position}
        self.trade_log = []

    def run_week(self, week_data, spy_data):
        """
        week_data: {ticker: {close, ma30, ma30_slope, rsi14, ...}}
        """
        market_ok = spy_data['close'] > spy_data['ma40w']

        # Step 1: 检查现有持仓的止损
        for ticker, pos in list(self.positions.items()):
            row = week_data[ticker]
            pos.weeks_held += 1

            # 硬止损
            if check_hard_stop(row['close'], pos.entry_price):
                self._close_position(ticker, row['close'], 'hard_stop')
                continue

            # 趋势止损
            if check_trend_stop(row['close'], row['ma30'], row['ma30_slope']):
                self._close_position(ticker, row['close'], 'trend_stop')
                continue

            # 时间止损（可选）
            gain = row['close'] / pos.entry_price - 1
            if check_time_stop(pos.weeks_held, gain):
                self._close_position(ticker, row['close'], 'time_stop')

        # Step 2: 扫描买入信号（仅在有空余资金和仓位槽时）
        if len(self.positions) < MAX_POSITIONS and self.capital > 1000:
            for ticker, row in week_data.items():
                if ticker in self.positions:
                    continue
                prev_row = get_prev_week(ticker)

                # 计算 Stage2 持续周数
                stage2_weeks = get_stage2_weeks(ticker)

                # 检查信号
                if signal_buy_a(row, prev_row, market_ok):
                    self._open_position(ticker, row['close'], 'A')
                elif signal_buy_b(row, stage2_weeks, market_ok):
                    self._open_position(ticker, row['close'], 'B')
```

---

## 8. 回测验证指标（必须全部输出）

```python
# 基础指标
total_return_pct        # 总收益率
annualized_return_pct   # 年化收益率
max_drawdown_pct        # 最大回撤（从高点到低点）
sharpe_ratio            # 夏普比率 = 超额收益 / 波动率（无风险利率取 4%）
sortino_ratio           # 索提诺比率（只计算下行波动）

# 交易统计
total_trades            # 总交易次数（需要 ≥ 30 才有统计意义）
win_rate                # 胜率 = 盈利笔数 / 总笔数
avg_win_pct             # 平均盈利幅度
avg_loss_pct            # 平均亏损幅度
win_loss_ratio          # 盈亏比 = avg_win / avg_loss
expectancy              # 期望值 = win_rate × avg_win - loss_rate × avg_loss（必须 > 0）
avg_holding_weeks       # 平均持仓周数

# 对标基准
vs_spy_alpha            # 超额收益 vs SPY
vs_buy_hold_alpha       # 超额收益 vs 买入持有

# 敏感性测试输出（把每个参数改 ±20% 后重跑）
sensitivity_table       # 参数扰动 → 指标变化矩阵
```

---

## 9. 回测的常见陷阱（必读）

### 9.1 幸存者偏差
**问题：** 只对现在还在的好公司回测，会高估策略效果。  
**解决：** 包含已退市或已大跌的标的（比如把 2022 年后暴跌的 ARKK 成分股也纳入测试）。

### 9.2 前视偏差（最常见）
**问题：** 用了"当时不知道"的信息，比如用事后修订的 EPS 数据。  
**解决：** 技术指标类（MA、RSI、成交量）没有前视问题；基本面数据要用"point-in-time"版本（即财报发布当日可知的数字）。

### 9.3 过度拟合
**问题：** 参数调到刚好在历史数据上表现完美，但未来失效。  
**解决：**
- 用 in-sample（70%）优化参数，out-of-sample（30%）验证
- 敏感性测试：参数变化 20% 后结果应该方向不变
- 参数越少越好，每多一个参数，过拟合风险翻倍

### 9.4 交易成本
**问题：** 不计入买卖价差和佣金，会高估结果。  
**解决：** 每笔交易假设 0.1% 的买卖价差（周线策略交易频率低，影响不大，但要计入）。

### 9.5 单只股票不足以得出结论
**问题：** NVDA 2023 年的结果无法证明框架有效，它只是样本量为 1。  
**解决：** 用清单里所有 13 只股票跑，再加入 3-5 只"失败案例"（INTC、同期表现差的标的）一起验证。

---

## 10. 参数调优建议范围

回测时，以下参数在合理范围内探索，找到稳健区间（不是最优点）：

| 参数 | 基准值 | 测试范围 |
|------|--------|---------|
| MA30 斜率转正阈值 | 0 | -0.05 ~ +0.1 |
| pct_vs_ma30 上限（买点A）| 30% | 20% ~ 40% |
| pct_vs_ma30 上限（买点B）| 12% | 8% ~ 18% |
| RSI 上限（买点A）| 82 | 75 ~ 90 |
| RSI 上限（买点B）| 55 | 45 ~ 65 |
| 硬止损 | -8% | -6% ~ -10% |
| Stage2 最少持续周数（买点B）| 8 | 6 ~ 12 |
| 时间止损周数 | 13 | 8 ~ 20 |

---

## 11. 推荐回测标的池

**核心观察清单（13只）：** NVDA, AVGO, MU, VRT, GEV, ETN, ANET, MRVL, TER, COHR, ONTO, AMKR, ALAB  
**对照失败案例（必须加入）：** INTC, AMD(部分阶段), SMCI(暴雷前后)  
**宽泛验证（可选）：** SOXX 成分股前 20 只，2019-2024

---

*下一版本（v2）：加入基本面过滤层（forwardPE 区间、RS Rating 阈值），与纯技术版本对比收益差异*
