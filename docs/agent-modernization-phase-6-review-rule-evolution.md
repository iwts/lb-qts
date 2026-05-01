# Phase 6：独立 Review 与规则进化机制

## 目标

把 review agent 从“报告检查者”升级成：

```text
后验统计 + 错误归因 + 规则候选生成 + 规则生命周期治理
```

Review 必须独立于当日 market main 流程，避免污染当前分析上下文。

## 当前问题

如果 review 只检查报告质量，会漏掉真正重要的问题：

- 方向是否真的对；
- entry/stop/target 是否合理；
- 是体制判断错，还是风险计划错；
- 是基本面权重错，还是技术面权重错；
- learned rule 是否过拟合；
- 哪些错误值得沉淀成规则。

## Review 输入

```text
data/performance/predictions.csv
data/<symbol>/1d_k.csv
deduction/<symbol>/pm_decision_*.json
deduction/<symbol>/deduction_*.md
report/<symbol>/report_*.md
agents/learned_rules.md
data/youtube_insights/challenges.md
```

## 后验统计窗口

统一评估：

| 窗口 | 目的 |
| --- | --- |
| N+1 | 次日方向是否正确 |
| N+5 | 一周交易计划是否有效 |
| N+20 | 中短期观点是否有效 |

关键指标：

- direction hit；
- target_1 是否先于 stop 触达；
- target_2 是否触达；
- MFE 最大有利波动；
- MAE 最大不利波动；
- 是否触发 invalidation；
- 原计划是否应当 neutral。

## 错误归因分类

统一 enum：

```text
data_error
regime_misread
fundamental_weight_error
technical_weight_error
liquidity_ignored
options_signal_ignored
event_risk_ignored
rr_or_stop_design_error
overfit_learned_rule
execution_report_distortion
no_error_random_noise
```

每次 miss 必须选择一个主归因，最多两个辅助归因。

## Review 输出

路径：

```text
deduction/<symbol>/review_<yyyy_mm_dd>_<seq>.json
deduction/<symbol>/review_<yyyy_mm_dd>_<seq>.md
```

JSON 示例：

```json
{
  "symbol": "NVDA.US",
  "review_window": "N+5",
  "prediction_result": "hit|miss|partial|invalid",
  "attribution": "regime_misread",
  "mfe": 0.0,
  "mae": 0.0,
  "stop_hit": false,
  "target_1_hit": true,
  "rule_candidates": [],
  "rules_to_deprecate": [],
  "quality_notes": []
}
```

## Rule Candidate 机制

不允许 review agent 直接随意改 `learned_rules.md`。

建议新增：

```text
agents/rule_candidates.md
agents/deprecated_rules.md
```

规则生命周期：

```text
candidate -> active -> deprecated
```

## 规则升级准入

一条 candidate 进入 `learned_rules.md` 需要满足：

- 至少 3 次相似案例；
- 有明确触发条件；
- 有可执行动作；
- 不与现有高优先级规则冲突；
- 能解释历史损失或提升风险控制；
- 不是单一标的的偶发事件。

## Rule Candidate 模板

```markdown
## Candidate Rule: <title>

- Status: candidate
- Source cases:
  - <symbol> <date> <review file>
- Trigger:
  - 明确可识别条件
- Action:
  - 触发后 PM / validator 应怎么做
- Evidence:
  - 至少 3 个案例或明确统计
- Conflict Check:
  - 与现有 learned_rules 的关系
```

## Review Agent 职责

Review agent 做：

- 读取 prediction；
- 对照后续价格；
- 判断 hit/miss/partial；
- 做错误归因；
- 生成 rule candidate；
- 建议废弃过拟合规则。

Review agent 不做：

- 不直接重写当日报告；
- 不覆盖 PM 的原始判断；
- 不无门槛修改 learned_rules；
- 不因为单次错误新增硬规则。

## 验收标准

- review 能基于 `pm_decision.json` 和 `predictions.csv` 做后验统计；
- 输出结构化 review JSON；
- 至少支持 N+1 / N+5；
- learned_rules 不再无限膨胀；
- 每条新增规则有案例来源；
- 错误归因能反向影响 skills/profile/rules。
- 必须运行 baseline agent 并得到 `PASS`，报告写入 `data/_baseline/phase6-after/baseline_agent_report.md`：
```bash
.venv/bin/python test/baseline_agent/run.py --phase 6 --base-label phase5-after --strict
```

## 风险与控制

### 风险：复盘过拟合

控制：

- 单案例不得升级为 active rule；
- 保留 candidate 阶段；
- 定期清理 deprecated rules；
- review 输出“未形成规则”的原因。

### 风险：review 污染当前分析

控制：

- review main 独立入口；
- market main 只读取已 active 的 learned_rules；
- candidate rules 不能自动影响当日分析。

## 交接给下一阶段

Phase 6 结束后，Phase 7 agent 应读取：

```text
docs/agent-modernization-phase-6-review-rule-evolution.md
data/_baseline/phase6-after/baseline_agent_report.md
agents/rule_candidates.md
agents/learned_rules.md
deduction/<symbol>/review_*.json
```

然后建设 PM 责任制、risk officer 和公司化运行模型。
