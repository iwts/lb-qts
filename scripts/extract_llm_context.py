#!/usr/bin/env python3
"""
从指标 CSV 中提取 LLM 推理所需的精简上下文 + 算法预计算信号。

用途：替代让 LLM 直接读取 50 行 × 38 列的原始 indicators CSV，
     输出精简数据表 + 可靠的算法信号结论（文字形式）。

用法：
  .venv/bin/python scripts/extract_llm_context.py --symbol 0700.HK
  .venv/bin/python scripts/extract_llm_context.py --symbol 0700.HK --format json

输出文件：data/<标的>/llm_context.md  (默认)
         data/<标的>/llm_context.json (--format json)
"""

import argparse
import csv
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

PERIODS = {
    "1h": {"file": "1h_indicators.csv", "rows": 30, "label": "1小时线"},
    "1d": {"file": "1d_indicators.csv", "rows": 40, "label": "日线"},
    "1w": {"file": "1w_indicators.csv", "rows": 15, "label": "周线"},
}

KEY_COLUMNS = [
    "timestamp", "close", "volume",
    "sma_5", "sma_10", "sma_20", "sma_60",
    "macd", "macd_signal", "macd_hist",
    "rsi_12", "kdj_k", "kdj_d", "kdj_j",
    "bb_upper", "bb_mid", "bb_lower", "bb_pctb",
    "atr_14", "adx", "+di", "-di",
    "obv", "volume_ratio",
]

ALL_COLUMNS = [
    "timestamp", "open", "high", "low", "close", "volume", "turnover",
    "sma_5", "sma_10", "sma_20", "sma_60", "sma_120", "sma_250",
    "ema_12", "ema_26", "macd", "macd_signal", "macd_hist",
    "rsi_6", "rsi_12", "rsi_24", "kdj_k", "kdj_d", "kdj_j",
    "bb_upper", "bb_mid", "bb_lower", "bb_pctb", "bb_width",
    "atr_14", "adx", "+di", "-di",
    "obv", "vol_ma_5", "vol_ma_10", "vol_ma_20", "volume_ratio",
]


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def truncate_float(val: str, decimals: int = 2) -> str:
    try:
        f = float(val)
        if abs(f) > 1e12:
            return f"{f:.0f}"
        if abs(f) > 100:
            return f"{f:.{decimals}f}"
        return f"{f:.{min(decimals + 1, 4)}f}"
    except (ValueError, TypeError):
        return val


def read_tail_rows(filepath: str, n: int) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows[-n:] if len(rows) > n else rows


