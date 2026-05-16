#!/usr/bin/env python3
"""Validate real Phase 3 profile-effect proof from worker result JSON files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_worker_result import validate_worker_result

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOLS = ["NVDA.US", "0700.HK", "600900.SH"]
PROFILE_AWARE_PHASES = {"reasoning", "execution"}


def validate_phase3_profile_effect(
    *,
    project_root: Path | str = PROJECT_ROOT,
    symbols: list[str] | None = None,
    phase: str = "reasoning",
    run_id: str | None = None,
    result_jsons: list[Path | str] | None = None,
    min_results: int = 2,
    min_profiles: int = 2,
    check_files: bool = True,
) -> dict[str, Any]:
    root = Path(project_root)
    errors: list[str] = []

    if phase not in PROFILE_AWARE_PHASES:
        errors.append(f"phase must be one of {sorted(PROFILE_AWARE_PHASES)}")

    result_paths = normalize_result_paths(root, result_jsons)
    if not result_paths:
        result_paths = discover_result_paths(root, symbols or DEFAULT_SYMBOLS, phase, run_id)
    if not result_paths:
        errors.append("no profile-aware worker result JSON files found")

    checked: list[dict[str, Any]] = []
    valid_result_count = 0
    profile_names: set[str] = set()
    weight_signatures: set[str] = set()
    phases: set[str] = set()

    for path in result_paths:
        rel = relpath(path, root)
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{rel}: cannot read worker result JSON: {exc}")
            continue
        if not isinstance(result, dict):
            errors.append(f"{rel}: worker result must be a JSON object")
            continue

        result_error_count = len(errors)
        worker_errors = validate_worker_result(result, project_root=root, check_files=check_files)
        errors.extend(f"{rel}: {error}" for error in worker_errors)
        errors.extend(validate_profile_resolution_alignment(root, result, rel))

        result_phase = result.get("phase")
        phases.add(str(result_phase))
        if result_phase != phase:
            errors.append(f"{rel}: expected phase {phase}, got {result_phase}")
        if result.get("status") == "failed":
            errors.append(f"{rel}: failed worker result cannot prove profile effect")
        if not result.get("output_files"):
            errors.append(f"{rel}: output_files must include the markdown artifact for profile-effect proof")

        profile_used = result.get("profile_used")
        if isinstance(profile_used, str) and profile_used and profile_used != "default":
            profile_names.add(profile_used)
        else:
            errors.append(f"{rel}: profile_used must be a non-default profile")

        profile_effect = result.get("profile_effect") if isinstance(result.get("profile_effect"), dict) else {}
        weight_bias = profile_effect.get("weight_bias_applied")
        if isinstance(weight_bias, dict) and weight_bias:
            weight_signatures.add(json.dumps(weight_bias, ensure_ascii=False, sort_keys=True))
        else:
            errors.append(f"{rel}: profile_effect.weight_bias_applied must be non-empty for proof")

        checked.append(
            {
                "path": rel,
                "symbol": result.get("symbol"),
                "phase": result_phase,
                "status": result.get("status"),
                "profile_used": profile_used,
                "weight_bias_applied": weight_bias if isinstance(weight_bias, dict) else None,
            }
        )
        if len(errors) == result_error_count:
            valid_result_count += 1

    if valid_result_count < min_results:
        errors.append(f"need at least {min_results} valid worker results, got {valid_result_count}")
    if len(profile_names) < min_profiles:
        errors.append(f"need at least {min_profiles} distinct non-default profiles, got {len(profile_names)}")
    if len(weight_signatures) < min_profiles:
        errors.append(f"need at least {min_profiles} distinct weight_bias_applied payloads, got {len(weight_signatures)}")
    if len(phases) > 1:
        errors.append(f"all worker results must use the same phase, got {sorted(phases)}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "phase": phase,
        "checked_results": checked,
        "valid_result_count": valid_result_count,
        "profiles": sorted(profile_names),
        "distinct_weight_bias_count": len(weight_signatures),
        "errors": errors,
    }


def normalize_result_paths(root: Path, result_jsons: list[Path | str] | None) -> list[Path]:
    paths: list[Path] = []
    for raw_path in result_jsons or []:
        path = Path(raw_path)
        if not path.is_absolute():
            path = root / path
        paths.append(path)
    return paths


def discover_result_paths(root: Path, symbols: list[str], phase: str, run_id: str | None) -> list[Path]:
    results_dir_glob = [root / "data" / "_runs" / run_id / "worker_results"] if run_id else (root / "data" / "_runs").glob("*/worker_results")
    latest_by_symbol: dict[str, Path] = {}
    for results_dir in results_dir_glob:
        for symbol in symbols:
            path = results_dir / f"{symbol}_{phase}.json"
            if not path.exists():
                continue
            existing = latest_by_symbol.get(symbol)
            if existing is None or path.stat().st_mtime >= existing.stat().st_mtime:
                latest_by_symbol[symbol] = path
    return [latest_by_symbol[symbol] for symbol in symbols if symbol in latest_by_symbol]


def validate_profile_resolution_alignment(root: Path, result: dict[str, Any], rel: str) -> list[str]:
    errors: list[str] = []
    symbol = result.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        return errors
    resolution_path = root / "data" / symbol / "profile_resolution.json"
    if not resolution_path.exists():
        return errors
    try:
        resolution = json.loads(resolution_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{rel}: cannot read profile_resolution.json for {symbol}: {exc}"]

    for key in ("profile_used", "optional_profiles", "profile_file_paths", "profile_source"):
        if result.get(key) != resolution.get(key):
            errors.append(f"{rel}: {key} does not match data/{symbol}/profile_resolution.json")
    return errors


def parse_symbols(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    symbols = []
    for item in raw.split(","):
        symbol = item.strip()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 3 profile-effect proof from real worker results")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--symbols", default=None, help="comma-separated symbols; defaults to standard regression symbols")
    parser.add_argument("--phase", default="reasoning", choices=sorted(PROFILE_AWARE_PHASES))
    parser.add_argument("--run-id", default=None, help="specific data/_runs/<run-id> to inspect")
    parser.add_argument("--result-json", action="append", default=[], help="explicit worker result JSON path; may be repeated")
    parser.add_argument("--min-results", type=int, default=2)
    parser.add_argument("--min-profiles", type=int, default=2)
    parser.add_argument("--no-check-files", action="store_true")
    parser.add_argument("--json", action="store_true", help="print machine-readable validation output")
    args = parser.parse_args()

    report = validate_phase3_profile_effect(
        project_root=Path(args.project_root),
        symbols=parse_symbols(args.symbols),
        phase=args.phase,
        run_id=args.run_id,
        result_jsons=[Path(path) for path in args.result_json],
        min_results=args.min_results,
        min_profiles=args.min_profiles,
        check_files=not args.no_check_files,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["errors"]:
        print("FAIL phase3 profile-effect validation")
        for error in report["errors"]:
            print(f"- {error}")
    else:
        print("PASS phase3 profile-effect validation")
        print(f"profiles={','.join(report['profiles'])}")
        print(f"checked_results={len(report['checked_results'])}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
