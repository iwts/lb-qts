#!/usr/bin/env python3
"""
技术指标计算脚本 — 读取 K 线 CSV，计算全部技术指标，生成指标文件和信号摘要。

用法:
    python calc_indicators.py --symbol 0700.HK
    python calc_indicators.py --symbol 0700.HK --periods 1d
"""
import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import ta

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir, log

KLINE_FILES = {
    "1h": "1h_k.csv",
    "1d": "1d_k.csv",
    "1w": "1w_k.csv",
    "1M": "1M_k.csv",
}

MARKET_CONFIG = {
    ".US": {"tz": "America/New_York", "open_hour": 9, "close_hour": 16},
    ".HK": {"tz": "Asia/Hong_Kong", "open_hour": 9, "close_hour": 16},
    ".SH": {"tz": "Asia/Shanghai", "open_hour": 9, "close_hour": 15},
    ".SZ": {"tz": "Asia/Shanghai", "open_hour": 9, "close_hour": 15},
}


def _market_meta(symbol: str) -> dict:
    for suffix, meta in MARKET_CONFIG.items():
        if symbol.endswith(suffix):
            return meta
    return MARKET_CONFIG[".US"]


def _market_now(symbol: str) -> datetime:
    return datetime.now(ZoneInfo(_market_meta(symbol)["tz"]))


def _is_live_market_window(symbol: str) -> bool:
    meta = _market_meta(symbol)
    now_local = _market_now(symbol)
    if now_local.weekday() >= 5:
        return False
    # Include a small post-close buffer so late bars can still roll into synthetic 1d/1w.
    return meta["open_hour"] <= now_local.hour <= meta["close_hour"] + 4


def _load_kline_df(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="mixed")
    return df.sort_values("timestamp").reset_index(drop=True)


def _aggregate_from_1h(base_df: pd.DataFrame, hourly_df: pd.DataFrame, symbol: str, period: str) -> pd.DataFrame:
    """
    For in-progress trading sessions, synthesize the current 1d/1w bar from latest 1h bars
    so indicator calculations can include the current day/week even before the upstream
    provider publishes a finalized daily/weekly candle.
    """
    if base_df.empty or hourly_df.empty or period not in {"1d", "1w"} or not _is_live_market_window(symbol):
        return base_df

    tz = ZoneInfo(_market_meta(symbol)["tz"])
    hourly_local = hourly_df["timestamp"].dt.tz_convert(tz)
    latest_hour_local = hourly_local.iloc[-1]

    if period == "1d":
        mask = hourly_local.dt.date == latest_hour_local.date()
        same_bucket = lambda ts: ts.date() == latest_hour_local.date()
    else:
        cur_year, cur_week, _ = latest_hour_local.isocalendar()
        mask = hourly_local.apply(lambda ts: ts.isocalendar()[:2] == (cur_year, cur_week))
        same_bucket = lambda ts: ts.isocalendar()[:2] == (cur_year, cur_week)

    bucket = hourly_df.loc[mask].copy()
    if bucket.empty:
        return base_df

    synthetic = {
        "timestamp": bucket["timestamp"].iloc[-1],
        "open": float(bucket["open"].iloc[0]),
        "high": float(bucket["high"].max()),
        "low": float(bucket["low"].min()),
        "close": float(bucket["close"].iloc[-1]),
        "volume": float(bucket["volume"].sum()),
        "turnover": float(bucket["turnover"].sum()),
    }

    result = base_df.copy()
    base_local = result["timestamp"].dt.tz_convert(tz)
    if not result.empty and same_bucket(base_local.iloc[-1]):
        result = result.iloc[:-1].copy()

    result = pd.concat([result, pd.DataFrame([synthetic])], ignore_index=True)
    result = result.sort_values("timestamp").reset_index(drop=True)
    return result


