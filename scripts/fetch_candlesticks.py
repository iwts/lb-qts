#!/usr/bin/env python3
"""
通过 longbridge CLI 拉取 K 线数据，保存为 parse_mcp_data 兼容的 JSON 格式。
供增量合并到 data/<symbol>/。统一复用现有 CLI 登录态。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import log, run_longbridge_json

PERIOD_MAP = {
    "1h": "1h",
    "1d": "day",
    "1w": "week",
}


def candlestick_to_dict(item: dict) -> dict:
    return {
        "timestamp": item["time"].replace(" ", "T"),
        "open": item["open"],
        "high": item["high"],
        "low": item["low"],
        "close": item["close"],
        "volume": item["volume"],
        "turnover": item["turnover"],
    }


def run(symbol: str, periods: list[str], count: int = 200):
    tmp_dir = os.path.join("/tmp", "lb-qts-data", symbol)
    os.makedirs(tmp_dir, exist_ok=True)
    for p in periods:
        cli_period = PERIOD_MAP.get(p)
        if not cli_period:
            log.warning(f"跳过不支持的周期: {p}")
            continue
        try:
            candles = run_longbridge_json(
                [
                    "kline",
                    symbol,
                    "--period",
                    cli_period,
                    "--count",
                    str(count),
                    "--adjust",
                    "forward",
                    "--session",
                    "all",
                ]
            )
            data = [candlestick_to_dict(item) for item in candles]
            out_path = os.path.join(tmp_dir, f"{p}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log.info(f"{p}: {len(data)} 条 -> {out_path}")
        except Exception as e:
            log.warning(f"{p} 拉取失败: {e}")

    return tmp_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--periods", default="1h,1d,1w", help="逗号分隔: 1h,1d,1w")
    parser.add_argument("--count", type=int, default=200)
    args = parser.parse_args()
    run(args.symbol, args.periods.split(","), args.count)
