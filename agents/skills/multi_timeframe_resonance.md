# Multi Timeframe Resonance Skill

## Purpose

把周线、日线、小时线压缩成可执行的方向偏好。优先遵循 `agents/policies/trading_playbook.md` §2。

## Inputs

- `data/<symbol>/llm_context.md`
- `data/<symbol>/signals_summary.json`
- 各周期指标 CSV（若可用）

## Method

1. 填写 1w / 1d / 1h 三行矩阵：趋势方向、动量方向、体制、RSI、ADX、MA 排列。
2. 判定 `aligned_long`、`aligned_short`、`conflict`、`mixed`。
3. 周期冲突时声明主导周期，并说明原因。
4. 高低周期互相抵消且证据差异不足 10 分时，方向偏好降为 `neutral`。

## Output

- 共振标签
- 主导周期
- `long|short|neutral` 方向偏好
