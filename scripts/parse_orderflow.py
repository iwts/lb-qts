#!/usr/bin/env python3
"""
解析盘口深度和逐笔成交数据，生成订单流分析。

数据来源：Longbridge 官方行情路径返回的 depth 和 trades JSON。
由 Orchestrator / Data Agent 将 JSON 保存到临时文件，再调用本脚本解析。

用法：
  .venv/bin/python scripts/parse_orderflow.py --symbol 0700.HK \
      --depth-file /tmp/depth.json \
      --trades-file /tmp/trades.json

输出：data/<标的>/orderflow_snapshot.json
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def analyze_depth(depth_data: dict) -> dict:
    """分析盘口深度：买卖力量对比"""
    asks = depth_data.get("asks", [])
    bids = depth_data.get("bids", [])

    total_ask_vol = sum(safe_float(a.get("volume", 0)) for a in asks)
    total_bid_vol = sum(safe_float(b.get("volume", 0)) for b in bids)
    total_ask_orders = sum(int(a.get("order_num", 0)) for a in asks)
    total_bid_orders = sum(int(b.get("order_num", 0)) for b in bids)

    bid_ask_ratio = total_bid_vol / total_ask_vol if total_ask_vol > 0 else 0

    if bid_ask_ratio > 2.0:
        pressure = "强买盘压力（买盘量 > 卖盘量 2倍以上）"
    elif bid_ask_ratio > 1.3:
        pressure = "买盘占优"
    elif bid_ask_ratio > 0.7:
        pressure = "买卖均衡"
    elif bid_ask_ratio > 0.5:
        pressure = "卖盘占优"
    else:
        pressure = "强卖盘压力（卖盘量 > 买盘量 2倍以上）"

    best_ask = safe_float(asks[0]["price"]) if asks else 0
    best_bid = safe_float(bids[0]["price"]) if bids else 0
    spread = best_ask - best_bid if best_ask and best_bid else 0
    spread_pct = (spread / best_bid * 100) if best_bid > 0 else 0

    top_ask_levels = []
    for a in asks[:5]:
        top_ask_levels.append({
            "price": safe_float(a.get("price")),
            "volume": int(safe_float(a.get("volume", 0))),
            "orders": int(a.get("order_num", 0)),
        })

    top_bid_levels = []
    for b in bids[:5]:
        top_bid_levels.append({
            "price": safe_float(b.get("price")),
            "volume": int(safe_float(b.get("volume", 0))),
            "orders": int(b.get("order_num", 0)),
        })

    return {
        "total_ask_volume": int(total_ask_vol),
        "total_bid_volume": int(total_bid_vol),
        "bid_ask_volume_ratio": round(bid_ask_ratio, 2),
        "total_ask_orders": total_ask_orders,
        "total_bid_orders": total_bid_orders,
        "pressure_judgment": pressure,
        "spread": round(spread, 3),
        "spread_pct": f"{spread_pct:.3f}%",
        "top_ask_levels": top_ask_levels,
        "top_bid_levels": top_bid_levels,
    }


def analyze_trades(trades_data: list) -> dict:
    """分析逐笔成交：主动买卖比例、大单识别"""
    if not trades_data:
        return {"error": "no trades data"}

    total_up_vol = 0
    total_down_vol = 0
    total_neutral_vol = 0
    total_up_count = 0
    total_down_count = 0

    large_trades = []
    volumes = [safe_float(t.get("volume", 0)) for t in trades_data]
    avg_vol = sum(volumes) / len(volumes) if volumes else 0
    large_threshold = avg_vol * 5

    for t in trades_data:
        vol = safe_float(t.get("volume", 0))
        direction = t.get("direction", "")
        price = safe_float(t.get("price", 0))

        if direction == "Up":
            total_up_vol += vol
            total_up_count += 1
        elif direction == "Down":
            total_down_vol += vol
            total_down_count += 1
        else:
            total_neutral_vol += vol

        if vol >= large_threshold and vol > 0:
            large_trades.append({
                "price": price,
                "volume": int(vol),
                "direction": direction,
                "timestamp": t.get("timestamp", ""),
                "trade_type": t.get("trade_type", ""),
            })

    total_vol = total_up_vol + total_down_vol + total_neutral_vol
    buy_ratio = total_up_vol / total_vol if total_vol > 0 else 0
    sell_ratio = total_down_vol / total_vol if total_vol > 0 else 0

    if buy_ratio > 0.6:
        flow_judgment = "主动买入主导（买方积极进攻）"
    elif sell_ratio > 0.6:
        flow_judgment = "主动卖出主导（卖方积极出货）"
    elif buy_ratio > 0.45:
        flow_judgment = "买方略占优"
    elif sell_ratio > 0.45:
        flow_judgment = "卖方略占优"
    else:
        flow_judgment = "买卖均衡"

    large_buy = sum(t["volume"] for t in large_trades if t["direction"] == "Up")
    large_sell = sum(t["volume"] for t in large_trades if t["direction"] == "Down")

    if large_trades:
        if large_buy > large_sell * 2:
            large_judgment = "大单以买入为主，可能有机构建仓"
        elif large_sell > large_buy * 2:
            large_judgment = "大单以卖出为主，可能有机构出货"
        else:
            large_judgment = "大单买卖较均衡"
    else:
        large_judgment = "未检测到明显大单"

    return {
        "total_trades": len(trades_data),
        "total_volume": int(total_vol),
        "active_buy_volume": int(total_up_vol),
        "active_sell_volume": int(total_down_vol),
        "neutral_volume": int(total_neutral_vol),
        "buy_ratio": f"{buy_ratio:.1%}",
        "sell_ratio": f"{sell_ratio:.1%}",
        "flow_judgment": flow_judgment,
        "large_trades_count": len(large_trades),
        "large_buy_volume": int(large_buy),
        "large_sell_volume": int(large_sell),
        "large_trade_judgment": large_judgment,
        "large_trades": large_trades[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="Parse orderflow data from MCP depth/trades")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--depth-file", help="Path to depth JSON file")
    parser.add_argument("--trades-file", help="Path to trades JSON file")
    args = parser.parse_args()

    symbol_dir = os.path.join(DATA_DIR, args.symbol)
    os.makedirs(symbol_dir, exist_ok=True)

    result = {
        "symbol": args.symbol,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.depth_file and os.path.exists(args.depth_file):
        with open(args.depth_file, "r") as f:
            depth_data = json.load(f)
        result["depth_analysis"] = analyze_depth(depth_data)
    else:
        result["depth_analysis"] = {"error": "no depth data file"}

    if args.trades_file and os.path.exists(args.trades_file):
        with open(args.trades_file, "r") as f:
            trades_data = json.load(f)
        result["trades_analysis"] = analyze_trades(trades_data)
    else:
        result["trades_analysis"] = {"error": "no trades data file"}

    output_path = os.path.join(symbol_dir, "orderflow_snapshot.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"OK: {output_path}")
    da = result.get("depth_analysis", {})
    ta = result.get("trades_analysis", {})
    if "error" not in da:
        print(f"  盘口: {da.get('pressure_judgment', '—')}, 买卖比={da.get('bid_ask_volume_ratio', 0)}")
    if "error" not in ta:
        print(f"  成交: {ta.get('flow_judgment', '—')}, 买入占比={ta.get('buy_ratio', '—')}")
        print(f"  大单: {ta.get('large_trade_judgment', '—')}")


if __name__ == "__main__":
    main()
