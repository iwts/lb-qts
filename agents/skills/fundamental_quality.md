# Fundamental Quality Skill

## Purpose

把基本面分析从财务数字复述升级为投资质量、成长、估值、现金回报和催化风险的系统判断。

## Required Inputs

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

## Output Fields

- 五维评分
- 三维兼容评分
- 基本面方向
- Technical x Fundamental 整合提示

## Failure / Degraded Conditions

- `fundamental.json` 与 `earnings.json` 同时缺失时，返回 `failed` 或最高 `degraded`，并限制综合评分置信度。
- 缺估值、现金流、财报日期或关键分部数据时允许降级，但必须列入 `warnings`。
- ETF 或指数类标的缺公司财务字段时不视为失败，改用行业主题、持仓和宏观因子降级分析。
- 五维任一维无法给出证据时，该维默认中性并降低总置信度。

## Common Mistakes

- 不要把财务指标复述当作投资质量判断。
- 不要用短期技术走势改写基本面方向，只能给 Technical x Fundamental 整合提示。
- 不要在缺少财报或现金流证据时给高置信度强方向。
- 不要把权重规则复制到其他 worker；本 skill 只输出可复用基本面判断。
