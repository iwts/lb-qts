# Long Short Thesis Skill

## Purpose

强制双侧论证，降低确认偏差。适用于技术、基本面、组合决策和复盘。

## Inputs

- `data/<symbol>/llm_context.md`
- `data/<symbol>/signals_summary.json`
- `deduction/<symbol>/*.md`
- `agents/learned_rules.md`

## Method

1. Long thesis 至少 3 条量化证据，每条包含数据项、具体数值、来源文件和置信度。
2. Short thesis 至少 3 条量化证据，格式同上。
3. 对比两侧证据强度，给出定量差距。
4. 若核心证据互相抵消或差距不足 10 分，结论不得强行定向。

## Output

- Long thesis
- Short thesis
- 证据强度差
- 对最终方向的影响