# ── 核心指标计算 ───────────────────────────────────────────────────────────
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """对 OHLCV DataFrame 计算全部技术指标，返回带指标列的 DataFrame."""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"].astype(float)

    # ── 均线 ───────────────────────────────────────────────────────────
    for w in [5, 10, 20, 60, 120, 250]:
        if len(df) >= w:
            df[f"sma_{w}"] = ta.trend.SMAIndicator(close, window=w).sma_indicator()
    for w in [12, 26]:
        df[f"ema_{w}"] = ta.trend.EMAIndicator(close, window=w).ema_indicator()

    # ── MACD (12, 26, 9) ──────────────────────────────────────────────
    macd = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    # ── RSI ────────────────────────────────────────────────────────────
    for w in [6, 12, 24]:
        df[f"rsi_{w}"] = ta.momentum.RSIIndicator(close, window=w).rsi()

    # ── KDJ (Stochastic 9, 3, 3) ──────────────────────────────────────
    stoch = ta.momentum.StochasticOscillator(high, low, close, window=9, smooth_window=3)
    df["kdj_k"] = stoch.stoch()
    df["kdj_d"] = stoch.stoch_signal()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

    # ── 布林带 (20, 2) ────────────────────────────────────────────────
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pctb"] = bb.bollinger_pband()
    df["bb_width"] = bb.bollinger_wband()

    # ── ATR (14) ──────────────────────────────────────────────────────
    df["atr_14"] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

    # ── ADX (14) 趋势强度 ──────────────────────────────────────────────
    adx_ind = ta.trend.ADXIndicator(high, low, close, window=14)
    df["adx"] = adx_ind.adx()
    df["+di"] = adx_ind.adx_pos()
    df["-di"] = adx_ind.adx_neg()

    # ── OBV ───────────────────────────────────────────────────────────
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()

    # ── 成交量均线 ────────────────────────────────────────────────────
    for w in [5, 10, 20]:
        df[f"vol_ma_{w}"] = volume.rolling(window=w).mean()

    # ── 量比 (当日成交量 / 过去5日平均) ──────────────────────────────
    df["volume_ratio"] = volume / volume.rolling(window=5).mean()

    return df


