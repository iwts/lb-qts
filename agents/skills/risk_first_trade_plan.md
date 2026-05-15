# Risk First Trade Plan Skill

## Purpose

用风险优先顺序构造交易计划。优先遵循 `agents/policies/trading_playbook.md` §6-§7 与 `agents/learned_rules.md` 4.x。

## Required Inputs

- `data/<symbol>/llm_context.md`
- `data/<symbol>/signals_summary.json`
- 上游分析报告

## Method

1. 思考顺序固定为：体制、方向、入场类型、触发、失效、风险、目标。
2. 非观望结论至少给出主计划和独立备选计划。
3. 每套计划必须包含：方向、入场类型、触发条件、entry、stop、stop 依据、target_1、target_2、RR、仓位系数、失效条件、执行优先级。
4. 按 `agents/policies/runtime_contract.md` 与 `agents/policies/trading_playbook.md` 校验 stop 方向、ATR 距离、RR、两档止盈和仓位系数。
5. 不满足风险门禁时，先重选入场或降级为观望，不得为了维持方向倒推 stop 或 target。

## Output Fields

- 计划列表
- 风险校验结果
- 最佳 RR
- 观望触发条件（若不交易）

## Failure / Degraded Conditions

- 无法取得 entry、stop 或 ATR 相关输入时，非观望计划返回 `failed`。
- 主计划或备选计划缺少失效条件、仓位系数、两档止盈时，调用方至少 `degraded`。
- 风险门禁未通过且仍输出交易方向时，调用方必须转为 `failed`。
- 证据不足以支撑至少两套独立计划时，输出观望条件而不是强行补计划。

## Common Mistakes

- 不要先定目标价再倒推出好看的 RR。
- 不要在 skill 内维护 stop、ATR 或 RR 的硬阈值副本。
- 不要把同一入场价微调后伪装成独立备选计划。
- 不要忽略“观望也是计划”；风险不合格时应明确等待条件。
