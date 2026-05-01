# Phase 1：瘦身 Worker Prompt，固化最小契约

## 目标

把 worker 从“大型自包含 prompt”改为：

```text
轻角色 + 输入契约 + Required Skills + Output Contract
```

Phase 1 的重点不是改变行为，而是降低每个 worker 的上下文负担，为 Phase 2 skills 化做准备。

## 当前问题

以 `reasoning_agent.md`、`strategy_agent.md`、`fundamental_master_agent.md` 为例，它们同时包含：

- 角色定义；
- 必读文件；
- 输入白名单；
- 完整方法论；
- learned_rules 扫描；
- 自检清单；
- 质量门禁；
- JSON schema；
- 写入路径。

这会导致：

- 每次调用都加载大量稳定背景知识；
- worker 之间重复方法论；
- prompt 变长后真正分析空间减少；
- 后续拆分 profiles 和 skills 时边界不清。

## 设计原则

### Worker 只保留四块

每个 worker 文件建议统一成：

```text
1. Role
2. Inputs
3. Required Skills
4. Output Contract
```

### 方法论下沉到 skills

例如：

| 当前内容 | 迁移目标 |
| --- | --- |
| 市场体制识别 | `agents/skills/market_regime.md` |
| 多周期共振 | `agents/skills/multi_timeframe_resonance.md` |
| Long / Short thesis | `agents/skills/long_short_thesis.md` |
| 风险优先交易计划 | `agents/skills/risk_first_trade_plan.md` |
| 基本面五维分析 | `agents/skills/fundamental_quality.md` 等 |

### 硬约束留在 policies

以下内容不要放到 worker 内重复：

- 标的隔离；
- 产物必须落盘；
- LongPort 核心数据失败直接 failed；
- learned_rules 优先级；
- RR 不达标不得强行给方向；
- stop 方向校验；
- worker JSON 必须校验。

这些继续由：

```text
agents/policies/common_rules.md
agents/policies/runtime_contract.md
```

承载。

## 推荐 Worker 模板

```markdown
# PM Agent

## Role

你是组合经理，负责把基本面、技术面、期权面和 learned_rules 整合成最终交易决策。

## Inputs

- `data/<symbol>/analysis_packet.json`
- `deduction/<symbol>/fundamental_view_*.json`
- `deduction/<symbol>/technical_view_*.json`
- `deduction/<symbol>/options_view_*.json`（可选）
- `agents/learned_rules.md`

## Required Skills

- `agents/skills/market_regime.md`
- `agents/skills/multi_timeframe_resonance.md`
- `agents/skills/long_short_thesis.md`
- `agents/skills/risk_first_trade_plan.md`

## Output Contract

- 写入 `deduction/<symbol>/pm_decision_<yyyy_mm_dd>_<seq>.json`
- 写入 `deduction/<symbol>/deduction_<yyyy_mm_dd>_<seq>.md`
- JSON 必须包含 `skills_used`、`profile_used`、`rules_applied`
- 返回统一 worker result JSON
```

## 文件调整范围

优先调整：

```text
agents/workers/reasoning_agent.md
agents/workers/strategy_agent.md
agents/workers/fundamental_master_agent.md
agents/workers/execution_agent.md
agents/workers/review_agent.md
```

谨慎调整：

```text
agents/workers/data_agent.md
```

数据 agent 更偏执行，Phase 1 可以先保留，只清理重复 rules。

## 字段扩展

worker JSON 建议新增：

```json
{
  "skills_used": [],
  "skills_skipped": [],
  "profile_used": "",
  "rules_applied_count": 0,
  "rules_applied_ids": []
}
```

Phase 1 不要求所有字段都有真实逻辑，但字段要先稳定下来。

## 迁移步骤

1. 读取 Phase 0 基线；
2. 为每个 worker 标注“哪些内容是角色、哪些是方法论、哪些是硬规则”；
3. 方法论先不删除，移动到临时 skill 草稿；
4. worker 中改为引用 skill；
5. 保持原输出路径不变；
6. 跑 Phase 0 回归标的；
7. 对比产物是否缺失或明显退化。

## 验收标准

- 每个核心 worker prompt 控制在 80-120 行以内；
- worker 不再重复粘贴完整方法论；
- worker 明确列出 `Required Skills`；
- worker JSON 包含 `skills_used` 和 `profile_used` 字段；
- 原有三阶段仍能跑通；
- 关键产物路径保持兼容。
- 必须运行 baseline agent 并得到 `PASS`，报告写入 `data/_baseline/phase1-after/baseline_agent_report.md`：
```bash
.venv/bin/python test/baseline_agent/run.py --phase 1 --base-label phase0-before --strict
```

## 风险与控制

### 风险：worker 变轻后漏步骤

控制：

- Phase 1 只改结构，不大改行为；
- 必须跑 Phase 0 标的回归；
- 关键门禁迁移到 validator 或 runtime contract，而不是靠 worker 记忆。

### 风险：skill 尚未完全拆出

控制：

- Phase 1 允许建立临时 skill 草稿；
- Phase 2 再系统化整理 skill；
- 不要求一次性完美拆分。

## 不做事项

Phase 1 不做：

- 不引入新 DAG；
- 不改变报告格式；
- 不新增复杂 profile 逻辑；
- 不让 review 自动改规则；
- 不改变主 agent 调度语义。

## 交接给下一阶段

Phase 1 结束后，Phase 2 agent 应读取：

```text
docs/agent-modernization-phase-1-worker-slimming.md
data/_baseline/phase1-after/baseline_agent_report.md
agents/workers/*.md
agents/policies/trading_playbook.md
```

并开始把临时 skill 草稿整理成稳定方法库。
