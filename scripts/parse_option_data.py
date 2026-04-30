#!/usr/bin/env python3
"""
解析期权 MCP 数据，生成期权 OI 分析文件。

用法:
    python parse_option_data.py --symbol NVDA.US \
        --option-quote-file /tmp/opt_quotes.json \
        --current-price 195.5

输入:
    MCP quote 工具对期权合约的批量查询结果（JSON）。
    支持两种格式：
    - 包含 option_extend 字段（完整期权数据：OI、IV 等）
    - 不含 option_extend（降级模式：仅使用 volume 和 last_done）

输出:
    data/<标的>/option_oi.csv         — 期权链逐合约明细
    data/<标的>/option_summary.json   — 结构化分析摘要（max pain、P/C ratio、OI 集中度、gamma wall）
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir, log


def _parse_direction_from_symbol(symbol: str) -> str:
    """从期权代码中提取方向 (C/P)，如 NVDA260306C200000.US → C"""
    m = re.search(r"[CP](?=\d)", symbol)
    return m.group(0) if m else ""


def _parse_strike_from_symbol(symbol: str) -> float:
    """从期权代码中提取行权价，如 NVDA260306C200000.US → 200.0"""
    m = re.search(r"[CP](\d+)\.", symbol)
    if m:
        raw = m.group(1)
        return int(raw) / 1000
    return 0.0


def _parse_expiry_from_symbol(symbol: str) -> str:
    """从期权代码中提取到期日，如 NVDA260306C200000.US → 20260306"""
    m = re.search(r"(\d{6})[CP]", symbol)
    if m:
        return "20" + m.group(1)
    return ""


def parse_option_quotes(raw_data) -> pd.DataFrame:
    """解析 MCP quote 返回的期权报价数据。兼容有/无 option_extend 两种格式。"""
    items = []
    if isinstance(raw_data, dict):
        if "secu_quote" in raw_data:
            items = raw_data["secu_quote"]
        else:
            items = [raw_data]
    elif isinstance(raw_data, list):
        items = raw_data

    rows = []
    for item in items:
        symbol = item.get("symbol", "")
        if not symbol:
            continue

        opt_ext = item.get("option_extend", {})
        if opt_ext and opt_ext.get("strike_price"):
            rows.append({
                "symbol": symbol,
                "last_done": float(item.get("last_done", 0)),
                "volume": int(item.get("volume", 0)),
                "open_interest": int(opt_ext.get("open_interest", 0)),
                "implied_volatility": float(opt_ext.get("implied_volatility", 0)),
                "strike_price": float(opt_ext.get("strike_price", 0)),
                "direction": opt_ext.get("direction", ""),
                "expiry_date": opt_ext.get("expiry_date", ""),
                "historical_volatility": float(opt_ext.get("historical_volatility", 0)),
            })
        else:
            rows.append({
                "symbol": symbol,
                "last_done": float(item.get("last_done", 0)),
                "volume": int(item.get("volume", 0)),
                "open_interest": 0,
                "implied_volatility": 0.0,
                "strike_price": _parse_strike_from_symbol(symbol),
                "direction": _parse_direction_from_symbol(symbol),
                "expiry_date": _parse_expiry_from_symbol(symbol),
                "historical_volatility": 0.0,
            })

    return pd.DataFrame(rows)


def calc_max_pain(df: pd.DataFrame) -> dict:
    """计算每个到期日的 max pain 价位（期权卖方最大收益点）。"""
    result = {}
    for expiry in df["expiry_date"].unique():
        expiry_df = df[df["expiry_date"] == expiry]
        strikes = sorted(expiry_df["strike_price"].unique())
        if not strikes:
            continue

        oi_col = "open_interest" if df["open_interest"].sum() > 0 else "volume"

        min_pain = float("inf")
        max_pain_strike = 0.0

        for test_strike in strikes:
            total_pain = 0.0
            for _, row in expiry_df.iterrows():
                weight = row[oi_col]
                strike = row["strike_price"]
                if row["direction"] == "C":
                    total_pain += max(0, test_strike - strike) * weight
                else:
                    total_pain += max(0, strike - test_strike) * weight

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_strike

        result[expiry] = max_pain_strike
    return result


def calc_put_call_ratio(df: pd.DataFrame) -> dict:
    """计算看跌/看涨比率（OI 和成交量两个维度）。"""
    calls = df[df["direction"] == "C"]
    puts = df[df["direction"] == "P"]

    call_oi = int(calls["open_interest"].sum())
    put_oi = int(puts["open_interest"].sum())
    call_vol = int(calls["volume"].sum())
    put_vol = int(puts["volume"].sum())

    return {
        "oi_ratio": round(put_oi / call_oi, 3) if call_oi > 0 else 0,
        "volume_ratio": round(put_vol / call_vol, 3) if call_vol > 0 else 0,
        "total_call_oi": call_oi,
        "total_put_oi": put_oi,
        "total_call_volume": call_vol,
        "total_put_volume": put_vol,
    }


def find_oi_concentration(df: pd.DataFrame, current_price: float, top_n: int = 5) -> dict:
    """识别 OI/成交量集中的行权价：gamma wall、put support、关键阻力/支撑。"""
    weight_col = "open_interest" if df["open_interest"].sum() > 0 else "volume"

    grouped = df.groupby(["strike_price", "direction"]).agg(
        total_weight=(weight_col, "sum"),
        total_volume=("volume", "sum"),
        avg_iv=("implied_volatility", "mean"),
    ).reset_index()

    top_calls = grouped[grouped["direction"] == "C"].nlargest(top_n, "total_weight")
    top_puts = grouped[grouped["direction"] == "P"].nlargest(top_n, "total_weight")

    above_calls = grouped[
        (grouped["direction"] == "C") & (grouped["strike_price"] > current_price)
    ]
    gamma_wall = (
        float(above_calls.nlargest(1, "total_weight")["strike_price"].iloc[0])
        if not above_calls.empty else None
    )

    below_puts = grouped[
        (grouped["direction"] == "P") & (grouped["strike_price"] < current_price)
    ]
    put_support = (
        float(below_puts.nlargest(1, "total_weight")["strike_price"].iloc[0])
        if not below_puts.empty else None
    )

    has_oi = df["open_interest"].sum() > 0

    return {
        "metric": "open_interest" if has_oi else "volume (OI不可用，降级为成交量)",
        "top_call_strikes": [
            {"strike": float(r["strike_price"]), "weight": int(r["total_weight"]),
             "iv": round(float(r["avg_iv"]), 4)}
            for _, r in top_calls.iterrows()
        ],
        "top_put_strikes": [
            {"strike": float(r["strike_price"]), "weight": int(r["total_weight"]),
             "iv": round(float(r["avg_iv"]), 4)}
            for _, r in top_puts.iterrows()
        ],
        "gamma_wall": gamma_wall,
        "put_support": put_support,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="解析期权 MCP 数据并生成分析摘要")
    parser.add_argument("--symbol", required=True, help="标的代码，如 NVDA.US")
    parser.add_argument("--option-quote-file", required=True,
                        help="MCP quote 工具对期权合约的返回 JSON 文件路径")
    parser.add_argument("--current-price", type=float, required=True,
                        help="标的当前价格（用于计算 gamma wall 等相对位置）")
    args = parser.parse_args()

    data_dir = symbol_data_dir(args.symbol)

    with open(args.option_quote_file, "r") as f:
        raw_data = json.loads(f.read().strip())

    df = parse_option_quotes(raw_data)

    if df.empty:
        log.warning("未解析到有效的期权数据，跳过")
        sys.exit(0)

    csv_path = os.path.join(data_dir, "option_oi.csv")
    df.to_csv(csv_path, index=False)
    log.info(f"期权链明细: {len(df)} 条 → {csv_path}")

    max_pain = calc_max_pain(df)
    pc_ratio = calc_put_call_ratio(df)
    oi_conc = find_oi_concentration(df, args.current_price)

    summary = {
        "symbol": args.symbol,
        "current_price": args.current_price,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_contracts": len(df),
        "expiry_dates": sorted(df["expiry_date"].unique().tolist()),
        "has_open_interest": bool(df["open_interest"].sum() > 0),
        "max_pain": max_pain,
        "put_call_ratio": pc_ratio,
        "oi_concentration": oi_conc,
    }

    summary_path = os.path.join(data_dir, "option_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    log.info(f"期权分析摘要 → {summary_path}")

    log.info("=== 期权关键发现 ===")
    log.info(f"P/C OI 比率: {pc_ratio['oi_ratio']}  |  P/C 成交量比率: {pc_ratio['volume_ratio']}")
    for expiry, mp in max_pain.items():
        log.info(f"Max Pain ({expiry}): {mp}")
    if oi_conc.get("gamma_wall"):
        log.info(f"Gamma Wall（上方最大 Call OI 集中价）: {oi_conc['gamma_wall']}")
    if oi_conc.get("put_support"):
        log.info(f"Put Support（下方最大 Put OI 集中价）: {oi_conc['put_support']}")
