已完成只读分析。未修改文件、未安装依赖，也未运行应用、测试或构建命令。以下结论基于当前工作区，包含大量尚未提交的迁移改动，并不完全等同于 main 分支。

## 1. 项目的主要用途

这是一个面向个人投资研究与学习的金融研究工作台，基于 Tauric Research 的 TradingAgents 扩展而来，当前主界面已经从 Streamlit 迁移到 Next.js + FastAPI。

主要功能包括：

- 市场仪表盘：指数、板块、宏观指标、新闻及 LLM 市场摘要。
- 个股追踪：技术面、基本面、图表、LLM 阶段判断。
- TradingAgents 多智能体研究：市场、新闻、社交、基本面分析，随后进行多空辩论、交易计划、风险辩论和组合决策。
- X 资讯简报：采集关注账号内容，做主题编排、翻译和 Markdown/JSON 落盘。
- 策略研究：LRS、Wheel 评估和 QQQ/TQQQ 回测。
- CLI 交互式分析及历史 Markdown 报告。

定位是研究辅助，不是券商交易系统，目前也没有真实下单链路。项目概览见 README.md。

## 2. 技术栈与关键依赖

后端与核心：

- Python 3.10+
- FastAPI、Uvicorn、Pydantic
- LangChain、LangGraph
- OpenAI、Anthropic、Google Gemini，以及 OpenAI-compatible 的 SiliconFlow、xAI、OpenRouter、Ollama
- yfinance、Alpha Vantage
- pandas、NumPy、stockstats
- Matplotlib
- Typer、Rich、Questionary
- rank-bm25，用作智能体的本地记忆检索

依赖声明见 pyproject.toml。

前端：

- Next.js 15 App Router
- React 19
- TypeScript strict mode
- Zustand
- Tailwind CSS 4
- npm package-lock.json 当前锁定到 Next 15.5.15、React 19.2.5、Zustand 5.0.12

前端声明见 frontend/package.json。

存储与任务模型：

- 没有数据库、Redis 或正式任务队列。
- 业务数据主要落在本地 JSON、Markdown、PNG 文件。
- 长任务主要使用进程内字典加 daemon thread 管理。
- 前端通过轮询获取任务状态。

## 3. 目录结构及模块职责

| 目录 | 职责 |
|---|---|
| frontend/ | Next.js 页面、组件、API 客户端、Zustand UI 状态，以及两个读取本地文件的 Next API Route |
| backend/api/ | FastAPI 应用、请求模型、统一响应封装和业务服务适配 |
| tradingagents/ | 多智能体核心、LangGraph 工作流、LLM 客户端、行情数据路由和 BM25 记忆 |
| tradingagents/agents/ | 市场、新闻、社交、基本面分析师；多空研究员；交易员；风险辩论员；组合经理 |
| tradingagents/graph/ | 图构建、条件分支、状态传播、反思和最终信号处理 |
| tradingagents/dataflows/ | yfinance/Alpha Vantage 数据获取及供应商 fallback |
| cli/ | Typer/Rich 交互式终端、实时状态展示、报告输出 |
| web/services/ | 实际的共享业务层：行情、回测、个股追踪、投资大师框架、X 简报、TradingAgents Web 任务 |
| web/wheel_* | Wheel 策略参数和指标逻辑 |
| data/ | 仪表盘快照、回测结果、X 简报、关注列表、个股追踪缓存 |
| reports/、results/ | TradingAgents 生成的历史分析报告和运行日志 |
| docs/ | PRD、迁移、策略研究、部署和案例文档 |
| scripts/ | 双栈启动、Futu 导出、Excel 导出和开发基准脚本 |
| tests/ | 少量 Python 单元测试 |
| assets/ | README 和说明文档使用的图片 |

FastAPI 路由集中在 backend/api/main.py，共享业务适配集中在 backend/api/services.py。

## 4. 程序启动入口

主要入口：

- FastAPI：

  python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
- Next.js：

  cd frontend
npm run dev
- 双栈启动：

  bash scripts/start_dual_stack.sh

  脚本见 scripts/start_dual_stack.sh。
- CLI：

  python -m cli.main
tradingagents analyze

  tradingagents console script 映射到 cli.main:app；命令入口见 cli/main.py。
- 根目录 main.py 是硬编码 NVDA 的演示程序，不是当前 Web 主入口，运行时会请求外部 LLM/行情并写文件。

## 5. 核心数据流和调用关系

Next.js 页面
  ↓ frontend/src/lib/api.ts
FastAPI 路由
  ↓ backend/api/services.py
web/services 业务层
  ├─ yfinance / Alpha Vantage
  ├─ LLM Provider
  ├─ 本地 JSON / Markdown / PNG
  └─ TradingAgentsGraph
       ↓
