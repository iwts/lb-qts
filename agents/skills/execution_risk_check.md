# Execution Risk Check Skill

## Purpose

复核 Reasoning Agent 的交易计划，并把可执行动作转换成最终报告。

## Inputs

- `deduction/<symbol>/deduction_*.md`
- `data/<symbol>/signals_summary.json`
- `data/<symbol>/llm_context.md`
- `agents/learned_rules.md`

## Method

1. 逐计划复核体制匹配、stop 方向、stop 距离、RR、两档止盈、失效条件、仓位系数。
2. 主计划和备选计划都不通过时，执行结论转为 `neutral`。
3. 明确仓位数学：单笔风险、股数、账户占比、仓位系数后的最终仓位。
4. 用 if-then 格式输出今日可执行清单。
5. 若存在飞书配置，必须尝试同步；失败记录为 `degraded` 或 `failed`，不得静默跳过。

## Output

- risk sanity check
- position sizing
- if-then action list
- sync status
