# Phase 2：建设可组合 Skills 方法库

## 目标

把 `trading_playbook.md` 和各 worker prompt 中可复用的方法论拆成小粒度 skills。

Phase 2 的目标不是把所有 prompt 都变成 skills，而是把“可复用研究方法”沉淀成可组合模块，并让 worker 只负责角色、输入、调用和输出契约。

## Phase 2 启动状态

Phase 1 已完成 worker prompt 瘦身，核心 worker 已显式引用 `agents/skills/*.md`。

启动 Phase 2 前必须确认：

- `data/_baseline/phase1-after/baseline_agent_report.md` 存在；
- `data/_baseline/phase1-after/baseline_agent_result.json` 的 `conclusion` 为 `PASS`；
- 核心 worker 已包含 `Required Skills`；
- 核心 worker 回传协议已包含 `skills_used`、`skills_skipped`、`profile_used`。

当前已落地 8 个 skill，Phase 2 的第一优先级是标准化和边界修正，而不是继续扩大数量。

## Skills 的定位

skills 像投研机构内部的研究手册章节：

- 可被多个 worker 复用；
- 只描述方法和判断框架；
- 不绑定具体 worker；
- 不重复全局 rules；
- 不承担输出报告模板；
- 不直接执行脚本、同步外部系统或更新 run manifest。

## 不适合放进 Skills 的内容

不要把这些内容放进 skill：

- “你是资深交易员”这类角色设定；
- worker 输出路径；
- run manifest 更新方法；
- 飞书同步流程；
- stop 方向、ATR 距离、RR 阈值这类硬规则的完整定义；
- JSON schema 细节；
- 大段报告模板。

这些应分别留在：

```text
agents/workers/
agents/policies/
scripts/
schemas/（Phase 4 引入）
```

skill 可以引用硬规则来源，例如“按 `agents/policies/runtime_contract.md` 与 `trading_playbook.md` 的风险门禁校验”，但不要在 skill 内维护另一份独立规则定义。

## 当前 Skill Inventory

| Skill | 当前调用方 | Phase 2 处理动作 |
| --- | --- | --- |
| `market_regime.md` | `strategy_agent.md`、`reasoning_agent.md` | 标准化模板；补充 degraded 条件和常见误判 |
| `multi_timeframe_resonance.md` | `strategy_agent.md`、`reasoning_agent.md` | 标准化模板；明确缺周期数据时的降级输出 |
| `technical_structure_scan.md` | `strategy_agent.md` | 标准化模板；确认它合并承载 price structure / volume flow / support resistance 的 MVP 范围 |
| `long_short_thesis.md` | `fundamental_master_agent.md`、`reasoning_agent.md`、`review_agent.md` | 标准化模板；保留为跨 worker 复用核心 skill |
| `risk_first_trade_plan.md` | `reasoning_agent.md`、`execution_agent.md` | 标准化模板；硬门禁只引用 policies，不在 skill 内重复维护 |
| `fundamental_quality.md` | `fundamental_master_agent.md` | 标准化模板；补齐基本面缺字段时的 degraded 条件 |
| `execution_risk_check.md` | `execution_agent.md` | 收窄边界为交易计划复核和仓位数学；飞书同步留在 execution worker / scripts |
| `review_rule_lifecycle.md` | `review_agent.md` | 替代旧设计中的 `review_attribution.md`；补齐 lifecycle 动作输出字段 |

当前满足：

- 已有 skill 数量超过 Phase 2 MVP 的 5 个；
- 至少 2 个 worker 复用同一个 skill：`long_short_thesis.md`、`market_regime.md`、`multi_timeframe_resonance.md`、`risk_first_trade_plan.md` 均满足；
- worker 已声明 `Required Skills` 并在 JSON 示例中写入 `skills_used`。

当前未满足：

- 现有 skill 仍使用 `## Inputs` / `## Output`，尚未统一为 Phase 2 模板；
- 现有 skill 普遍缺少 `Failure / Degraded Conditions`；
- 现有 skill 普遍缺少 `Common Mistakes`；
- 个别 skill 混入 execution / sync / hard gate 细节，需要收窄边界。