def read_all_rows(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def filter_columns(rows: list[dict], columns: list[str]) -> list[dict]:
    available = [c for c in columns if rows and c in rows[0]]
    return [{c: truncate_float(r.get(c, "")) for c in available} for r in rows]


def read_capital_distribution(symbol: str) -> dict:
    filepath = os.path.join(DATA_DIR, symbol, "capital_distribution.csv")
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return {}
    row = rows[-1]
    return {k: truncate_float(v, 0) for k, v in row.items()}


# ---------------------------------------------------------------------------
# 算法预计算信号（只做有明确数学定义、参数不敏感的信号）
# ---------------------------------------------------------------------------

def detect_ma_alignment(rows: list[dict]) -> dict:
    """均线排列状态：多头/空头/交织"""
    if not rows:
        return {"state": "无数据"}
    last = rows[-1]
    sma5 = safe_float(last.get("sma_5"))
    sma10 = safe_float(last.get("sma_10"))
    sma20 = safe_float(last.get("sma_20"))
    sma60 = safe_float(last.get("sma_60"))
    close = safe_float(last.get("close"))

    if sma5 == 0 or sma60 == 0:
        return {"state": "数据不足"}

    if close > sma5 > sma10 > sma20 > sma60:
        state = "完美多头排列"
    elif sma5 > sma10 > sma20:
        state = "多头排列（短中期）"
    elif close < sma5 < sma10 < sma20 < sma60:
        state = "完美空头排列"
    elif sma5 < sma10 < sma20:
        state = "空头排列（短中期）"
    else:
        state = "均线交织（无明确方向）"

    price_vs_sma20 = ((close - sma20) / sma20 * 100) if sma20 else 0
    price_vs_sma60 = ((close - sma60) / sma60 * 100) if sma60 else 0

    return {
        "state": state,
        "price_vs_sma20": f"{price_vs_sma20:+.1f}%",
        "price_vs_sma60": f"{price_vs_sma60:+.1f}%",
    }


def detect_trend_regime(rows: list[dict]) -> dict:
    """趋势强度体制分类"""
    if not rows:
        return {"regime": "无数据"}
    last = rows[-1]
    adx = safe_float(last.get("adx"))
    plus_di = safe_float(last.get("+di"))
    minus_di = safe_float(last.get("-di"))

    if adx >= 40:
        strength = "极强趋势"
    elif adx >= 25:
        strength = "趋势市"
    elif adx >= 20:
        strength = "弱趋势/过渡"
    else:
        strength = "震荡市"

    if plus_di > minus_di:
        direction = "多方主导"
    elif minus_di > plus_di:
        direction = "空方主导"
    else:
        direction = "多空均衡"

    return {
        "regime": strength,
        "direction": direction,
        "adx": f"{adx:.1f}",
        "+di": f"{plus_di:.1f}",
        "-di": f"{minus_di:.1f}",
    }


def detect_volatility_regime(rows: list[dict]) -> dict:
    """波动率体制：ATR 扩张/收缩，BB 带宽变化"""
    if len(rows) < 5:
        return {"regime": "数据不足"}
    last = rows[-1]
    atr_now = safe_float(last.get("atr_14"))
    close = safe_float(last.get("close"))
    bb_pctb = safe_float(last.get("bb_pctb"))

    atrs = [safe_float(r.get("atr_14")) for r in rows[-10:] if safe_float(r.get("atr_14")) > 0]
    if not atrs:
        return {"regime": "数据不足"}

    avg_atr = sum(atrs) / len(atrs)
    atr_ratio = atr_now / avg_atr if avg_atr > 0 else 1.0
    atr_pct = (atr_now / close * 100) if close > 0 else 0

    if atr_ratio > 1.3:
        vol_state = "波动率急剧扩张"
    elif atr_ratio > 1.1:
        vol_state = "波动率扩张"
    elif atr_ratio < 0.7:
        vol_state = "波动率极度收缩（可能酝酿突破）"
    elif atr_ratio < 0.9:
        vol_state = "波动率收缩"
    else:
        vol_state = "波动率正常"

    return {
        "regime": vol_state,
        "atr": f"{atr_now:.2f}",
        "atr_pct_of_price": f"{atr_pct:.2f}%",
        "atr_vs_avg": f"{atr_ratio:.2f}x",
        "bb_pctb": f"{bb_pctb:.2f}",
    }


def detect_volume_price_divergence(rows: list[dict], lookback: int = 10) -> dict:
    """量价背离检测：价格方向 vs 成交量方向"""
    if len(rows) < lookback + 1:
        return {"divergence": "数据不足"}

    recent = rows[-lookback:]
    closes = [safe_float(r.get("close")) for r in recent]
    volumes = [safe_float(r.get("volume")) for r in recent]

    if not all(closes) or not all(volumes):
        return {"divergence": "数据不足"}

    half = lookback // 2
    close_first_half = sum(closes[:half]) / half
    close_second_half = sum(closes[half:]) / half
    vol_first_half = sum(volumes[:half]) / half
    vol_second_half = sum(volumes[half:]) / half

    price_rising = close_second_half > close_first_half * 1.005
    price_falling = close_second_half < close_first_half * 0.995
    vol_rising = vol_second_half > vol_first_half * 1.1
    vol_falling = vol_second_half < vol_first_half * 0.9

    if price_rising and vol_falling:
        div = "⚠️ 上涨缩量（量价背离）：价格上涨但成交量萎缩，上涨持续性存疑"
    elif price_falling and vol_falling:
        div = "下跌缩量：抛压减弱，可能接近阶段性底部"
    elif price_falling and vol_rising:
        div = "⚠️ 下跌放量：恐慌性抛售或主力出货，短期风险大"
    elif price_rising and vol_rising:
        div = "上涨放量：量价配合良好，趋势健康"
    else:
        div = "量价关系中性"

    return {
        "divergence": div,
        "price_change": f"{(close_second_half / close_first_half - 1) * 100:+.2f}%",
        "volume_change": f"{(vol_second_half / vol_first_half - 1) * 100:+.2f}%",
    }


def detect_support_resistance(rows: list[dict]) -> dict:
    """水平支撑阻力位：基于近期局部极值 + 均线"""
    if len(rows) < 10:
        return {"levels": []}

    closes = [safe_float(r.get("close")) for r in rows]
    highs = [safe_float(r.get("high", r.get("close"))) for r in rows]
    lows = [safe_float(r.get("low", r.get("close"))) for r in rows]
    current = closes[-1]

    local_highs = []
    local_lows = []
    for i in range(2, len(closes) - 2):
        if highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+1] and highs[i] >= highs[i+2]:
            local_highs.append(highs[i])
        if lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and lows[i] <= lows[i+1] and lows[i] <= lows[i+2]:
            local_lows.append(lows[i])

    last = rows[-1]
    sma_levels = {}
    for ma in ["sma_5", "sma_10", "sma_20", "sma_60"]:
        v = safe_float(last.get(ma))
        if v > 0:
            sma_levels[ma.upper()] = v

    bb_upper = safe_float(last.get("bb_upper"))
    bb_lower = safe_float(last.get("bb_lower"))

    levels = []

    for h in sorted(set(local_highs), reverse=True)[:3]:
        if h > current:
            pct = (h / current - 1) * 100
            levels.append({"type": "阻力", "price": f"{h:.2f}", "source": "近期高点", "distance": f"+{pct:.1f}%"})

    if bb_upper > current:
        pct = (bb_upper / current - 1) * 100
        levels.append({"type": "阻力", "price": f"{bb_upper:.2f}", "source": "布林上轨", "distance": f"+{pct:.1f}%"})

    for name, val in sma_levels.items():
        if val > current * 1.01:
            pct = (val / current - 1) * 100
            levels.append({"type": "阻力", "price": f"{val:.2f}", "source": name, "distance": f"+{pct:.1f}%"})

    for name, val in sma_levels.items():
        if val < current * 0.99:
            pct = (val / current - 1) * 100
            levels.append({"type": "支撑", "price": f"{val:.2f}", "source": name, "distance": f"{pct:.1f}%"})

    if bb_lower < current:
        pct = (bb_lower / current - 1) * 100
        levels.append({"type": "支撑", "price": f"{bb_lower:.2f}", "source": "布林下轨", "distance": f"{pct:.1f}%"})

    for l in sorted(set(local_lows))[:3]:
        if l < current:
            pct = (l / current - 1) * 100
            levels.append({"type": "支撑", "price": f"{l:.2f}", "source": "近期低点", "distance": f"{pct:.1f}%"})

    return {"current_price": f"{current:.2f}", "levels": levels}


