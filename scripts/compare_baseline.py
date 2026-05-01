#!/usr/bin/env python3
"""Compare two lb-qts baseline snapshots and report regressions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_RANK = {"ok": 0, "degraded": 1, "failed": 2}
KEY_ARTIFACTS = ("fundamental_report", "deduction_report", "final_report")


def load_summary(root: Path, label: str) -> dict[str, Any]:
    path = root / "data" / "_baseline" / label / "run_summary.json"
    if not path.exists():
        raise FileNotFoundError(f"baseline summary not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def compare_baselines(
    *,
    base_label: str,
    candidate_label: str,
    project_root: Path | str = PROJECT_ROOT,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    base = load_summary(root, base_label)
    candidate = load_summary(root, candidate_label)

    base_results = {result["symbol"]: result for result in base.get("results", [])}
    candidate_results = {result["symbol"]: result for result in candidate.get("results", [])}
    target_symbols = symbols or list(dict.fromkeys([*base_results.keys(), *candidate_results.keys()]))

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    unchanged: list[str] = []
    missing_symbols: list[str] = []

    for symbol in target_symbols:
        before = base_results.get(symbol)
        after = candidate_results.get(symbol)
        if before is None or after is None:
            missing_symbols.append(symbol)
            regressions.append(
                {
                    "symbol": symbol,
                    "type": "missing_symbol",
                    "base_exists": before is not None,
                    "candidate_exists": after is not None,
                }
            )
            continue

        before_rank = STATUS_RANK.get(before.get("status"), 99)
        after_rank = STATUS_RANK.get(after.get("status"), 99)
        if after_rank > before_rank:
            regressions.append(
                {
                    "symbol": symbol,
                    "type": "status_worse",
                    "base_status": before.get("status"),
                    "candidate_status": after.get("status"),
                }
            )
        elif after_rank < before_rank:
            improvements.append(
                {
                    "symbol": symbol,
                    "type": "status_better",
                    "base_status": before.get("status"),
                    "candidate_status": after.get("status"),
                }
            )
        else:
            unchanged.append(symbol)

        for artifact in KEY_ARTIFACTS:
            if before.get(artifact) and not after.get(artifact):
                regressions.append(
                    {
                        "symbol": symbol,
                        "type": "missing_artifact",
                        "artifact": artifact,
                        "base_path": before.get(artifact),
                    }
                )

    return {
        "base_label": base_label,
        "candidate_label": candidate_label,
        "symbols": target_symbols,
        "status": "failed" if regressions else "ok",
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "missing_symbols": missing_symbols,
    }


def parse_symbols(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    symbols = []
    for part in raw.split(","):
        symbol = part.strip()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols or None


def print_report(report: dict[str, Any]) -> None:
    print(f"baseline_compare={report['base_label']}..{report['candidate_label']}")
    print(f"status={report['status']}")
    print(
        "counts="
        f"regressions:{len(report['regressions'])} "
        f"improvements:{len(report['improvements'])} "
        f"unchanged:{len(report['unchanged'])}"
    )
    for regression in report["regressions"]:
        print(f"REGRESSION {regression}")
    for improvement in report["improvements"]:
        print(f"IMPROVEMENT {improvement}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two lb-qts baseline snapshots")
    parser.add_argument("--base", required=True, help="baseline label/date under data/_baseline")
    parser.add_argument("--candidate", required=True, help="candidate label/date under data/_baseline")
    parser.add_argument("--symbols", default=None, help="optional comma-separated symbol subset")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--json", action="store_true", help="print JSON report")
    parser.add_argument("--strict", action="store_true", help="return non-zero when regressions exist")
    args = parser.parse_args()

    report = compare_baselines(
        base_label=args.base,
        candidate_label=args.candidate,
        project_root=Path(args.project_root),
        symbols=parse_symbols(args.symbols),
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    if args.strict and report["regressions"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
