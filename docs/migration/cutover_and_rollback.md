# 切换与回滚预案

> **更新（2026-05）**：Streamlit UI 已下线；主栈为 **Next.js + FastAPI**。回滚以 Git 版本与部署回退为主。

## 当前主栈

1. FastAPI：`python -m uvicorn backend.api.main:app`
2. Next.js：`cd frontend && npm run dev`（需 `NEXT_PUBLIC_API_BASE`）
3. 一键脚本：`bash scripts/start_dual_stack.sh`

## 回滚策略

- 场景：前端构建失败、API 不稳定、关键策略指标不一致。
- 操作：
  1. 将部署回退到上一稳定 Git 提交或 Vercel/后端上一版本。
  2. 停止有问题的服务进程，保留健康的一端（例如仅 API 或仅静态页）。
  3. 记录失败版本与触发条件，修复后重新灰度。

## 已移除项

- 原 `app.py` + Streamlit 页面树已不再维护；历史说明见 `docs/webui_prd.md`（已归档）。
