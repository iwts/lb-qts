import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline_state import create_run_manifest, load_manifest, update_phase
from validate_worker_result import validate_worker_result
from validate_profiles import validate_profiles
from validate_phase3_profile_effect import validate_phase3_profile_effect
from resolve_profile import resolve_profile
from record_prediction import append_prediction, prediction_from_execution_summary
from collect_baseline import collect_baseline
from compare_baseline import compare_baselines


def write_profile(path: Path, *, overlay: bool = False) -> None:
    overlay_note = "作为 overlay profile 只补充关注点。\n\n" if overlay else ""
    path.write_text(
        "# Test Profile\n\n"
        "## Mandate\n\n"
        f"{overlay_note}测试 mandate。\n\n"
        "## Evidence Priority\n\n"
        "1. 测试证据。\n\n"
        "## Weight Bias\n\n"
        "成长权重上调。\n\n"
        "## Hard Concerns\n\n"
        "- 测试风险。\n\n"
        "## Preferred Setups\n\n"
        "- 测试机会。\n\n"
        "## Common Mistakes\n\n"
        "- 测试误判。\n",
        encoding="utf-8",
    )


def write_symbol_profile(
    root: Path,
    symbol: str,
    style_profile: str,
    *,
    optional_profiles: list[str] | None = None,
) -> None:
    symbol_dir = root / "data" / symbol
    symbol_dir.mkdir(parents=True)
    payload = {
        "symbol": symbol,
        "market": symbol.rsplit(".", 1)[-1],
        "asset_type": "equity",
        "sector": "test",
        "style_profile": style_profile,
        "optional_profiles": optional_profiles or [],
        "profile_source": "manual",
        "profile_confidence": 0.9,
    }
    (symbol_dir / "symbol_profile.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def profile_aware_reasoning_result(symbol: str, profile_used: str, weight_bias: dict[str, str]) -> dict:
    return {
        "symbol": symbol,
        "status": "ok",
        "phase": "reasoning",
        "output_files": [],
        "skills_used": ["agents/skills/long_short_thesis.md"],
        "skills_skipped": [],
        "profile_used": profile_used,
        "optional_profiles": [],
        "profile_source": "manual",
        "profile_file_paths": [f"agents/profiles/{profile_used}.md"],
        "profile_effect": {
            "weight_bias_applied": weight_bias,
            "hard_concerns_triggered": [],
            "preferred_setups_considered": ["profile_specific_setup"],
            "profile_not_applicable_risk": "low",
        },
        "summary": "test",
        "metrics": {
            "direction": "neutral",
            "trade_plans_count": 0,
            "best_rr": 0,
            "numeric_evidence_count": 6,
            "rules_applied_count": 1,
            "rules_applied_ids": ["4.1"],
        },
        "warnings": [],
    }


def write_profile_effect_fixture(
    root: Path,
    *,
    run_id: str,
    symbol: str,
    profile_used: str,
    weight_bias: dict[str, str],
) -> Path:
    profile_dir = root / "agents" / "profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    write_profile(profile_dir / f"{profile_used}.md")

    artifact = root / "deduction" / symbol / "deduction.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        "# Deduction\n\n"
        "## Profile 应用\n\n"
        f"- profile_used: {profile_used}\n"
        "- profile 权重影响：已根据 mandate 调整证据权重。\n"
        "- profile hard concerns: 未触发。\n",
        encoding="utf-8",
    )

    result = profile_aware_reasoning_result(symbol, profile_used, weight_bias)
    result["output_files"] = [f"deduction/{symbol}/deduction.md"]

    symbol_dir = root / "data" / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    resolution = {
        "symbol": symbol,
        "status": "ok",
        "profile_used": profile_used,
        "optional_profiles": [],
        "profile_file_paths": [f"agents/profiles/{profile_used}.md"],
        "profile_source": "manual",
        "profile_confidence": 0.9,
        "profile_warnings": [],
    }
    (symbol_dir / "profile_resolution.json").write_text(
        json.dumps(resolution, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result_path = root / "data" / "_runs" / run_id / "worker_results" / f"{symbol}_reasoning.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path


class PipelineStateTests(unittest.TestCase):
    def test_create_and_update_manifest_records_symbols_phases_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = create_run_manifest(
                symbols=["AAPL.US", "0700.HK"],
                run_id="2026-04-30_2300",
                base_dir=root,
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.run_id, "2026-04-30_2300")
            self.assertEqual(manifest.symbols, ["AAPL.US", "0700.HK"])
            self.assertEqual(manifest.symbol_status["AAPL.US"]["data"], "pending")

            update_phase(
                manifest_path,
                symbol="AAPL.US",
                phase="data",
                status="ok",
                output_files=["data/AAPL.US/llm_context.md"],
                metrics={"freshness": {"1d": "OK"}},
                warnings=[],
            )

            updated = load_manifest(manifest_path)
            self.assertEqual(updated.symbol_status["AAPL.US"]["data"], "ok")
            self.assertEqual(
                updated.artifacts["AAPL.US"]["data"],
                ["data/AAPL.US/llm_context.md"],
            )
            self.assertEqual(updated.metrics["AAPL.US"]["data"]["freshness"]["1d"], "OK")

    def test_manifest_rejects_unknown_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = create_run_manifest(["AAPL.US"], run_id="r1", base_dir=Path(tmp))
            with self.assertRaises(ValueError):
                update_phase(manifest_path, symbol="AAPL.US", phase="unknown", status="ok")


class WorkerResultValidationTests(unittest.TestCase):
    def test_reasoning_result_requires_trade_plans_or_neutral(self):
        result = {
            "symbol": "AAPL.US",
            "status": "ok",
            "phase": "reasoning",
            "output_files": [],
            "skills_used": ["agents/skills/long_short_thesis.md"],
            "skills_skipped": [],
            "profile_used": "tech_growth_pm",
            "optional_profiles": [],
            "profile_source": "manual",
            "profile_file_paths": ["agents/profiles/tech_growth_pm.md"],
            "profile_effect": {
                "weight_bias_applied": {"growth": "up"},
                "hard_concerns_triggered": [],
                "preferred_setups_considered": ["high_base_breakout"],
                "profile_not_applicable_risk": "low",
            },
            "summary": "test",
            "metrics": {
                "direction": "long",
                "trade_plans_count": 1,
                "best_rr": 1.2,
                "numeric_evidence_count": 6,
                "rules_applied_count": 1,
                "rules_applied_ids": ["4.1"],
            },
            "warnings": [],
        }
        errors = validate_worker_result(result, project_root=Path.cwd(), check_files=False)
        self.assertIn("reasoning.trade_plans_count must be >= 2 for non-neutral direction", errors)
        self.assertIn("reasoning.best_rr must be >= 1.5 for non-neutral direction", errors)

    def test_execution_result_requires_if_then_report_file_when_check_files_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report" / "AAPL.US" / "report.md"
            profile = root / "agents" / "profiles" / "tech_growth_pm.md"
            report.parent.mkdir(parents=True)
            profile.parent.mkdir(parents=True)
            report.write_text(
                "# Report\n\n"
                "若 站上 190，则 买入；止损 180。\n\n"
                "## Profile 执行复核\n\n"
                "- profile_used: tech_growth_pm\n"
                "- profile 权重影响：成长权重上调。\n"
                "- profile hard concerns: 未触发。\n",
                encoding="utf-8",
            )
            profile.write_text("# Tech Growth PM\n", encoding="utf-8")
            result = {
                "symbol": "AAPL.US",
                "status": "ok",
                "phase": "execution",
                "output_files": ["report/AAPL.US/report.md"],
                "skills_used": ["agents/skills/execution_risk_check.md"],
                "skills_skipped": [],
                "profile_used": "tech_growth_pm",
                "optional_profiles": [],
                "profile_source": "manual",
                "profile_file_paths": ["agents/profiles/tech_growth_pm.md"],
                "profile_effect": {
                    "weight_bias_applied": {"growth": "up"},
                    "hard_concerns_triggered": [],
                    "preferred_setups_considered": ["high_base_breakout"],
                    "profile_not_applicable_risk": "low",
                },
                "summary": "test",
                "metrics": {
                    "direction": "long",
                    "best_rr": 1.8,
                    "plans_passed_risk_check": 2,
                    "plans_total": 2,
                    "rules_applied_count": 1,
                    "rules_applied_ids": ["4.1"],
                },
                "warnings": [],
            }
            self.assertEqual(validate_worker_result(result, project_root=root, check_files=True), [])

    def test_phase1_core_worker_result_requires_skill_and_rule_fields(self):
        result = {
            "symbol": "AAPL.US",
            "status": "ok",
            "phase": "strategy",
            "output_files": [],
            "summary": "test",
            "metrics": {},
            "warnings": [],
        }
        errors = validate_worker_result(result, project_root=Path.cwd(), check_files=False)
        self.assertIn("skills_used must be a list", errors)
        self.assertIn("skills_skipped must be a list", errors)
        self.assertIn("profile_used must be a non-empty string", errors)
        self.assertIn("strategy.rules_applied_count is required", errors)
        self.assertIn("strategy.rules_applied_ids is required", errors)


class ProfilePhase3Tests(unittest.TestCase):
    def test_repository_phase3_assets_are_present_and_valid(self):
        self.assertEqual(validate_profiles(project_root=PROJECT_ROOT), [])
        expected = {
            "NVDA.US": ("tech_growth_pm", ["options_flow_trader"]),
            "0700.HK": ("hk_liquidity_pm", []),
            "600900.SH": ("dividend_defensive_pm", []),
        }
        for symbol, (profile_used, optional_profiles) in expected.items():
            resolution = resolve_profile(symbol, project_root=PROJECT_ROOT)
            self.assertEqual(resolution["status"], "ok")
            self.assertEqual(resolution["profile_used"], profile_used)
            self.assertEqual(resolution["optional_profiles"], optional_profiles)
            self.assertTrue(resolution["profile_file_paths"])

    def test_validate_profiles_accepts_standard_phase3_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_dir = root / "agents" / "profiles"
            profile_dir.mkdir(parents=True)
            for name in ("tech_growth_pm", "dividend_defensive_pm", "hk_liquidity_pm", "options_flow_trader"):
                write_profile(profile_dir / f"{name}.md", overlay=name == "options_flow_trader")

            write_symbol_profile(
                root,
                "NVDA.US",
                "tech_growth_pm",
                optional_profiles=["options_flow_trader"],
            )
            write_symbol_profile(root, "0700.HK", "hk_liquidity_pm")
            write_symbol_profile(root, "600900.SH", "dividend_defensive_pm")

            self.assertEqual(validate_profiles(project_root=root), [])

    def test_resolve_profile_uses_manual_mapping_and_writes_profile_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_dir = root / "agents" / "profiles"
            profile_dir.mkdir(parents=True)
            write_profile(profile_dir / "tech_growth_pm.md")
            write_profile(profile_dir / "options_flow_trader.md", overlay=True)
            write_symbol_profile(
                root,
                "NVDA.US",
                "tech_growth_pm",
                optional_profiles=["options_flow_trader"],
            )

            resolution = resolve_profile("NVDA.US", project_root=root)

            self.assertEqual(resolution["status"], "ok")
            self.assertEqual(resolution["profile_used"], "tech_growth_pm")
            self.assertEqual(resolution["profile_source"], "manual")
            self.assertEqual(
                resolution["profile_file_paths"],
                ["agents/profiles/tech_growth_pm.md", "agents/profiles/options_flow_trader.md"],
            )

    def test_resolve_profile_cli_write_creates_resolution_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_dir = root / "agents" / "profiles"
            profile_dir.mkdir(parents=True)
            write_profile(profile_dir / "tech_growth_pm.md")
            write_symbol_profile(root, "NVDA.US", "tech_growth_pm")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "resolve_profile.py"),
                    "--symbol",
                    "NVDA.US",
                    "--project-root",
                    str(root),
                    "--write",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            output = json.loads(completed.stdout)
            output_path = root / "data" / "NVDA.US" / "profile_resolution.json"
            self.assertEqual(output["output_file"], "data/NVDA.US/profile_resolution.json")
            self.assertTrue(output_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["profile_used"], "tech_growth_pm")

    def test_resolve_profile_cli_allows_degraded_default_without_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agents" / "profiles").mkdir(parents=True)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "resolve_profile.py"),
                    "--symbol",
                    "UNKNOWN.US",
                    "--project-root",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            strict_completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "resolve_profile.py"),
                    "--symbol",
                    "UNKNOWN.US",
                    "--project-root",
                    str(root),
                    "--strict",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["status"], "degraded")
            self.assertEqual(strict_completed.returncode, 2)

    def test_resolve_profile_degrades_to_rule_when_symbol_profile_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_dir = root / "agents" / "profiles"
            profile_dir.mkdir(parents=True)
            write_profile(profile_dir / "hk_liquidity_pm.md")

            resolution = resolve_profile("0700.HK", project_root=root)

            self.assertEqual(resolution["status"], "ok")
            self.assertEqual(resolution["profile_used"], "hk_liquidity_pm")
            self.assertEqual(resolution["profile_source"], "rule")
            self.assertTrue(resolution["profile_warnings"])

    def test_reasoning_worker_contract_allows_profile_specific_weight_bias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_dir = root / "agents" / "profiles"
            profile_dir.mkdir(parents=True)
            write_profile(profile_dir / "tech_growth_pm.md")
            write_profile(profile_dir / "dividend_defensive_pm.md")

            tech_result = profile_aware_reasoning_result(
                "NVDA.US",
                "tech_growth_pm",
                {"growth": "up", "valuation_absolute_cheapness": "down"},
            )
            dividend_result = profile_aware_reasoning_result(
                "600900.SH",
                "dividend_defensive_pm",
                {"cash_flow_quality": "up", "short_term_momentum": "down"},
            )

            self.assertEqual(validate_worker_result(tech_result, project_root=root, check_files=True), [])
            self.assertEqual(validate_worker_result(dividend_result, project_root=root, check_files=True), [])
            self.assertNotEqual(
                tech_result["profile_effect"]["weight_bias_applied"],
                dividend_result["profile_effect"]["weight_bias_applied"],
            )

    def test_phase3_profile_effect_validation_accepts_distinct_real_worker_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_profile_effect_fixture(
                root,
                run_id="phase3-proof",
                symbol="NVDA.US",
                profile_used="tech_growth_pm",
                weight_bias={"growth": "up", "valuation_absolute_cheapness": "down"},
            )
            write_profile_effect_fixture(
                root,
                run_id="phase3-proof",
                symbol="600900.SH",
                profile_used="dividend_defensive_pm",
                weight_bias={"cash_flow_quality": "up", "short_term_momentum": "down"},
            )

            report = validate_phase3_profile_effect(
                project_root=root,
                symbols=["NVDA.US", "600900.SH"],
                phase="reasoning",
                run_id="phase3-proof",
            )

            self.assertEqual(report["status"], "PASS", report["errors"])
            self.assertEqual(report["profiles"], ["dividend_defensive_pm", "tech_growth_pm"])
            self.assertEqual(report["distinct_weight_bias_count"], 2)

    def test_phase3_profile_effect_validation_rejects_same_weight_bias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            same_bias = {"growth": "up"}
            write_profile_effect_fixture(
                root,
                run_id="phase3-proof",
                symbol="NVDA.US",
                profile_used="tech_growth_pm",
                weight_bias=same_bias,
            )
            write_profile_effect_fixture(
                root,
                run_id="phase3-proof",
                symbol="600900.SH",
                profile_used="dividend_defensive_pm",
                weight_bias=same_bias,
            )

            report = validate_phase3_profile_effect(
                project_root=root,
                symbols=["NVDA.US", "600900.SH"],
                phase="reasoning",
                run_id="phase3-proof",
            )

            self.assertEqual(report["status"], "FAIL")
            self.assertIn("need at least 2 distinct weight_bias_applied payloads, got 1", report["errors"])