分析师 + 工具循环
       ↓
Bull / Bear 辩论
       ↓
Research Manager
       ↓
Trader
       ↓
激进 / 中性 / 保守风险辩论
       ↓
Portfolio Manager
       ↓
最终交易决策和报告

TradingAgents 图的节点和边定义见 setup.py，主编排类见 trading_graph.py。

具体业务流：

- 仪表盘：yfinance 行情/新闻 → LLM 摘要 → data/cache、data/dashboard/latest.json 和历史快照。
- 个股追踪：后台线程遍历硬编码股票池 → 技术/基本面计算 → Matplotlib 图表 → SiliconFlow LLM → data/stock_tracker/latest.json。
- 投资大师框架：读取个股快照和 docs/investor-frameworks 方法论 → 最多两个并行 LLM worker → investor_analysis.json。
- X 简报：关注列表 Markdown → Nitter/snscrape/RSSHub → LLM 编排与翻译 → JSON、Markdown、历史记录。当前刷新是同步 HTTP 请求。
- 回测：后台线程下载 QQQ/TQQQ → 生成 MA 信号 → 模拟交易 → 结果只保存在进程内 job。
- Web TradingAgents：创建后台线程 → 流式执行 LangGraph → 前端每 1.5 秒轮询 → 完成后写入 reports/。

前端 API 封装见 frontend/src/lib/api.ts。

## 6. 当前测试、构建和部署方式

测试：

- 只有三个 Python unittest 文件、约六个测试方法：
  - Google API Key 映射
  - 模型目录与验证器一致性
  - ticker 后缀处理
- 没有 FastAPI 路由测试、LangGraph 流程测试、回测断言、文件持久化测试或前端测试。
- 没有发现 GitHub Actions 或其他 CI 配置。
- 按要求，本次没有实际执行测试。

构建：

- Python 使用 setuptools。
- requirements.txt 只有 -e .，实际依赖来自 pyproject.toml。
- Next.js 使用：

  npm ci
npm run build
- 另有 npm run lint、TypeScript --noEmit 和生成 UI 人工验收清单的脚本，但没有自动化 UI 测试。

部署：

- 文档建议 Vercel 只部署 frontend/。
- FastAPI 需要独立部署到常驻 Python 服务，例如云主机、Render、Railway 或 Fly.io。
- 前端通过 NEXT_PUBLIC_API_BASE 连接后端。
- 没有 Dockerfile、Compose、Procfile、后端部署描述文件或基础设施配置。

部署说明见 docs/vercel_deploy.md。

## 7. 明显技术债、潜在风险和待确认问题

### 高优先级

1. 当前工作区不可由一次干净提交稳定复现。

   多个已被现有代码引用的文件仍未跟踪，例如：
   - frontend/src/lib/api.ts
   - frontend/src/components/investor-analysis-section.tsx
   - web/services/stock_tracker_service.py
   - web/services/investor_framework_service.py
   - web/services/trading_agents_service.py
   - web/wheel_strategy_shared.py
   - web/wheel_style_profiles.py

   其中 frontend/src/lib/api.ts 还被根 .gitignore 的通用 lib/ 规则意外忽略。干净克隆当前提交很可能无法构建或启动。

   **通俗解释：**

   你现在电脑上的项目，像是一套“在你家里能正常组装的家具”。Git 仓库相当于装家具时要寄给别人的包装箱，但目前有几块关键木板还放在你的桌上，没有被装进箱子里。`frontend/src/lib/api.ts` 的情况更特殊：`.gitignore` 相当于一张“不要装箱”的清单，它误把这个关键文件列成了不需要保存的东西，所以 Git 甚至不会主动提醒你它没有被提交。

   **实际会发生什么：**

   - 你在当前电脑上运行项目时，文件都还在，所以可能感觉一切正常。
   - 换一台电脑、重新克隆仓库，或者让 Vercel/服务器从 Git 拉代码时，这些文件不会出现。
   - 其他代码明明引用了这些文件，最后可能报“找不到模块”“构建失败”或“后端无法启动”。
   - 即使项目目前只有你一个人使用，这也会影响备份：如果本机文件丢失，Git 仓库未必能帮你恢复完整项目。

   **为什么是高优先级：**

   在继续部署、重构或处理其他技术债之前，首先要保证“Git 中保存的项目”和“你电脑上实际能运行的项目”是同一份。否则后续修复可能只在当前电脑有效，无法稳定复制到其他环境。

