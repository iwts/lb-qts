#!/usr/bin/env python3
"""保存 quote 快照数据到各股票目录的 quote_snapshot.csv"""
import json
import os
import sys
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir

QUOTES = [
    {"symbol":"MSFT.US","last_done":"401.720","prev_close":"400.600","open":"404.710","high":"407.490","low":"398.740","timestamp":"2026-02-26T21:00:00Z","volume":34405869,"turnover":"13827981612.150","change_pct":0.28},
    {"symbol":"BX.US","last_done":"117.950","prev_close":"118.220","open":"119.090","high":"120.880","low":"115.520","timestamp":"2026-02-26T21:00:00Z","volume":9118572,"turnover":"1076650591.913","change_pct":-0.23},
    {"symbol":"MA.US","last_done":"514.770","prev_close":"509.390","open":"510.950","high":"519.900","low":"509.010","timestamp":"2026-02-26T21:00:00Z","volume":4843689,"turnover":"2489855816.843","change_pct":1.06},
    {"symbol":"NVDA.US","last_done":"184.890","prev_close":"195.560","open":"194.270","high":"194.290","low":"184.315","timestamp":"2026-02-26T21:00:00Z","volume":360807905,"turnover":"67558283140.548","change_pct":-5.46},
    {"symbol":"AMZN.US","last_done":"207.920","prev_close":"210.640","open":"210.730","high":"211.050","low":"205.345","timestamp":"2026-02-26T21:00:00Z","volume":47756762,"turnover":"9926699976.556","change_pct":-1.29},
    {"symbol":"META.US","last_done":"657.010","prev_close":"653.690","open":"650.550","high":"661.000","low":"647.500","timestamp":"2026-02-26T21:00:01Z","volume":10637736,"turnover":"6973018113.116","change_pct":0.51},
    {"symbol":"MCD.US","last_done":"334.530","prev_close":"333.010","open":"334.870","high":"336.940","low":"333.110","timestamp":"2026-02-26T21:00:00Z","volume":2425874,"turnover":"811947194.477","change_pct":0.46},
    {"symbol":"AAPL.US","last_done":"272.950","prev_close":"274.230","open":"274.945","high":"276.110","low":"270.795","timestamp":"2026-02-26T21:00:01Z","volume":32345114,"turnover":"8819756116.547","change_pct":-0.47},
    {"symbol":"GOOG.US","last_done":"307.150","prev_close":"313.030","open":"312.805","high":"313.000","low":"302.410","timestamp":"2026-02-26T21:00:00Z","volume":22379978,"turnover":"6859417106.684","change_pct":-1.88},
    {"symbol":"AMD.US","last_done":"203.680","prev_close":"210.860","open":"208.800","high":"209.790","low":"201.460","timestamp":"2026-02-26T21:00:00Z","volume":35020472,"turnover":"7143914405.905","change_pct":-3.41},
    {"symbol":"TSLA.US","last_done":"408.580","prev_close":"417.400","open":"414.420","high":"416.810","low":"403.660","timestamp":"2026-02-26T21:00:00Z","volume":53602497,"turnover":"21891989813.762","change_pct":-2.11},
    {"symbol":"KO.US","last_done":"80.500","prev_close":"80.470","open":"80.750","high":"80.890","low":"80.021","timestamp":"2026-02-26T21:00:00Z","volume":12843186,"turnover":"1033445997.860","change_pct":0.04},
    {"symbol":"LLY.US","last_done":"1022.020","prev_close":"1028.830","open":"1024.080","high":"1026.915","low":"1007.380","timestamp":"2026-02-26T21:00:00Z","volume":2666432,"turnover":"2710832569.303","change_pct":-0.66},
    {"symbol":"TRV.US","last_done":"306.240","prev_close":"304.760","open":"306.260","high":"308.620","low":"304.500","timestamp":"2026-02-26T21:00:00Z","volume":1018292,"turnover":"311750252.616","change_pct":0.49},
    {"symbol":"FTNT.US","last_done":"79.200","prev_close":"77.350","open":"77.315","high":"79.740","low":"76.850","timestamp":"2026-02-26T21:00:01Z","volume":5871925,"turnover":"463891627.413","change_pct":2.39},
    {"symbol":"MRK.US","last_done":"119.300","prev_close":"122.460","open":"122.400","high":"122.500","low":"119.000","timestamp":"2026-02-26T21:00:00Z","volume":10327287,"turnover":"1236146587.734","change_pct":-2.58},
    {"symbol":"ASML.US","last_done":"1463.800","prev_close":"1526.510","open":"1512.820","high":"1514.330","low":"1426.590","timestamp":"2026-02-26T21:00:01Z","volume":2177889,"turnover":"3180379808.851","change_pct":-4.11},
]

for q in QUOTES:
    symbol = q["symbol"]
    data_dir = symbol_data_dir(symbol)
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, "quote_snapshot.csv")

    last = float(q["last_done"])
    prev = float(q["prev_close"])
    chg = last - prev
    chg_pct = (chg / prev) * 100

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "last_done", "prev_close", "open", "high", "low", "volume", "turnover", "change", "change_pct"])
        writer.writerow([
            q["timestamp"],
            q["last_done"],
            q["prev_close"],
            q["open"],
            q["high"],
            q["low"],
            q["volume"],
            q["turnover"],
            f"{chg:.3f}",
            f"{chg_pct:.2f}",
        ])
    print(f"[{symbol}] quote_snapshot.csv saved  last={q['last_done']}  chg={chg_pct:.2f}%")

print("\nDone.")
