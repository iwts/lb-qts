#!/usr/bin/env python3
"""
通过 longbridge CLI 拉取 capital_flow、capital_distribution 和 quote。
供 parse_mcp_data.py 解析。统一复用现有 CLI 登录态。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir, log, run_longbridge_json


def run(symbol: str):
    data_dir = symbol_data_dir(symbol)
    os.makedirs(data_dir, exist_ok=True)
    flow_path = os.path.join(data_dir, "capital_flow_raw.json")
    try:
        lines = run_longbridge_json(["capital", symbol, "--flow"])
        data = [{"timestamp": item["time"].replace(" ", "T"), "inflow": item["inflow"]} for item in lines]
        with open(flow_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"capital_flow: {len(data)} 条 -> {flow_path}")
    except Exception as e:
        log.warning(f"capital_flow 拉取失败: {e}")

    dist_path = os.path.join(data_dir, "capital_dist_raw.json")
    try:
        resp = run_longbridge_json(["capital", symbol])
        data = {
            "timestamp": resp["timestamp"].replace(" ", "T"),
            "capital_in": resp["capital_in"],
            "capital_out": resp["capital_out"],
        }
        with open(dist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"capital_distribution -> {dist_path}")
    except Exception as e:
        log.warning(f"capital_distribution 拉取失败: {e}")

    quote_path = os.path.join(data_dir, "quote_raw.json")
    try:
        quotes = run_longbridge_json(["quote", symbol])
        if quotes:
            q = quotes[0]
            ts = None
            if q.get("post_market_quote") and q["post_market_quote"].get("timestamp"):
                ts = q["post_market_quote"]["timestamp"]
            elif q.get("pre_market_quote") and q["pre_market_quote"].get("timestamp"):
                ts = q["pre_market_quote"]["timestamp"]
            else:
                ts = q.get("timestamp") or ""
            qobj = {
                "timestamp": ts.replace(" ", "T"),
                "symbol": q["symbol"],
                "last_done": q["last"],
                "open": q["open"],
                "high": q["high"],
                "low": q["low"],
                "prev_close": q["prev_close"],
                "volume": q["volume"],
                "turnover": q["turnover"],
            }
            with open(quote_path, "w", encoding="utf-8") as f:
                json.dump(qobj, f, ensure_ascii=False, indent=2)
            log.info(f"quote -> {quote_path}")
    except Exception as e:
        log.warning(f"quote 拉取失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args()
    run(args.symbol)
