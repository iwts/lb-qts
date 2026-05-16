#!/usr/bin/env python3
"""Resolve Phase 3 profile inputs for a symbol.

Exit codes are shell-friendly for the pipeline:
- 0: resolution written/read successfully, including degraded default fallback
- 1: invalid input such as malformed symbol_profile.json
- 2: degraded resolution only when --strict is requested
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = Path("agents/profiles")
TECH_GROWTH_SYMBOLS = {"AAPL.US", "AMD.US", "AMZN.US", "ASML.US", "GOOG.US", "META.US", "MSFT.US", "NVDA.US", "TSLA.US"}
DIVIDEND_DEFENSIVE_SYMBOLS = {"600900.SH", "600025.SH", "600941.SH"}


def resolve_profile(symbol: str, project_root: Path | str = PROJECT_ROOT) -> dict[str, Any]:
    root = Path(project_root)
    symbol_dir = root / "data" / symbol
    profile_path = symbol_dir / "symbol_profile.json"
    warnings: list[str] = []

    if profile_path.exists():
        payload = read_json(profile_path)
        profile_used = str(payload.get("style_profile", "")).strip()
        optional_profiles = normalize_optional_profiles(payload.get("optional_profiles", []), warnings)
        profile_source = payload.get("profile_source", "manual")
        profile_confidence = payload.get("profile_confidence", 0.0)
    else:
        profile_used, optional_profiles, profile_source, profile_confidence = infer_profile(symbol, root, warnings)

    profile_file_paths = []
    status = "ok"
    if not profile_used:
        profile_used = "default"
        profile_source = "default"
        profile_confidence = 0.0
        warnings.append("empty style_profile; using default profile")

    if len(optional_profiles) > 2:
        status = "degraded"
        warnings.append("optional_profiles contains more than 2 entries; extra profiles were dropped")
        optional_profiles = optional_profiles[:2]

    for profile_name in [profile_used, *optional_profiles]:
        if profile_name == "default":
            continue
        candidate = PROFILE_DIR / f"{profile_name}.md"
        if (root / candidate).exists():
            profile_file_paths.append(str(candidate))
        else:
            status = "degraded"
            warnings.append(f"missing profile file: {candidate}")

    if profile_used == "default":
        status = "degraded"

    return {
        "symbol": symbol,
        "status": status,
        "profile_used": profile_used,
        "optional_profiles": optional_profiles,
        "profile_file_paths": profile_file_paths,
        "profile_source": profile_source,
        "profile_confidence": profile_confidence,
        "profile_warnings": warnings,
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid profile JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"profile JSON must be an object: {path}")
    return payload


def normalize_optional_profiles(raw: Any, warnings: list[str]) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        warnings.append("optional_profiles is not a list; ignoring overlays")
        return []
    profiles = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            warnings.append("optional_profiles contains a non-string entry; ignoring it")
            continue
        if item not in profiles:
            profiles.append(item)
    return profiles


def infer_profile(symbol: str, root: Path, warnings: list[str]) -> tuple[str, list[str], str, float]:
    warnings.append("symbol_profile.json missing; using rule/default profile inference")
    if symbol.endswith(".HK"):
        return "hk_liquidity_pm", [], "rule", 0.7
    if symbol in DIVIDEND_DEFENSIVE_SYMBOLS:
        return "dividend_defensive_pm", [], "rule", 0.75
    if symbol in TECH_GROWTH_SYMBOLS:
        optional_profiles = ["options_flow_trader"] if has_option_data(root, symbol) else []
        return "tech_growth_pm", optional_profiles, "rule", 0.7
    return "default", [], "default", 0.0


def has_option_data(root: Path, symbol: str) -> bool:
    symbol_dir = root / "data" / symbol
    return (symbol_dir / "option_summary.json").exists() or (symbol_dir / "option_oi.csv").exists()


def write_resolution(root: Path, symbol: str, resolution: dict[str, Any]) -> Path:
    output_path = root / "data" / symbol / "profile_resolution.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(resolution, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve Phase 3 profiles for one symbol")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--write", action="store_true", help="write data/<symbol>/profile_resolution.json")
    parser.add_argument("--strict", action="store_true", help="return 2 when the resolved status is degraded")
    args = parser.parse_args()

    root = Path(args.project_root)
    try:
        resolution = resolve_profile(args.symbol, root)
    except ValueError as exc:
        print(json.dumps({"symbol": args.symbol, "status": "failed", "profile_warnings": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1

    if args.write:
        output_path = write_resolution(root, args.symbol, resolution)
        resolution["output_file"] = str(output_path.relative_to(root))

    print(json.dumps(resolution, ensure_ascii=False, indent=2))
    if args.strict and resolution["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
