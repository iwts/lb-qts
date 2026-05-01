#!/usr/bin/env python3
"""Run manifest helpers for lb-qts pipeline checkpoint/resume state.

The manifest intentionally lives under data/_runs so runtime state follows the
project's existing artifact policy and stays out of git by default.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_PHASES = ["data", "fundamental", "strategy", "reasoning", "execution", "review", "youtube"]
ALLOWED_STATUSES = {"pending", "in_progress", "ok", "degraded", "failed", "skipped"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunManifest:
    run_id: str
    created_at: str
    updated_at: str
    symbols: list[str]
    phases: list[str] = field(default_factory=lambda: list(DEFAULT_PHASES))
    symbol_status: dict[str, dict[str, str]] = field(default_factory=dict)
    artifacts: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    metrics: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    warnings: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    @classmethod
    def new(cls, symbols: list[str], run_id: str | None = None) -> "RunManifest":
        now = _now_iso()
        normalized_symbols = _normalize_symbols(symbols)
        manifest = cls(
            run_id=run_id or datetime.now().strftime("%Y-%m-%d_%H%M%S"),
            created_at=now,
            updated_at=now,
            symbols=normalized_symbols,
        )
        for symbol in normalized_symbols:
            manifest.symbol_status[symbol] = {phase: "pending" for phase in manifest.phases}
            manifest.artifacts[symbol] = {phase: [] for phase in manifest.phases}
            manifest.metrics[symbol] = {phase: {} for phase in manifest.phases}
            manifest.warnings[symbol] = {phase: [] for phase in manifest.phases}
        return manifest

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunManifest":
        return cls(
            run_id=data["run_id"],
            created_at=data["created_at"],
            updated_at=data.get("updated_at", data["created_at"]),
            symbols=list(data.get("symbols", [])),
            phases=list(data.get("phases", DEFAULT_PHASES)),
            symbol_status=data.get("symbol_status", {}),
            artifacts=data.get("artifacts", {}),
            metrics=data.get("metrics", {}),
            warnings=data.get("warnings", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized = []
    for symbol in symbols:
        clean = symbol.strip()
        if clean and clean not in normalized:
            normalized.append(clean)
    if not normalized:
        raise ValueError("symbols must contain at least one non-empty symbol")
    return normalized


def manifest_path_for(run_id: str, base_dir: Path | str | None = None) -> Path:
    root = Path(base_dir) if base_dir is not None else PROJECT_ROOT
    return root / "data" / "_runs" / run_id / "run_manifest.json"


def save_manifest(manifest: RunManifest, path: Path) -> Path:
    manifest.updated_at = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def create_run_manifest(
    symbols: list[str],
    run_id: str | None = None,
    base_dir: Path | str | None = None,
) -> Path:
    manifest = RunManifest.new(symbols=symbols, run_id=run_id)
    return save_manifest(manifest, manifest_path_for(manifest.run_id, base_dir))


def load_manifest(path: Path | str) -> RunManifest:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return RunManifest.from_dict(data)


def update_phase(
    manifest_path: Path | str,
    *,
    symbol: str,
    phase: str,
    status: str,
    output_files: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> Path:
    manifest_file = Path(manifest_path)
    manifest = load_manifest(manifest_file)
    if symbol not in manifest.symbols:
        raise ValueError(f"unknown symbol: {symbol}")
    if phase not in manifest.phases:
        raise ValueError(f"unknown phase: {phase}")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"unknown status: {status}")

    manifest.symbol_status.setdefault(symbol, {})[phase] = status
    if output_files is not None:
        manifest.artifacts.setdefault(symbol, {})[phase] = list(output_files)
    if metrics is not None:
        manifest.metrics.setdefault(symbol, {})[phase] = dict(metrics)
    if warnings is not None:
        manifest.warnings.setdefault(symbol, {})[phase] = list(warnings)
    return save_manifest(manifest, manifest_file)


def _parse_symbols(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update lb-qts pipeline run manifests")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="create a new run manifest")
    create_parser.add_argument("--symbols", required=True, help="comma-separated symbols")
    create_parser.add_argument("--run-id", default=None)

    update_parser = subparsers.add_parser("update", help="update one symbol phase")
    update_parser.add_argument("--manifest", required=True)
    update_parser.add_argument("--symbol", required=True)
    update_parser.add_argument("--phase", required=True)
    update_parser.add_argument("--status", required=True)
    update_parser.add_argument("--output-file", action="append", default=[])
    update_parser.add_argument("--metrics-json", default=None)
    update_parser.add_argument("--warning", action="append", default=[])

    args = parser.parse_args()
    if args.command == "create":
        path = create_run_manifest(_parse_symbols(args.symbols), run_id=args.run_id)
        print(path)
        return 0

    metrics = json.loads(args.metrics_json) if args.metrics_json else None
    path = update_phase(
        args.manifest,
        symbol=args.symbol,
        phase=args.phase,
        status=args.status,
        output_files=args.output_file or None,
        metrics=metrics,
        warnings=args.warning or None,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
