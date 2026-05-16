#!/usr/bin/env python3
"""Validate Phase 3 profile files and standard symbol profile mappings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SECTIONS = [
    "Mandate",
    "Evidence Priority",
    "Weight Bias",
    "Hard Concerns",
    "Preferred Setups",
    "Common Mistakes",
]
MINIMUM_REQUIRED_PROFILES = {
    "tech_growth_pm",
    "dividend_defensive_pm",
    "hk_liquidity_pm",
}
EXPECTED_SYMBOL_MAPPINGS = {
    "NVDA.US": {
        "style_profile": "tech_growth_pm",
        "optional_profiles": ["options_flow_trader"],
    },
    "0700.HK": {
        "style_profile": "hk_liquidity_pm",
        "optional_profiles": [],
    },
    "600900.SH": {
        "style_profile": "dividend_defensive_pm",
        "optional_profiles": [],
    },
}
VALID_PROFILE_SOURCES = {"manual", "rule", "default"}


def validate_profiles(project_root: Path = PROJECT_ROOT) -> list[str]:
    errors: list[str] = []
    profile_dir = project_root / "agents" / "profiles"
    data_dir = project_root / "data"

    profiles = collect_profile_files(profile_dir)
    if not profile_dir.exists():
        errors.append("missing profile directory: agents/profiles")
        return errors
    if len(profiles) < 3:
        errors.append("at least 3 profiles are required")

    missing_required = sorted(MINIMUM_REQUIRED_PROFILES - set(profiles))
    if missing_required:
        errors.append(f"missing required profiles: {', '.join(missing_required)}")

    for profile_name, path in sorted(profiles.items()):
        errors.extend(validate_profile_file(profile_name, path))

    errors.extend(validate_symbol_profile_files(project_root, data_dir, profile_dir))
    return errors


def collect_profile_files(profile_dir: Path) -> dict[str, Path]:
    if not profile_dir.exists():
        return {}
    return {path.stem: path for path in profile_dir.glob("*.md") if path.is_file()}


def validate_profile_file(profile_name: str, path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > 80:
        errors.append(f"{path}: profile exceeds 80 lines ({len(lines)})")

    heading_lines = {line.strip() for line in lines if line.startswith("## ")}
    for section in REQUIRED_SECTIONS:
        if f"## {section}" not in heading_lines:
            errors.append(f"{path}: missing section ## {section}")

    if not text.startswith("# "):
        errors.append(f"{path}: first line must be an H1 title")
    if "通用分析方法" in text or "输出格式" in text or "run manifest" in text:
        errors.append(f"{path}: profile appears to include non-profile responsibilities")
    if profile_name == "options_flow_trader" and "overlay" not in text.lower():
        errors.append(f"{path}: options flow profile must declare overlay behavior")
    return errors


def validate_symbol_profile_files(project_root: Path, data_dir: Path, profile_dir: Path) -> list[str]:
    errors: list[str] = []
    for symbol, expected in EXPECTED_SYMBOL_MAPPINGS.items():
        path = data_dir / symbol / "symbol_profile.json"
        if not path.exists():
            errors.append(f"missing standard symbol profile: {path.relative_to(data_dir.parent)}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue
        errors.extend(validate_symbol_profile_payload(project_root, path, payload, profile_dir, expected))

    for path in data_dir.glob("*/symbol_profile.json"):
        symbol = path.parent.name
        if symbol in EXPECTED_SYMBOL_MAPPINGS:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue
        errors.extend(validate_symbol_profile_payload(project_root, path, payload, profile_dir, None))
    return errors


def validate_symbol_profile_payload(
    project_root: Path,
    path: Path,
    payload: Any,
    profile_dir: Path,
    expected: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"{path}: symbol profile must be a JSON object"]

    symbol = payload.get("symbol")
    if symbol != path.parent.name:
        errors.append(f"{path}: symbol must match directory name {path.parent.name}")

    style_profile = payload.get("style_profile")
    if not isinstance(style_profile, str) or not style_profile.strip():
        errors.append(f"{path}: style_profile must be a non-empty string")
    else:
        errors.extend(validate_profile_reference(project_root, path, profile_dir, style_profile, "style_profile"))

    optional_profiles = payload.get("optional_profiles", [])
    if not isinstance(optional_profiles, list):
        errors.append(f"{path}: optional_profiles must be a list")
        optional_profiles = []
    elif len(optional_profiles) > 2:
        errors.append(f"{path}: optional_profiles must contain at most 2 profiles")

    for index, profile_name in enumerate(optional_profiles):
        if not isinstance(profile_name, str) or not profile_name.strip():
            errors.append(f"{path}: optional_profiles[{index}] must be a non-empty string")
            continue
        errors.extend(validate_profile_reference(project_root, path, profile_dir, profile_name, f"optional_profiles[{index}]"))

    profile_source = payload.get("profile_source")
    if profile_source not in VALID_PROFILE_SOURCES:
        errors.append(f"{path}: profile_source must be one of {sorted(VALID_PROFILE_SOURCES)}")

    confidence = payload.get("profile_confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append(f"{path}: profile_confidence must be a number between 0 and 1")

    if expected is not None:
        if style_profile != expected["style_profile"]:
            errors.append(
                f"{path}: expected style_profile {expected['style_profile']}, got {style_profile}"
            )
        expected_optional = expected["optional_profiles"]
        if optional_profiles != expected_optional:
            errors.append(
                f"{path}: expected optional_profiles {expected_optional}, got {optional_profiles}"
            )
    return errors


def validate_profile_reference(project_root: Path, path: Path, profile_dir: Path, profile_name: str, field: str) -> list[str]:
    profile_path = profile_dir / f"{profile_name}.md"
    if not profile_path.exists():
        return [f"{path}: {field} references missing profile {relpath(profile_path, project_root)}"]
    return []


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 3 profile files and mappings")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--json", action="store_true", help="print machine-readable validation output")
    args = parser.parse_args()

    errors = validate_profiles(Path(args.project_root))
    if args.json:
        print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("FAIL profile validation")
        for error in errors:
            print(f"- {error}")
    else:
        print("PASS profile validation")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
