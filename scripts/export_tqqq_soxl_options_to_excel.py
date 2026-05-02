#!/usr/bin/env python3
"""
Download option chain data for TQQQ and SOXL from yfinance and save to Excel.

Important limitation:
- yfinance does NOT provide full historical daily option chain snapshots for past 5 years.
- This script exports all currently available expirations/chains, and attaches 5Y
  underlying OHLCV history for manual analysis.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time
from typing import Iterable

import pandas as pd
import yfinance as yf


TICKERS = ("TQQQ", "SOXL")
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 1.5


def _fetch_with_retries(ticker: yf.Ticker, expiry: str):
    last_error = None
    for _ in range(MAX_RETRIES):
        try:
            return ticker.option_chain(expiry)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(RETRY_SLEEP_SECONDS)
    raise RuntimeError(f"Failed to fetch option chain for expiry={expiry}: {last_error}") from last_error


def _normalize_option_df(df: pd.DataFrame, symbol: str, option_type: str, expiry: str, fetched_at: str) -> pd.DataFrame:
    out = _sanitize_for_excel(df)
    out.insert(0, "symbol", symbol)
    out.insert(1, "option_type", option_type)
    out.insert(2, "expiry", expiry)
    out.insert(3, "fetched_at", fetched_at)
    return out


def fetch_all_current_option_chains(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ticker = yf.Ticker(symbol)
    expiries: Iterable[str] = ticker.options or []
    fetched_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    calls_all: list[pd.DataFrame] = []
    puts_all: list[pd.DataFrame] = []

    for expiry in expiries:
        chain = _fetch_with_retries(ticker, expiry)
        calls_all.append(_normalize_option_df(chain.calls, symbol, "call", expiry, fetched_at))
        puts_all.append(_normalize_option_df(chain.puts, symbol, "put", expiry, fetched_at))

    calls_df = pd.concat(calls_all, ignore_index=True) if calls_all else pd.DataFrame()
    puts_df = pd.concat(puts_all, ignore_index=True) if puts_all else pd.DataFrame()
    return calls_df, puts_df


def fetch_5y_underlying_history(symbol: str) -> pd.DataFrame:
    df = yf.download(symbol, period="5y", interval="1d", auto_adjust=False, progress=False)
    if df.empty:
        return pd.DataFrame()
    out = _sanitize_for_excel(df.reset_index())
    out.insert(0, "symbol", symbol)
    return out


def _sanitize_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = ["_".join([str(x) for x in tup if str(x) != ""]).strip("_") for tup in out.columns.to_flat_index()]
    for col in out.columns:
        if isinstance(out[col].dtype, pd.DatetimeTZDtype):
            out[col] = out[col].dt.tz_convert(None)
    return out


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"tqqq_soxl_options_snapshot_{ts}.xlsx"

    summary_rows = []
    data: dict[str, pd.DataFrame] = {}

    for symbol in TICKERS:
        calls_df, puts_df = fetch_all_current_option_chains(symbol)
        hist_df = fetch_5y_underlying_history(symbol)

        data[f"{symbol.lower()}_calls"] = calls_df
        data[f"{symbol.lower()}_puts"] = puts_df
        data[f"{symbol.lower()}_spot_5y"] = hist_df

        summary_rows.append(
            {
                "symbol": symbol,
                "calls_rows": len(calls_df),
                "puts_rows": len(puts_df),
                "spot_5y_rows": len(hist_df),
                "expiries_found": calls_df["expiry"].nunique() if not calls_df.empty else 0,
            }
        )

    note_df = pd.DataFrame(
        [
            {
                "note": (
                    "yfinance does not provide full historical daily option chain data for past 5 years. "
                    "This workbook contains all CURRENTLY available option expiries/chains plus 5Y spot history."
                )
            }
        ]
    )
    summary_df = pd.DataFrame(summary_rows)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="summary", index=False)
        note_df.to_excel(writer, sheet_name="note", index=False)
        for sheet, df in data.items():
            safe_sheet = sheet[:31]
            df.to_excel(writer, sheet_name=safe_sheet, index=False)

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()

