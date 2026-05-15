# Multi Timeframe Resonance Skill

## Purpose

把周线、日线、小时线压缩成可执行的方向偏好。优先遵循 `agents/policies/trading_playbook.md` §2。

## Required Inputs

- `data/<symbol>/llm_context.md`
- `data/<symbol>/signals_summary.json`
- 各周期指标 CSV（若可用）

## Method

1. 填写 1w / 1d / 1h 三行矩阵：趋势方向、动量方向、体制、RSI、ADX、MA 排列。
2. 判定 `aligned_long`、`aligned_short`、`conflict`、`mixed`。
3. 周期冲突时声明主导周期，并说明原因。
4. 高低周期互相抵消且证据差异不足 10 分时，方向偏好降为 `neutral`。

## Output Fields

- 共振标签
- 主导周期
- `long|short|neutral` 方向偏好

## Failure / Degraded Conditions

- 缺少 1d 数据时返回 `failed`，因为无法形成主交易周期判断。
- 缺少 1w 或 1h 数据时允许 `degraded`，但必须说明缺周期对结论的影响。
- 周线、日线、小时线方向相互冲突且强度差不足 10 分时，方向偏好必须降为 `neutral`。
- 任一周期指标不可追溯时，对应矩阵单元标记为 `missing`。

## Common Mistakes

- 不要用小时线信号推翻明确的周线趋势，除非说明时间窗口只限短线。
- 不要把“混合”包装成“共振”。
- 不要忽略缺失周期数据对置信度的影响。
- 不要把多周期矩阵写成指标清单；必须说明主导周期和交易含义。
