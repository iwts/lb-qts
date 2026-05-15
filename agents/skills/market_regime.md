# Market Regime Skill

## Purpose

识别当前标的的交易体制，并约束后续入场类型选择。优先遵循 `agents/policies/trading_playbook.md` §1；若与 `agents/learned_rules.md` 冲突，以 learned rules 为准。

## Required Inputs

- `data/<symbol>/llm_context.md`
- `data/<symbol>/signals_summary.json`
- `data/<symbol>/1w_indicators.csv` / `1d_indicators.csv` / `1h_indicators.csv`（若调用方已提供）

## Method

1. 从趋势强度、方向、波动率三维识别体制：ADX / DI / MA 排列 / ATR% / BB width。
2. 输出明确标签：`strong_trend_up`、`strong_trend_down`、`weak_trend`、`range`、`vol_contract`、`vol_expand`、`event_driven`。
3. 写清当前体制下有效和失效的入场类型。
4. ADX<20 时，不得把趋势跟随作为主计划，除非有高周期结构和量能共同确认。

## Output Fields

- 体制标签
- 关键证据数值
- 对策略类型的约束

## Failure / Degraded Conditions

- 缺少 `signals_summary.json` 或无法取得任何趋势/波动率证据时，返回 `failed`。
- 缺少某一周期指标时允许 `degraded`，但必须说明缺口对体制判断的影响。
- ADX、MA、ATR 或 BB width 证据互相冲突时，输出 `mixed` 或 `event_driven`，并降低置信度。
- 无法追溯关键数值来源时，调用方结果至少为 `degraded`。

## Common Mistakes

- 不要只因单日涨跌或新闻标题判定体制。
- 不要在 ADX<20 且缺少高周期确认时，把趋势跟随列为主策略。
- 不要把波动率扩张自动等同于方向突破。
- 不要复制全局风险门禁；只引用 `agents/policies/trading_playbook.md` 和 `agents/learned_rules.md`。
