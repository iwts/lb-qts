#!/usr/bin/env python3
"""
解析 MCP 工具返回的 JSON 数据，增量合并保存为标准 CSV。

用法:
    python parse_mcp_data.py --symbol 0700.HK --daily /tmp/daily.json --hourly /tmp/hourly.json
    python parse_mcp_data.py --symbol 0700.HK --capital-flow-file /tmp/flow.json
    python parse_mcp_data.py --symbol 0700.HK --quote-file /tmp/quote.json

K 线数据以 timestamp 为 key 做增量合并。
合并前会校验重叠区间的价格一致性，若检测到前复权因子变化或列结构变化，
清除该标的全部 K 线及衍生指标数据，以 exit code 2 退出，通知 Agent 全量重新获取。
"""
import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir, log

PRICE_DRIFT_THRESHOLD = 0.0001

KLINE_FILES = [
    "1h_k.csv", "1d_k.csv", "1w_k.csv", "1M_k.csv",
    "1h_indicators.csv", "1d_indicators.csv", "1w_indicators.csv", "1M_indicators.csv",
    "signals_summary.json",
]


def _check_price_drift(existing: pd.DataFrame, new_df: pd.DataFrame, key: str) -> bool:
    """比较重叠时间戳的 close 价格，判断前复权因子是否发生变化。"""
    if "close" not in existing.columns or "close" not in new_df.columns:
        return False

    overlap = pd.merge(
        existing[[key, "close"]], new_df[[key, "close"]],
        on=key, suffixes=("_old", "_new"),
    )
    if overlap.empty:
        return False

    old_prices = overlap["close_old"].astype(float)
    new_prices = overlap["close_new"].astype(float)
    rel_diff = (old_prices - new_prices).abs() / old_prices.abs().clip(lower=1e-9)
    return bool((rel_diff > PRICE_DRIFT_THRESHOLD).any())


def _wipe_kline_data(data_dir: str):
    """清除该标的全部 K 线原始数据和衍生指标数据。"""
    for fname in KLINE_FILES:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            log.info(f"已删除: {fname}")


def _merge_csv(path: str, new_df: pd.DataFrame, key: str = "timestamp") -> tuple[int, bool]:
    """
    增量合并 CSV。返回 (最终行数, 是否检测到漂移)。
    漂移包括：前复权因子变化、列结构不一致。
    检测到漂移时不写入任何数据，由调用方统一处理。
    """
    if new_df.empty:
        n = len(pd.read_csv(path)) if os.path.exists(path) and os.path.getsize(path) > 0 else 0
        return n, False

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        result = new_df.sort_values(key).reset_index(drop=True)
        result.to_csv(path, index=False)
        return len(result), False

    existing = pd.read_csv(path)

    if set(existing.columns) != set(new_df.columns):
        log.warning(f"列结构变化: {path}")
        return 0, True

    if _check_price_drift(existing, new_df, key):
        log.warning(f"前复权因子变化: {path}")
        return 0, True

    merged = pd.concat([existing, new_df], ignore_index=True)
    merged = merged.drop_duplicates(subset=[key], keep="last")
    merged = merged.sort_values(key).reset_index(drop=True)
    merged.to_csv(path, index=False)
    return len(merged), False


def parse_candlestick_file(path: str) -> pd.DataFrame:
    with open(path, "r") as f:
        data = json.loads(f.read().strip())
    rows = []
    for c in data:
        rows.append({
            "timestamp": c.get("timestamp", ""),
            "open": float(c.get("open", 0)),
            "high": float(c.get("high", 0)),
            "low": float(c.get("low", 0)),
            "close": float(c.get("close", 0)),
            "volume": int(c.get("volume", 0)),
            "turnover": float(c.get("turnover", 0)),
        })
    return pd.DataFrame(rows)