class PredictionRecordTests(unittest.TestCase):
    def test_append_prediction_creates_stable_csv_header_and_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "predictions.csv"
            prediction = {
                "symbol": "AAPL.US",
                "report_date": "2026-04-30",
                "direction": "long",
                "rating": "推荐做多",
                "regime": "强势趋势市",
                "entry_type": "pullback",
                "entry": "190.5",
                "stop": "184.2",
                "target_1": "201.0",
                "target_2": "214.0",
                "rr": "1.67",
                "rules_applied": "4.1;4.2",
                "report_file": "report/AAPL.US/report.md",
                "deduction_file": "deduction/AAPL.US/deduction.md",
            }
            append_prediction(csv_path, prediction)

            with csv_path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["symbol"], "AAPL.US")
            self.assertEqual(rows[0]["rr"], "1.67")

    def test_prediction_from_execution_summary_extracts_primary_plan(self):
        summary = {
            "symbol": "AAPL.US",
            "phase": "execution",
            "metrics": {
                "direction": "long",
                "rating": "推荐做多",
                "regime": "强势趋势市",
                "rules_applied_ids": ["4.1", "4.2"],
            },
            "plans": [
                {
                    "name": "主计划",
                    "direction": "long",
                    "entry_type": "pullback",
                    "entry": 190.5,
                    "stop": 184.2,
                    "target_1": 201.0,
                    "target_2": 214.0,
                    "rr": 1.67,
                }
            ],
            "output_files": ["report/AAPL.US/report.md"],
            "source_files": {"deduction": "deduction/AAPL.US/deduction.md"},
        }
        prediction = prediction_from_execution_summary(summary, report_date="2026-04-30")
        self.assertEqual(prediction["symbol"], "AAPL.US")
        self.assertEqual(prediction["entry"], "190.5")
        self.assertEqual(prediction["rules_applied"], "4.1;4.2")


