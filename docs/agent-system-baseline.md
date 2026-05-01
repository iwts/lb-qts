# LB-QTS Agent System Baseline

生成时间：2026-05-01 CST

## Baseline 目的

Phase 0 的目标是冻结当前三阶段投研系统的可比较基线。后续拆分 worker prompt、抽取 skills、引入 profiles、typed artifacts 和 validator 时，必须用本基线确认核心链路没有退化。

本阶段不做架构改造，不改变主流程，不新增投资风格 profile，不修改 `learned_rules.md`。

## 回归标的

默认最小回归集：

```text
NVDA.US
0700.HK
600900.SH
600036.SH
```

覆盖目的：

| 标的 | 类型 | 验证重点 |
| --- | --- | --- |
| `NVDA.US` | 高成长科技 | 成长、估值、财报预期、波动率 |
| `0700.HK` | 港股互联网 | 港股流动性、估值折价、政策风险 |
| `600900.SH` | 红利/防御 | 分红现金流、防御型判断 |
| `600036.SH` | 金融/银行 | 净息差、资产质量、估值约束 |

## 基线采集命令

采集默认回归集：

```bash
.venv/bin/python scripts/collect_baseline.py
```

采集指定标的：

```bash
.venv/bin/python scripts/collect_baseline.py --symbols NVDA.US,0700.HK,600900.SH,600036.SH
```

严格模式用于 CI 或人工验收，任一标的不是 `ok` 时返回非零退出码：

```bash
.venv/bin/python scripts/collect_baseline.py --strict
```

## 产物位置

每次采集写入：

```text
data/_baseline/<yyyy-mm-dd>/run_summary.json
data/_baseline/<yyyy-mm-dd>/<symbol>_baseline_metrics.json
```

`run_summary.json` 记录：

- 采集日期；
- 回归标的列表；
- 每个标的状态；
- fundamental / deduction / final report 最新产物路径；
- warning 列表；
- 每个标的 metrics 文件路径。

`<symbol>_baseline_metrics.json` 记录：

- 三类关键 Markdown 产物是否存在、大小、行数、修改时间；
- K 线和核心数据文件快照；
- `1h` / `1d` / `1w` 数据新鲜度；
- 最近一次 `data/_runs/*/run_manifest.json` 中该标的阶段状态；
- 最新 worker result JSON metrics（如存在）；
- 缺失或过期原因。

## 质量地板

后续 Phase 不可破坏以下最低标准：

1. 每个完整分析标的必须产出：
   - `deduction/<symbol>/fundamental_analysis_*.md`
   - `deduction/<symbol>/deduction_*.md`
   - `report/<symbol>/report_*.md`
2. 阶段状态必须能结构化追踪，优先使用 `data/_runs/<run_id>/run_manifest.json`。
3. worker JSON 必须能被 `scripts/validate_worker_result.py` 校验。
4. 阶段一进入阶段二前必须通过关键数据门禁，至少覆盖 `1h` / `1d`。
5. 已知失败、缺失、过期必须进入 warning 或 failed 状态，不允许只在对话中口头忽略。

## 状态定义

| 状态 | 含义 |
| --- | --- |
| `ok` | 三类关键产物存在，关键数据新鲜度通过 |
| `degraded` | 三类关键产物存在，但存在数据过期、辅助文件缺失或其他 warning |
| `failed` | 缺失 fundamental / deduction / final report 任一关键产物 |

## Phase 1 交接

Phase 1 开始前应读取：

```text
docs/agent-system-modernization-design.md
docs/agent-modernization-phase-0-baseline.md
docs/agent-system-baseline.md
data/_baseline/<yyyy-mm-dd>/run_summary.json
```

若 `run_summary.json` 中有 `failed` 标的，Phase 1 可以继续做 prompt 瘦身，但验收时必须保留失败原因，并避免把既有缺口误判为 Phase 1 引入的回归。
