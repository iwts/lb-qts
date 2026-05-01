#!/usr/bin/env python3
"""
解析期权链数据，计算关键期权指标。

数据来源：Longbridge 官方行情路径（hosted MCP 已暴露的 option_quote /
option_volume，或 longbridge CLI 的 option chain / option quote）。
由 Data Agent 先将期权链和报价结果保存为 JSON，再调用本脚本。

调用流程：
  1. 获取到期日列表
  2. 获取最近 2 个到期日的行权价和 call/put symbol
  3. 获取接近平值的 call/put symbols 的 last_done, volume 等报价字段

用法：
  .venv/bin/python scripts/fetch_option_chain.py --symbol NVDA.US \
      --chain-file /tmp/option_chain.json \
      --quotes-file /tmp/option_quotes.json \
      --current-price 177.0

输出：data/<标的>/option_analysis.json
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def calc_put_call_ratio(quotes: list) -> dict:
    """计算 Put/Call Ratio（基于成交量和 OI）"""
    total_call_vol = 0
    total_put_vol = 0
    total_call_oi = 0
    total_put_oi = 0

    for q in quotes:
        symbol = q.get("symbol", "")
        vol = safe_float(q.get("volume", 0))
        oi = safe_float(q.get("open_interest", 0))

        if "C" in symbol.split(".")[-2][-7:]:
            total_call_vol += vol
            total_call_oi += oi
        elif "P" in symbol.split(".")[-2][-7:]:
            total_put_vol += vol
            total_put_oi += oi

    vol_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else 0
    oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 0

    if vol_ratio > 1.5:
        sentiment = "极度看空（Put 远超 Call，恐慌或对冲需求高）"
    elif vol_ratio > 1.0:
        sentiment = "偏空（Put 多于 Call）"
    elif vol_ratio > 0.7:
        sentiment = "中性偏空"
    elif vol_ratio > 0.5:
        sentiment = "中性"
    elif vol_ratio > 0.3:
        sentiment = "偏多"
    else:
        sentiment = "极度看多（Call 远超 Put）"

    return {
        "volume_pc_ratio": round(vol_ratio, 2),
        "oi_pc_ratio": round(oi_ratio, 2),
        "total_call_volume": int(total_call_vol),
        "total_put_volume": int(total_put_vol),
        "total_call_oi": int(total_call_oi),
        "total_put_oi": int(total_put_oi),
        "sentiment": sentiment,
    }


def calc_max_pain(chain_data: list, quotes: list, current_price: float) -> dict:
    """计算 Max Pain（期权到期时让最多买方亏损的价位）"""
    strikes = []
    for item in chain_data:
        strike = safe_float(item.get("price", 0))
        if strike > 0:
            strikes.append(strike)

    if not strikes:
        return {"max_pain": 0, "note": "无行权价数据"}

    oi_by_strike = {}
    for q in quotes:
        symbol = q.get("symbol", "")
        oi = safe_float(q.get("open_interest", 0))
        vol = safe_float(q.get("volume", 0))
        weight = oi if oi > 0 else vol

        for item in chain_data:
            if symbol == item.get("call_symbol") or symbol == item.get("put_symbol"):
                strike = safe_float(item.get("price", 0))
                if strike not in oi_by_strike:
                    oi_by_strike[strike] = {"call_weight": 0, "put_weight": 0}
                if symbol == item.get("call_symbol"):
                    oi_by_strike[strike]["call_weight"] = weight
                else:
                    oi_by_strike[strike]["put_weight"] = weight
                break

    if not oi_by_strike:
        min_diff = float('inf')
        max_pain_price = current_price
        for s in strikes:
            diff = abs(s - current_price)
            if diff < min_diff:
                min_diff = diff
                max_pain_price = s
        return {"max_pain": max_pain_price, "note": "基于最近平值估算（无OI数据）"}

    min_pain = float('inf')
    max_pain_price = strikes[0]

    for test_price in strikes:
        total_pain = 0
        for strike, data in oi_by_strike.items():
            call_pain = max(0, test_price - strike) * data["call_weight"]
            put_pain = max(0, strike - test_price) * data["put_weight"]
            total_pain += call_pain + put_pain

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_price = test_price

    distance_pct = (max_pain_price / current_price - 1) * 100 if current_price > 0 else 0
    return {
        "max_pain": max_pain_price,
        "current_price": current_price,
        "distance": f"{distance_pct:+.1f}%",
        "note": "期权到期日股价倾向靠近此价位",
    }


def find_iv_skew(quotes: list, chain_data: list, current_price: float) -> dict:
    """IV 偏斜分析（如果有 IV 数据）"""
    iv_data = []
    for q in quotes:
        iv = safe_float(q.get("implied_volatility", 0))
        if iv > 0:
            symbol = q.get("symbol", "")
            for item in chain_data:
                if symbol == item.get("call_symbol") or symbol == item.get("put_symbol"):
                    strike = safe_float(item.get("price", 0))
                    direction = "call" if symbol == item.get("call_symbol") else "put"
                    iv_data.append({"strike": strike, "iv": iv, "direction": direction})
                    break

    if not iv_data:
        return {"available": False, "note": "IV 数据不可用（非交易时段或无权限）"}

    atm_iv = None
    min_dist = float('inf')
    for d in iv_data:
        dist = abs(d["strike"] - current_price)
        if dist < min_dist:
            min_dist = dist
            atm_iv = d["iv"]

    otm_put_ivs = [d["iv"] for d in iv_data if d["direction"] == "put" and d["strike"] < current_price * 0.95]
    otm_call_ivs = [d["iv"] for d in iv_data if d["direction"] == "call" and d["strike"] > current_price * 1.05]

    avg_put_iv = sum(otm_put_ivs) / len(otm_put_ivs) if otm_put_ivs else 0
    avg_call_iv = sum(otm_call_ivs) / len(otm_call_ivs) if otm_call_ivs else 0

    skew = "中性"
    if avg_put_iv > avg_call_iv * 1.3:
        skew = "看空偏斜（下方保护需求高）"
    elif avg_call_iv > avg_put_iv * 1.3:
        skew = "看多偏斜（上方投机需求高）"

    return {
        "available": True,
        "atm_iv": f"{atm_iv:.1f}%" if atm_iv else "N/A",
        "avg_otm_put_iv": f"{avg_put_iv:.1f}%",
        "avg_otm_call_iv": f"{avg_call_iv:.1f}%",
        "skew": skew,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze option chain data")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--chain-file", help="Path to option_chain_info JSON")
    parser.add_argument("--quotes-file", help="Path to option quotes JSON")
    parser.add_argument("--current-price", type=float, default=0)
    args = parser.parse_args()

    symbol_dir = os.path.join(DATA_DIR, args.symbol)
    os.makedirs(symbol_dir, exist_ok=True)

    chain_data = []
    if args.chain_file and os.path.exists(args.chain_file):
        with open(args.chain_file, "r") as f:
            chain_data = json.load(f)

    quotes = []
    if args.quotes_file and os.path.exists(args.quotes_file):
        with open(args.quotes_file, "r") as f:
            quotes = json.load(f)

    result = {
        "symbol": args.symbol,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_price": args.current_price,
        "has_options": len(chain_data) > 0,
    }

    if chain_data:
        result["put_call_ratio"] = calc_put_call_ratio(quotes)
        result["max_pain"] = calc_max_pain(chain_data, quotes, args.current_price)
        result["iv_skew"] = find_iv_skew(quotes, chain_data, args.current_price)
    else:
        result["note"] = "该标的无期权数据（仅美股有期权链）"

    output_path = os.path.join(symbol_dir, "option_analysis.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"OK: {output_path}")
    if result.get("has_options"):
        pcr = result.get("put_call_ratio", {})
        print(f"  P/C Ratio: {pcr.get('volume_pc_ratio', 0)} ({pcr.get('sentiment', '—')})")
        mp = result.get("max_pain", {})
        print(f"  Max Pain: {mp.get('max_pain', 0)} ({mp.get('distance', '—')})")


if __name__ == "__main__":
    main()
