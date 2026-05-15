# Technical Structure Scan Skill

## Purpose

把指标结果转化为可用于下单决策的技术结构判断。优先遵循 `agents/policies/trading_playbook.md` §3-§5。

## Inputs

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

## Output

- 价格结构
- 七维摘要
- 可行入场类型
- 技术面评分
