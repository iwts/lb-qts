# Long Short Thesis Skill

## Purpose

强制双侧论证，降低确认偏差。适用于技术、基本面、组合决策和复盘。

## Required Inputs

- `data/<symbol>/llm_context.md`
- `data/<symbol>/signals_summary.json`
- `deduction/<symbol>/*.md`
- `agents/learned_rules.md`

## Method

1. Long thesis 至少 3 条量化证据，每条包含数据项、具体数值、来源文件和置信度。
2. Short thesis 至少 3 条量化证据，格式同上。
3. 对比两侧证据强度，给出定量差距。
4. 若核心证据互相抵消或差距不足 10 分，结论不得强行定向。

## Output Fields

- Long thesis
- Short thesis
- 证据强度差
- 对最终方向的影响

## Failure / Degraded Conditions

- Long 或 Short 任一侧少于 3 条可追溯量化证据时，调用方结果至少为 `degraded`。
- 两侧核心证据都来自同一指标族时，必须标记证据集中风险。
- 数据不足以形成双侧论证时，输出 `neutral` 倾向和缺口清单。
- 证据强度差无法解释时，不得输出强方向。

## Common Mistakes

- 不要先定结论再挑证据。
- 不要把同一事实换词后计为多条证据。
- 不要忽略反向证据或把反向证据写成风险提示后跳过评分。
- 不要把宏观、基本面和技术证据混在一起而不标明来源。
