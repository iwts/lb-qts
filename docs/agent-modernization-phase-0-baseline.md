# Phase 0：基线盘点与边界冻结

## 目标

在重构前冻结当前系统行为，避免后续拆分 prompt、skills、rules 时失去可比较基准。

Phase 0 不做架构改造，只做盘点、回归样本、产物标准和质量基线。后续每个 Phase 都必须能回答一个问题：

```text
新方案是否比 Phase 0 更稳定、更可监督，且没有损坏现有核心链路？
```

## 背景问题

当前系统已经有完整三阶段：

```text
数据准备 -> 推理分析 -> 报告同步
```

但后续会拆 worker、拆 skills、引入 profiles 和 typed artifacts。如果没有基线，任何退化都会变得难以归因。

## 盘点范围

### 入口和主流程

```text
agents/main/router.md
agents/main/market_main_agent.md
agents/main/review_main_agent.md
agents/main/youtube_main_agent.md
```

### Worker

```text
agents/workers/data_agent.md
agents/workers/fundamental_master_agent.md
agents/workers/strategy_agent.md
agents/workers/reasoning_agent.md
agents/workers/execution_agent.md
agents/workers/review_agent.md
agents/workers/youtube_insight_agent.md
```

### Policies / Rules

```text
agents/policies/common_rules.md
agents/policies/runtime_contract.md
agents/policies/trading_playbook.md
agents/policies/report_specs.md
agents/learned_rules.md
```

### 核心脚本

```text
scripts/check_data_freshness.py
scripts/parse_mcp_data.py
scripts/fetch_fundamental.py
scripts/calc_indicators.py
scripts/extract_llm_context.py
scripts/verify_data_freshness.py
scripts/pipeline_state.py
scripts/validate_worker_result.py
scripts/record_prediction.py
```

## 回归标的池

选择 3-5 个代表标的作为后续所有 Phase 的对照组：

| 类型 | 候选标的 | 目的 |
| --- | --- | --- |
| 高成长科技 | `NVDA.US` / `TSLA.US` | 验证成长、估值、财报预期和波动率处理 |
| 港股互联网 | `0700.HK` | 验证港股流动性、估值折价、政策风险 |
| 红利/防御 | `600900.SH` / `511090.SH` | 验证防御型 profile 和分红现金流逻辑 |
| 金融/银行 | `600036.SH` / `1288.HK` | 验证银行、净息差、资产质量、估值约束 |
| 消费/医药 | `KO.US` / `LLY.US` | 验证质量成长、估值溢价和稳健型结论 |

建议首批最小回归集：

```text
NVDA.US
0700.HK
600900.SH
```

## 基线执行流程

每个标的按现有主流程完整跑通：

```text
market_main_agent
  -> data_agent
  -> fundamental_master_agent
  -> calc_indicators
  -> extract_llm_context
  -> strategy_agent
  -> reasoning_agent
  -> execution_agent
```

必须记录：

- 数据新鲜度；
- 每阶段状态；
- `failed/degraded` 原因；
- 输出文件路径；
- worker JSON metrics；
- 报告长度；
- 运行耗时。

## 建议新增产物

```text
docs/agent-system-baseline.md
data/_baseline/<date>/run_summary.json
data/_baseline/<date>/<symbol>_baseline_metrics.json
```

当前实现入口：

```bash
.venv/bin/python scripts/collect_baseline.py --symbols NVDA.US,0700.HK,600900.SH --run-date <yyyy-mm-dd>
```

推荐自动化入口（独立 test agent，不进入正式投研流水线）：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --symbols NVDA.US,0700.HK,600900.SH \
  --base-label <base-label> \
  --candidate-label <candidate-label>
```

严格验收模式：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --base-label <base-label> \
  --candidate-label <candidate-label> \
  --strict
```

`run_summary.json` 示例：

```json
{
  "run_date": "2026-05-01",
  "symbols": ["NVDA.US", "0700.HK", "600900.SH"],
  "results": [
    {
      "symbol": "NVDA.US",
      "status": "ok",
      "fundamental_report": "deduction/NVDA.US/fundamental_analysis_*.md",
      "deduction_report": "deduction/NVDA.US/deduction_*.md",
      "final_report": "report/NVDA.US/report_*.md",
      "warnings": []
    }
  ]
}
```

## 验收标准

- 至少 3 个代表标的完整跑通；
- 每个标的具备 `fundamental_analysis`、`deduction`、`report` 三类关键产物；
- 每个阶段有结构化状态记录；
- 已知失败点被记录，而不是口头忽略；
- 明确后续重构不可破坏的最小质量标准。

## 不做事项

Phase 0 不做：

- 不拆 prompt；
- 不新增 profiles；
- 不改主流程；
- 不引入 DAG 框架；
- 不改 learned rules；
- 不优化报告模板。

## 交接给下一阶段

Phase 0 结束后，Phase 1 agent 应读取：

```text
docs/agent-system-modernization-design.md
docs/agent-modernization-phase-0-baseline.md
docs/agent-system-baseline.md
data/_baseline/<date>/run_summary.json
```

然后开始瘦身 worker prompt。