def detect_multi_period_resonance(period_data: dict) -> dict:
    """多周期共振判断"""
    resonance = {}
    for period, info in period_data.items():
        rows = info.get("raw_rows", [])
        if not rows:
            resonance[period] = {"trend": "无数据", "momentum": "无数据"}
            continue
        last = rows[-1]
        sma5 = safe_float(last.get("sma_5"))
        sma20 = safe_float(last.get("sma_20"))
        macd_hist = safe_float(last.get("macd_hist"))
        rsi = safe_float(last.get("rsi_12"))

        if sma5 > sma20:
            trend = "多"
        elif sma5 < sma20:
            trend = "空"
        else:
            trend = "平"

        if macd_hist > 0:
            momentum = "多"
        elif macd_hist < 0:
            momentum = "空"
        else:
            momentum = "平"

        resonance[period] = {"trend": trend, "momentum": momentum, "rsi": f"{rsi:.1f}"}

    periods = list(resonance.values())
    trends = [p["trend"] for p in periods if p["trend"] != "无数据"]
    momentums = [p["momentum"] for p in periods if p["momentum"] != "无数据"]

    if trends and all(t == "多" for t in trends):
        trend_resonance = "✅ 全周期多头共振"
    elif trends and all(t == "空" for t in trends):
        trend_resonance = "✅ 全周期空头共振"
    else:
        trend_resonance = "⚠️ 周期间趋势分歧"

    if momentums and all(m == "多" for m in momentums):
        mom_resonance = "✅ 全周期动量向上"
    elif momentums and all(m == "空" for m in momentums):
        mom_resonance = "✅ 全周期动量向下"
    else:
        mom_resonance = "⚠️ 周期间动量分歧"

    return {
        "periods": resonance,
        "trend_resonance": trend_resonance,
        "momentum_resonance": mom_resonance,
    }


