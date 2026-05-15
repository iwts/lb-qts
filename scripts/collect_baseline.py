#!/usr/bin/env python3
"""Collect Phase 0 baseline artifacts for the lb-qts agent pipeline.

The collector does not run analysis workers. It snapshots existing artifacts so
later modernization phases can compare behavior against a frozen baseline.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from verify_data_freshness import check_symbol

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOLS = ["NVDA.US", "0700.HK", "600900.SH"]
PERIOD_THRESHOLDS_HOURS = {"1h": 4, "1d": 24, "1w": 192}
DATA_FILES = {
    "1h": "1h_k.csv",
    "1d": "1d_k.csv",
    "1w": "1w_k.csv",
}
KEY_ARTIFACT_PATTERNS = {
    "fundamental_report": "deduction/{symbol}/fundamental_analysis_*.md",
    "deduction_report": "deduction/{symbol}/deduction_*.md",
    "final_report": "report/{symbol}/report_*.md",
}
SUPPORTING_DATA_FILES = [
    "fundamental.json",
    "earnings.json",
    "signals_summary.json",
    "llm_context.md",
    "factor_scores.json",
]


def parse_symbols(raw: str | None) -> list[str]:
    if raw is None:
        return list(DEFAULT_SYMBOLS)
    symbols: list[str] = []
    for part in raw.split(","):
        symbol = part.strip()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    if not symbols:
        raise ValueError("symbols must contain at least one non-empty symbol")
    return symbols


def collect_baseline(
    *,
    symbols: list[str],
    run_date: str,
    project_root: Path | str = PROJECT_ROOT,
) -> dict[str, Any]:
    started = time.monotonic()
    root = Path(project_root)
    baseline_dir = root / "data" / "_baseline" / run_date
    baseline_dir.mkdir(parents=True, exist_ok=True)

    results = []
    status_counts = {"ok": 0, "degraded": 0, "failed": 0}
    for symbol in symbols:
        metrics = collect_symbol_metrics(root, symbol)
        status_counts[metrics["status"]] = status_counts.get(metrics["status"], 0) + 1
        write_json(baseline_dir / f"{symbol}_baseline_metrics.json", metrics)
        results.append(
            {
                "symbol": symbol,
                "status": metrics["status"],
                "stage_status": metrics["inferred_stage_status"],
                "fundamental_report": metrics["artifacts"]["fundamental_report"]["path"],
                "deduction_report": metrics["artifacts"]["deduction_report"]["path"],
                "final_report": metrics["artifacts"]["final_report"]["path"],
                "report_length": metrics["report_length"],
                "warnings": metrics["warnings"],
                "metrics_file": relpath(baseline_dir / f"{symbol}_baseline_metrics.json", root),
            }
        )

    summary = {
        "run_date": run_date,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "symbols": symbols,
        "results": results,
        "status_counts": status_counts,
        "duration_seconds": round(time.monotonic() - started, 2),
        "quality_floor": {
            "required_artifacts": [
                "deduction/<symbol>/fundamental_analysis_*.md",
                "deduction/<symbol>/deduction_*.md",
                "report/<symbol>/report_*.md",
            ],
            "critical_data_periods": ["1h", "1d"],
            "degraded_is_allowed_for_baseline": True,
        },
    }
    write_json(baseline_dir / "run_summary.json", summary)
    return summary


def collect_symbol_metrics(root: Path, symbol: str) -> dict[str, Any]:
    started = time.monotonic()
    artifacts = {
        name: file_snapshot(latest_match(root, pattern.format(symbol=symbol)), root)
        for name, pattern in KEY_ARTIFACT_PATTERNS.items()
    }
    data_files = collect_data_files(root, symbol)
    freshness = collect_data_freshness(root, symbol)
    latest_manifest = find_latest_run_manifest(root, symbol)
    worker_results = collect_worker_results(root, symbol)
    inferred_stage_status = infer_stage_status(artifacts, data_files, freshness)
    report_length = {
        "line_count": artifacts["final_report"]["line_count"],
        "size_bytes": artifacts["final_report"]["size_bytes"],
    }

    warnings = build_warnings(artifacts, data_files, freshness)
    status = "ok"
    if any(not artifacts[name]["exists"] for name in KEY_ARTIFACT_PATTERNS):
        status = "failed"
    elif warnings:
        status = "degraded"

    return {
        "symbol": symbol,
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "artifacts": artifacts,
        "data_files": data_files,
        "data_freshness": freshness,
        "latest_pipeline_manifest": latest_manifest,
        "inferred_stage_status": inferred_stage_status,
        "worker_results": worker_results,
        "report_length": report_length,
        "duration_seconds": round(time.monotonic() - started, 2),
        "warnings": warnings,
    }


def collect_data_files(root: Path, symbol: str) -> dict[str, dict[str, Any]]:
    symbol_dir = root / "data" / symbol
    result: dict[str, dict[str, Any]] = {}
    for filename in [*DATA_FILES.values(), *SUPPORTING_DATA_FILES]:
        result[filename] = file_snapshot(symbol_dir / filename, root)
    return result


def collect_data_freshness(root: Path, symbol: str) -> dict[str, Any]:
    gate = check_symbol(symbol, project_root=root)
    return {
        "critical_pass": gate["critical_pass"],
        "periods": gate["periods"],
    }


def latest_csv_timestamp(path: Path) -> datetime | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    latest_raw = None
    try:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "timestamp" not in (reader.fieldnames or []):
                return None
            for row in reader:
                if row.get("timestamp"):
                    latest_raw = row["timestamp"]
    except OSError:
        return None
    if not latest_raw:
        return None
    return parse_timestamp(latest_raw)


def parse_timestamp(raw: str) -> datetime | None:
    value = raw.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def find_latest_run_manifest(root: Path, symbol: str) -> dict[str, Any]:
    manifests = []
    for path in (root / "data" / "_runs").glob("*/run_manifest.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if symbol not in data.get("symbols", []):
            continue
        manifests.append((path, data))
    if not manifests:
        return {"exists": False, "path": None}

    path, data = max(manifests, key=lambda item: item[1].get("updated_at", item[1].get("created_at", "")))
    return {
        "exists": True,
        "path": relpath(path, root),
        "run_id": data.get("run_id"),
        "updated_at": data.get("updated_at"),
        "symbol_status": data.get("symbol_status", {}).get(symbol, {}),
    }


def collect_worker_results(root: Path, symbol: str) -> dict[str, Any]:
    files = sorted((root / "data" / "_runs").glob(f"*/worker_results/{symbol}_*.json"))
    latest_by_phase: dict[str, dict[str, Any]] = {}
    for path in files:
        phase = path.stem.replace(f"{symbol}_", "", 1)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            latest_by_phase[phase] = {"path": relpath(path, root), "status": "unreadable"}
            continue
        existing = latest_by_phase.get(phase)
        if existing is None or path.stat().st_mtime >= existing.get("_mtime", 0):
            latest_by_phase[phase] = {
                "path": relpath(path, root),
                "status": data.get("status"),
                "phase": data.get("phase", phase),
                "summary": data.get("summary", ""),
                "metrics": data.get("metrics", {}),
                "_mtime": path.stat().st_mtime,
            }
    for result in latest_by_phase.values():
        result.pop("_mtime", None)
    return latest_by_phase


def infer_stage_status(
    artifacts: dict[str, dict[str, Any]],
    data_files: dict[str, dict[str, Any]],
    freshness: dict[str, Any],
) -> dict[str, str]:
    data_missing = any(not data_files[name]["exists"] for name in DATA_FILES.values())
    if data_missing:
        data_status = "failed"
    elif freshness["critical_pass"]:
        data_status = "ok"
    else:
        data_status = "degraded"

    strategy_inputs = ["signals_summary.json", "llm_context.md", "factor_scores.json"]
    return {
        "data": data_status,
        "fundamental": "ok" if artifacts["fundamental_report"]["exists"] else "failed",
        "strategy": "ok" if all(data_files[name]["exists"] for name in strategy_inputs) else "degraded",
        "reasoning": "ok" if artifacts["deduction_report"]["exists"] else "failed",
        "execution": "ok" if artifacts["final_report"]["exists"] else "failed",
    }


def build_warnings(
    artifacts: dict[str, dict[str, Any]],
    data_files: dict[str, dict[str, Any]],
    freshness: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for name, snapshot in artifacts.items():
        if not snapshot["exists"]:
            warnings.append(f"missing key artifact: {name}")
    for filename, snapshot in data_files.items():
        if not snapshot["exists"]:
            warnings.append(f"missing data file: {filename}")
    for period, info in freshness["periods"].items():
        if info["status"] != "OK":
            if info["critical"]:
                warnings.append(f"critical data freshness {period}: {info['status']}")
    return warnings


def latest_match(root: Path, pattern: str) -> Path | None:
    matches = [path for path in root.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def file_snapshot(path: Path | None, root: Path) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"exists": False, "path": None, "size_bytes": 0, "modified_at": None, "line_count": 0}
    line_count = 0
    if path.is_file() and path.suffix in {".md", ".csv", ".json"}:
        try:
            with path.open(encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)
        except OSError:
            line_count = 0
    return {
        "exists": True,
        "path": relpath(path, root),
        "size_bytes": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "line_count": line_count,
    }


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def print_summary(summary: dict[str, Any], summary_path: Path) -> None:
    counts = {"ok": 0, "degraded": 0, "failed": 0}
    for result in summary["results"]:
        counts[result["status"]] = counts.get(result["status"], 0) + 1

    print(f"baseline_summary={summary_path}")
    print(
        "status_counts="
        f"ok:{counts.get('ok', 0)} "
        f"degraded:{counts.get('degraded', 0)} "
        f"failed:{counts.get('failed', 0)}"
    )
    for result in summary["results"]:
        warning_count = len(result.get("warnings", []))
        print(f"{result['symbol']} {result['status']} warnings={warning_count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Phase 0 modernization baseline artifacts")
    parser.add_argument("--symbols", default=None, help="comma-separated symbols; defaults to Phase 0 regression set")
    parser.add_argument("--run-date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--json", action="store_true", help="print the full run_summary JSON to stdout")
    parser.add_argument("--strict", action="store_true", help="return non-zero when any symbol is not ok")
    args = parser.parse_args()

    summary = collect_baseline(
        symbols=parse_symbols(args.symbols),
        run_date=args.run_date,
        project_root=Path(args.project_root),
    )
    summary_path = Path(args.project_root) / "data" / "_baseline" / args.run_date / "run_summary.json"
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_summary(summary, summary_path)
    if args.strict and any(result["status"] != "ok" for result in summary["results"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
