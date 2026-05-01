# Agent Modernization Migration Workflow

生成时间：2026-05-01 CST

## 目标

本文件定义 `lb-qts` 多 Agent 现代化改造的固定迁移流程。所有 Phase 结束前都必须跑独立 baseline agent，形成基准测试报告；没有报告，不进入下一阶段。

baseline agent 独立放在：

```text
test/baseline_agent/
```

它不属于正式投研流水线，不参与交易观点生成，只负责：

```text
刷新 K 线 -> 重算衍生产物 -> 采样 baseline -> 回归比较 -> 输出阶段结论
```

## 标准回归标的

默认使用：

```text
NVDA.US
0700.HK
600900.SH
600036.SH
```

除非某阶段明确只影响单一市场，否则不要缩小标的池。新增市场/品类能力时，可以追加标的，但不能删除默认标的。

## 基线标签约定

推荐标签：

| 场景 | 标签 |
| --- | --- |
| Phase 0 固定基线 | `phase0-before` |
| Phase 1 完成后 | `phase1-after` |
| Phase 2 完成后 | `phase2-after` |
| Phase 3 完成后 | `phase3-after` |
| Phase 4 完成后 | `phase4-after` |
| Phase 5 完成后 | `phase5-after` |
| Phase 6 完成后 | `phase6-after` |
| Phase 7 完成后 | `phase7-after` |

如果同一阶段多次迭代，用后缀区分：

```text
phase2-after-r1
phase2-after-r2
```

## Phase 0：建立基线

首次迁移前先建立稳定基线：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --candidate-label phase0-before \
  --skip-compare \
  --strict
```

如果输出 `DEGRADED` 或 `FAIL`：

1. 先看 `data/_baseline/phase0-before/baseline_agent_report.md`；
2. 若是 K 线过期，去掉 `--skip-compare` 也不要加 `--skip-refresh`，让 agent 自动刷新；
3. 若是关键报告缺失，先跑现有完整分析流程补齐该标的；
4. 重新采集 `phase0-before`。

## 每个 Phase 的统一出口门禁

完成任一 Phase 后执行：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --phase <phase-number> \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label <base-label> \
  --strict
```

示例：Phase 1 结束后，对比 Phase 0 基线：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --phase 1 \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase0-before \
  --strict
```

这会自动生成：

```text
data/_baseline/phase1-after/baseline_agent_report.md
data/_baseline/phase1-after/baseline_agent_result.json
```

Phase 2 结束后通常对比 Phase 1 稳定结果：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --phase 2 \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase1-after \
  --strict
```

如果需要始终对比 Phase 0 原始基线，也可以固定：

```bash
--base-label phase0-before
```

## baseline agent 自动做什么

每次运行会执行：

1. 使用 `verify_data_freshness.py` 检查本地数据；
2. 对过期标的自动调用 Longbridge CLI 拉取 `1h` / `1d` / `1w` K 线；
3. 调用 `parse_mcp_data.py` 增量合并；
4. 若检测到前复权/结构漂移，自动用 `--full-count` 重拉；
5. 调用 `calc_indicators.py` 重算指标；
6. 调用 `extract_llm_context.py` 重建 LLM context；
7. 再次执行数据门禁；
8. 调用 `collect_baseline.py` 采样 candidate baseline；
9. 调用 `compare_baseline.py` 对比 base baseline；
10. 输出 Markdown 和 JSON 结论。

## 结论处理

| 结论 | 是否允许进入下一 Phase | 处理 |
| --- | --- | --- |
| `PASS` | 允许 | 在阶段交接记录报告路径 |
| `DEGRADED` | 默认不允许 | 需要人工确认是否为已知非阻塞问题 |
| `FAIL` | 不允许 | 必须修复后重跑 |

阶段交接必须记录：

```text
baseline_label: phaseN-after
baseline_report: data/_baseline/phaseN-after/baseline_agent_report.md
baseline_result: data/_baseline/phaseN-after/baseline_agent_result.json
conclusion: PASS|DEGRADED|FAIL
```

## 常用命令

强制刷新全部标的：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --phase 3 \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase2-after \
  --refresh-all \
  --strict
```

只采样和比较，不刷新数据：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --phase 3 \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase2-after \
  --skip-refresh
```

为一次重试指定自定义 candidate label：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase2-after \
  --candidate-label phase3-after-r2 \
  --strict
```

## 最低要求

每个 Phase 合并或交接前至少满足：

```bash
.venv/bin/python -m unittest scripts/tests/test_pipeline_foundation.py
.venv/bin/python test/baseline_agent/run.py --phase <N> --base-label <base-label> --strict
```

`baseline_agent_report.md` 是阶段验收附件。缺失该附件视为迁移未完成。
