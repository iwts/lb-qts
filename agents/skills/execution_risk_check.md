# Execution Risk Check Skill

## Purpose

复核上游交易计划，把可执行动作转换成仓位数学和 if-then 执行清单。

## Required Inputs

- `deduction/<symbol>/deduction_*.md`
- `data/<symbol>/signals_summary.json`
- `data/<symbol>/llm_context.md`
- `agents/learned_rules.md`

## Method

1. 逐计划复核体制匹配、stop 方向、stop 距离、RR、两档止盈、失效条件、仓位系数。
2. 主计划和备选计划都不通过时，执行结论转为 `neutral`。
3. 明确仓位数学：单笔风险、股数、账户占比、仓位系数后的最终仓位。
4. 用 if-then 格式输出今日可执行清单。
5. 外部同步、报告写入和 run manifest 更新由调用方与脚本负责，本 skill 不执行这些动作。

## Output Fields

- risk sanity check
- position sizing
- if-then action list

## Failure / Degraded Conditions

- deduction 报告缺少交易计划时返回 `failed`。
- 计划关键字段缺 entry、stop、target、RR、失效条件或仓位输入时，调用方至少 `degraded`。
- 全部计划未通过风险复核时，输出 `neutral` 执行结论和等待条件。
- 仓位数学无法计算时，不得给出具体下单数量。

## Common Mistakes

- 不要替上游推理重新发明方向；只复核和执行。
- 不要把外部同步、报告路径或 manifest 写入逻辑放进 skill。
- 不要在风险复核失败后用“轻仓试错”绕过门禁。
- 不要输出没有触发条件、失效条件或仓位上限的行动清单。
