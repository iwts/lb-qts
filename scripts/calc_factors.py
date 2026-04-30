#!/usr/bin/env python3
"""
从 fundamental.json 和 indicators CSV 计算因子评分。

因子模型：
  - 价值因子：PE/PB/PS 排名 → 低估值高分
  - 质量因子：ROE 稳定性、利润率、低杠杆
  - 动量因子：过去 N 日收益率（学术标准：12M-1M 动量）
  - 防守因子：低波动率、高股息率

用法：
  .venv/bin/python scripts/calc_factors.py --symbol 0700.HK

输出：data/<标的>/factor_scores.json
"""

import argparse
import csv
import json
import math
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def safe_float(val, default=None):
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def score_value_factor(fundamental: dict) -> dict:
    """价值因子评分：低估值 = 高分"""
    pe = safe_float(fundamental.get("pe_trailing") or fundamental.get("pe_ttm") or fundamental.get("trailingPE"))
    fwd_pe = safe_float(fundamental.get("pe_forward") or fundamental.get("forwardPE"))
    pb = safe_float(fundamental.get("pb") or fundamental.get("priceToBook"))
    ps = safe_float(fundamental.get("ps") or fundamental.get("priceToSalesTrailing12Months"))
    div_yield = safe_float(fundamental.get("dividend_yield") or fundamental.get("dividendYield"), 0)

    scores = []
    details = {}

    if pe is not None and pe > 0:
        if pe < 10:
            s = 90
        elif pe < 15:
            s = 75
        elif pe < 25:
            s = 55
        elif pe < 40:
            s = 35
        else:
            s = 20
        scores.append(s)
        details["PE_TTM"] = {"value": round(pe, 1), "score": s}

    if fwd_pe is not None and fwd_pe > 0:
        if fwd_pe < 10:
            s = 90
        elif fwd_pe < 15:
            s = 75
        elif fwd_pe < 25:
            s = 55
        elif fwd_pe < 40:
            s = 35
        else:
            s = 20
        scores.append(s)
        details["Forward_PE"] = {"value": round(fwd_pe, 1), "score": s}

    if pb is not None and pb > 0:
        if pb < 1.0:
            s = 90
        elif pb < 2.0:
            s = 70
        elif pb < 4.0:
            s = 50
        elif pb < 8.0:
            s = 30
        else:
            s = 15
        scores.append(s)
        details["PB"] = {"value": round(pb, 2), "score": s}

    if div_yield > 0:
        # fundamental.json 中 dividend_yield 已是百分比形式（如 7.78 = 7.78%）
        dy_pct = div_yield
        if dy_pct > 5:
            s = 90
        elif dy_pct > 3:
            s = 70
        elif dy_pct > 1.5:
            s = 50
        else:
            s = 30
        scores.append(s)
        details["dividend_yield"] = {"value": f"{dy_pct:.2f}%", "score": s}

    final = round(sum(scores) / len(scores)) if scores else 50
    return {"score": final, "details": details, "note": "低估值=高分"}