# ── 信号检测 ───────────────────────────────────────────────────────────────
def detect_signals(df: pd.DataFrame, period: str) -> dict:
    """检测关键交易信号，返回信号字典."""
    if len(df) < 30:
        return {"period": period, "error": "数据不足30条，无法分析"}

    signals = {"period": period, "data_points": len(df), "latest_close": float(df["close"].iloc[-1])}
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # ── MACD 金叉/死叉 ────────────────────────────────────────────────
    if "macd_hist" in df.columns:
        curr_hist = latest.get("macd_hist", 0)
        prev_hist = prev.get("macd_hist", 0)
        if not pd.isna(curr_hist) and not pd.isna(prev_hist):
            if prev_hist <= 0 < curr_hist:
                signals["macd_cross"] = "golden_cross"
            elif prev_hist >= 0 > curr_hist:
                signals["macd_cross"] = "death_cross"
            else:
                signals["macd_cross"] = "none"
            signals["macd_hist_value"] = round(float(curr_hist), 4)
            signals["macd_trend"] = "bullish" if curr_hist > 0 else "bearish"

    # ── 均线排列 ──────────────────────────────────────────────────────
    ma_keys = ["sma_5", "sma_10", "sma_20", "sma_60"]
    ma_vals = [float(latest[k]) for k in ma_keys if k in df.columns and not pd.isna(latest.get(k))]
    if len(ma_vals) >= 3:
        if ma_vals == sorted(ma_vals, reverse=True):
            signals["ma_alignment"] = "bullish_aligned"
        elif ma_vals == sorted(ma_vals):
            signals["ma_alignment"] = "bearish_aligned"
        else:
            signals["ma_alignment"] = "mixed"

    # ── 均线金叉/死叉 ────────────────────────────────────────────────
    for fast, slow in [("sma_5", "sma_10"), ("sma_10", "sma_20"), ("sma_20", "sma_60")]:
        if fast in df.columns and slow in df.columns:
            curr_diff = latest.get(fast, 0) - latest.get(slow, 0)
            prev_diff = prev.get(fast, 0) - prev.get(slow, 0)
            if not pd.isna(curr_diff) and not pd.isna(prev_diff):
                if prev_diff <= 0 < curr_diff:
                    signals[f"ma_cross_{fast}_{slow}"] = "golden_cross"
                elif prev_diff >= 0 > curr_diff:
                    signals[f"ma_cross_{fast}_{slow}"] = "death_cross"

    # ── RSI 超买超卖 ──────────────────────────────────────────────────
    rsi_12 = latest.get("rsi_12")
    if not pd.isna(rsi_12):
        signals["rsi_12"] = round(float(rsi_12), 2)
        if rsi_12 > 80:
            signals["rsi_status"] = "overbought"
        elif rsi_12 < 20:
            signals["rsi_status"] = "oversold"
        elif rsi_12 > 70:
            signals["rsi_status"] = "near_overbought"
        elif rsi_12 < 30:
            signals["rsi_status"] = "near_oversold"
        else:
            signals["rsi_status"] = "neutral"

    # ── KDJ 信号 ──────────────────────────────────────────────────────
    kdj_j = latest.get("kdj_j")
    if not pd.isna(kdj_j):
        signals["kdj_j"] = round(float(kdj_j), 2)
        if kdj_j > 100:
            signals["kdj_status"] = "overbought"
        elif kdj_j < 0:
            signals["kdj_status"] = "oversold"
        else:
            signals["kdj_status"] = "neutral"

    # ── 布林带位置 ────────────────────────────────────────────────────
    bb_pctb = latest.get("bb_pctb")
    if not pd.isna(bb_pctb):
        signals["bb_pctb"] = round(float(bb_pctb), 4)
        if bb_pctb > 1:
            signals["bb_status"] = "above_upper"
        elif bb_pctb < 0:
            signals["bb_status"] = "below_lower"
        else:
            signals["bb_status"] = "within_bands"

    bb_width = latest.get("bb_width")
    if not pd.isna(bb_width):
        signals["bb_width"] = round(float(bb_width), 4)
        width_sma = df["bb_width"].rolling(20).mean().iloc[-1] if "bb_width" in df.columns else None
        if width_sma and not pd.isna(width_sma) and bb_width < width_sma * 0.5:
            signals["bb_squeeze"] = True

    # ── 波动率与风险 (ATR) ────────────────────────────────────────────
    atr = latest.get("atr_14")
    if not pd.isna(atr):
        signals["atr_14"] = round(float(atr), 2)
        # 以 1.5 倍 ATR 作为基准止损参考
        signals["suggested_stop_loss_long"] = round(float(latest["close"] - 1.5 * atr), 2)
        signals["suggested_stop_loss_short"] = round(float(latest["close"] + 1.5 * atr), 2)

    # ── 背离分析 (MACD & RSI Divergence) ──────────────────────────────
    lookback = min(20, len(df))
    recent_df = df.tail(lookback)
    signals["divergence"] = "none"
    if len(recent_df) >= 10:
        # 如果当前收盘价是近20周期最低，但指标不是最低，则为底背离
        if recent_df['close'].idxmin() == recent_df.index[-1]:
            prev_lows = df.iloc[-lookback:-5]
            if not prev_lows.empty:
                prev_min_idx = prev_lows['close'].idxmin()
                if latest['close'] <= df.loc[prev_min_idx, 'close']:
                    if latest['macd_hist'] > df.loc[prev_min_idx, 'macd_hist'] or latest['rsi_12'] > df.loc[prev_min_idx, 'rsi_12']:
                        signals["divergence"] = "bullish_divergence"
        # 如果当前收盘价是近20周期最高，但指标不是最高，则为顶背离
        elif recent_df['close'].idxmax() == recent_df.index[-1]:
            prev_highs = df.iloc[-lookback:-5]
            if not prev_highs.empty:
                prev_max_idx = prev_highs['close'].idxmax()
                if latest['close'] >= df.loc[prev_max_idx, 'close']:
                    if latest['macd_hist'] < df.loc[prev_max_idx, 'macd_hist'] or latest['rsi_12'] < df.loc[prev_max_idx, 'rsi_12']:
                        signals["divergence"] = "bearish_divergence"

    # ── 量价分析 ──────────────────────────────────────────────────────
    vr = latest.get("volume_ratio")
    if not pd.isna(vr):
        signals["volume_ratio"] = round(float(vr), 2)
        if vr > 2.0:
            signals["volume_status"] = "heavy_volume"
        elif vr > 1.5:
            signals["volume_status"] = "above_average"
        elif vr < 0.5:
            signals["volume_status"] = "light_volume"
        else:
            signals["volume_status"] = "normal"
            
    # ── OBV 资金流向趋势 ──────────────────────────────────────────────
    if "obv" in df.columns and len(df) >= 20:
        obv_ma = df["obv"].rolling(20).mean().iloc[-1]
        obv_latest = latest["obv"]
        signals["obv_trend"] = "bullish" if obv_latest > obv_ma else "bearish"

    # ── 支撑位/阻力位 (近 60 周期高低点) ──────────────────────────────
    lookback = min(60, len(df))
    recent = df.tail(lookback)
    signals["support_level"] = round(float(recent["low"].min()), 2)
    signals["resistance_level"] = round(float(recent["high"].max()), 2)

    pivot = (latest["high"] + latest["low"] + latest["close"]) / 3
    signals["pivot"] = round(float(pivot), 2)
    signals["pivot_r1"] = round(float(2 * pivot - latest["low"]), 2)
    signals["pivot_s1"] = round(float(2 * pivot - latest["high"]), 2)

    # ── 趋势强度（ADX & MAs）────────────────────────────────────────
    above_count = 0
    total_ma = 0
    for k in ["sma_5", "sma_10", "sma_20", "sma_60", "sma_120"]:
        val = latest.get(k)
        if not pd.isna(val):
            total_ma += 1
            if latest["close"] > val:
                above_count += 1
    if total_ma > 0:
        signals["trend_strength"] = round(above_count / total_ma, 2)
        
    adx = latest.get("adx")
    if not pd.isna(adx):
        signals["adx"] = round(float(adx), 2)
        signals["di_plus"] = round(float(latest["+di"]), 2)
        signals["di_minus"] = round(float(latest["-di"]), 2)
        if signals["adx"] > 25:
            signals["trend_regime"] = "trending"
        else:
            signals["trend_regime"] = "ranging"

    return signals


