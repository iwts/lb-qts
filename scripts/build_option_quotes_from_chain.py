#!/usr/bin/env python3
"""
从 option_chain_info 返回的期权链构建 parse_option_data 可解析的 JSON。
当 MCP quote 对期权返回空、且无 LONGPORT 凭证时，用于验证解析链路。
数据中 OI/IV 为 0，仅验证结构。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--chain-0306", required=True, help="2026-03-06 期权链 JSON 文件或内联")
    parser.add_argument("--chain-0313", required=True, help="2026-03-13 期权链 JSON 文件或内联")
    parser.add_argument("--strike-min", type=float, default=129.5)
    parser.add_argument("--strike-max", type=float, default=240.5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    def load_chain(s):
        if s.startswith("["):
            return json.loads(s)
        with open(s) as f:
            return json.load(f)

    c1 = load_chain(args.chain_0306)
    c2 = load_chain(args.chain_0313)

    def in_range(p):
        try:
            x = float(p)
            return args.strike_min <= x <= args.strike_max
        except (TypeError, ValueError):
            return False

    rows = []
    for item in c1 + c2:
        if not in_range(item.get("price")):
            continue
        for key in ("call_symbol", "put_symbol"):
            sym = item.get(key)
            if not sym:
                continue
            direction = "C" if key == "call_symbol" else "P"
            try:
                strike = float(item.get("price", 0))
            except (TypeError, ValueError):
                strike = 0.0
            exp = "260306" if "260306" in sym else "260313"
            exp_full = "20260306" if "260306" in sym else "20260313"
            rows.append({
                "symbol": sym,
                "last_done": "0",
                "volume": 0,
                "option_extend": {
                    "open_interest": 0,
                    "implied_volatility": 0.0,
                    "strike_price": strike,
                    "direction": direction,
                    "expiry_date": exp_full,
                    "historical_volatility": 0.0,
                },
            })

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"Built {len(rows)} option rows (OI/IV=0) -> {args.output}")


if __name__ == "__main__":
    main()
