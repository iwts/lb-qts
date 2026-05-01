# LB-QTS 量化分析 Agent 系统

LB-QTS 是一个基于 Longbridge 数据、Yahoo Finance 基本面、飞书同步和多 Agent 编排的投研分析系统。当前现代化改造目标是把系统从“重 prompt + 三阶段流水线”逐步升级为：

```text
轻 Agent + 可组合 Skills + Profiles/Mandates + Typed Artifacts + Validator + 独立 Review
```

现代化设计索引见：

```text
docs/agent-system-modernization-design.md
docs/agent-modernization-migration-workflow.md
```

## 当前阶段

当前应优先执行 Phase 0：基线盘点与边界冻结。

Phase 0 不做架构改造，不拆 worker prompt，不新增 profiles，不改主流程。它只回答一个问题：

```text
后续改造有没有破坏现在已经能跑通的核心投研链路？
```

Phase 0 的详细设计见：

```text
docs/agent-modernization-phase-0-baseline.md
docs/agent-system-baseline.md
```

## Baseline 是什么

baseline 是当前系统行为的结构化快照。它不会重新跑完整分析，也不会调用 Longbridge、Yahoo Finance 或飞书同步；它只读取本地已有产物并生成对照数据。

每个标的会检查：

- `deduction/<symbol>/fundamental_analysis_*.md`
- `deduction/<symbol>/deduction_*.md`
- `report/<symbol>/report_*.md`
- `data/<symbol>/1h_k.csv`
- `data/<symbol>/1d_k.csv`
- `data/<symbol>/1w_k.csv`
- `data/<symbol>/fundamental.json`
- `data/<symbol>/earnings.json`
- `data/<symbol>/signals_summary.json`
- `data/<symbol>/llm_context.md`
- `data/_runs/*/run_manifest.json` 中已有阶段状态
- `data/_runs/*/worker_results/*.json` 中已有 worker metrics

默认回归标的：

```text
NVDA.US
0700.HK
600900.SH
600036.SH
```

## Baseline 状态

| 状态 | 含义 | 处理方式 |
| --- | --- | --- |
| `ok` | 关键报告存在，关键 K 线新鲜度通过 | 可作为干净基线 |
| `degraded` | 关键报告存在，但数据过期或辅助产物缺失 | 可作为历史行为基线，但验收前建议刷新数据 |
| `failed` | fundamental / deduction / report 任一关键报告缺失 | 不能作为完整链路基线，需先补跑对应标的 |

注意：`degraded` 不等于失败。比如报告都存在，但 `1h/1d` K 线相对今天过期，就会标记为 `degraded`。这对 Phase 0 是有价值的，因为它把“已有缺口”记录下来，避免后续误判为重构引入的问题。

## 基线采集

采集默认回归集：

```bash
.venv/bin/python scripts/collect_baseline.py
```

采集指定标的：

```bash
.venv/bin/python scripts/collect_baseline.py --symbols NVDA.US,0700.HK,600900.SH,600036.SH
```

给基线指定标签。建议在重构前后使用明确标签，而不是只用日期：

```bash
.venv/bin/python scripts/collect_baseline.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --run-date phase0-before
```

严格模式。任一标的不是 `ok` 时返回非零退出码，适合验收或 CI：

```bash
.venv/bin/python scripts/collect_baseline.py --strict
```

输出位置：

```text
data/_baseline/<label>/run_summary.json
data/_baseline/<label>/<symbol>_baseline_metrics.json
```

`run_summary.json` 是总览，适合快速看状态。`<symbol>_baseline_metrics.json` 是单标的细节，适合排查 degraded / failed 原因。

## 一键自动化流程

日常改造优先使用独立 baseline agent：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase0-before \
  --candidate-label phase1-after