## Skill 模板

Phase 2 结束前，每个 skill 必须使用统一结构：

```markdown
# Skill Name

## Purpose

这个 skill 解决什么可复用研究问题。

## Required Inputs

需要哪些字段、文件或上下文。只列输入，不写 worker 调度流程。

## Method

具体判断框架。只写方法，不复制全局 rules 的完整条款。

## Output Fields

调用该 skill 后应该产出哪些结构化字段。

## Failure / Degraded Conditions

哪些情况必须 failed 或 degraded；哪些输入缺失时允许降级。

## Common Mistakes

常见误判、禁止行为和边界提醒。
```

命名约束：

- 标题使用可读名称，例如 `# Market Regime Skill`；
- 文件名使用 snake_case，例如 `market_regime.md`；
- worker 的 `skills_used` 使用相对文件路径，例如 `agents/skills/market_regime.md`，与现有 worker JSON 保持一致；
- 不再新增 `review_attribution.md`，复盘归因统一并入 `review_rule_lifecycle.md`。

## Phase 2 必做事项

### 1. 标准化现有 8 个 skill

对 `agents/skills/*.md` 做最小可逆改造：

- `## Inputs` 改为 `## Required Inputs`；
- `## Output` 改为 `## Output Fields`；
- 为每个 skill 补充 `## Failure / Degraded Conditions`；
- 为每个 skill 补充 `## Common Mistakes`；
- 保持单个 skill 小于 100 行；
- 不改 worker 输出路径和调度语义。

### 2. 修正边界污染

优先处理两个边界问题：

- `execution_risk_check.md`：只保留交易计划复核、仓位数学、if-then 执行清单的方法；飞书同步动作由 `execution_agent.md` 和脚本承担。
- `risk_first_trade_plan.md`：保留风险优先构造顺序和校验思路；stop / ATR / RR 的硬阈值只引用 `agents/policies/runtime_contract.md` 与 `agents/policies/trading_playbook.md`。

### 3. 明确 `technical_structure_scan.md` 的 MVP 范围

Phase 2 先不拆出 `price_structure.md`、`volume_flow_analysis.md`、`support_resistance.md`。

`technical_structure_scan.md` 暂时作为技术面聚合 skill，覆盖：

- price structure；
- volume / capital flow；
- support / resistance；
- feasible entry types。

若后续该文件超过 100 行，或不同 worker 需要单独复用其中一部分，再拆分成独立 skill。

### 4. 补齐 worker-skill 对照

Phase 2 结束前保留以下最小调用矩阵：

| Worker | Required Skills |
| --- | --- |
| `fundamental_master_agent.md` | `fundamental_quality.md`、`long_short_thesis.md` |
| `strategy_agent.md` | `market_regime.md`、`multi_timeframe_resonance.md`、`technical_structure_scan.md` |
| `reasoning_agent.md` | `market_regime.md`、`multi_timeframe_resonance.md`、`long_short_thesis.md`、`risk_first_trade_plan.md` |
| `execution_agent.md` | `execution_risk_check.md`、`risk_first_trade_plan.md` |
| `review_agent.md` | `review_rule_lifecycle.md`、`long_short_thesis.md` |

新增 optional skill 时，必须同步更新对应 worker 的 `skills_skipped` 说明。

## 暂缓新增的 Skill Backlog

以下 skill 可以进入后续迭代，但不作为 Phase 2 完成条件：

```text
options_oi_flow.md
hk_liquidity_discount.md
a_share_policy_cycle.md
etf_holdings_analysis.md
growth_analysis.md
valuation_context.md
cash_return.md
earnings_catalyst.md
sector_cycle.md
tech_growth_equity.md
dividend_defensive_equity.md
cyclical_resources_equity.md
conflict_resolution.md      # Phase 5 再引入
report_quality_review.md    # 可与 validator / report_specs 协同
```

新增 skill 的触发条件：

