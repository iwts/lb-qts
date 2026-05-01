import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline_state import create_run_manifest, load_manifest, update_phase
from validate_worker_result import validate_worker_result
from record_prediction import append_prediction, prediction_from_execution_summary
from collect_baseline import collect_baseline
from compare_baseline import compare_baselines


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
            "summary": "test",
            "metrics": {
                "direction": "long",
                "trade_plans_count": 1,
                "best_rr": 1.2,
                "numeric_evidence_count": 6,
                "rules_applied_count": 1,
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
            report.parent.mkdir(parents=True)
            report.write_text("# Report\n\n若 站上 190，则 买入；止损 180。\n", encoding="utf-8")
            result = {
                "symbol": "AAPL.US",
                "status": "ok",
                "phase": "execution",
                "output_files": ["report/AAPL.US/report.md"],
                "summary": "test",
                "metrics": {
                    "direction": "long",
                    "best_rr": 1.8,
                    "plans_passed_risk_check": 2,
                    "plans_total": 2,
                    "rules_applied_count": 1,
                    "feishu_report": "ok",
                    "feishu_deduction": "ok",
                    "feishu_fundamental": "ok",
                },
                "warnings": [],
            }
            self.assertEqual(validate_worker_result(result, project_root=root, check_files=True), [])


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

            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["artifacts"]["deduction_report"]["line_count"], 1)
            self.assertIn(metrics["status"], {"ok", "degraded"})

    def test_collect_baseline_marks_missing_key_artifact_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = collect_baseline(symbols=["MISSING.US"], run_date="2026-05-01", project_root=root)

            self.assertEqual(summary["results"][0]["status"], "failed")
            self.assertIn("missing key artifact: final_report", summary["results"][0]["warnings"])


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
