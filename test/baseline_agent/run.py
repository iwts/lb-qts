#!/usr/bin/env python3
"""Automated baseline/test agent runner for lb-qts modernization work."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
DEFAULT_SYMBOLS = ["NVDA.US", "0700.HK", "600900.SH", "600036.SH"]
PERIODS = ["1h", "1d", "1w"]


@dataclass
class CommandResult:
    name: str
    command: list[str]
    returncode: int
    duration_seconds: float
    stdout_tail: str = ""
    stderr_tail: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class SymbolRun:
    symbol: str
    status: str = "ok"
    warnings: list[str] = field(default_factory=list)
    commands: list[CommandResult] = field(default_factory=list)
    refreshed: bool = False
    refresh_mode: str = "none"


def parse_symbols(raw: str | None) -> list[str]:
    if raw is None:
        return list(DEFAULT_SYMBOLS)
    symbols: list[str] = []
    for item in raw.split(","):
        symbol = item.strip()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    if not symbols:
        raise ValueError("symbols must contain at least one non-empty symbol")
    return symbols


def python_cmd(script: str, *args: str) -> list[str]:
    executable = PYTHON if PYTHON.exists() else Path(sys.executable)
    return [str(executable), str(PROJECT_ROOT / script), *args]


def run_command(name: str, command: list[str], *, allow_fail: bool = False) -> CommandResult:
    started = time.monotonic()
    completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    result = CommandResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        duration_seconds=round(time.monotonic() - started, 2),
        stdout_tail=tail(completed.stdout),
        stderr_tail=tail(completed.stderr),
    )
    if completed.returncode != 0 and not allow_fail:
        raise RuntimeError(format_command_failure(result))
    return result


def tail(text: str, limit: int = 2000) -> str:
    value = text.strip()
    return value[-limit:] if len(value) > limit else value


def format_command_failure(result: CommandResult) -> str:
    return (
        f"command failed: {result.name} rc={result.returncode}\n"
        f"cmd={' '.join(result.command)}\n"
        f"stdout={result.stdout_tail}\n"
        f"stderr={result.stderr_tail}"
    )


def refresh_symbol(
    symbol: str,
    *,
    count: int,
    full_count: int,
    skip_refresh: bool,
    force_full: bool = False,
) -> SymbolRun:
    symbol_run = SymbolRun(symbol=symbol)
    if skip_refresh:
        symbol_run.warnings.append("refresh skipped")
        symbol_run.status = "degraded"
        return symbol_run

    try:
        fetch_and_parse(symbol_run, count=full_count if force_full else count, suffix="full" if force_full else "incremental")
        symbol_run.refreshed = True
        symbol_run.refresh_mode = "full" if force_full else "incremental"
    except RuntimeError as exc:
        symbol_run.status = "failed"
        symbol_run.warnings.append(str(exc))
        return symbol_run

    parse_result = next((cmd for cmd in symbol_run.commands if cmd.name == "parse_kline"), None)
    if parse_result and parse_result.returncode == 2:
        symbol_run.warnings.append("price drift detected; retried with full count")
        try:
            fetch_and_parse(symbol_run, count=full_count, suffix="full")
        except RuntimeError as exc:
            symbol_run.status = "failed"
            symbol_run.warnings.append(str(exc))
            return symbol_run

    for command_name, command in [
        (
            "calc_indicators",
            python_cmd("scripts/calc_indicators.py", "--symbol", symbol, "--periods", ",".join(PERIODS)),
        ),
        (
            "extract_llm_context",
            python_cmd("scripts/extract_llm_context.py", "--symbol", symbol),
        ),
    ]:
        result = run_command(command_name, command, allow_fail=True)
        symbol_run.commands.append(result)
        if not result.ok:
            symbol_run.status = "failed"
            symbol_run.warnings.append(format_command_failure(result))

    return symbol_run


def fetch_and_parse(symbol_run: SymbolRun, *, count: int, suffix: str = "incremental") -> None:
    symbol = symbol_run.symbol
    tmp_dir = PROJECT_ROOT / "data" / symbol / "tmp"
    fetch_result = run_command(
        f"fetch_kline_{suffix}",
        python_cmd(
            "scripts/fetch_longbridge_data.py",
            "--symbol",
            symbol,
            "--periods",
            ",".join(PERIODS),
            "--count",
            str(count),
            "--fetch",
            "kline",
            "--output-dir",
            str(tmp_dir),
        ),
        allow_fail=True,
    )
    symbol_run.commands.append(fetch_result)
    if not fetch_result.ok:
        raise RuntimeError(format_command_failure(fetch_result))

    parse_args = [
        "--symbol",
        symbol,
        "--hourly",
        str(tmp_dir / "1h_mcp.json"),
        "--daily",
        str(tmp_dir / "1d_mcp.json"),
        "--weekly",
        str(tmp_dir / "1w_mcp.json"),
    ]
    parse_result = run_command(
        "parse_kline" if suffix == "incremental" else f"parse_kline_{suffix}",
        python_cmd("scripts/parse_mcp_data.py", *parse_args),
        allow_fail=True,
    )
    symbol_run.commands.append(parse_result)
    if parse_result.returncode not in {0, 2}:
        raise RuntimeError(format_command_failure(parse_result))


def run_data_gate(symbols: list[str]) -> CommandResult:
    return run_command(
        "verify_data_freshness",
        python_cmd("scripts/verify_data_freshness.py", "--symbols", ",".join(symbols), "--critical-only"),
        allow_fail=True,
    )


def stale_symbols_from_gate(result: CommandResult, symbols: list[str]) -> list[str]:
    if result.ok:
        return []
    stale: list[str] = []
    text = "\n".join([result.stdout_tail, result.stderr_tail])
    for symbol in symbols:
        if symbol in text and symbol not in stale:
            stale.append(symbol)
    return stale or list(symbols)


def collect_candidate(symbols: list[str], label: str) -> tuple[CommandResult, dict[str, Any]]:
    result = run_command(
        "collect_baseline",
        python_cmd("scripts/collect_baseline.py", "--symbols", ",".join(symbols), "--run-date", label, "--json"),
        allow_fail=True,
    )
    summary_path = PROJECT_ROOT / "data" / "_baseline" / label / "run_summary.json"
    summary = read_json(summary_path) if summary_path.exists() else {}
    return result, summary


def compare_baseline(base_label: str, candidate_label: str, symbols: list[str]) -> tuple[CommandResult, dict[str, Any]]:
    result = run_command(
        "compare_baseline",
        python_cmd(
            "scripts/compare_baseline.py",
            "--base",
            base_label,
            "--candidate",
            candidate_label,
            "--symbols",
            ",".join(symbols),
            "--json",
        ),
        allow_fail=True,
    )
    report = json.loads(result.stdout_tail) if result.stdout_tail.startswith("{") else {}
    return result, report


def build_conclusion(
    *,
    symbol_runs: list[SymbolRun],
    data_gate: CommandResult,
    collect_result: CommandResult,
    baseline_summary: dict[str, Any],
    compare_result: CommandResult | None,
    compare_report: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    failed_symbols = [item.symbol for item in symbol_runs if item.status == "failed"]
    if failed_symbols:
        reasons.append(f"refresh_or_rebuild_failed={','.join(failed_symbols)}")

    if not data_gate.ok:
        reasons.append("data_gate_failed")
    if not collect_result.ok:
        reasons.append("baseline_collection_failed")
    if compare_result is not None and not compare_result.ok:
        reasons.append("baseline_compare_failed")

    baseline_failed = [
        item["symbol"]
        for item in baseline_summary.get("results", [])
        if item.get("status") == "failed"
    ]
    baseline_degraded = [
        item["symbol"]
        for item in baseline_summary.get("results", [])
        if item.get("status") == "degraded"
    ]
    if baseline_failed:
        reasons.append(f"baseline_failed={','.join(baseline_failed)}")
    if baseline_degraded:
        reasons.append(f"baseline_degraded={','.join(baseline_degraded)}")

    regressions = compare_report.get("regressions", []) if compare_report else []
    if regressions:
        reasons.append(f"regressions={len(regressions)}")

    if regressions or baseline_failed or not collect_result.ok or (compare_result is not None and not compare_result.ok):
        return "FAIL", reasons
    if failed_symbols or not data_gate.ok or baseline_degraded:
        return "DEGRADED", reasons
    return "PASS", reasons


def write_outputs(
    *,
    candidate_label: str,
    result: dict[str, Any],
) -> None:
    output_dir = PROJECT_ROOT / "data" / "_baseline" / candidate_label
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "baseline_agent_result.json", result)
    (output_dir / "baseline_agent_report.md").write_text(render_markdown(result), encoding="utf-8")


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Baseline Agent Report",
        "",
        f"- candidate: `{result['candidate_label']}`",
        f"- base: `{result.get('base_label') or 'N/A'}`",
        f"- conclusion: `{result['conclusion']}`",
        f"- generated_at: `{result['generated_at']}`",
        "",
        "## Reasons",
        "",
    ]
    if result["reasons"]:
        lines.extend(f"- {reason}" for reason in result["reasons"])
    else:
        lines.append("- no blocking issue")

    lines.extend(["", "## Symbols", ""])
    for item in result["symbols"]:
        warnings = "; ".join(item["warnings"]) if item["warnings"] else "none"
        lines.append(
            f"- `{item['symbol']}`: {item['status']}; "
            f"refreshed={item['refreshed']}; mode={item['refresh_mode']}; warnings={warnings}"
        )

    lines.extend(["", "## Refresh", ""])
    refresh_targets = result.get("refresh_targets", [])
    lines.append(f"- targets: `{','.join(refresh_targets) if refresh_targets else 'none'}`")

    lines.extend(["", "## Pre Data Gate", ""])
    pre_gate = result["pre_data_gate"]
    lines.append(f"- returncode: `{pre_gate['returncode']}`")
    if pre_gate["stdout_tail"]:
        lines.extend(["", "```text", pre_gate["stdout_tail"], "```"])

    lines.extend(["", "## Data Gate", ""])
    data_gate = result["data_gate"]
    lines.append(f"- returncode: `{data_gate['returncode']}`")
    if data_gate["stdout_tail"]:
        lines.extend(["", "```text", data_gate["stdout_tail"], "```"])

    lines.extend(["", "## Baseline Summary", ""])
    for row in result.get("baseline_summary", {}).get("results", []):
        lines.append(f"- `{row['symbol']}`: {row['status']} warnings={len(row.get('warnings', []))}")

    compare_report = result.get("compare_report")
    if compare_report:
        lines.extend(["", "## Regression", ""])
        lines.append(f"- status: `{compare_report.get('status')}`")
        lines.append(f"- regressions: `{len(compare_report.get('regressions', []))}`")
        lines.append(f"- improvements: `{len(compare_report.get('improvements', []))}`")
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_symbol_runs(existing: dict[str, SymbolRun], updates: list[SymbolRun]) -> None:
    for update in updates:
        current = existing.get(update.symbol)
        if current is None:
            existing[update.symbol] = update
            continue
        current.commands.extend(update.commands)
        current.warnings.extend(update.warnings)
        current.refreshed = current.refreshed or update.refreshed
        current.refresh_mode = update.refresh_mode if update.refresh_mode != "none" else current.refresh_mode
        if update.status == "failed":
            current.status = "failed"
        elif current.status != "failed" and update.status == "degraded":
            current.status = "degraded"


def default_candidate_label() -> str:
    return "baseline-agent-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def normalize_phase_label(raw: str) -> str:
    value = raw.strip().lower().replace("_", "-")
    if value.startswith("phase") and "-" not in value:
        return value
    if value.isdigit():
        return f"phase{value}"
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated baseline regression agent")
    parser.add_argument("--symbols", default=None, help="comma-separated symbols")
    parser.add_argument("--phase", default=None, help="migration phase label, e.g. phase1 or 1")
    parser.add_argument("--base-label", default=None, help="existing baseline label to compare against")
    parser.add_argument("--candidate-label", default=None, help="new candidate baseline label")
    parser.add_argument("--count", type=int, default=320, help="incremental K-line count per period")
    parser.add_argument("--full-count", type=int, default=1000, help="fallback full K-line count on drift")
    parser.add_argument("--skip-refresh", action="store_true", help="skip K-line refresh and derived rebuild")
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="refresh every symbol without first checking freshness; default refreshes only stale symbols",
    )
    parser.add_argument("--skip-compare", action="store_true", help="skip baseline comparison even when base-label is set")
    parser.add_argument("--strict", action="store_true", help="return non-zero unless conclusion is PASS")
    args = parser.parse_args()

    symbols = parse_symbols(args.symbols)
    phase_label = normalize_phase_label(args.phase) if args.phase else None
    candidate_label = args.candidate_label or (f"{phase_label}-after" if phase_label else default_candidate_label())

    symbol_run_map = {symbol: SymbolRun(symbol=symbol) for symbol in symbols}
    pre_gate = run_data_gate(symbols)
    refresh_targets = symbols if args.refresh_all else stale_symbols_from_gate(pre_gate, symbols)
    if not refresh_targets and not args.skip_refresh:
        for symbol in symbols:
            symbol_run_map[symbol].warnings.append("data already fresh; refresh skipped")

    refresh_runs = [
        refresh_symbol(symbol, count=args.count, full_count=args.full_count, skip_refresh=args.skip_refresh)
        for symbol in refresh_targets
    ]
    merge_symbol_runs(symbol_run_map, refresh_runs)
    data_gate = run_data_gate(symbols)
    stale_after_refresh = stale_symbols_from_gate(data_gate, symbols)
    if stale_after_refresh and not args.skip_refresh:
        full_refresh_runs = [
            refresh_symbol(
                symbol,
                count=args.count,
                full_count=args.full_count,
                skip_refresh=False,
                force_full=True,
            )
            for symbol in stale_after_refresh
        ]
        merge_symbol_runs(symbol_run_map, full_refresh_runs)
        data_gate = run_data_gate(symbols)

    symbol_runs = list(symbol_run_map.values())
    collect_result, baseline_summary = collect_candidate(symbols, candidate_label)
    compare_result = None
    compare_report = None
    if args.base_label and not args.skip_compare:
        compare_result, compare_report = compare_baseline(args.base_label, candidate_label, symbols)

    conclusion, reasons = build_conclusion(
        symbol_runs=symbol_runs,
        data_gate=data_gate,
        collect_result=collect_result,
        baseline_summary=baseline_summary,
        compare_result=compare_result,
        compare_report=compare_report,
    )

    result = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_label": args.base_label,
        "candidate_label": candidate_label,
        "conclusion": conclusion,
        "reasons": reasons,
        "pre_data_gate": asdict(pre_gate),
        "refresh_targets": refresh_targets,
        "symbols": [asdict(item) for item in symbol_runs],
        "data_gate": asdict(data_gate),
        "collect_baseline": asdict(collect_result),
        "compare_baseline": asdict(compare_result) if compare_result else None,
        "baseline_summary": baseline_summary,
        "compare_report": compare_report,
    }
    write_outputs(candidate_label=candidate_label, result=result)

    print(f"candidate_label={candidate_label}")
    print(f"conclusion={conclusion}")
    print(f"reasons={'; '.join(reasons) if reasons else 'none'}")
    print(f"report=data/_baseline/{candidate_label}/baseline_agent_report.md")
    if args.strict and conclusion != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
