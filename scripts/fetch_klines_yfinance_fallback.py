#!/usr/bin/env python3
"""
用 yfinance 拉取 K 线并写出 parse_mcp_data 兼容 JSON。
仅作非核心兜底路径；主流程优先使用 longbridge CLI 或 MCP。
"""
import argparse
import json
import os
import sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(__file__))
from utils import log

# yfinance interval 映射
IV = {"1h": "60m", "1d": "1d", "1w": "1wk"}


def _iso_utc(ts) -> str:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(symbol: str, period_key: str, count: int) -> list[dict]:
    iv = IV[period_key]
    # 足够长的 lookback 以覆盖 count
    lookback = {"1h": "730d", "1d": "max", "1w": "max"}[period_key]
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=lookback, interval=iv, auto_adjust=True)
    if df is None or df.empty:
        log.warning(f"{symbol} {period_key}: yfinance 无数据")
        return []
    df = df.tail(count)
    rows = []
    for idx, row in df.iterrows():
        rows.append({
            "timestamp": _iso_utc(idx),
            "open": str(float(row["Open"])),
            "high": str(float(row["High"])),
            "low": str(float(row["Low"])),
            "close": str(float(row["Close"])),
            "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
            "turnover": str(float(row["Close"]) * float(row["Volume"])) if pd.notna(row["Volume"]) else "0",
        })
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--out-dir", required=True, help="例如 /tmp/lb-qts-data/0700.HK")
    p.add_argument("--hourly", type=int, default=0, help="1h 拉取条数，0 跳过")
    p.add_argument("--daily", type=int, default=0, help="日 K 条数，0 跳过")
    p.add_argument("--weekly", type=int, default=0, help="周 K 条数，0 跳过")
    args = p.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    spec = [("1h", args.hourly), ("1d", args.daily), ("1w", args.weekly)]
    for pk, cnt in spec:
        if cnt <= 0:
            continue
        data = fetch(args.symbol, pk, min(cnt, 1000))
        path = os.path.join(args.out_dir, f"{pk}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"{pk}: {len(data)} 条 -> {path}")


if __name__ == "__main__":
    main()
