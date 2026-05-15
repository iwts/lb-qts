# Market Regime Skill

## Purpose

识别当前标的的交易体制，并约束后续入场类型选择。优先遵循 `agents/policies/trading_playbook.md` §1；若与 `agents/learned_rules.md` 冲突，以 learned rules 为准。

## Inputs

- `data/<symbol>/llm_context.md`
- `data/<symbol>/signals_summary.json`
- `data/<symbol>/1w_indicators.csv` / `1d_indicators.csv` / `1h_indicators.csv`（若调用方已提供）

## Method

1. 从趋势强度、方向、波动率三维识别体制：ADX / DI / MA 排列 / ATR% / BB width。
2. 输出明确标签：`strong_trend_up`、`strong_trend_down`、`weak_trend`、`range`、`vol_contract`、`vol_expand`、`event_driven`。
3. 写清当前体制下有效和失效的入场类型。
4. ADX<20 时，不得把趋势跟随作为主计划，除非有高周期结构和量能共同确认。

## Output

- 体制标签
- 关键证据数值
- 对策略类型的约束
