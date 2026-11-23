"""Ad-hoc benchmark for yfinance indicator window (dev only; not part of the public API)."""
import time

from tradingagents.dataflows.y_finance import get_stock_stats_indicators_window

if __name__ == "__main__":
    print("Testing optimized implementation with 30-day lookback:")
    start_time = time.time()
    result = get_stock_stats_indicators_window("AAPL", "macd", "2024-11-01", 30)
    end_time = time.time()
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Result length: {len(result)} characters")
    print(result)
