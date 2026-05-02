# Streamlit -> npm 页面映射

## 路由映射

- `仪表盘` -> `frontend/src/app/page.tsx`
- `个股分析` -> `frontend/src/app/analysis/page.tsx`
- `策略` -> `frontend/src/app/strategy/page.tsx`
- `股票筛选` -> `frontend/src/app/screener/page.tsx`
- `股票详情` -> `frontend/src/app/stock-detail/page.tsx`
- `持仓` -> `frontend/src/app/portfolio/page.tsx`
- `策略回测` -> `frontend/src/app/backtesting/page.tsx`

## API 映射

- Streamlit `session_state` 默认值 -> `GET /api/v1/state/defaults`
- 策略文档/子策略 -> `GET /api/v1/strategy/metadata`
- LRS 聊天 -> `POST /api/v1/strategy/lrs/chat`
- 回测周期 -> `GET /api/v1/backtest/periods`
- 启动回测 -> `POST /api/v1/backtest/jobs`
- 查询回测 -> `GET /api/v1/backtest/jobs/{job_id}`

## 状态迁移

- `st.session_state.current_page` -> `useUiStore.currentPage`
- `st.session_state.selected_ticker` -> `useUiStore.selectedTicker`
- `st.session_state.strategy_sub_menu` -> `useUiStore.strategySubMenu`
- `st.session_state.runtime_stage` -> `useUiStore.runtimeStage`
- `st.session_state.error` -> `useUiStore.error`

