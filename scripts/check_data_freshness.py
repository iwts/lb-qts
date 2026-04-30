#!/usr/bin/env python3
"""
检查本地 K 线数据的新鲜度，计算增量拉取所需的 count。

用法:
    python check_data_freshness.py --symbol 0700.HK
    python check_data_freshness.py --symbol 0700.HK --periods 1h,1d,1w

输出 JSON，供 Agent 读取后决定 candlesticks 的 count 参数:
{
  "symbol": "0700.HK",
  "periods": {
    "1h": {"status": "stale", "count": 25, "existing_rows": 1000, "latest": "2026-02-25T08:00:00Z", "hours_ago": 20.5},
    "1d": {"status": "fresh", "count": 0, "existing_rows": 1000, "latest": "2026-02-25T16:00:00Z", "hours_ago": 2.3},
    "1w": {"status": "missing", "count": 1000, "existing_rows": 0, "latest": null, "hours_ago": null}
  }
}

status 说明:
  - "missing": 无本地数据，需全量拉取 1000 条
  - "stale":   有数据但不是最新，需增量拉取 count 条
  - "fresh":   数据已是最新（距今 < 1 个周期），无需拉取
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir

PERIOD_CONFIG = {
    "1h": {"csv": "1h_k.csv", "mcp_period": "60m",   "bar_hours": 1,    "freshness_hours": 2},
    "1d": {"csv": "1d_k.csv", "mcp_period": "day",    "bar_hours": 24,   "freshness_hours": 18},
    "1w": {"csv": "1w_k.csv", "mcp_period": "week",   "bar_hours": 168,  "freshness_hours": 120},
    "1M": {"csv": "1M_k.csv", "mcp_period": "month",  "bar_hours": 720,  "freshness_hours": 600},
}

MARKET_CONFIG = {
    ".US": {"tz": "America/New_York", "open_hour": 9, "close_hour": 16},
    ".HK": {"tz": "Asia/Hong_Kong", "open_hour": 9, "close_hour": 16},
    ".SH": {"tz": "Asia/Shanghai", "open_hour": 9, "close_hour": 15},
    ".SZ": {"tz": "Asia/Shanghai", "open_hour": 9, "close_hour": 15},
}

FULL_FETCH_COUNT = 1000
MIN_INCREMENTAL_COUNT = 20
SAFETY_BUFFER_RATIO = 2.0


def _parse_latest_timestamp(csv_path: str) -> datetime | None:
    """读取 CSV 最后一行的 timestamp，解析为 UTC datetime。"""
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return None
    try:
        df = pd.read_csv(csv_path, usecols=["timestamp"])
        if df.empty:
            return None
        return pd.to_datetime(df["timestamp"].iloc[-1], utc=True).to_pydatetime()
    except Exception:
        return None


def _market_meta(symbol: str) -> dict:
    for suffix, meta in MARKET_CONFIG.items():
        if symbol.endswith(suffix):
            return meta
    return MARKET_CONFIG[".US"]


def _prev_trading_day(d: date) -> date:
    cur = d - timedelta(days=1)
    while cur.weekday() >= 5:
        cur -= timedelta(days=1)
    return cur


def _expected_latest_date(symbol: str, period: str, now_utc: datetime) -> date | None:
    if period not in {"1h", "1d"}:
        return None
    meta = _market_meta(symbol)
    local_now = now_utc.astimezone(ZoneInfo(meta["tz"]))
    current_date = local_now.date()
    if current_date.weekday() >= 5:
        return _prev_trading_day(current_date)
    if period == "1d" and local_now.hour < meta["close_hour"] + 1:
        return _prev_trading_day(current_date)
    if period == "1h" and local_now.hour < meta["open_hour"]:
        return _prev_trading_day(current_date)
    return current_date


def check_period(symbol: str, period: str) -> dict:
    cfg = PERIOD_CONFIG.get(period)
    if not cfg:
        return {"status": "unknown", "count": 0, "error": f"不支持的周期: {period}"}

    data_dir = symbol_data_dir(symbol)
    csv_path = os.path.join(data_dir, cfg["csv"])

    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return {
            "status": "missing",
            "count": FULL_FETCH_COUNT,
            "existing_rows": 0,
            "latest": None,
            "hours_ago": None,
            "mcp_period": cfg["mcp_period"],
        }

    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return {
            "status": "missing",
            "count": FULL_FETCH_COUNT,
            "existing_rows": 0,
            "latest": None,
            "hours_ago": None,
            "mcp_period": cfg["mcp_period"],
        }

    existing_rows = len(df)
    latest_dt = _parse_latest_timestamp(csv_path)

    if latest_dt is None:
        return {
            "status": "missing",
            "count": FULL_FETCH_COUNT,
            "existing_rows": 0,
            "latest": None,
            "hours_ago": None,
            "mcp_period": cfg["mcp_period"],
        }

    now = datetime.now(timezone.utc)
    hours_ago = (now - latest_dt).total_seconds() / 3600
    expected_date = _expected_latest_date(symbol, period, now)
    latest_local_date = latest_dt.astimezone(ZoneInfo(_market_meta(symbol)["tz"])).date()

    if hours_ago <= cfg["freshness_hours"] or (expected_date and latest_local_date >= expected_date):
        return {
            "status": "fresh",
            "count": 0,
            "existing_rows": existing_rows,
            "latest": latest_dt.isoformat(),
            "hours_ago": round(hours_ago, 1),
            "mcp_period": cfg["mcp_period"],
            "expected_latest_date": expected_date.isoformat() if expected_date else None,
        }

    estimated_bars = hours_ago / cfg["bar_hours"]
    safe_count = int(estimated_bars * SAFETY_BUFFER_RATIO) + MIN_INCREMENTAL_COUNT
    safe_count = max(safe_count, MIN_INCREMENTAL_COUNT)
    safe_count = min(safe_count, FULL_FETCH_COUNT)

    return {
        "status": "stale",
        "count": safe_count,
        "existing_rows": existing_rows,
        "latest": latest_dt.isoformat(),
        "hours_ago": round(hours_ago, 1),
        "mcp_period": cfg["mcp_period"],
        "expected_latest_date": expected_date.isoformat() if expected_date else None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检查 K 线数据新鲜度，输出增量拉取建议")
    parser.add_argument("--symbol", required=True, help="标的代码")
    parser.add_argument("--periods", default="1h,1d,1w", help="周期，逗号分隔")
    args = parser.parse_args()

    result = {"symbol": args.symbol, "periods": {}}
    for p in args.periods.split(","):
        result["periods"][p] = check_period(args.symbol, p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
