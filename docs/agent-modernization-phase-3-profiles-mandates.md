# Phase 3：引入职业化 Profiles / Mandates

## 目标

实现：

```text
同一个职业 agent + 不同 profile = 不同投资经理风格
```

不要为每类股票复制一套 agent。更好的方式是让 PM / analyst 加载不同 mandate。

## Profile 的职责

profile 只定义差异化投资风格：

- 关注什么；
- 忽略什么；
- 哪些证据权重更高；
- 哪些风险有否决权；
- 哪些机会类型更适合；
- 该类型标的常见误判。

profile 不负责：

- 通用分析方法；
- 输出格式；
- run manifest；
- 全局硬规则；
- 报告模板。

## 推荐目录

```text
agents/profiles/
  tech_growth_pm.md
  dividend_defensive_pm.md
  cyclical_resources_pm.md
  hk_liquidity_pm.md
  options_flow_trader.md
  bank_financial_pm.md
  healthcare_quality_pm.md
  etf_allocation_pm.md
```

## Profile 模板

```markdown
# Profile Name

## Mandate

这个 profile 管什么类型的标的。

## Evidence Priority

不同证据的优先级。

## Weight Bias

基本面、技术面、估值、流动性、期权等权重倾向。

## Hard Concerns

哪些风险会压制结论。

## Preferred Setups

适合什么交易机会。

## Common Mistakes

该类型标的常见误判。
```

## 首批 Profiles

### tech_growth_pm.md

适用：

- 高成长科技；
- 半导体；
- AI；
- 云计算；
- SaaS；
- 电动车等高预期差标的。

关注：

- 收入增长质量；
- forward guidance；
- 毛利率与经营杠杆；
- TAM 与渗透率；
- 财报前后波动率；
- 高估值下的预期差。

权重倾向：

```text
成长 > 财报催化剂 > 技术趋势 > 估值绝对便宜
```

常见误判：

- 用传统低 PE 框架过早否定高成长；
- 忽略财报预期已经过满；
- 在波动率高位追价。

### dividend_defensive_pm.md

适用：

- 高股息；
- 电力；
- 公用事业；
- 红利 ETF；
- 现金流稳定型公司。

关注：

- 股息率；
- 分红可持续性；
- 经营现金流覆盖；
- 负债结构；
- 利率环境；
- 回撤控制。

权重倾向：

```text
现金流质量 > 估值安全垫 > 股息可持续 > 短期动量
```

常见误判：

- 把短期弱动量误判为基本面恶化；
- 忽略高派息背后的负债压力；
- 在利率上行期高估红利资产估值。

### cyclical_resources_pm.md

适用：

- 煤炭；
- 石油；
- 有色；
- 大宗商品；
- 资源周期股。

关注：

- 商品价格周期；
- 供需缺口；
- 库存周期；
- 政策和资本开支；
- 周期顶部低 PE 陷阱。

权重倾向：

```text
行业周期位置 > 价格趋势 > 盈利弹性 > 静态 PE
```

常见误判：

- 在周期顶部相信低 PE；
- 忽略库存拐点；
- 把短期商品反弹误判为周期反转。

### hk_liquidity_pm.md

适用：

- 港股；
- 中概；
- 港股互联网；
- 低估值但受流动性压制的标的。

关注：

- 南向资金；
- 港股整体风险偏好；
- 流动性折价；
- ADR / A-H 折溢价；
- 政策与监管预期；
- 成交量是否支持估值修复。

权重倾向：

```text
流动性与风险偏好 > 估值折价 > 技术结构 > 单日反弹
```

常见误判：

- 把便宜当成上涨理由；
- 忽略成交量不足；
- 在政策预期未确认时过早押注修复。

### options_flow_trader.md

适用：

- 美股；
- 有期权链数据的标的；
- 财报和事件驱动交易。

关注：

- OI 变化；
- put/call ratio；
- max pain；
- gamma wall；
- IV rank；
- 财报和事件前波动率定价。

权重倾向：

```text
波动率定价 > Gamma 结构 > 价格关键位 > 基本面长期观点
```

常见误判：

- 把 max pain 当成确定方向；
- 忽略 IV crush；
- 只看 call OI 不看价格位置和期限结构。

## Profile 选择机制

初期可以手工维护：

```text
data/<symbol>/symbol_profile.json
```

示例：

```json
{
  "symbol": "NVDA.US",
  "market": "US",
  "asset_type": "equity",
  "sector": "semiconductor",
  "style_profile": "tech_growth_pm",
  "optional_profiles": ["options_flow_trader"]
}
```

后续由脚本自动生成：

```text
scripts/build_analysis_packet.py
```

## 主 Agent 调度变化

主 agent 在调度 worker 时传入：

```text
symbol
profile_used
required_skills
optional_skills
```

worker 输出：

```json
{
  "profile_used": "tech_growth_pm",
  "profile_effect": {
    "growth_weight_adjusted": true,
    "valuation_weight_down": true
  }
}
```

## 验收标准

- 至少建立 3 个 profiles；
- PM / reasoning agent 调用时必须记录 `profile_used`；
- 同一 worker 在不同 profile 下能体现权重差异；
- profile 不重复通用方法论；
- profile 不覆盖全局 rules。

## 风险与控制

### 风险：profile 变成另一个大 prompt

控制：

- 每个 profile 控制在 80 行以内；
- 只写差异化 mandate；
- 不重复 skills 中的方法。

### 风险：profile 误选

控制：

- 初期允许手工覆盖；
- `analysis_packet.json` 记录 profile 来源；
- PM agent 可在输出中标注 profile 不适配风险。

## 交接给下一阶段

Phase 3 结束后，Phase 4 agent 应读取：

```text
docs/agent-modernization-phase-3-profiles-mandates.md
agents/profiles/*.md
agents/skills/*.md
```

然后建设 typed artifacts 和 validator，让 profile 影响结果可以被结构化记录。

