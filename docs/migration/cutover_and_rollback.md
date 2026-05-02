# 切换与回滚预案

## 切换步骤

1. 保持 Streamlit 在线，新增 FastAPI + Next.js 并行运行。
2. 通过 `docs/migration/parallel_validation_checklist.md` 完成验收。
3. 将默认入口从 Streamlit 调整为 Next.js（文档/运维层）。
4. Streamlit 保留为兼容入口（仅调试或灰度应急）。

## 回滚策略

- 场景：前端构建失败、API 不稳定、关键策略指标不一致。
- 操作：
  1. 停止 Next.js 与 FastAPI。
  2. 恢复 `streamlit run app.py` 作为唯一入口。
  3. 记录失败版本与触发条件，修复后重新灰度。

## 下线 Streamlit 的前置条件

- 前端所有核心页面完成 API 化。
- LRS/Wheel 策略交互全部可用。
- 至少 1 个交易周稳定运行无 P0 问题。

