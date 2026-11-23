from __future__ import annotations

import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

# 在导入业务模块前加载 .env，确保 SILICONFLOW_API_KEY 等
# 在 LLM client 初始化时可被读到（与 main.py / cli/main.py 行为一致）。
load_dotenv()

from backend.api.schemas import (
    ApiEnvelope,
    BatchQuoteRequest,
    BacktestJobRequest,
    DashboardRefreshRequest,
    InvestorAnalysisRequest,
    LrsChatRequest,
    TaRunRequest,
    WheelEvaluateRequest,
    XBriefRefreshRequest,
)
from backend.api.services import (
    DEFAULT_SESSION_STATE,
    answer_lrs_chat,
    batch_quotes,
    create_backtest_job,
    get_dashboard_snapshot,
    get_backtest_job,
    refresh_dashboard_snapshot,
    refresh_x_brief,
    strategy_metadata,
    get_x_brief_latest,
    wheel_evaluate,
    wheel_profiles,
    get_stock_tracker_latest,
    create_stock_tracker_refresh_job,
    get_stock_tracker_job,
    get_stock_tracker_chart,
    get_investor_analysis_cached,
    create_investor_analysis_job,
    get_investor_analysis_job,
    ta_get_options,
    ta_create_run_job,
    ta_get_job,
    ta_list_reports,
    ta_get_report,
)
from web.services.backtesting_core import _PERIOD_ORDER, _PERIOD_SPECS