# ── 综合评分 ───────────────────────────────────────────────────────────────
def compute_score(signals: dict) -> dict:
    """根据信号计算多维度评分."""
    scores = {}

    # 趋势评分 (0-100)
    trend_score = 50
    alignment = signals.get("ma_alignment", "mixed")
    if alignment == "bullish_aligned":
        trend_score += 30
    elif alignment == "bearish_aligned":
        trend_score -= 30
    trend_str = signals.get("trend_strength", 0.5)
    trend_score += (trend_str - 0.5) * 40
    scores["trend"] = max(0, min(100, trend_score))

    # 动量评分 (0-100)
    momentum_score = 50
    macd_cross = signals.get("macd_cross", "none")
    if macd_cross == "golden_cross":
        momentum_score += 25
    elif macd_cross == "death_cross":
        momentum_score -= 25
    macd_trend = signals.get("macd_trend", "")
    if macd_trend == "bullish":
        momentum_score += 10
    elif macd_trend == "bearish":
        momentum_score -= 10
    rsi = signals.get("rsi_12", 50)
    adx = signals.get("adx", 20)
    # 动态 RSI 评估：趋势市(ADX>25)和震荡市的区别
    if adx > 25:
        # 强趋势中，RSI超买是强势，极度超买才扣分
        if signals.get("di_plus", 0) > signals.get("di_minus", 0):
            if rsi > 85: momentum_score -= (rsi - 85) * 2
            elif rsi > 60: momentum_score += 10
        else:
            if rsi < 15: momentum_score += (15 - rsi) * 2
            elif rsi < 40: momentum_score -= 10
    else:
        # 震荡市中，RSI > 70 就是明确卖点
        if rsi > 70:
            momentum_score -= (rsi - 70) * 1.5
        elif rsi < 30:
            momentum_score += (30 - rsi) * 1.5
            
    divergence = signals.get("divergence", "none")
    if divergence == "bullish_divergence":
        momentum_score += 30
    elif divergence == "bearish_divergence":
        momentum_score -= 30
    scores["momentum"] = max(0, min(100, momentum_score))

    # 量能评分 (0-100)
    volume_score = 50
    vs = signals.get("volume_status", "normal")
    if vs == "heavy_volume" and signals.get("macd_trend") == "bullish":
        volume_score += 20
    elif vs == "heavy_volume" and signals.get("macd_trend") == "bearish":
        volume_score -= 20
    elif vs == "light_volume" and signals.get("macd_trend") == "bullish":
        volume_score -= 10
    elif vs == "light_volume" and signals.get("macd_trend") == "bearish":
        volume_score += 10 # 下跌缩量是好事
        
    obv_trend = signals.get("obv_trend", "")
    if obv_trend == "bullish":
        volume_score += 15
    elif obv_trend == "bearish":
        volume_score -= 15
    scores["volume"] = max(0, min(100, volume_score))

    # 波动评分 (0-100, 高=适合做波段)
    volatility_score = 50
    bb_status = signals.get("bb_status", "within_bands")
    if bb_status == "above_upper":
        volatility_score += 15
    elif bb_status == "below_lower":
        volatility_score -= 15
    if signals.get("bb_squeeze"):
        volatility_score += 10
    scores["volatility"] = max(0, min(100, volatility_score))

    # 综合评分 (加权)
    weights = {"trend": 0.35, "momentum": 0.30, "volume": 0.20, "volatility": 0.15}
    composite = sum(scores[k] * weights[k] for k in weights)
    scores["composite"] = round(composite, 1)

    # 建议映射
    if composite >= 80:
        scores["recommendation"] = "强力做多"
    elif composite >= 68:
        scores["recommendation"] = "推荐做多"
    elif composite >= 58:
        scores["recommendation"] = "看多"
    elif composite >= 42:
        scores["recommendation"] = "中性"
    elif composite >= 32:
        scores["recommendation"] = "看空"
    elif composite >= 20:
        scores["recommendation"] = "推荐做空"
    else:
        scores["recommendation"] = "强力做空"

    return scores