2. 公网部署缺少安全边界。
   - 没有认证、授权或限流。
   - CORS 为 allow_origins=["*"] 且允许 credentials，见 backend/api/main.py。
   - 任何访问者都可能触发行情抓取、LLM 消耗、文件写入和后台任务。
   - backend_url 由请求传入且未做域名白名单校验，存在潜在 SSRF 风险。
   - ticker 仅检查非空，却会参与报告目录名拼接，存在潜在路径穿越风险。

   **通俗解释：**

   如果把后端服务想象成一间办公室，现在的状态接近于：门没有锁、没有前台登记、没有规定访客一天能办多少次业务，而且部分访客还能告诉工作人员“去这个地址替我拿一份资料”。在你自己的电脑上、只有你自己访问时，这些问题不一定马上造成麻烦；一旦后端地址公开到互联网，任何知道地址的人都可能调用这些接口。

   这里几个术语可以这样理解：

   - **认证**：确认“你是谁”，类似进门时检查身份证。
   - **授权**：确认“你能做什么”，类似普通访客不能进入财务室。
   - **限流**：限制短时间内可以请求多少次，类似每人每天只能办理一定数量的任务。
   - **CORS 全开放**：浏览器基本允许任何网站尝试调用你的后端，而不是只允许你自己的前端网站。
   - **SSRF**：外部用户可能诱导你的服务器替他访问某个地址，包括本来不应从公网访问的内部服务。可以理解为陌生人让办公室员工拿着内部通行证替他到处取东西。
   - **路径穿越**：本来 ticker 应该只是 `NVDA`、`AAPL` 这样的股票代码，但如果没有严格限制，恶意输入可能被当成文件路径的一部分，导致程序把文件写到原定目录之外。

   **实际会发生什么：**

   - 陌生人可以反复触发付费 LLM 请求，消耗你的 API 额度或产生账单。
   - 大量行情刷新和分析任务可能拖慢甚至打挂后端。
   - 攻击者可能尝试访问内网地址、探测服务器环境或影响本地文件。
   - 错误信息直接返回前端时，还可能暴露服务商、目录或内部配置线索。

   **为什么是高优先级：**

   如果项目永远只绑定在本机 `127.0.0.1` 并由你本人使用，风险相对较低；只要准备把 FastAPI 后端部署到公网，这一项就必须在公开地址之前处理，而不是上线后再补。

3. 长任务架构不适合多实例生产环境。

   Job 保存在进程内字典，工作由 daemon thread 执行：
   - 重启后任务状态丢失。
   - 多 worker 之间无法共享 job。
   - daemon thread 可能在进程退出时被直接终止。
   - 回测和个股刷新缺少统一并发上限。
   - 本地文件存储不适合水平扩容。

   **通俗解释：**

   TradingAgents 分析、个股刷新和回测都可能需要几十秒到几分钟。现在系统处理这些任务的方式，类似餐厅服务员把顾客的订单记在自己脑子里，然后临时找一位兼职员工去做。对于你一个人在本机使用，这种方式简单直接；但服务器重启、同时来了很多用户，或者部署了多台服务器以后，订单就容易丢失或互相找不到。

   这里几个现象可以这样理解：

   - **Job 保存在进程内字典**：任务记录只存在运行中程序的内存里，没有写入一个大家都能访问的任务数据库。
   - **重启后状态丢失**：程序一重启，内存被清空，前端再查询原来的任务编号时，后端会说“任务不存在”。
   - **多 worker 无法共享**：如果有两个后端进程，任务创建在 A 进程，下一次查询却被分配到 B 进程，B 完全不知道 A 记录过什么。
   - **daemon thread 会被终止**：后台线程依附于主程序；主程序关闭或部署平台回收进程时，尚未完成的分析可能被直接中断。
   - **没有统一并发上限**：如果连续点击刷新或多人同时请求，系统可能同时启动很多耗 CPU、网络和 LLM 额度的任务。
   - **本地文件无法水平扩容**：两台服务器各有自己的硬盘，A 写出的报告，B 不一定看得到；它们同时写同一个文件时还可能互相覆盖。

   **实际会发生什么：**

   - 页面一直显示“处理中”，但后端已经重启，任务永远不会完成。
   - 同一个任务有时查得到、有时显示不存在。
   - 并发任务过多时，服务器变慢、请求超时或 LLM 成本突然上升。
   - 部署多个后端实例后，不同用户看到的任务状态和报告可能不一致。

   **为什么是高优先级：**

   如果这是单用户、本机运行的研究工具，现有实现暂时可以接受；如果目标是长期在线、允许多人使用或使用多个后端进程，就需要把任务状态和任务执行从单个进程中独立出来。它决定了系统能不能稳定地执行最核心的长时间分析任务。