def compute_algo_signals(symbol_dir: str) -> dict:
    """汇总所有算法预计算信号"""
    signals = {"per_period": {}}

    period_raw = {}
    for period, cfg in PERIODS.items():
        filepath = os.path.join(symbol_dir, cfg["file"])
        rows = read_all_rows(filepath)
        tail = rows[-cfg["rows"]:] if len(rows) > cfg["rows"] else rows
        period_raw[period] = {"raw_rows": rows, "tail_rows": tail, "label": cfg["label"]}

        p_signals = {
            "ma_alignment": detect_ma_alignment(tail),
            "trend_regime": detect_trend_regime(tail),
            "volatility": detect_volatility_regime(tail),
            "volume_price": detect_volume_price_divergence(tail),
        }
        signals["per_period"][period] = p_signals

    sr = detect_support_resistance(period_raw.get("1d", {}).get("raw_rows", [])[-60:])
    signals["support_resistance"] = sr

    resonance_input = {p: {"raw_rows": d["tail_rows"]} for p, d in period_raw.items()}
    signals["multi_period_resonance"] = detect_multi_period_resonance(resonance_input)

    return signals


def format_algo_signals_md(signals: dict) -> list[str]:
    """将算法信号格式化为 Markdown"""
    lines = ["## 算法预计算信号（可靠度高，基于明确数学定义）", ""]

    for period in ["1h", "1d", "1w"]:
        ps = signals.get("per_period", {}).get(period, {})
        label = PERIODS[period]["label"]
        lines.append(f"### {label}（{period}）")
        lines.append("")

        ma = ps.get("ma_alignment", {})
        tr = ps.get("trend_regime", {})
        vol = ps.get("volatility", {})
        vp = ps.get("volume_price", {})

        lines.append(f"- **均线排列**：{ma.get('state', '—')}，价格距SMA20 {ma.get('price_vs_sma20', '—')}，距SMA60 {ma.get('price_vs_sma60', '—')}")
        lines.append(f"- **趋势体制**：{tr.get('regime', '—')}，{tr.get('direction', '—')}（ADX={tr.get('adx', '—')}，+DI={tr.get('+di', '—')}，-DI={tr.get('-di', '—')}）")
        lines.append(f"- **波动率**：{vol.get('regime', '—')}，ATR={vol.get('atr', '—')}（占股价{vol.get('atr_pct_of_price', '—')}），近期ATR比={vol.get('atr_vs_avg', '—')}，BB%B={vol.get('bb_pctb', '—')}")
        lines.append(f"- **量价关系**：{vp.get('divergence', '—')}（价格{vp.get('price_change', '—')}，量{vp.get('volume_change', '—')}）")
        lines.append("")

    sr = signals.get("support_resistance", {})
    levels = sr.get("levels", [])
    if levels:
        lines.append(f"### 支撑阻力位（日线，当前价 {sr.get('current_price', '—')}）")
        lines.append("")
        lines.append("| 类型 | 价位 | 来源 | 距当前价 |")
        lines.append("| --- | --- | --- | --- |")
        resistances = [l for l in levels if l["type"] == "阻力"]
        supports = [l for l in levels if l["type"] == "支撑"]
        for l in sorted(resistances, key=lambda x: float(x["price"]))[:4]:
            lines.append(f"| {l['type']} | {l['price']} | {l['source']} | {l['distance']} |")
        for l in sorted(supports, key=lambda x: float(x["price"]), reverse=True)[:4]:
            lines.append(f"| {l['type']} | {l['price']} | {l['source']} | {l['distance']} |")
        lines.append("")

    res = signals.get("multi_period_resonance", {})
    lines.append("### 多周期共振")
    lines.append("")
    lines.append("| 周期 | 趋势方向 | 动量方向 | RSI |")
    lines.append("| --- | --- | --- | --- |")
    for period in ["1h", "1d", "1w"]:
        p = res.get("periods", {}).get(period, {})
        lines.append(f"| {period} | {p.get('trend', '—')} | {p.get('momentum', '—')} | {p.get('rsi', '—')} |")
    lines.append("")
    lines.append(f"- **趋势共振**：{res.get('trend_resonance', '—')}")
    lines.append(f"- **动量共振**：{res.get('momentum_resonance', '—')}")
    lines.append("")

    return lines


