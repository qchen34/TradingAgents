# UI / 交互自检（主编检说明）

本文档描述**如何**做一轮完整的 UI 与交互自检，以及如何与机器生成清单、优化 backlog 配合。  
**逐步路由表请勿在此手写维护**，以机器生成为准：

- 完整步骤表：[generated_ui_checklist.md](./generated_ui_checklist.md)（运行 `cd frontend && npm run ui:checklist` 更新）
- 优化条目沉淀：[ui_optimization_backlog.md](./ui_optimization_backlog.md)

---

## 何时执行

- 发版前、大改导航/布局/关键表单后
- 升级 Next.js / 换一批 UI 组件库后
- 用户反馈「某页异常」后的回归

---

## 环境准备（必做）

1. `frontend/.env.development` 中 `NEXT_PUBLIC_API_BASE` 指向可访问后端（如 `http://127.0.0.1:8000`）。
2. `cd frontend && npm run dev`，浏览器打开 `http://localhost:3000`。
3. 按需启动 FastAPI，保证数据类页面可测真实链路。

---

## 全局检查（所有页面通用）

在按路由逐步检查**之前或之后**扫一遍：

| 检查项 | 操作 | 期望 | 异常时记入 backlog |
|--------|------|------|---------------------|
| 侧栏 active 态 | 逐一点侧栏入口 | 当前页高亮与路由一致 | 是 |
| 侧栏 hover 提示 | 悬停图标 | 浮层文案与入口一致 | 是 |
| 窄屏 / 小视口 | 将窗口宽度缩至 ~375px | 无横向溢出不可达内容；关键按钮可点 | 是 |
| 键盘 Tab | 从地址栏 Tab 进入页面 | 焦点顺序合理；无焦点陷阱 | 是 |
| 无后端 / 错 API | 临时改错 `NEXT_PUBLIC_API_BASE` 刷新 | 有可读错误提示，非白屏崩溃 | 是 |
| 大表 / 长列表 | 个股追踪等页纵向滚动 | 表头或关键控件仍可理解当前位置 | 是 |
| 外链图片 / Chart | 个股详情技术图等 | 加载失败时有占位或说明，不破坏布局 | 是 |

---

## 逐步检查（人工记录表）

按 [generated_ui_checklist.md](./generated_ui_checklist.md) 从 Step 1 顺序执行。  
每步可在下表复制一行记录（或在表格工具中维护）；**优化点**请同步抄录到 [ui_optimization_backlog.md](./ui_optimization_backlog.md)。

| 步骤 | 路由 | 操作摘要 | 期望摘要 | 实际结果 | 优化点 | 严重度 | 跟进 |
|------|------|----------|----------|----------|--------|--------|------|
| 例 | `/analysis` | 打开后点刷新 | 出现进度并最终加载表格 | （填） | （填） | P2 | （填） |
| | | | | | | | |

**严重度建议**：P0 阻塞 / P1 高影响 / P2 体验 / P3 锦上添花。

---

## 与生成脚本的关系

- 导航或新增 `app/**/page.tsx` 后务必运行：`npm run ui:checklist`，将 `docs/generated_ui_checklist.md` **一并提交**，便于 PR 审查是否漏测新路由。
- 需要 query、异步轮询等说明时，编辑 [`frontend/scripts/ui-checklist-overrides.json`](../frontend/scripts/ui-checklist-overrides.json)，勿改生成结果文件正文。

---

## 可选后续（自动化）

若引入 Playwright，可将本文件中的「全局检查」与生成清单中的关键 Step 映射为 smoke 用例；本文件仍保留为探索性测试与体验类问题记录。
