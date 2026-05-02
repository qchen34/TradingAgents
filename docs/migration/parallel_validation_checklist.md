# 双栈并行验收清单

## 环境准备

- [ ] Python 依赖已安装（含 `fastapi`、`uvicorn`）
- [ ] `frontend/` 已执行 `npm install`
- [ ] `.env` 与现有 Streamlit 配置一致

## 启动验证

- [ ] `streamlit run app.py` 可正常打开
- [ ] `python -m uvicorn backend.api.main:app --reload` 可访问 `/health`
- [ ] `npm run dev` 可打开前端首页

## 功能一致性

- [ ] 策略文档内容与 Streamlit 一致
- [ ] LRS 聊天对同一问题返回语义一致结果
- [ ] 回测任务可启动、查询、完成
- [ ] 子策略切换（LRS/Wheel）行为一致

## 数据与指标

- [ ] 关键回测指标（收益率、最大回撤、交易次数）在允许误差范围内一致
- [ ] 错误提示与空态展示可用

## 发布前门禁

- [ ] 前端构建通过（`npm run build`）
- [ ] API 健康检查通过（`/health`）
- [ ] 回滚脚本与降级路径已验证