```

它会自动执行：

1. 先执行数据新鲜度门禁，定位本地过期标的；
2. 自动拉取过期标的最新 `1h` / `1d` / `1w` K 线；
3. 增量合并到 `data/<symbol>/*_k.csv`；
4. 重算技术指标；
5. 重新生成 `llm_context.md`；
6. 再次执行数据新鲜度门禁；
7. 如果仍过期，自动用 full-count 对失败标的重拉一轮；
8. 采集 candidate baseline；
9. 与 base baseline 做回归比较；
10. 输出结论。

输出文件：

```text
data/_baseline/<candidate-label>/baseline_agent_report.md
data/_baseline/<candidate-label>/baseline_agent_result.json
```

结论含义：

| 结论 | 含义 |
| --- | --- |
| `PASS` | 无回归，且 candidate baseline 无 failed |
| `DEGRADED` | 无回归，但存在数据门禁失败、采样 degraded 或刷新失败 |
| `FAIL` | 出现 baseline 回归或 candidate baseline failed |

严格模式适合验收：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase0-before \
  --candidate-label phase1-after \
  --strict
```

如果只想采样和比较，不拉 K 线：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase0-before \
  --candidate-label phase1-after \
  --skip-refresh
```

如果不管是否过期都要强制刷新全部标的：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase0-before \
  --candidate-label phase1-after \
  --refresh-all
```

baseline agent 的职责说明在：

```text
test/baseline_agent/agent.md
```

每个迁移 Phase 的出口门禁统一使用：

```bash
.venv/bin/python test/baseline_agent/run.py \
  --phase <phase-number> \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label <base-label> \
  --strict
```

详细迁移调用规范见：

```text
docs/agent-modernization-migration-workflow.md
```

## 手工分步流程

### 1. 改造前冻结基线

在开始 Phase 1 或任何 prompt / worker / validator 改造前执行：

```bash
.venv/bin/python scripts/collect_baseline.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --run-date phase0-before
```

如果结果包含 `degraded`，先看 warning 是否只是数据过期：

```bash
sed -n '1,240p' data/_baseline/phase0-before/run_summary.json
```

如果是关键报告缺失导致 `failed`，先按现有完整分析流程补跑该标的，再重新采集。

### 2. 改造代码

按 Phase 文档推进，例如 Phase 1 瘦身 worker prompt。改造过程中不要直接修改 baseline 产物；每次需要对照时重新生成一个新的 baseline 标签。

### 3. 改造后采集候选基线

```bash
.venv/bin/python scripts/collect_baseline.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --run-date phase1-after
```

### 4. 比较改造前后

```bash
.venv/bin/python scripts/compare_baseline.py \
  --base phase0-before \
  --candidate phase1-after
```

严格比较。发现回归时返回非零退出码：

```bash
.venv/bin/python scripts/compare_baseline.py \
  --base phase0-before \
  --candidate phase1-after \
  --strict
```

比较规则：

- `ok -> degraded` 是回归；
- `ok -> failed` 是回归；
- `degraded -> failed` 是回归；
- `degraded -> ok` 是改善；
- 改造前存在的关键报告路径在候选基线中消失，是回归；
- 某个标的在候选基线中缺失，是回归。

### 5. 验收后进入下一 Phase

进入下一 Phase 前至少确认：

```bash
.venv/bin/python -m unittest scripts/tests/test_pipeline_foundation.py
.venv/bin/python scripts/compare_baseline.py --base phase0-before --candidate phase1-after --strict
```

如果比较失败，先修复回归，再推进下一 Phase。

## 当前真实基线

已生成过一次 2026-05-01 基线：

```text
data/_baseline/2026-05-01/run_summary.json
```

当时 4 个默认标的的 fundamental / deduction / report 关键报告均存在，但 `1h` / `1d` / `1w` K 线相对 2026-05-01 已过期，因此状态为 `degraded`。这说明当前历史报告链路可作为行为参考，但若要做严格验收，应先刷新数据并重新跑完整分析。

## 常用命令

数据新鲜度门禁：

```bash
.venv/bin/python scripts/verify_data_freshness.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --critical-only
```

运行基础测试：

```bash
.venv/bin/python -m unittest scripts/tests/test_pipeline_foundation.py
```

校验 worker JSON：

```bash
.venv/bin/python scripts/validate_worker_result.py data/_runs/<run_id>/worker_results/<symbol>_<phase>.json
```

创建运行 manifest：

```bash
.venv/bin/python scripts/pipeline_state.py create \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --run-id <label>
```

## 目录速查

```text
agents/main/                         主 Agent 编排
agents/workers/                      执行 worker prompt
agents/policies/                     全局规则、运行契约、报告规范、交易方法论
agents/learned_rules.md              后验强化规则
scripts/collect_baseline.py          Phase 0 基线采集
scripts/compare_baseline.py          baseline 回归比较
scripts/pipeline_state.py            运行 manifest 创建与更新
scripts/validate_worker_result.py    worker JSON 校验
scripts/verify_data_freshness.py     阶段一到阶段二的数据门禁
data/_baseline/                      baseline 快照
data/_runs/                          pipeline 运行状态
deduction/                           基本面和推理记录
report/                              正式报告
```

## 推进原则

1. 先冻结基线，再改架构。
2. 每个 Phase 结束都生成候选 baseline。
3. 候选 baseline 必须与 Phase 0 baseline 比较。
4. 允许记录既有 degraded，但不允许引入新的 failed。
5. 任何失败点必须落到 JSON warning / status 中，不能只在对话中口头解释。
