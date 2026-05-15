# Fundamental Quality Skill

## Purpose

把基本面分析从财务数字复述升级为投资质量、成长、估值、现金回报和催化风险的系统判断。

## Inputs

- `data/<symbol>/fundamental.json`
- `data/<symbol>/earnings.json`
- `data/<symbol>/factor_scores.json`（可选）
- `agents/learned_rules.md`

## Method

1. 五维分析：Quality、Growth、Valuation、Cash、Catalysts & Risks。
2. 每维列 2-5 个可追溯数值证据，给 0-100 分，并标注 `bull|bear|neutral` 推力。
3. 映射到兼容三维：`financial_score`、`industry_score`、`earnings_score`。
4. 按标的类型动态权重：默认 35/35/30；ETF 15/70/15；银行/红利 45/30/25；高成长科技 25/30/45；周期股 25/50/25；新上市 20/50/30。
5. 输出 Bull Case、Bear Case 和 bull/base/bear 情景概率。

## Output

- 五维评分
- 三维兼容评分
- 基本面方向
- Technical x Fundamental 整合提示
