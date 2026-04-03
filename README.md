<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents：多智能体 LLM 金融交易框架

## 最新动态
- [2026-03] **TradingAgents v0.2.3** 发布，支持多语言、GPT-5.4 系列模型、统一模型目录、回测日期保真和代理支持。
- [2026-03] **TradingAgents v0.2.2** 发布，覆盖 GPT-5.4/Gemini 3.1/Claude 4.6，支持五级评分、OpenAI Responses API、Anthropic effort 控制和跨平台稳定性优化。
- [2026-02] **TradingAgents v0.2.0** 发布，支持多提供商 LLM（GPT-5.x、Gemini 3.x、Claude 4.x、Grok 4.x）并优化系统架构。
- [2026-01] **Trading-R1** [技术报告](https://arxiv.org/abs/2509.11420) 发布，[终端项目](https://github.com/TauricResearch/Trading-R1) 即将推出。

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** 已正式发布！感谢社区对我们工作的热情关注与支持。  
> 因此我们决定完整开源该框架，期待与你一起构建有影响力的项目。

<div align="center">

🚀 [框架介绍](#tradingagents-框架) | ⚡ [安装与 CLI](#安装与命令行) | 🕒 [GitHub Actions 定时/手动运行指南](docs/github-scheduled-analysis.md) | 🎬 [演示](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [包使用方式](#tradingagents-包) | 🤝 [贡献](#贡献) | 📄 [引用](#引用)

</div>

## TradingAgents 框架

TradingAgents 是一个模拟真实交易机构协作流程的多智能体交易框架。系统通过由大语言模型驱动的专业角色协同完成分析与决策：包括基本面分析师、情绪分析师、新闻分析师、技术分析师、交易员与风险管理团队。各智能体还会通过动态讨论来形成更稳健的交易策略。

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents 仅用于研究目的。实际交易表现可能受多种因素影响，包括底层模型选择、温度参数、交易周期、数据质量与其他非确定性因素。[本项目不构成任何金融、投资或交易建议。](https://tauric.ai/disclaimer/)

框架将复杂交易任务拆分为多个专业角色，从而实现更稳健、可扩展的市场分析和决策流程。

### 分析师团队
- 基本面分析师：评估公司财务与经营指标，识别内在价值与潜在风险信号。
- 情绪分析师：分析社交媒体与公众情绪，判断短期市场情绪变化。
- 新闻分析师：跟踪全球新闻和宏观事件，评估其对市场的影响。
- 技术分析师：使用 MACD、RSI 等技术指标识别交易形态并预测价格走势。

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### 研究团队
- 由多头与空头研究员组成，对分析师结论进行批判性评估，通过结构化辩论平衡收益与风险。

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### 交易员智能体
- 整合分析师与研究员报告，形成交易计划并决定交易时机与仓位规模。

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### 风险管理与组合经理
- 持续评估市场波动、流动性与其他风险，调整交易策略并提交风险评估报告。
- 组合经理最终审批交易提案；通过后，订单发送至模拟交易所执行。

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## 安装与命令行

### 安装

克隆 TradingAgents：
```bash
git clone https://github.com/qchen34/TradingAgents.git
cd TradingAgents
```

创建虚拟环境（可使用任意你习惯的环境管理器）：
```bash
python3 -m venv venv
source venv/bin/activate
```

安装项目与依赖：
```bash
pip install -r requirements.txt
```

### 必需 API

TradingAgents 支持多个 LLM 提供商。请为你选择的提供商设置 API Key：

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export SILICONFLOW_API_KEY=...     # SiliconFlow (OpenAI-compatible)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

如使用本地模型，可在配置中设置 `llm_provider: "ollama"`。

也可以复制 `.env.example` 到 `.env` 后填写密钥：
```bash
cp .env.example .env
```

### CLI 使用

启动交互式 CLI：
```bash
tradingagents          # 安装后的命令
python -m cli.main     # 直接从源码运行
```

界面中可选择股票代码、分析日期、LLM 提供商、研究深度等参数。

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

运行过程中会实时展示报告生成进度，便于跟踪各智能体执行状态。

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents 包

### 实现细节

TradingAgents 基于 LangGraph 构建，以保证灵活性和模块化。当前支持的 LLM 提供商包括：OpenAI、SiliconFlow、Google、Anthropic、xAI、OpenRouter、Ollama。

### Python 使用

你可以在代码中导入 `tradingagents` 并初始化 `TradingAgentsGraph()`。调用 `.propagate()` 会返回交易决策。快速示例如下：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

你也可以基于默认配置修改模型、辩论轮次等参数：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # openai, siliconflow, google, anthropic, xai, openrouter, ollama
config["deep_think_llm"] = "gpt-5.4"     # 复杂推理模型
config["quick_think_llm"] = "gpt-5.4-mini" # 快速响应模型
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

SiliconFlow 可通过 OpenAI-compatible 端点使用：

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "siliconflow"
config["backend_url"] = "https://api.siliconflow.cn/v1"  # 可选，默认即此地址
config["deep_think_llm"] = "deepseek-ai/DeepSeek-R1"
config["quick_think_llm"] = "Qwen/Qwen3-32B"
```

完整配置请见 `tradingagents/default_config.py`。

## 贡献

欢迎社区贡献！无论是修复 Bug、改进文档，还是提出新功能建议，你的参与都会让项目更好。如果你对这一研究方向感兴趣，欢迎加入我们的开源金融 AI 研究社区 [Tauric Research](https://tauric.ai/)。

## 引用

如果 *TradingAgents* 对你有帮助，欢迎引用我们的工作：

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
