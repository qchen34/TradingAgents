from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiEnvelope(BaseModel):
    success: bool = True
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None
    trace_id: str


class LrsChatRequest(BaseModel):
    question: str = Field(min_length=1)
    last_params: dict[str, Any] | None = None


class BacktestJobRequest(BaseModel):
    period_key: Literal["2y", "3y", "5y", "10y", "2015_2020", "2010_2015"]


class DashboardRefreshRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=30)


class WheelEvaluateRequest(BaseModel):
    style_key: Literal["aggressive", "neutral", "conservative"] = "neutral"
    underlying_ticker: str = Field(default="TQQQ", min_length=1)
    signal_ticker: str = Field(default="QQQ", min_length=1)


class BatchQuoteRequest(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=200)


class XBriefRefreshRequest(BaseModel):
    days: int = Field(default=7, ge=3, le=30)
    per_account_limit: int = Field(default=80, ge=10, le=200)

