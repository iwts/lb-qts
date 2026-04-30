#!/usr/bin/env python3
"""
基本面数据拉取脚本 — 从 Yahoo Finance 获取最新财务数据、PE、现金流等。

用法:
    python fetch_fundamental.py --symbol 0700.HK
    python fetch_fundamental.py --symbol 0700.HK --force
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

import yfinance as yf

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir, log

def convert_symbol_for_yf(symbol: str) -> str:
    """将 Longport 的标的代码转换为 yfinance 格式"""
    if symbol.endswith(".US"):
        return symbol.replace(".US", "")
    elif symbol.endswith(".SH"):
        return symbol.replace(".SH", ".SS")
    return symbol

def run(symbol: str, force: bool = False):
    data_dir = symbol_data_dir(symbol)
    out_path = os.path.join(data_dir, "fundamental.json")

    # 检查缓存
    if not force and os.path.exists(out_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(out_path))
        if datetime.now() - mtime < timedelta(days=1):
            log.info(f"基本面数据已存在且在1天内 ({mtime})，跳过拉取。如需重新生成请使用 --force")
            return

    yf_symbol = convert_symbol_for_yf(symbol)
    log.info(f"正在从 yfinance 拉取 {yf_symbol} 的基本面数据...")
    
    ticker = yf.Ticker(yf_symbol)
    info = ticker.info
    
    if not info or 'regularMarketPrice' not in info and 'previousClose' not in info:
        log.warning(f"无法获取 {yf_symbol} 的完整基本面数据。")
        # 尝试获取最基础的
        info = info or {}

    # 提取关键数据
    data = {
        "symbol": symbol,
        "yf_symbol": yf_symbol,
        "updated_at": datetime.now().isoformat(),
        "industry": info.get("industry", ""),
        "sector": info.get("sector", ""),
        "market_cap": info.get("marketCap", None),
        "pe_trailing": info.get("trailingPE", None),
        "pe_forward": info.get("forwardPE", None),
        "pb": info.get("priceToBook", None),
        "ps": info.get("priceToSalesTrailing12Months", None),
        "dividend_yield": info.get("dividendYield", None),
        "roe": info.get("returnOnEquity", None),
        "roa": info.get("returnOnAssets", None),
        "operating_margin": info.get("operatingMargins", None),
        "profit_margin": info.get("profitMargins", None),
        "total_cash": info.get("totalCash", None),
        "total_debt": info.get("totalDebt", None),
        "free_cashflow": info.get("freeCashflow", None),
        "operating_cashflow": info.get("operatingCashflow", None),
        "revenue_growth": info.get("revenueGrowth", None),
        "earnings_growth": info.get("earningsGrowth", None),
        "current_ratio": info.get("currentRatio", None),
        "quick_ratio": info.get("quickRatio", None),
        "debt_to_equity": info.get("debtToEquity", None)
    }

    # 提取财报/利润表信息
    try:
        q_income = ticker.quarterly_income_stmt
        if q_income is not None and not q_income.empty:
            # 取最近两期的关键财务数据进行同环比分析
            earnings_data = q_income.iloc[:10, :2].to_dict() if not q_income.empty else {}
            # 格式化 datetime key 为 string
            earnings_dict = {str(k)[:10]: v for k, v in earnings_data.items()}
        else:
            earnings_dict = {}
    except Exception as e:
        log.warning(f"获取财报数据失败: {e}")
        earnings_dict = {}

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    earnings_path = os.path.join(data_dir, "earnings.json")
    with open(earnings_path, "w", encoding="utf-8") as f:
        json.dump({"symbol": symbol, "quarterly_income_stmt": earnings_dict}, f, ensure_ascii=False, indent=2)
    
    log.info(f"基本面与财报数据已保存至: {data_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="拉取基本面数据")
    parser.add_argument("--symbol", required=True, help="标的代码")
    parser.add_argument("--force", action="store_true", help="强制重新拉取")
    args = parser.parse_args()
    run(args.symbol, args.force)
