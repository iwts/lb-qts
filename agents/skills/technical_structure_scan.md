# Technical Structure Scan Skill

## Purpose

把指标结果转化为可用于下单决策的技术结构判断。优先遵循 `agents/policies/trading_playbook.md` §3-§5。

## Required Inputs

- `data/<symbol>/signals_summary.json`
- `data/<symbol>/llm_context.md`
- `data/<symbol>/capital_flow.csv` / `capital_distribution.csv`（若存在）
- `data/<symbol>/market_temperature.json`（若存在）

## Method

1. 识别最近 20 日价格结构：HH/HL、LH/LL 或盘整。
2. 找出最近关键 HL / LH，标注多空防线。
3. 七维扫描：趋势、动量、波动率、量能、资金流、支撑阻力、多周期共振。
4. 每一维回答“说明什么”和“对交易有什么用”，避免只复述数值。
5. 输出当前可行入场类型：breakout、pullback、rally_short、reversal、range、stand_aside。
6. Phase 2 MVP 中本 skill 合并承载 price structure、volume / capital flow、support / resistance 与 feasible entry types；超过 100 行或复用边界变化时再拆分。

## Output Fields

- 价格结构
- 七维摘要
- 可行入场类型
- 技术面评分

## Failure / Degraded Conditions

- 缺少 `signals_summary.json` 或无法读取价格结构时返回 `failed`。
- 资金流、资金分布或市场温度缺失时允许 `degraded`，并禁止输出资金结论。
- 最近关键 HL/LH 无法识别时，标记为盘整或结构不清，不得虚构支撑阻力。
- 七维扫描缺两维以上时，技术面评分置信度必须降低。

## Common Mistakes

- 不要把指标读数堆砌成技术结论。
- 不要将支撑阻力画在当前价格附近的任意整数位。
- 不要忽略成交量和资金流对突破有效性的约束。
- 不要在 Phase 2 中拆出新 skill，除非文件超过 100 行或复用边界已经明确变化。
