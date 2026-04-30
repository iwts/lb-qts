#!/usr/bin/env python3
"""
阶段一→阶段二的数据门禁脚本。
批量检查所有标的的 K 线数据新鲜度，输出 PASS/FAIL 及过期标的清单。

用法:
    python verify_data_freshness.py --symbols 600025.SH,0700.HK,NVDA.US
    python verify_data_freshness.py --symbols-file task/stack.md
    python verify_data_freshness.py --symbols 600025.SH --max-stale-hours 48

退出码:
    0 = PASS (全部新鲜)
    1 = FAIL (存在过期标的)
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir

PERIOD_CONFIG = {
    "1h": {"csv": "1h_k.csv", "max_stale_hours": 4,   "critical": True},
    "1d": {"csv": "1d_k.csv", "max_stale_hours": 24,  "critical": True},
    "1w": {"csv": "1w_k.csv", "max_stale_hours": 192,  "critical": False},
}

MARKET_CONFIG = {
    ".US": {"tz": "America/New_York", "open_hour": 9, "close_hour": 16},
    ".HK": {"tz": "Asia/Hong_Kong", "open_hour": 9, "close_hour": 16},
    ".SH": {"tz": "Asia/Shanghai", "open_hour": 9, "close_hour": 15},
    ".SZ": {"tz": "Asia/Shanghai", "open_hour": 9, "close_hour": 15},
}


def parse_symbols_from_file(filepath: str) -> list[str]:
    """从 task/stack.md 格式文件中提取标的代码。"""
    symbols = []
    market = None
    market_suffix = {"A股": ".SH", "港股": ".HK", "美股": ".US"}

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# "):
                market = line[2:].strip()
                continue
            if not line or "：" not in line:
                continue
            code = line.split("：")[0].strip()
            if not code:
                continue
            suffix = market_suffix.get(market, "")
            if suffix and not code.endswith(suffix):
                symbols.append(f"{code}{suffix}")
            else:
                symbols.append(code)
    return symbols


def get_latest_timestamp(csv_path: str) -> datetime | None:
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return None
    try:
        df = pd.read_csv(csv_path, usecols=["timestamp"])
        if df.empty:
            return None
        return pd.to_datetime(df["timestamp"].iloc[-1], utc=True).to_pydatetime()
    except Exception:
        return None


def _market_meta(symbol: str) -> dict:
    for suffix, meta in MARKET_CONFIG.items():
        if symbol.endswith(suffix):
            return meta
    return MARKET_CONFIG[".US"]


def _prev_trading_day(d: date) -> date:
    cur = d - timedelta(days=1)
    while cur.weekday() >= 5:
        cur -= timedelta(days=1)
    return cur


def _expected_latest_date(symbol: str, period: str, now_utc: datetime) -> date | None:
    if period not in {"1h", "1d"}:
        return None
    meta = _market_meta(symbol)
    local_now = now_utc.astimezone(ZoneInfo(meta["tz"]))
    current_date = local_now.date()
    if current_date.weekday() >= 5:
        return _prev_trading_day(current_date)
    if period == "1d" and local_now.hour < meta["close_hour"] + 1:
        return _prev_trading_day(current_date)
    if period == "1h" and local_now.hour < meta["open_hour"]:
        return _prev_trading_day(current_date)
    return current_date


def check_symbol(symbol: str, max_stale_override: float | None = None) -> dict:
    data_dir = symbol_data_dir(symbol)
    now = datetime.now(timezone.utc)
    results = {}
    critical_pass = True
    all_pass = True

    for period, cfg in PERIOD_CONFIG.items():
        csv_path = os.path.join(data_dir, cfg["csv"])
        threshold = max_stale_override if max_stale_override else cfg["max_stale_hours"]
        latest = get_latest_timestamp(csv_path)

        if latest is None:
            results[period] = {"status": "MISSING", "latest": None, "hours_ago": None, "critical": cfg["critical"]}
            all_pass = False
            if cfg["critical"]:
                critical_pass = False
        else:
            hours_ago = (now - latest).total_seconds() / 3600
            expected_date = _expected_latest_date(symbol, period, now)
            latest_local_date = latest.astimezone(ZoneInfo(_market_meta(symbol)["tz"])).date()
            market_fresh = bool(expected_date and latest_local_date >= expected_date)
            if hours_ago <= threshold or market_fresh:
                results[period] = {
                    "status": "OK",
                    "latest": latest.strftime("%Y-%m-%d"),
                    "hours_ago": round(hours_ago, 1),
                    "critical": cfg["critical"],
                    "expected_latest_date": expected_date.isoformat() if expected_date else None,
                }
            else:
                results[period] = {
                    "status": "STALE",
                    "latest": latest.strftime("%Y-%m-%d"),
                    "hours_ago": round(hours_ago, 1),
                    "critical": cfg["critical"],
                    "expected_latest_date": expected_date.isoformat() if expected_date else None,
                }
                all_pass = False
                if cfg["critical"]:
                    critical_pass = False

    return {"symbol": symbol, "pass": all_pass, "critical_pass": critical_pass, "periods": results}


def main():
    parser = argparse.ArgumentParser(description="批量验证 K 线数据新鲜度")
    parser.add_argument("--symbols", help="逗号分隔的标的列表")
    parser.add_argument("--symbols-file", help="从文件解析标的（如 task/stack.md）")
    parser.add_argument(
        "--max-stale-hours",
        type=float,
        default=None,
        help="统一覆盖所有周期的最大过期小时数（默认使用各周期独立阈值：1h=4h, 1d=24h, 1w=192h）",
    )
    parser.add_argument(
        "--critical-only",
        action="store_true",
        help="仅检查关键数据（1h/1d），忽略 1w 过期",
    )
    args = parser.parse_args()

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    elif args.symbols_file:
        symbols = parse_symbols_from_file(args.symbols_file)
    else:
        print("错误：必须提供 --symbols 或 --symbols-file", file=sys.stderr)
        sys.exit(2)

    failed_symbols = []
    all_results = []

    for symbol in symbols:
        result = check_symbol(symbol, args.max_stale_hours)
        all_results.append(result)
        is_fail = (not result["critical_pass"]) if args.critical_only else (not result["pass"])
        if is_fail:
            failed_symbols.append(result)

    thresholds = {p: f"{c['max_stale_hours']}h" for p, c in PERIOD_CONFIG.items()}
    if args.max_stale_hours:
        thresholds = {p: f"{args.max_stale_hours}h" for p in PERIOD_CONFIG}

    print(f"\n{'='*60}")
    print(f"数据门禁校验结果")
    print(f"阈值：{thresholds}" + (" [仅关键数据]" if args.critical_only else ""))
    print(f"{'='*60}")
    print(f"总标的数：{len(symbols)}")
    print(f"通过：{len(symbols) - len(failed_symbols)}")
    print(f"未通过：{len(failed_symbols)}")
    print()

    if failed_symbols:
        print("❌ FAIL — 以下标的数据过期或缺失：\n")
        for r in failed_symbols:
            issues = []
            for p, info in r["periods"].items():
                if info["status"] != "OK":
                    tag = " [关键]" if info.get("critical") else ""
                    issues.append(f"{p}={info['status']}(latest={info['latest']}, {info['hours_ago']}h ago){tag}")
            print(f"  {r['symbol']}: {', '.join(issues)}")
        print(f"\n需要重新拉取的标的清单（可直接复制）：")
        print(",".join(r["symbol"] for r in failed_symbols))
        sys.exit(1)
    else:
        print("✅ PASS — 所有标的数据均为最新")
        sys.exit(0)


if __name__ == "__main__":
    main()