def read_json_file(filepath: str) -> dict | list | None:
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def format_orderflow_md(data: dict) -> list[str]:
    """格式化订单流分析"""
    lines = ["## 订单流分析（盘口深度 + 逐笔成交）", ""]

    da = data.get("depth_analysis", {})
    if "error" not in da:
        lines.append("### 盘口深度")
        lines.append("")
        lines.append(f"- **买卖力量对比**：{da.get('pressure_judgment', '—')}")
        lines.append(f"- **买卖量比**：{da.get('bid_ask_volume_ratio', 0)}（买盘量={da.get('total_bid_volume', 0):,} / 卖盘量={da.get('total_ask_volume', 0):,}）")
        lines.append(f"- **价差**：{da.get('spread', 0)}（{da.get('spread_pct', '—')}）")
        lines.append("")

        top_bids = da.get("top_bid_levels", [])
        top_asks = da.get("top_ask_levels", [])
        if top_bids or top_asks:
            lines.append("| 档位 | 买价 | 买量 | 卖价 | 卖量 |")
            lines.append("| --- | --- | --- | --- | --- |")
            for i in range(max(len(top_bids), len(top_asks))):
                b = top_bids[i] if i < len(top_bids) else {}
                a = top_asks[i] if i < len(top_asks) else {}
                lines.append(f"| {i+1} | {b.get('price', '—')} | {b.get('volume', '—'):,} | {a.get('price', '—')} | {a.get('volume', '—'):,} |")
            lines.append("")

    ta = data.get("trades_analysis", {})
    if "error" not in ta:
        lines.append("### 逐笔成交分析")
        lines.append("")
        lines.append(f"- **资金方向判定**：{ta.get('flow_judgment', '—')}")
        lines.append(f"- **主动买入占比**：{ta.get('buy_ratio', '—')}（主动卖出：{ta.get('sell_ratio', '—')}）")
        lines.append(f"- **大单判定**：{ta.get('large_trade_judgment', '—')}（大单买入量={ta.get('large_buy_volume', 0):,}，大单卖出量={ta.get('large_sell_volume', 0):,}）")
        lines.append(f"- **总成交笔数**：{ta.get('total_trades', 0)}，总成交量：{ta.get('total_volume', 0):,}")
        lines.append("")

    if "error" in da and "error" in ta:
        lines.append("> 订单流数据暂不可用（非交易时段或数据未获取）")
        lines.append("")

    return lines