4. 依赖锁文件明显过期。

   uv.lock 仍记录项目 0.2.0 及旧的 Chainlit、Backtrader、Redis 等依赖，而当前 pyproject.toml 已是 0.2.3，并加入 FastAPI、Uvicorn、Matplotlib 等。当前 README 又走未固定版本的 pip install -e .，Python 环境可复现性不足。

   **通俗解释：**

   项目的依赖就像做菜需要采购的原料。`pyproject.toml` 主要写“需要牛奶、面粉和鸡蛋，并且版本不能太旧”；锁文件 `uv.lock` 则应该写清楚“牛奶买哪个品牌、哪个批次，面粉具体是哪一个版本”。这样换一台电脑时，才能买到完全相同的原料，做出相同的结果。

   现在的问题是：新的采购清单已经改过了，但锁文件还是旧菜谱留下的，甚至还列着项目已经不再使用的 Chainlit、Backtrader、Redis，同时没有正确反映现在使用的 FastAPI、Uvicorn、Matplotlib。另一方面，README 推荐的 `pip install -e .` 主要按最低版本范围临时选择依赖，新安装时可能拿到比你当前电脑更新的版本。

   **实际会发生什么：**

   - 当前电脑可以运行，换一台电脑安装后却报错。
   - 同一天和几个月后执行相同安装命令，得到的依赖版本可能不同。
   - 某个依赖发布不兼容更新后，项目可能在没有修改代码的情况下突然无法启动。
   - 有人使用 `uv.lock` 安装，另一个人按 README 使用 pip 安装，两边得到的环境可能完全不同，排查问题会很困难。

   **为什么是高优先级：**

   依赖版本是项目能否重复安装和部署的基础。它不一定会让当前正在运行的环境立刻出错，但在换电脑、重新创建虚拟环境或部署服务器时很容易集中爆发，因此应在正式验证和部署之前统一依赖管理方式并更新锁文件。

### 中优先级

5. 本地文件持久化缺少原子写、事务和跨进程锁。

   多个刷新任务直接覆盖 JSON/Markdown；并发请求或进程中断可能产生部分文件或相互覆盖。部分路径还是相对当前工作目录解析。
6. Vercel 部署存在路径不一致风险。

   两个 Next API Route 会读取 ../data 和 ../scripts，但 Vercel 文档要求 Root Directory 为 frontend，而 outputFileTracingRoot 也设置为 frontend。据此推断，生产构建中父目录文件可能不会被打包，相关接口会静默返回空结果。
7. 测试覆盖和发布门禁不足。

   核心 API、投资计算、LLM fallback、后台任务、路径安全和前端交互均无自动测试，也没有 CI 负责 lint、类型检查和构建。
8. 仓库混入大量运行产物。

   当前约 411 个已跟踪文件中，有约 169 个属于 reports/、results/、dashboard 快照、X 简报 debug/history 等运行数据。还跟踪了 .DS_Store、tsconfig.tsbuildinfo 和 frontend/.env.development。这会增加仓库体积，也可能泄露研究输入、LLM prompt 或内部数据。
9. 模块体积和耦合较高。

   stock_tracker_service.py 超过 1300 行，investor_framework_service.py 接近 1000 行，部分前端页面也接近 1000 行。Web 服务还反向导入 CLI 的报告保存和消息分类函数，CLI 与服务层职责没有完全拆开。
10. Python 发布包不包含 Web 栈。

    setuptools 只包含 tradingagents* 和 cli*，不包含 backend*、web*。因此 wheel/PyPI 安装只能可靠提供 CLI，不能提供当前主力 Web 应用；若这是有意设计，需要在文档中明确。
11. 错误处理较宽泛。

    大量 except Exception 会吞掉上下文或只回传字符串；API 的 trace_id 没有对应结构化日志，生产排障能力有限，并可能把供应商或内部错误细节直接暴露给前端。
12. 功能和文档存在漂移。
    - portfolio 仍是占位页。
    - screener 直接跳转到 X 简报。
    - strategy_module_future.md 仍说策略页未实现，但当前已有 LRS/Wheel/回测。
    - LLM TODO 中一些“未修复”描述与当前代码不一致。

### 需要进一步确认

- 产品最终是单用户本地工具，还是准备公开部署的多用户服务？
- Python 依赖应以 pyproject.toml + pip 还是 uv.lock 为唯一来源？
- reports/、X Brief debug、dashboard 历史是样例数据还是应移出 Git 的运行产物？
- 后端部署环境是否提供持久磁盘？否则报告和 JSON 缓存会在重新部署后丢失。
- Next API Route 是否必须保留；还是所有文件读取都应统一迁移到 FastAPI？
- frontend/src/lib/api.ts 和新增 Web 服务是否准备纳入当前迁移提交？
- 个股池、SiliconFlow 模型和 X 数据源是否应配置化，而不是写死在代码中？