class BaselineCollectionTests(unittest.TestCase):
    def test_collect_baseline_writes_summary_and_symbol_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symbol = "AAPL.US"
            data_dir = root / "data" / symbol
            deduction_dir = root / "deduction" / symbol
            report_dir = root / "report" / symbol
            data_dir.mkdir(parents=True)
            deduction_dir.mkdir(parents=True)
            report_dir.mkdir(parents=True)

            for name in ("1h_k.csv", "1d_k.csv", "1w_k.csv"):
                (data_dir / name).write_text(
                    "timestamp,open,high,low,close,volume\n"
                    "2026-05-01T01:00:00Z,1,2,1,2,100\n",
                    encoding="utf-8",
                )
            for name in ("fundamental.json", "earnings.json", "signals_summary.json", "factor_scores.json"):
                (data_dir / name).write_text("{}", encoding="utf-8")
            (data_dir / "llm_context.md").write_text("# Context\n", encoding="utf-8")
            (deduction_dir / "fundamental_analysis_2026_05_01.md").write_text("# Fundamental\n", encoding="utf-8")
            (deduction_dir / "deduction_2026_05_01_01.md").write_text("# Deduction\n", encoding="utf-8")
            (report_dir / "report_2026_05_01_01.md").write_text("# Report\n", encoding="utf-8")

            summary = collect_baseline(symbols=[symbol], run_date="2026-05-01", project_root=root)

            summary_path = root / "data" / "_baseline" / "2026-05-01" / "run_summary.json"
            metrics_path = root / "data" / "_baseline" / "2026-05-01" / f"{symbol}_baseline_metrics.json"
            self.assertTrue(summary_path.exists())
            self.assertTrue(metrics_path.exists())
            self.assertEqual(summary["results"][0]["symbol"], symbol)
            self.assertEqual(summary["results"][0]["final_report"], "report/AAPL.US/report_2026_05_01_01.md")
            self.assertEqual(summary["results"][0]["stage_status"]["reasoning"], "ok")
            self.assertIn("duration_seconds", summary)

            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["artifacts"]["deduction_report"]["line_count"], 1)
            self.assertEqual(metrics["inferred_stage_status"]["execution"], "ok")
            self.assertEqual(metrics["report_length"]["line_count"], 1)
            self.assertEqual(metrics["data_freshness"]["periods"]["1h"]["latest"], "2026-05-01")
            self.assertNotEqual(metrics["data_freshness"]["periods"]["1h"]["status"], "MISSING")
            self.assertIn(metrics["status"], {"ok", "degraded"})

    def test_collect_baseline_marks_missing_key_artifact_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = collect_baseline(symbols=["MISSING.US"], run_date="2026-05-01", project_root=root)

            self.assertEqual(summary["results"][0]["status"], "failed")
            self.assertIn("missing key artifact: final_report", summary["results"][0]["warnings"])

    def test_collect_baseline_ignores_noncritical_freshness_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symbol = "AAPL.US"
            data_dir = root / "data" / symbol
            deduction_dir = root / "deduction" / symbol
            report_dir = root / "report" / symbol
            data_dir.mkdir(parents=True)
            deduction_dir.mkdir(parents=True)
            report_dir.mkdir(parents=True)

            for name in ("1h_k.csv", "1d_k.csv", "1w_k.csv"):
                (data_dir / name).write_text(
                    "timestamp,open,high,low,close,volume\n"
                    "2026-05-01T01:00:00Z,1,2,1,2,100\n",
                    encoding="utf-8",
                )
            for name in ("fundamental.json", "earnings.json", "signals_summary.json", "factor_scores.json"):
                (data_dir / name).write_text("{}", encoding="utf-8")
            (data_dir / "llm_context.md").write_text("# Context\n", encoding="utf-8")
            (deduction_dir / "fundamental_analysis_2026_05_01.md").write_text("# Fundamental\n", encoding="utf-8")
            (deduction_dir / "deduction_2026_05_01_01.md").write_text("# Deduction\n", encoding="utf-8")
            (report_dir / "report_2026_05_01_01.md").write_text("# Report\n", encoding="utf-8")

            freshness = {
                "symbol": symbol,
                "pass": False,
                "critical_pass": True,
                "periods": {
                    "1h": {"status": "OK", "latest": "2026-05-01", "hours_ago": 1, "critical": True},
                    "1d": {"status": "OK", "latest": "2026-05-01", "hours_ago": 1, "critical": True},
                    "1w": {"status": "STALE", "latest": "2026-04-26", "hours_ago": 210, "critical": False},
                },
            }
            with patch("collect_baseline.check_symbol", return_value=freshness):
                summary = collect_baseline(symbols=[symbol], run_date="2026-05-01", project_root=root)

            self.assertEqual(summary["results"][0]["status"], "ok")
            self.assertEqual(summary["results"][0]["warnings"], [])