def parse_capital_flow_file(path: str) -> pd.DataFrame:
    with open(path, "r") as f:
        data = json.loads(f.read().strip())
    rows = []
    for item in data:
        rows.append({
            "timestamp": item.get("timestamp", ""),
            "inflow": float(item.get("inflow", 0)),
        })
    return pd.DataFrame(rows)


def parse_capital_distribution_file(path: str) -> pd.DataFrame:
    with open(path, "r") as f:
        data = json.loads(f.read().strip())
    return pd.DataFrame([{
        "timestamp": data.get("timestamp", ""),
        "large_in": float(data.get("capital_in", {}).get("large", 0)),
        "medium_in": float(data.get("capital_in", {}).get("medium", 0)),
        "small_in": float(data.get("capital_in", {}).get("small", 0)),
        "large_out": float(data.get("capital_out", {}).get("large", 0)),
        "medium_out": float(data.get("capital_out", {}).get("medium", 0)),
        "small_out": float(data.get("capital_out", {}).get("small", 0)),
    }])


def parse_quote_file(path: str) -> pd.DataFrame:
    with open(path, "r") as f:
        data = json.loads(f.read().strip())
    return pd.DataFrame([{
        "timestamp": data.get("timestamp", ""),
        "symbol": data.get("symbol", ""),
        "last_done": float(data.get("last_done", 0)),
        "open": float(data.get("open", 0)),
        "high": float(data.get("high", 0)),
        "low": float(data.get("low", 0)),
        "prev_close": float(data.get("prev_close", 0)),
        "volume": int(data.get("volume", 0)),
        "turnover": float(data.get("turnover", 0)),
    }])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="解析 MCP JSON 数据并增量合并保存为 CSV")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--daily", help="日K线 JSON 文件路径")
    parser.add_argument("--hourly", help="小时K线 JSON 文件路径")
    parser.add_argument("--weekly", help="周K线 JSON 文件路径")
    parser.add_argument("--monthly", help="月K线 JSON 文件路径")
    parser.add_argument("--capital-flow-file", help="资金流 JSON 文件路径")
    parser.add_argument("--capital-dist-file", help="资金分布 JSON 文件路径")
    parser.add_argument("--quote-file", help="报价 JSON 文件路径")
    args = parser.parse_args()

    data_dir = symbol_data_dir(args.symbol)

    kline_args = [
        (args.hourly,  "1h_k.csv",  "小时K线"),
        (args.daily,   "1d_k.csv",  "日K线"),
        (args.weekly,  "1w_k.csv",  "周K线"),
        (args.monthly, "1M_k.csv",  "月K线"),
    ]

    drift_detected = False
    for json_path, csv_name, label in kline_args:
        if not json_path:
            continue
        df = parse_candlestick_file(json_path)
        n, drift = _merge_csv(os.path.join(data_dir, csv_name), df)
        if drift:
            drift_detected = True
            break
        log.info(f"{label}: {n} 条 (增量合并)")

    if drift_detected:
        _wipe_kline_data(data_dir)
        log.error("=" * 60)
        log.error("检测到前复权因子变化或数据结构变化")
        log.error("已清除该标的全部 K 线及指标数据")
        log.error("请使用 count=1000 重新获取所有周期数据")
        log.error("=" * 60)
        sys.exit(2)

    if args.capital_flow_file:
        df = parse_capital_flow_file(args.capital_flow_file)
        n, _ = _merge_csv(os.path.join(data_dir, "capital_flow.csv"), df)
        log.info(f"资金流: {n} 条 (增量合并)")

    if args.capital_dist_file:
        df = parse_capital_distribution_file(args.capital_dist_file)
        df.to_csv(os.path.join(data_dir, "capital_distribution.csv"), index=False)
        log.info(f"资金分布: 1 条")

    if args.quote_file:
        df = parse_quote_file(args.quote_file)
        n, _ = _merge_csv(os.path.join(data_dir, "quote_snapshot.csv"), df)
        log.info(f"报价快照: {n} 条 (增量合并)")

    log.info(f"数据已保存到: {data_dir}")
