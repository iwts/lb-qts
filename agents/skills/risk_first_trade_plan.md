# Risk First Trade Plan Skill

## Purpose

用风险优先顺序构造交易计划。优先遵循 `agents/policies/trading_playbook.md` §6-§7 与 `agents/learned_rules.md` 4.x。

## Inputs

- `data/<symbol>/llm_context.md`
- `data/<symbol>/signals_summary.json`
- 上游分析报告

## Method

1. 思考顺序固定为：体制、方向、入场类型、触发、失效、风险、目标。
2. 非观望结论至少给出主计划和独立备选计划。
3. 每套计划必须包含：方向、入场类型、触发条件、entry、stop、stop 依据、target_1、target_2、RR、仓位系数、失效条件、执行优先级。
4. 校验 stop 方向：做多 stop < entry；做空 stop > entry。
5. 校验止损距离：默认 `|entry-stop| >= 1.5 * 日线 ATR`；结构止损例外必须解释且不少于 1.0 ATR。
6. 校验 `RR_at_target_1 >= 1.5`；不满足则重选入场或转观望。

## Output

- 计划列表
- 风险校验结果
- 最佳 RR
- 观望触发条件（若不交易）