def score_quality_factor(fundamental: dict) -> dict:
    """质量因子评分：高 ROE + 高利润率 + 低杠杆"""
    roe = safe_float(fundamental.get("roe") or fundamental.get("returnOnEquity"))
    roa = safe_float(fundamental.get("roa") or fundamental.get("returnOnAssets"))
    profit_margin = safe_float(fundamental.get("profit_margin") or fundamental.get("profitMargins"))
    op_margin = safe_float(fundamental.get("operating_margin") or fundamental.get("operatingMargins"))
    de_ratio = safe_float(fundamental.get("debt_to_equity") or fundamental.get("debtToEquity"))
    current_ratio = safe_float(fundamental.get("current_ratio") or fundamental.get("currentRatio"))
    fcf = safe_float(fundamental.get("free_cashflow") or fundamental.get("freeCashflow"))

    scores = []
    details = {}

    if roe is not None:
        # yfinance stores ratios as decimals (0.198 = 19.8%)
        roe_pct = roe * 100
        if roe_pct > 25:
            s = 90
        elif roe_pct > 15:
            s = 70
        elif roe_pct > 8:
            s = 50
        elif roe_pct > 0:
            s = 30
        else:
            s = 10
        scores.append(s)
        details["ROE"] = {"value": f"{roe_pct:.1f}%", "score": s}

    if profit_margin is not None:
        pm_pct = profit_margin * 100
        if pm_pct > 30:
            s = 90
        elif pm_pct > 15:
            s = 70
        elif pm_pct > 5:
            s = 50
        elif pm_pct > 0:
            s = 30
        else:
            s = 10
        scores.append(s)
        details["profit_margin"] = {"value": f"{pm_pct:.1f}%", "score": s}

    if de_ratio is not None:
        if de_ratio < 30:
            s = 90
        elif de_ratio < 80:
            s = 70
        elif de_ratio < 150:
            s = 50
        elif de_ratio < 300:
            s = 30
        else:
            s = 10
        scores.append(s)
        details["debt_to_equity"] = {"value": round(de_ratio, 1), "score": s}

    if current_ratio is not None:
        if current_ratio > 2.0:
            s = 85
        elif current_ratio > 1.5:
            s = 70
        elif current_ratio > 1.0:
            s = 50
        elif current_ratio > 0.5:
            s = 30
        else:
            s = 10
        scores.append(s)
        details["current_ratio"] = {"value": round(current_ratio, 2), "score": s}

    if fcf is not None:
        if fcf > 0:
            s = 70
        else:
            s = 20
        scores.append(s)
        details["free_cashflow"] = {"value": f"{fcf:,.0f}", "score": s, "positive": fcf > 0}

    final = round(sum(scores) / len(scores)) if scores else 50
    return {"score": final, "details": details, "note": "高ROE+高利润率+低杠杆=高分"}


def score_momentum_factor(symbol_dir: str) -> dict:
    """动量因子：基于日线收益率"""
    filepath = os.path.join(symbol_dir, "1d_indicators.csv")
    if not os.path.exists(filepath):
        return {"score": 50, "details": {}, "note": "日线数据缺失"}

    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if len(rows) < 20:
        return {"score": 50, "details": {}, "note": "日线数据不足20行"}

    closes = [safe_float(r.get("close")) for r in rows if safe_float(r.get("close")) is not None]
    if len(closes) < 20:
        return {"score": 50, "details": {}, "note": "收盘价数据不足"}

    details = {}

    def calc_return(days):
        if len(closes) > days:
            return (closes[-1] / closes[-days - 1] - 1) * 100
        return None

    ret_5d = calc_return(5)
    ret_20d = calc_return(20)
    ret_60d = calc_return(60)
    ret_120d = calc_return(120)

    if ret_5d is not None:
        details["return_5d"] = f"{ret_5d:+.2f}%"
    if ret_20d is not None:
        details["return_20d"] = f"{ret_20d:+.2f}%"
    if ret_60d is not None:
        details["return_60d"] = f"{ret_60d:+.2f}%"
    if ret_120d is not None:
        details["return_120d"] = f"{ret_120d:+.2f}%"

    # 12-1 month momentum (学术标准): use ~250d return minus ~20d return
    ret_250d = calc_return(250)
    if ret_250d is not None and ret_20d is not None:
        momentum_12_1 = ret_250d - ret_20d
        details["momentum_12_1"] = f"{momentum_12_1:+.2f}%"
    else:
        momentum_12_1 = ret_60d if ret_60d is not None else 0

    if momentum_12_1 is None:
        momentum_12_1 = 0

    if momentum_12_1 > 30:
        s = 90
    elif momentum_12_1 > 10:
        s = 70
    elif momentum_12_1 > 0:
        s = 55
    elif momentum_12_1 > -10:
        s = 40
    elif momentum_12_1 > -30:
        s = 25
    else:
        s = 10

    return {"score": s, "details": details, "note": "正动量=高分（12M-1M标准）"}