- 至少 2 个 worker 或 2 类标的会复用；
- 现有 skill 已超过 100 行或职责明显混杂；
- 新 skill 不会重复 `policies` 的硬规则；
- 能明确列出输入、输出字段和 degraded 条件。

## Skills 与 Profiles 的关系

skill 是方法，profile 是风格。

例如：

```text
market_regime.md
  -> 所有 PM 都会用

tech_growth_pm.md
  -> 决定成长、财报、预期差的权重更高
```

同一个 skill 在不同 profile 下可以产生不同权重，但方法本身不变。profile 不得复制 skill 的完整方法论。

## Worker 调用规则

worker prompt 中应声明：

```text
Required Skills:
- agents/skills/market_regime.md
- agents/skills/long_short_thesis.md

Optional Skills:
- agents/skills/options_oi_flow.md
```

worker JSON 回传：

```json
{
  "skills_used": [
    "agents/skills/market_regime.md",
    "agents/skills/long_short_thesis.md"
  ],
  "skills_skipped": [
    {
      "skill": "agents/skills/options_oi_flow.md",
      "reason": "非美股或无期权数据"
    }
  ]
}
```

规则：

- `skills_used` 必须只记录实际使用的 skill；
- Required skill 因输入缺失无法完成时，worker 状态至少为 `degraded`；
- Optional skill 不适用时必须写入 `skills_skipped`；
- worker 不得把未读取的 skill 写进 `skills_used`。

## 验收标准

Phase 2 完成必须同时满足：

- `agents/skills/` 至少保留 5 个核心 skill，且当前 8 个 skill 均完成模板标准化；
- 每个 skill 都有 `Purpose`、`Required Inputs`、`Method`、`Output Fields`、`Failure / Degraded Conditions`、`Common Mistakes`；
- 至少 2 个 worker 引用同一个 skill；
- worker prompt 不再重复完整方法论；
- skills 不直接绑定单个 worker；
- skills 不承担飞书同步、run manifest、报告路径写入或 JSON schema 校验；
- worker JSON 中 `skills_used`、`skills_skipped`、`profile_used` 与 `agents/policies/runtime_contract.md` 保持一致；
- 运行基础测试通过：

```bash
.venv/bin/python -m unittest scripts/tests/test_pipeline_foundation.py
```

- 运行 baseline agent 并得到 `PASS`，报告写入 `data/_baseline/phase2-after/baseline_agent_report.md`：

```bash
.venv/bin/python test/baseline_agent/run.py --phase 2 --base-label phase1-after --strict
```

## 风险与控制

### 风险：skills 数量太多，选择成本上升

控制：

- Phase 2 优先标准化现有 8 个 skill；
- optional skill 进入 backlog，不急于实现；
- 主 agent / worker 明确区分 `required` 和 `optional`；
- 每次 worker 记录 `skills_used` 和 `skills_skipped`。

### 风险：skill 再次变成大 prompt

控制：

- 单个 skill 控制在 100 行以内；
- 一个 skill 只解决一个研究问题；
- 超过范围时拆分；
- 不复制 `policies` 的硬规则全文。

### 风险：方法与硬规则产生双源维护

控制：

- skill 只引用硬规则来源；
- 硬阈值、状态定义、统一回传协议留在 `agents/policies/runtime_contract.md`；
- 交易计划细节和质量门禁留在 `agents/policies/trading_playbook.md`。

## 交接给下一阶段

Phase 2 结束后，Phase 3 agent 应读取：

```text
docs/agent-modernization-phase-2-skills-library.md
data/_baseline/phase2-after/baseline_agent_report.md
agents/skills/*.md
agents/workers/*.md
```

阶段交接必须记录：

```text
baseline_label: phase2-after
baseline_report: data/_baseline/phase2-after/baseline_agent_report.md
baseline_result: data/_baseline/phase2-after/baseline_agent_result.json
conclusion: PASS
```

然后建立 profiles / mandates，让同一 worker 在不同标的上体现不同投资风格。
