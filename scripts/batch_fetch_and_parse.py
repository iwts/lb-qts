#!/usr/bin/env python3
"""
批处理：解析外部已写入的 JSON 文件并合并到 data/<symbol>/。
本脚本仅负责 parse，不再承担任何 SDK 抓数逻辑。
用法：python batch_fetch_and_parse.py --symbol 561560.SH
依赖：/tmp/lb-qts-data/<symbol>/1h.json, 1d.json, 1w.json 已由上游流程写入
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import symbol_data_dir, log

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--skip-kline", action="store_true", help="仅 parse 辅助数据")
    args = parser.parse_args()
    symbol = args.symbol
    tmp_dir = f"/tmp/lb-qts-data/{symbol}"
    data_dir = symbol_data_dir(symbol)
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    parse_args = ["python", "scripts/parse_mcp_data.py", "--symbol", symbol]
    if not args.skip_kline:
        for p, f in [("1h", "1h.json"), ("1d", "1d.json"), ("1w", "1w.json")]:
            path = os.path.join(tmp_dir, f)
            if os.path.exists(path):
                parse_args.extend(["--hourly" if p == "1h" else "--daily" if p == "1d" else "--weekly", path])
    # 简化：只跑 parse，由 Agent 事先写入 JSON
    cmd = ["python", "scripts/parse_mcp_data.py", "--symbol", symbol]
    if os.path.exists(os.path.join(tmp_dir, "1h.json")):
        cmd.extend(["--hourly", os.path.join(tmp_dir, "1h.json")])
    if os.path.exists(os.path.join(tmp_dir, "1d.json")):
        cmd.extend(["--daily", os.path.join(tmp_dir, "1d.json")])
    if os.path.exists(os.path.join(tmp_dir, "1w.json")):
        cmd.extend(["--weekly", os.path.join(tmp_dir, "1w.json")])
    if os.path.exists(os.path.join(tmp_dir, "capital_flow.json")):
        cmd.extend(["--capital-flow-file", os.path.join(tmp_dir, "capital_flow.json")])
    if os.path.exists(os.path.join(tmp_dir, "capital_dist.json")):
        cmd.extend(["--capital-dist-file", os.path.join(tmp_dir, "capital_dist.json")])

    if len(cmd) <= 4:
        log.warning(f"无 JSON 文件可 parse，跳过")
        return 0
    r = subprocess.run(cmd, cwd=os.path.dirname(os.path.dirname(__file__)))
    return r.returncode

if __name__ == "__main__":
    sys.exit(main() or 0)