def format_factor_scores_md(data: dict) -> list[str]:
    """格式化因子评分"""
    lines = ["## 因子模型评分", ""]

    is_etf = data.get("is_etf", False)
    composite = data.get("composite_score", 50)
    weights = data.get("weights", {})

    lines.append(f"**综合因子评分：{composite}/100**" + ("（ETF 权重模式）" if is_etf else ""))
    lines.append("")
    lines.append("| 因子 | 评分 | 权重 | 加权 | 关键指标 |")
    lines.append("| --- | --- | --- | --- | --- |")

    for factor in ["value", "quality", "momentum", "defensive"]:
        fd = data.get(factor, {})
        score = fd.get("score", 50)
        w = weights.get(factor, 0)
        weighted = round(score * w / 100, 1)
        details = fd.get("details", {})
        detail_str = ", ".join(f"{k}={v}" for k, v in list(details.items())[:3])
        if not detail_str:
            detail_str = fd.get("note", "—")
        name_map = {"value": "价值", "quality": "质量", "momentum": "动量", "defensive": "防守"}
        lines.append(f"| {name_map.get(factor, factor)} | {score} | {w}% | {weighted} | {detail_str} |")

    lines.append("")

    if composite >= 70:
        lines.append("> 因子综合评价：**基本面偏强**，多因子支撑")
    elif composite >= 55:
        lines.append("> 因子综合评价：**中性偏积极**")
    elif composite >= 40:
        lines.append("> 因子综合评价：**中性**")
    else:
        lines.append("> 因子综合评价：**基本面偏弱**，需谨慎")
    lines.append("")

    return lines


def format_option_analysis_md(data: dict) -> list[str]:
    """格式化期权分析"""
    lines = ["## 期权情绪分析", ""]

    if not data.get("has_options"):
        lines.append(f"> {data.get('note', '该标的无期权数据')}")
        lines.append("")
        return lines

    pcr = data.get("put_call_ratio", {})
    lines.append(f"- **Put/Call Ratio（成交量）**：{pcr.get('volume_pc_ratio', '—')} → {pcr.get('sentiment', '—')}")
    lines.append(f"- **Call 总量**：{pcr.get('total_call_volume', 0):,}，**Put 总量**：{pcr.get('total_put_volume', 0):,}")
    if pcr.get("total_call_oi", 0) > 0:
        lines.append(f"- **OI P/C Ratio**：{pcr.get('oi_pc_ratio', '—')}（Call OI={pcr.get('total_call_oi', 0):,}, Put OI={pcr.get('total_put_oi', 0):,}）")
    lines.append("")

    mp = data.get("max_pain", {})
    lines.append(f"- **Max Pain**：{mp.get('max_pain', '—')}（距当前价 {mp.get('distance', '—')}）")
    lines.append(f"  - {mp.get('note', '')}")
    lines.append("")

    iv = data.get("iv_skew", {})
    if iv.get("available"):
        lines.append(f"- **ATM IV**：{iv.get('atm_iv', '—')}")
        lines.append(f"- **IV 偏斜**：{iv.get('skew', '—')}（OTM Put IV={iv.get('avg_otm_put_iv', '—')}, OTM Call IV={iv.get('avg_otm_call_iv', '—')}）")
    else:
        lines.append(f"> IV 数据：{iv.get('note', '不可用')}")
    lines.append("")

    return lines


def format_market_temperature_md(data: dict) -> list[str]:
    """格式化市场温度"""
    lines = ["## 宏观市场温度", ""]
    for market, info in data.items():
        temp = info.get("temperature", "—")
        desc = info.get("description", "—")
        val = info.get("valuation", "—")
        sent = info.get("sentiment", "—")
        lines.append(f"- **{market}**：温度={temp}/100，{desc}，估值={val}，情绪={sent}")
    lines.append("")

    all_temps = [info.get("temperature", 50) for info in data.values() if isinstance(info.get("temperature"), (int, float))]
    if all_temps:
        avg = sum(all_temps) / len(all_temps)
        if avg > 70:
            lines.append("> 宏观环境：**偏热**，注意追高风险")
        elif avg > 50:
            lines.append("> 宏观环境：**温和**，正常操作")
        elif avg > 30:
            lines.append("> 宏观环境：**偏冷**，可能存在超跌机会")
        else:
            lines.append("> 宏观环境：**极度冷淡**，恐慌情绪")
    lines.append("")
    return lines