# ── 主流程 ─────────────────────────────────────────────────────────────────
def run(symbol: str, periods: list[str]):
    data_dir = symbol_data_dir(symbol)
    all_signals = {}
    all_scores = {}
    hourly_df = None

    hourly_path = os.path.join(data_dir, KLINE_FILES["1h"])
    if os.path.exists(hourly_path):
        try:
            hourly_df = _load_kline_df(hourly_path)
        except Exception as e:
            log.warning(f"加载 1h 数据失败，跳过实时聚合: {e}")

    for period in periods:
        fname = KLINE_FILES.get(period)
        if not fname:
            log.warning(f"不支持的周期 {period}")
            continue
        csv_path = os.path.join(data_dir, fname)
        if not os.path.exists(csv_path):
            log.warning(f"文件不存在: {csv_path}，跳过")
            continue

        log.info(f"计算 {symbol} {period} 技术指标 ...")
        df = _load_kline_df(csv_path)
        if period in {"1d", "1w"} and hourly_df is not None:
            before_len = len(df)
            df = _aggregate_from_1h(df, hourly_df, symbol, period)
            if len(df) != before_len or (
                before_len > 0 and not df.empty and df["timestamp"].iloc[-1] != pd.to_datetime(pd.read_csv(csv_path)["timestamp"].iloc[-1], utc=True)
            ):
                log.info(f"  使用 1h 数据合成当前{period}未收盘 bar 参与计算")
        if len(df) < 10:
            log.warning(f"  数据不足10条，跳过")
            continue

        df = compute_indicators(df)

        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S%z").str.replace(r"(\+0000)$", "Z", regex=True)

        out_path = os.path.join(data_dir, f"{period}_indicators.csv")
        df.to_csv(out_path, index=False)
        log.info(f"  指标已保存: {out_path} ({len(df)} 行, {len(df.columns)} 列)")

        sigs = detect_signals(df, period)
        all_signals[period] = sigs

        score = compute_score(sigs)
        all_scores[period] = score
        log.info(f"  {period} 综合评分: {score['composite']} → {score['recommendation']}")

    summary = {
        "symbol": symbol,
        "generated_at": datetime.now().isoformat(),
        "signals": all_signals,
        "scores": all_scores,
    }

    # 长短期综合评分分离
    def _map_score(s):
        if s >= 80: return "强力做多"
        if s >= 68: return "推荐做多"
        if s >= 58: return "看多"
        if s >= 42: return "中性"
        if s >= 32: return "看空"
        if s >= 20: return "推荐做空"
        return "强力做空"

    if all_scores:
        # 短期 (1h, 1d)
        st_weights = {"1h": 0.40, "1d": 0.60}
        st_total, st_sum = 0, 0
        for p in ["1h", "1d"]:
            if p in all_scores:
                st_total += all_scores[p]["composite"] * st_weights[p]
                st_sum += st_weights[p]
        if st_sum > 0:
            st_score = round(st_total / st_sum, 1)
            summary["short_term_score"] = st_score
            summary["short_term_recommendation"] = _map_score(st_score)
            log.info(f"=== {symbol} 短期(1h/1d)综合评分: {st_score} → {summary['short_term_recommendation']} ===")

        # 中长期 (1w, 1M)
        lt_weights = {"1w": 0.60, "1M": 0.40}
        lt_total, lt_sum = 0, 0
        for p in ["1w", "1M"]:
            if p in all_scores:
                lt_total += all_scores[p]["composite"] * lt_weights[p]
                lt_sum += lt_weights[p]
        if lt_sum > 0:
            lt_score = round(lt_total / lt_sum, 1)
            summary["long_term_score"] = lt_score
            summary["long_term_recommendation"] = _map_score(lt_score)
            log.info(f"=== {symbol} 长期(1w/1M)综合评分: {lt_score} → {summary['long_term_recommendation']} ===")

    summary_path = os.path.join(data_dir, "signals_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log.info(f"信号摘要已保存: {summary_path}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="技术指标计算")
    parser.add_argument("--symbol", required=True, help="标的代码")
    parser.add_argument("--periods", default="1h,1d,1w,1M", help="计算周期")
    args = parser.parse_args()
    run(args.symbol, args.periods.split(","))
