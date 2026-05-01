# Phase 2：建设可组合 Skills 方法库

## 目标

把 `trading_playbook.md` 和各 worker prompt 中可复用的方法论拆成小粒度 skills。

目标不是把所有 prompt 都变成 skills，而是把“可复用研究方法”沉淀成可组合模块。

## Skills 的定位

skills 像投研机构内部的研究手册章节：

- 可被多个 worker 复用；
- 只描述方法；
- 不绑定具体 worker；
- 不重复全局 rules；
- 不承担输出报告模板。

## 不适合放进 Skills 的内容

不要把这些内容放进 skill：

- “你是资深交易员”这类角色设定；
- worker 输出路径；
- run manifest 更新方法；
- 飞书同步流程；
- stop 方向必须正确这类硬规则；
- JSON schema 细节；
- 大段报告模板。

这些应分别留在：

```text
agents/workers/
agents/policies/
scripts/
schemas/
```

## 推荐目录

```text
agents/skills/
  market_regime.md
  multi_timeframe_resonance.md
  price_structure.md
  volume_flow_analysis.md
  support_resistance.md
  long_short_thesis.md
  risk_first_trade_plan.md
  fundamental_quality.md
  growth_analysis.md
  valuation_context.md
  cash_return.md
  earnings_catalyst.md
  sector_cycle.md
  tech_growth_equity.md
  dividend_defensive_equity.md
  cyclical_resources_equity.md
  hk_liquidity_discount.md
  a_share_policy_cycle.md
  etf_holdings_analysis.md
  options_oi_flow.md
  review_attribution.md
  rule_evolution.md
  conflict_resolution.md
  report_quality_review.md
```

## Skill 模板

每个 skill 使用统一结构：

```markdown
# Skill Name

## Purpose

这个 skill 解决什么问题。

## Required Inputs

需要哪些字段、文件或上下文。

## Method

具体判断框架。

## Output Fields

调用该 skill 后应该产出哪些结构化字段。

## Failure / Degraded Conditions

哪些情况必须 failed 或 degraded。

## Common Mistakes

常见误判和禁止行为。
```

## 首批核心 Skills

Phase 2 最小可行版本建议先拆 5 个。

### 1. market_regime.md

目的：

- 识别市场体制；
- 决定趋势、反转、区间策略是否适用。

输入：

- ADX；
- MA 排列；
- DI 方向；
- ATR%；
- BB width；
- 最近波动状态。

输出：

```json
{
  "regime": "strong_trend_up|strong_trend_down|weak_trend|range|vol_contract|vol_expand|event_driven",
  "valid_entry_types": [],
  "invalid_entry_types": [],
  "confidence": 0.0
}
```

### 2. multi_timeframe_resonance.md

目的：

- 判断 1w / 1d / 1h 是否顺共振；
- 决定短线和中期结论是否一致。

输出：

```json
{
  "mtf_resonance": "aligned_long|aligned_short|conflict|mixed",
  "dominant_timeframe": "1w|1d|1h",
  "reason": ""
}
```

### 3. long_short_thesis.md

目的：

- 强制双侧证据；
- 避免只寻找支持自己方向的证据。

输出：

```json
{
  "bull_evidence": [],
  "bear_evidence": [],
  "bull_score": 0,
  "bear_score": 0,
  "difference": 0
}
```

### 4. risk_first_trade_plan.md

目的：

- 按风险优先原则生成交易计划；
- 明确 entry、stop、target、RR、position_size。

输出：

```json
{
  "trade_plans": [
    {
      "side": "long|short|neutral",
      "entry": 0,
      "stop": 0,
      "target_1": 0,
      "target_2": 0,
      "rr_target_1": 0,
      "position_size": 0,
      "invalidation": ""
    }
  ]
}
```

### 5. review_attribution.md

目的：

- 对历史预测进行错误归因；
- 为 learned rule candidate 提供依据。

输出：

```json
{
  "prediction_result": "hit|miss|partial|invalid",
  "attribution": "regime_misread|fundamental_weight_error|technical_weight_error|event_risk_ignored|rr_or_stop_design_error",
  "rule_candidate": ""
}
```

## Skills 与 Profiles 的关系

skill 是方法，profile 是风格。

例如：

```text
market_regime.md
  -> 所有 PM 都会用

tech_growth_pm.md
  -> 决定成长、财报、预期差的权重更高
```

同一个 skill 在不同 profile 下可以产生不同权重，但方法本身不变。

## Worker 调用规则

worker prompt 中应声明：

```text
Required Skills:
- market_regime.md
- long_short_thesis.md

Optional Skills:
- options_oi_flow.md
- hk_liquidity_discount.md
```

worker JSON 回传：

```json
{
  "skills_used": ["market_regime", "long_short_thesis"],
  "skills_skipped": [
    {
      "skill": "options_oi_flow",
      "reason": "非美股或无期权数据"
    }
  ]
}
```

## 验收标准

- 至少新增 5 个核心 skills；
- 至少 2 个 worker 引用同一个 skill；
- worker prompt 不再重复完整方法论；
- skills 不直接绑定单个 worker；
- skills 有明确输入、方法、输出字段和降级条件。
- 必须运行 baseline agent 并得到 `PASS`，报告写入 `data/_baseline/phase2-after/baseline_agent_report.md`：
```bash
.venv/bin/python test/baseline_agent/run.py --phase 2 --base-label phase1-after --strict
```

## 风险与控制

### 风险：skills 数量太多，选择成本上升

控制：

- 主 agent 负责装配 skills；
- skills 分 `required` 和 `optional`；
- 每次 worker 记录 `skills_used`。

### 风险：skill 再次变成大 prompt

控制：

- 单个 skill 建议控制在 100-150 行以内；
- 一个 skill 只解决一个问题；
- 超过范围时拆分。

## 交接给下一阶段

Phase 2 结束后，Phase 3 agent 应读取：

```text
docs/agent-modernization-phase-2-skills-library.md
data/_baseline/phase2-after/baseline_agent_report.md
agents/skills/*.md
agents/workers/*.md
```

然后建立 profiles / mandates，让同一 worker 在不同标的上体现不同投资风格。