class BaselineComparisonTests(unittest.TestCase):
    def test_compare_baselines_detects_status_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline_summary(root, "before", [{"symbol": "AAPL.US", "status": "ok"}])
            write_baseline_summary(root, "after", [{"symbol": "AAPL.US", "status": "failed"}])

            report = compare_baselines(base_label="before", candidate_label="after", project_root=root)

            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["regressions"][0]["type"], "status_worse")

    def test_compare_baselines_tracks_improvement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline_summary(root, "before", [{"symbol": "AAPL.US", "status": "degraded"}])
            write_baseline_summary(root, "after", [{"symbol": "AAPL.US", "status": "ok"}])

            report = compare_baselines(base_label="before", candidate_label="after", project_root=root)

            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["improvements"][0]["type"], "status_better")


def write_baseline_summary(root: Path, label: str, results: list[dict]):
    baseline_dir = root / "data" / "_baseline" / label
    baseline_dir.mkdir(parents=True)
    normalized = []
    for result in results:
        normalized.append(
            {
                "symbol": result["symbol"],
                "status": result["status"],
                "fundamental_report": result.get("fundamental_report", "deduction/AAPL.US/fundamental.md"),
                "deduction_report": result.get("deduction_report", "deduction/AAPL.US/deduction.md"),
                "final_report": result.get("final_report", "report/AAPL.US/report.md"),
                "warnings": result.get("warnings", []),
            }
        )
    (baseline_dir / "run_summary.json").write_text(
        json.dumps({"run_date": label, "symbols": [r["symbol"] for r in normalized], "results": normalized}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