def format_markdown(symbol: str, data: dict) -> str:
    lines = [f"# {symbol} 综合分析上下文", ""]

    mkt_temp = data.get("market_temperature")
    if mkt_temp:
        lines.extend(format_market_temperature_md(mkt_temp))

    factor = data.get("factor_scores")
    if factor:
        lines.extend(format_factor_scores_md(factor))

    algo_lines = format_algo_signals_md(data.get("algo_signals", {}))
    lines.extend(algo_lines)

    for period, info in data.get("periods", {}).items():
        rows = info["rows"]
        if not rows:
            lines.append(f"## {info['label']}（{period}）：数据缺失")
            lines.append("")
            continue

        cols = list(rows[0].keys())
        lines.append(f"## {info['label']}（{period}，最近 {len(rows)} 根）")
        lines.append("")
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for r in rows:
            lines.append("| " + " | ".join(r.get(c, "") for c in cols) + " |")
        lines.append("")

    cap = data.get("capital_distribution")
    if cap:
        lines.append("## 资金分布（最新）")
        lines.append("")
        cols = list(cap.keys())
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        lines.append("| " + " | ".join(cap.get(c, "") for c in cols) + " |")
        lines.append("")

    sig = data.get("signals_summary")
    if sig:
        lines.append("## 信号摘要 (signals_summary.json)")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(sig, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract LLM-friendly context from indicator CSVs")
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g. 0700.HK)")
    parser.add_argument("--format", choices=["md", "json"], default="md", help="Output format")
    parser.add_argument("--output", help="Custom output path (default: data/<symbol>/llm_context.<ext>)")
    args = parser.parse_args()

    symbol_dir = os.path.join(DATA_DIR, args.symbol)
    if not os.path.isdir(symbol_dir):
        print(f"ERROR: data directory not found: {symbol_dir}", file=sys.stderr)
        sys.exit(1)

    result = {"symbol": args.symbol, "periods": {}}

    total_tokens_estimate = 0
    for period, cfg in PERIODS.items():
        filepath = os.path.join(symbol_dir, cfg["file"])
        raw_rows = read_tail_rows(filepath, cfg["rows"])
        filtered = filter_columns(raw_rows, KEY_COLUMNS)
        result["periods"][period] = {"label": cfg["label"], "rows": filtered}
        row_bytes = sum(len(str(r)) for r in filtered)
        total_tokens_estimate += row_bytes // 4

    result["capital_distribution"] = read_capital_distribution(args.symbol)

    sig_path = os.path.join(symbol_dir, "signals_summary.json")
    if os.path.exists(sig_path):
        with open(sig_path, "r", encoding="utf-8") as f:
            result["signals_summary"] = json.load(f)
            total_tokens_estimate += os.path.getsize(sig_path) // 4

    result["algo_signals"] = compute_algo_signals(symbol_dir)
    total_tokens_estimate += 800

    # 盘口/逐笔数据对非日内分析价值有限，不再默认加载到 llm_context
    # 资金分布（大/中/小单聚合数据）已通过 capital_distribution 提供，信息密度更高

    factor = read_json_file(os.path.join(symbol_dir, "factor_scores.json"))
    if factor:
        result["factor_scores"] = factor
        total_tokens_estimate += 300

    mkt_temp = read_json_file(os.path.join(symbol_dir, "market_temperature.json"))
    if mkt_temp:
        result["market_temperature"] = mkt_temp
        total_tokens_estimate += 100

    ext = args.format
    output_path = args.output or os.path.join(symbol_dir, f"llm_context.{ext}")

    if args.format == "md":
        content = format_markdown(args.symbol, result)
    else:
        content = json.dumps(result, ensure_ascii=False, indent=2)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    line_count = content.count("\n") + 1
    byte_count = len(content.encode("utf-8"))
    print(f"OK: {output_path}")
    print(f"   {line_count} lines, {byte_count} bytes, ~{byte_count // 4} tokens (estimated)")


if __name__ == "__main__":
    main()
