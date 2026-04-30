#!/usr/bin/env python3
import os
import json
import logging
import subprocess
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORT_DIR = os.path.join(BASE_DIR, "report")
DEDUCTION_DIR = os.path.join(BASE_DIR, "deduction")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("lb-qts")


def symbol_data_dir(symbol: str) -> str:
    d = os.path.join(DATA_DIR, symbol)
    os.makedirs(d, exist_ok=True)
    return d


def symbol_report_dir(symbol: str) -> str:
    d = os.path.join(REPORT_DIR, symbol)
    os.makedirs(d, exist_ok=True)
    return d


def symbol_deduction_dir(symbol: str) -> str:
    d = os.path.join(DEDUCTION_DIR, symbol)
    os.makedirs(d, exist_ok=True)
    return d


def next_seq(directory: str, prefix: str) -> int:
    """Get next sequence number for files with given prefix in directory."""
    existing = [f for f in os.listdir(directory) if f.startswith(prefix)] if os.path.isdir(directory) else []
    if not existing:
        return 1
    nums = []
    for f in existing:
        parts = f.replace(".md", "").split("_")
        try:
            nums.append(int(parts[-1]))
        except (ValueError, IndexError):
            pass
    return max(nums, default=0) + 1


def today_str() -> str:
    return datetime.now().strftime("%Y_%m_%d")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run_longbridge_json(args: list[str], *, check: bool = True):
    """Run longbridge CLI and parse JSON output using the existing CLI login state."""
    cmd = ["longbridge", *args, "--format", "json"]
    last_result = None
    for attempt in range(3):
        result = subprocess.run(cmd, capture_output=True, text=True)
        last_result = result
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"invalid longbridge json: {' '.join(cmd)}\n"
                    f"stdout:\n{result.stdout}"
                ) from exc
        if "connections limitation is hit" in (result.stderr or "") and attempt < 2:
            time.sleep(1.5 * (attempt + 1))
            continue
        break
    if not check:
        return None
    raise RuntimeError(
        f"longbridge command failed: {' '.join(cmd)}\n"
        f"stdout:\n{last_result.stdout if last_result else ''}\n"
        f"stderr:\n{last_result.stderr if last_result else ''}"
    )
