# Review Rule Lifecycle Skill

## Purpose

把复盘从“解释过去”升级为“验证预测、识别方法漏洞、提出规则生命周期动作建议”。

## Inputs

- `deduction/<symbol>/deduction_*.md`
- `data/performance/predictions.csv`（若存在）
- `data/<symbol>/1d_indicators.csv` / `1h_indicators.csv`
- `data/youtube_insights/challenges.md`（可选）
- `agents/learned_rules.md`

## Method

1. 对照预测和实际：方向、关键价位、触发情况、止损止盈、实际 RR。
2. 分类归因：成功、方向对但计划错、方向错且系统性、方向错但随机、观望漏机会、正确观望。
3. 对 B/C/E 案例追问思维漏洞：确认偏差、结构冲突、周期错配、基本面盲区、体制错判、RR 倒推。
4. 提出规则生命周期动作建议：新增、强化、降级、废弃。新增规则建议要求至少 2 个同类案例；单案例只写入复盘报告。
5. 如有外部观点，批判性验证后再吸收。

## Output

- 预测 vs 实际表
- 归因与思维漏洞
- 规则生命周期动作建议
- 质量评分
