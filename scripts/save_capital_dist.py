#!/usr/bin/env python3
"""保存 capital_distribution 数据到各股票 tmp/ 目录并解析为 CSV"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir

CAPITAL_DIST_DATA = {
    "MSFT.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"10823.37","medium":"41677.08","small":"63311.38"},"capital_out":{"large":"28639.82","medium":"45130.96","small":"76156.59"}},
    "BX.US":   {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"1533.35","medium":"2022.75","small":"5541.30"},"capital_out":{"large":"2158.82","medium":"2112.47","small":"5667.12"}},
    "MA.US":   {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"866.99","medium":"5151.10","small":"9620.54"},"capital_out":{"large":"800.72","medium":"4985.42","small":"6857.13"}},
    "NVDA.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"111899.03","medium":"352531.66","small":"533705.91"},"capital_out":{"large":"112963.12","medium":"355752.21","small":"537418.42"}},
    "AMZN.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"15066.80","medium":"31982.48","small":"69153.42"},"capital_out":{"large":"9641.31","medium":"35565.70","small":"70792.87"}},
    "META.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"4686.51","medium":"15535.32","small":"29312.05"},"capital_out":{"large":"3348.10","medium":"14273.97","small":"28591.40"}},
    "MCD.US":  {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"317.71","medium":"1758.53","small":"3341.94"},"capital_out":{"large":"8480.11","medium":"1268.04","small":"2834.74"}},
    "AAPL.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"8587.69","medium":"33047.32","small":"69114.26"},"capital_out":{"large":"6159.11","medium":"25580.04","small":"64154.10"}},
    "GOOG.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"4341.61","medium":"13588.58","small":"57777.86"},"capital_out":{"large":"9884.04","medium":"15170.29","small":"56547.55"}},
    "AMD.US":  {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"7515.57","medium":"37238.16","small":"52334.26"},"capital_out":{"large":"8526.90","medium":"39940.37","small":"55324.40"}},
    "TSLA.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"26570.80","medium":"98712.37","small":"102774.46"},"capital_out":{"large":"32399.46","medium":"108783.23","small":"106550.75"}},
    "KO.US":   {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"678.88","medium":"1732.77","small":"5558.03"},"capital_out":{"large":"469.10","medium":"1889.25","small":"5210.73"}},
    "LLY.US":  {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"686.88","medium":"3468.39","small":"8715.77"},"capital_out":{"large":"1051.15","medium":"6110.30","small":"11506.27"}},
    "TRV.US":  {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"59.47","medium":"559.36","small":"1375.74"},"capital_out":{"large":"250.76","medium":"647.36","small":"1587.62"}},
    "MRK.US":  {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"655.74","medium":"3259.25","small":"7707.45"},"capital_out":{"large":"1356.42","medium":"3230.83","small":"7953.38"}},
    "ASML.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"4521.60","medium":"9709.65","small":"12368.52"},"capital_out":{"large":"1453.91","medium":"10679.26","small":"19430.58"}},
    "FTNT.US": {"timestamp":"2026-02-26 21:00:00.0 +00:00:00","capital_in":{"large":"837.52","medium":"1241.71","small":"5855.29"},"capital_out":{"large":"381.96","medium":"1107.01","small":"5115.65"}},
}

for symbol, data in CAPITAL_DIST_DATA.items():
    data_dir = symbol_data_dir(symbol)
    os.makedirs(os.path.join(data_dir, "tmp"), exist_ok=True)
    tmp_path = os.path.join(data_dir, "tmp", "capital_dist_raw.json")
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    print(f"[{symbol}] saved capital_dist_raw.json")

print("Done.")
