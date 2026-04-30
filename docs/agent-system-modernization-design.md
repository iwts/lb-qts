# LB-QTS 多 Agent 投研系统现代化设计索引

生成时间：2026-05-01 CST

## 目标

本系列文档用于把当前 `lb-qts` 多 Agent 投研系统从“重 prompt + 三阶段流水线”升级为：

```text
轻 Agent + 可组合 Skills + Profiles/Mandates + Typed Artifacts + Validator + 独立 Review
```

核心方向：

- 主 agent 只做调度、监督、恢复和汇总，不参与具体投研观点；
- worker/subagent 保持轻量，只承担明确岗位职责；
- skills 承载可复用方法论；
- profiles 承载不同投资经理风格与品类权重；
- rules 承载全局硬约束；
- typed artifacts 让主 agent 和 review agent 低成本监督；
- validator 负责机械校验；
- PM agent 对最终交易判断负责；
- review agent 独立做后验归因和规则进化。

## 分阶段文档

建议按顺序推进。每个 Phase 都可以独立开新 agent 执行、调试和验收。

| Phase | 文档 | 目标 |
| --- | --- | --- |
| Phase 0 | [agent-modernization-phase-0-baseline.md](agent-modernization-phase-0-baseline.md) | 冻结当前行为基线，建立回归标的和质量标准 |
| Phase 1 | [agent-modernization-phase-1-worker-slimming.md](agent-modernization-phase-1-worker-slimming.md) | 瘦身 worker prompt，固化 worker 最小契约 |
| Phase 2 | [agent-modernization-phase-2-skills-library.md](agent-modernization-phase-2-skills-library.md) | 拆出可组合 skills 方法库 |
| Phase 3 | [agent-modernization-phase-3-profiles-mandates.md](agent-modernization-phase-3-profiles-mandates.md) | 引入职业化 profiles / mandates |
| Phase 4 | [agent-modernization-phase-4-typed-artifacts-validator.md](agent-modernization-phase-4-typed-artifacts-validator.md) | 建设 typed artifacts 和 validator |
| Phase 5 | [agent-modernization-phase-5-dag-conflict-routing.md](agent-modernization-phase-5-dag-conflict-routing.md) | DAG 化编排与冲突处理 |
| Phase 6 | [agent-modernization-phase-6-review-rule-evolution.md](agent-modernization-phase-6-review-rule-evolution.md) | 独立 review 与 learned rules 进化机制 |
| Phase 7 | [agent-modernization-phase-7-operating-model.md](agent-modernization-phase-7-operating-model.md) | 公司化运行模型、PM 责任制和风控否决 |

## 推荐执行节奏

### 短期：1-2 周

优先执行：

1. Phase 0：建立基线；
2. Phase 1：瘦身 worker prompt；
3. Phase 2：拆出首批核心 skills；
4. Phase 4 的最小版本：在 worker JSON 中增加 `skills_used`、`profile_used`、`rules_applied` 等字段。

暂缓：

- 引入复杂 DAG 框架；
- 大量新增 subagent；
- 重写所有报告模板；
- 让 review agent 自动修改 `learned_rules.md`。

### 中期：3-6 周

优先执行：

1. Phase 3：profiles / mandates；
2. Phase 4：typed artifacts 与 validator；
3. Phase 5：基于 manifest 的 DAG 化；
4. execution 阶段稳定记录 prediction。

目标：

- 主 agent 基本不读长 Markdown；
- PM decision 有结构化 JSON；
- 不同投资风格可以复用同一 reasoning worker；
- 失败恢复可从中间节点继续。

### 长期：6-12 周

优先执行：

1. Phase 6：后验统计与规则进化；
2. Phase 7：PM 责任制与 risk officer；
3. 评估是否引入 LangGraph / Prefect / Temporal；
4. 建立 performance dashboard。

目标：

- 系统能稳定复盘自己的判断；
- `learned_rules.md` 有生命周期；
- 投资风格和市场品类形成职业化分工；
- 报告质量不依赖单次 prompt 表现。

## 最小可行闭环

如果只做一个 MVP，建议：

```text
1. 新增 agents/skills/
2. 从 trading_playbook 拆出 5 个 skills
3. 新增 agents/profiles/
4. 建立 3 个 profiles
5. worker JSON 增加 skills_used/profile_used
6. 新增 pm_decision.json
7. validator 校验 pm_decision.json
8. execution 根据 pm_decision 生成报告
9. record_prediction 记录最终观点
10. review 用 predictions.csv 做 N+5 复盘
```

首批 5 个 skills：

```text
market_regime.md
multi_timeframe_resonance.md
long_short_thesis.md
risk_first_trade_plan.md
review_attribution.md
```

首批 3 个 profiles：

```text
tech_growth_pm.md
dividend_defensive_pm.md
hk_liquidity_pm.md
```

首批关键 JSON：

```text
deduction/<symbol>/pm_decision_<yyyy_mm_dd>_<seq>.json
```