app = FastAPI(title="TradingAgents API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _trace_id(req: Request) -> str:
    return req.headers.get("x-trace-id") or uuid.uuid4().hex


def _ok(request: Request, data: dict[str, Any] | list[Any] | None = None) -> JSONResponse:
    payload = ApiEnvelope(success=True, data=data, trace_id=_trace_id(request))
    return JSONResponse(status_code=200, content=payload.model_dump())


def _err(request: Request, msg: str, code: int = 500) -> JSONResponse:
    payload = ApiEnvelope(success=False, error=msg, data=None, trace_id=_trace_id(request))
    return JSONResponse(status_code=code, content=payload.model_dump())


@app.get("/health")
def health(request: Request) -> JSONResponse:
    return _ok(request, {"status": "ok"})


@app.get("/api/v1/state/defaults")
def state_defaults(request: Request) -> JSONResponse:
    return _ok(request, DEFAULT_SESSION_STATE)


@app.get("/api/v1/strategy/metadata")
def get_strategy_metadata(request: Request) -> JSONResponse:
    return _ok(request, strategy_metadata())


@app.get("/api/v1/dashboard")
def get_dashboard(request: Request) -> JSONResponse:
    try:
        return _ok(request, get_dashboard_snapshot())
    except Exception as exc:
        return _err(request, f"仪表盘数据读取失败：{exc}", 500)


@app.post("/api/v1/dashboard/refresh")
def post_dashboard_refresh(body: DashboardRefreshRequest, request: Request) -> JSONResponse:
    try:
        return _ok(request, refresh_dashboard_snapshot(limit=body.limit))
    except Exception as exc:
        return _err(request, f"仪表盘刷新失败：{exc}", 500)


@app.post("/api/v1/quotes/batch")
def post_batch_quotes(body: BatchQuoteRequest, request: Request) -> JSONResponse:
    try:
        return _ok(request, batch_quotes(body.codes))
    except Exception as exc:
        return _err(request, f"批量报价失败：{exc}", 500)


@app.get("/api/v1/x-brief/latest")
def get_xbrief_latest(request: Request) -> JSONResponse:
    data = get_x_brief_latest()
    if data is None:
        return _ok(request, {"ready": False})
    return _ok(request, {"ready": True, **data})


@app.post("/api/v1/x-brief/refresh")
def post_xbrief_refresh(body: XBriefRefreshRequest, request: Request) -> JSONResponse:
    try:
        data = refresh_x_brief(days=body.days, per_account_limit=body.per_account_limit)
        return _ok(request, {"ready": True, **data})
    except Exception as exc:
        return _err(request, f"X资讯简报刷新失败：{exc}", 500)


@app.post("/api/v1/strategy/lrs/chat")
def post_lrs_chat(body: LrsChatRequest, request: Request) -> JSONResponse:
    try:
        answer = answer_lrs_chat(body.question, body.last_params)
        return _ok(request, {"answer": answer})
    except Exception as exc:
        return _err(request, f"LLM 调用失败：{exc}", 500)


@app.get("/api/v1/wheel/profiles")
def get_wheel_profiles(request: Request) -> JSONResponse:
    return _ok(request, wheel_profiles())


@app.post("/api/v1/wheel/evaluate")
def post_wheel_evaluate(body: WheelEvaluateRequest, request: Request) -> JSONResponse:
    try:
        data = wheel_evaluate(
            style_key=body.style_key,
            underlying_ticker=body.underlying_ticker,
            signal_ticker=body.signal_ticker,
        )
        return _ok(request, data)
    except Exception as exc:
        return _err(request, f"Wheel 评估失败：{exc}", 500)


@app.get("/api/v1/backtest/periods")
def get_backtest_periods(request: Request) -> JSONResponse:
    periods = [
        {"key": key, "label": _PERIOD_SPECS[key]["label"]}
        for key in _PERIOD_ORDER
    ]
    return _ok(request, periods)


@app.post("/api/v1/backtest/jobs")
def post_backtest_job(body: BacktestJobRequest, request: Request) -> JSONResponse:
    job = create_backtest_job(body.period_key)
    return _ok(
        request,
        {
            "job_id": job.job_id,
            "status": job.status,
            "period_key": job.period_key,
            "created_at": job.created_at,
        },
    )


@app.get("/api/v1/backtest/jobs/{job_id}")
def get_job(job_id: str, request: Request) -> JSONResponse:
    job = get_backtest_job(job_id)
    if job is None:
        return _err(request, "任务不存在", 404)
    return _ok(
        request,
        {
            "job_id": job.job_id,
            "status": job.status,
            "period_key": job.period_key,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "result": job.result,
            "error": job.error,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# 个股追踪路由
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/stock-tracker/latest")
def get_tracker_latest(request: Request) -> JSONResponse:
    try:
        return _ok(request, get_stock_tracker_latest())
    except Exception as exc:
        return _err(request, f"个股追踪数据读取失败：{exc}", 500)


@app.post("/api/v1/stock-tracker/refresh")
def post_tracker_refresh(request: Request) -> JSONResponse:
    try:
        return _ok(request, create_stock_tracker_refresh_job())
    except Exception as exc:
        return _err(request, f"个股追踪刷新失败：{exc}", 500)


@app.get("/api/v1/stock-tracker/jobs/{job_id}")
def get_tracker_job_status(job_id: str, request: Request) -> JSONResponse:
    job = get_stock_tracker_job(job_id)
    if job is None:
        return _err(request, "任务不存在", 404)
    return _ok(request, job)


@app.get("/api/v1/stock-tracker/investor-analysis/jobs/{job_id}")
def get_investor_analysis_job_status(job_id: str, request: Request) -> JSONResponse:
    job = get_investor_analysis_job(job_id)
    if job is None:
        return _err(request, "任务不存在", 404)
    return _ok(request, job)


@app.get("/api/v1/stock-tracker/investor-analysis/{ticker}")
def get_investor_analysis_route(ticker: str, request: Request) -> JSONResponse:
    try:
        data = get_investor_analysis_cached(ticker)
        return _ok(request, data)
    except Exception as exc:
        return _err(request, f"读取大佬框架分析失败：{exc}", 500)


@app.post("/api/v1/stock-tracker/investor-analysis/{ticker}")
def post_investor_analysis_route(
    ticker: str,
    body: InvestorAnalysisRequest,
    request: Request,
) -> JSONResponse:
    from web.services.investor_framework_service import (
        InvestorAnalysisError,
        InvestorJobConflictError,
        TickerNotFoundError,
    )

    try:
        return _ok(request, create_investor_analysis_job(ticker, body.mode))
    except TickerNotFoundError as exc:
        return _err(request, str(exc), 400)
    except InvestorJobConflictError as exc:
        return _err(request, str(exc), 409)
    except InvestorAnalysisError as exc:
        return _err(request, str(exc), 400)
    except Exception as exc:
        return _err(request, f"大佬框架分析启动失败：{exc}", 500)


@app.get("/api/v1/stock-tracker/{ticker}/chart")
def get_tracker_chart(ticker: str, request: Request) -> Response:
    img = get_stock_tracker_chart(ticker)
    if img is None:
        return _err(request, f"图表生成失败或无数据：{ticker}", 404)
    return Response(content=img, media_type="image/png")


# ──────────────────────────────────────────────────────────────────────────────
# TradingAgents 路由
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/trading-agents/options")
def get_ta_options(request: Request) -> JSONResponse:
    try:
        return _ok(request, ta_get_options())
    except Exception as exc:
        return _err(request, f"TradingAgents 选项加载失败：{exc}", 500)


@app.post("/api/v1/trading-agents/run")
def post_ta_run(body: TaRunRequest, request: Request) -> JSONResponse:
    try:
        return _ok(request, ta_create_run_job(body.model_dump()))
    except ValueError as exc:
        return _err(request, f"参数错误：{exc}", 400)
    except RuntimeError as exc:
        return _err(request, str(exc), 409)
    except Exception as exc:
        return _err(request, f"TradingAgents 启动失败：{exc}", 500)


@app.get("/api/v1/trading-agents/jobs/{job_id}")
def get_ta_job(job_id: str, request: Request) -> JSONResponse:
    job = ta_get_job(job_id)
    if job is None:
        return _err(request, "任务不存在", 404)
    return _ok(request, job)


@app.get("/api/v1/trading-agents/reports")
def get_ta_reports(request: Request) -> JSONResponse:
    try:
        return _ok(request, {"reports": ta_list_reports()})
    except Exception as exc:
        return _err(request, f"历史报告读取失败：{exc}", 500)


@app.get("/api/v1/trading-agents/reports/{report_id}")
def get_ta_report(report_id: str, request: Request) -> JSONResponse:
    detail = ta_get_report(report_id)
    if detail is None:
        return _err(request, "报告不存在", 404)
    return _ok(request, detail)
