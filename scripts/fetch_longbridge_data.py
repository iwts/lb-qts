#!/usr/bin/env python3
"""
Fetch Longbridge market data through the authenticated `longbridge` CLI.

This script is the local adapter for the hosted Longbridge MCP setup. The
hosted MCP exposes the tools available to the current AI client, while the CLI
keeps full coverage for K-line, capital flow/distribution, and market
temperature data that existing parsers already consume.
"""
import argparse
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from utils import run_longbridge_json, symbol_data_dir


PERIOD_MAP = {
    "1h": "1h",
    "1d": "day",
    "1w": "week",
    "1M": "month",
}


def _write_json(path: str, data: Any) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _normalize_kline(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        normalized.append({
            "timestamp": row.get("timestamp") or row.get("time") or "",
            "open": row.get("open", 0),
            "high": row.get("high", 0),
            "low": row.get("low", 0),
            "close": row.get("close", 0),
            "volume": row.get("volume", 0),
            "turnover": row.get("turnover", 0),
        })
    return normalized


def _normalize_quote(rows: Any) -> dict[str, Any]:
    item = rows[0] if isinstance(rows, list) and rows else rows
    if not isinstance(item, dict):
        return {}
    return {
        "timestamp": item.get("timestamp", ""),
        "symbol": item.get("symbol", ""),
        "last_done": item.get("last_done") or item.get("last") or 0,
        "open": item.get("open", 0),
        "high": item.get("high", 0),
        "low": item.get("low", 0),
        "prev_close": item.get("prev_close", 0),
        "volume": item.get("volume", 0),
        "turnover": item.get("turnover", 0),
        "trade_status": item.get("trade_status") or item.get("status", ""),
    }


def _normalize_capital_flow(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [
        {
            "timestamp": row.get("timestamp") or row.get("time") or "",
            "inflow": row.get("inflow", 0),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def _normalize_market_temperature(rows: Any) -> dict[str, Any]:
    if isinstance(rows, list):
        return {
            str(item.get("field", "")).lower().replace(" ", "_"): item.get("value")
            for item in rows
            if isinstance(item, dict) and item.get("field")
        }
    return rows if isinstance(rows, dict) else {}


def fetch_kline(symbol: str, period: str, count: int, output_dir: str) -> str:
    cli_period = PERIOD_MAP[period]
    rows = run_longbridge_json([
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
    ])
    return _write_json(
        os.path.join(output_dir, f"{period}_mcp.json"),
        _normalize_kline(rows),
    )


def fetch_quote(symbol: str, output_dir: str) -> str:
    rows = run_longbridge_json(["quote", symbol])
    return _write_json(
        os.path.join(output_dir, "quote_mcp.json"),
        _normalize_quote(rows),
    )


def fetch_capital_flow(symbol: str, output_dir: str) -> str:
    rows = run_longbridge_json(["capital", symbol, "--flow"])
    return _write_json(
        os.path.join(output_dir, "capital_flow_mcp.json"),
        _normalize_capital_flow(rows),
    )


def fetch_capital_distribution(symbol: str, output_dir: str) -> str:
    data = run_longbridge_json(["capital", symbol])
    return _write_json(os.path.join(output_dir, "capital_distribution_mcp.json"), data)


def fetch_market_temperature(output_dir: str) -> str:
    data = run_longbridge_json(["market-temp"])
    return _write_json(
        os.path.join(output_dir, "market_temperature.json"),
        _normalize_market_temperature(data),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Longbridge data as parser-compatible JSON")
    parser.add_argument("--symbol", required=True, help="Symbol in <CODE>.<MARKET> format")
    parser.add_argument("--periods", default="1h,1d,1w", help="K-line periods to fetch")
    parser.add_argument("--count", type=int, default=100, help="Candles per period")
    parser.add_argument(
        "--fetch",
        default="kline,quote,capital_flow,capital_distribution,market_temperature",
        help="Comma-separated data kinds",
    )
    parser.add_argument("--output-dir", help="Output directory; defaults to data/<symbol>/tmp")
    args = parser.parse_args()

    out_dir = args.output_dir or os.path.join(symbol_data_dir(args.symbol), "tmp")
    kinds = {item.strip() for item in args.fetch.split(",") if item.strip()}
    output_files: dict[str, str] = {}

    if "kline" in kinds:
        for period in [p.strip() for p in args.periods.split(",") if p.strip()]:
            if period not in PERIOD_MAP:
                raise SystemExit(f"unsupported period: {period}")
            output_files[period] = fetch_kline(args.symbol, period, args.count, out_dir)

    if "quote" in kinds:
        output_files["quote"] = fetch_quote(args.symbol, out_dir)
    if "capital_flow" in kinds:
        output_files["capital_flow"] = fetch_capital_flow(args.symbol, out_dir)
    if "capital_distribution" in kinds:
        output_files["capital_distribution"] = fetch_capital_distribution(args.symbol, out_dir)
    if "market_temperature" in kinds:
        output_files["market_temperature"] = fetch_market_temperature(out_dir)

    print(json.dumps({
        "symbol": args.symbol,
        "status": "ok",
        "output_dir": out_dir,
        "output_files": output_files,
    }, ensure_ascii=False, indent=2))
