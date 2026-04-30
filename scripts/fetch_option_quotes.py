#!/usr/bin/env python3
"""
通过 longbridge CLI 拉取期权报价，输出 parse_option_data 可解析的 JSON 格式。

用法:
    python fetch_option_quotes.py --symbol NVDA.US --expiry-dates 2026-03-06,2026-03-13 \
        --strike-min 129.5 --strike-max 240.5 --output data/NVDA.US/tmp/option_quotes.json
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import run_longbridge_json


def option_quote_to_dict(q: dict) -> dict:
    """将 longbridge option quote 输出转为 parse_option_data 期望的格式。"""
    symbol = q["symbol"]
    raw_symbol = symbol.split(".")[0]
    match = re.search(r"(\d{6})([CP])", raw_symbol)
    if not match:
        raise ValueError(f"unexpected option symbol format: {symbol}")
    expiry_digits, direction = match.groups()
    expiry_str = f"20{expiry_digits[0:2]}-{expiry_digits[2:4]}-{expiry_digits[4:6]}"
    return {
        "symbol": symbol,
        "last_done": float(q.get("last", 0) or 0),
        "volume": int(q.get("volume", 0) or 0),
        "option_extend": {
            "open_interest": int(q.get("open_interest", 0) or 0),
            "implied_volatility": float(q.get("implied_volatility", 0) or 0),
            "strike_price": float(q.get("strike_price", 0) or 0),
            "direction": direction,
            "expiry_date": expiry_str.replace("-", ""),
            "historical_volatility": float(q.get("historical_volatility", 0) or 0),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="拉取期权报价并保存为 JSON")
    parser.add_argument("--symbol", required=True, help="标的代码，如 NVDA.US")
    parser.add_argument("--expiry-dates", required=True, help="到期日列表，逗号分隔，如 2026-03-06,2026-03-13")
    parser.add_argument("--strike-min", type=float, default=0, help="最小行权价")
    parser.add_argument("--strike-max", type=float, default=99999, help="最大行权价")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    args = parser.parse_args()

    expiry_dates = [d.strip() for d in args.expiry_dates.split(",")]
    all_symbols = []

    for ed in expiry_dates:
        chain = run_longbridge_json(["option", "chain", args.symbol, "--date", ed])
        for item in chain:
            try:
                strike = float(item.get("strike", 0))
            except (TypeError, ValueError):
                strike = 0.0
            if args.strike_min <= strike <= args.strike_max:
                all_symbols.append(item["call_symbol"])
                all_symbols.append(item["put_symbol"])

    all_symbols = list(dict.fromkeys(all_symbols))
    if not all_symbols:
        print("No symbols in strike range", file=sys.stderr)
        sys.exit(1)

    batch_size = 500
    results = []
    for i in range(0, len(all_symbols), batch_size):
        batch = all_symbols[i : i + batch_size]
        quotes = run_longbridge_json(["option", "quote", *batch])
        for q in quotes:
            results.append(option_quote_to_dict(q))

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(results)} option quotes to {args.output}")


if __name__ == "__main__":
    main()