def score_defensive_factor(symbol_dir: str, fundamental: dict) -> dict:
    """防守因子：低波动率 + 高股息"""
    filepath = os.path.join(symbol_dir, "1d_indicators.csv")
    details = {}
    scores = []

    div_yield = safe_float(fundamental.get("dividend_yield") or fundamental.get("dividendYield"), 0)
    if div_yield > 0:
        dy_pct = div_yield
        if dy_pct > 5:
            s = 90
        elif dy_pct > 3:
            s = 70
        elif dy_pct > 1.5:
            s = 50
        else:
            s = 30
        scores.append(s)
        details["dividend_yield"] = f"{dy_pct:.2f}%"

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if len(rows) >= 20:
            closes = [safe_float(r.get("close")) for r in rows[-60:] if safe_float(r.get("close")) is not None]
            if len(closes) >= 20:
                returns = [(closes[i] / closes[i-1] - 1) for i in range(1, len(closes))]
                avg = sum(returns) / len(returns)
                variance = sum((r - avg) ** 2 for r in returns) / len(returns)
                daily_vol = variance ** 0.5
                annual_vol = daily_vol * (252 ** 0.5) * 100
                details["annual_volatility"] = f"{annual_vol:.1f}%"

                if annual_vol < 15:
                    s = 90
                elif annual_vol < 25:
                    s = 70
                elif annual_vol < 40:
                    s = 50
                elif annual_vol < 60:
                    s = 30
                else:
                    s = 10
                scores.append(s)

            atrs = [safe_float(r.get("atr_14")) for r in rows[-20:] if safe_float(r.get("atr_14")) is not None]
            if atrs:
                latest_close = safe_float(rows[-1].get("close"))
                if latest_close and latest_close > 0:
                    atr_pct = (sum(atrs) / len(atrs)) / latest_close * 100
                    details["avg_atr_pct"] = f"{atr_pct:.2f}%"

    beta = safe_float(fundamental.get("beta") or fundamental.get("beta3Year"))
    if beta is not None:
        details["beta"] = round(beta, 2)
        if beta < 0.5:
            s = 90
        elif beta < 0.8:
            s = 70
        elif beta < 1.2:
            s = 50
        elif beta < 1.5:
            s = 30
        else:
            s = 10
        scores.append(s)

    final = round(sum(scores) / len(scores)) if scores else 50
    return {"score": final, "details": details, "note": "低波动+高股息+低Beta=高分"}


def main():
    parser = argparse.ArgumentParser(description="Calculate factor scores")
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args()

    symbol_dir = os.path.join(DATA_DIR, args.symbol)
    if not os.path.isdir(symbol_dir):
        print(f"ERROR: data directory not found: {symbol_dir}", file=sys.stderr)
        sys.exit(1)

    fund_path = os.path.join(symbol_dir, "fundamental.json")
    fundamental = {}
    if os.path.exists(fund_path):
        with open(fund_path, "r") as f:
            fundamental = json.load(f)

    is_etf = not fundamental or fundamental.get("quoteType") == "ETF"

    result = {
        "symbol": args.symbol,
        "is_etf": is_etf,
    }

    if is_etf:
        result["value"] = {"score": 50, "details": {}, "note": "ETF不适用个股估值"}
        result["quality"] = {"score": 50, "details": {}, "note": "ETF不适用质量因子"}
    else:
        result["value"] = score_value_factor(fundamental)
        result["quality"] = score_quality_factor(fundamental)

    result["momentum"] = score_momentum_factor(symbol_dir)
    result["defensive"] = score_defensive_factor(symbol_dir, fundamental)

    weights = {"value": 25, "quality": 30, "momentum": 25, "defensive": 20}
    if is_etf:
        weights = {"value": 5, "quality": 5, "momentum": 50, "defensive": 40}

    composite = sum(result[f]["score"] * weights[f] / 100 for f in weights)
    result["composite_score"] = round(composite)
    result["weights"] = weights

    output_path = os.path.join(symbol_dir, "factor_scores.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"OK: {output_path}")
    print(f"  综合因子评分: {result['composite_score']}/100")
    for f in ["value", "quality", "momentum", "defensive"]:
        print(f"  {f}: {result[f]['score']}/100 (权重{weights[f]}%)")


if __name__ == "__main__":
    main()
