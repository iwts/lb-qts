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

位阶约束：

```text
learned_rules.md > policies/trading_playbook.md > policies/report_specs.md > agents/profiles/*.md > workers/*.md
```

profile 只能调整关注点、权重和风险敏感度，不能覆盖硬性门禁。例如 RR、stop 方向、数据新鲜度、Longbridge 数据源约束、报告格式和 worker JSON 协议仍由 policies / learned_rules 决定。

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

Phase 3 必做最小集：

```text
tech_growth_pm.md
dividend_defensive_pm.md
hk_liquidity_pm.md
```

Phase 3 推荐扩展集：

```text
cyclical_resources_pm.md
options_flow_trader.md
```

其余 `bank_financial_pm.md`、`healthcare_quality_pm.md`、`etf_allocation_pm.md` 暂列 backlog。这样既满足最小闭环，也避免首轮 profile 数量过多导致选择成本上升。

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
  "optional_profiles": ["options_flow_trader"],
  "profile_source": "manual",
  "profile_confidence": 0.9
}
```

### Profile Resolution Contract

Phase 3 不要求立即建设完整 `analysis_packet.json`，但必须先稳定 profile 解析产物，供主 agent 传给 worker。

当前 Phase 3 落地脚本：

```bash
.venv/bin/python scripts/resolve_profile.py --symbol <symbol> --write
```

默认退出码语义：

- `ok` / `degraded`：命令返回 0，调用方继续读取 JSON `status` 决定是否降级；
- JSON 非法等输入错误：命令返回 1；
- 需要 shell 级硬门禁时追加 `--strict`，此时 `degraded` 返回 2。

该脚本写入：

```text
data/<symbol>/profile_resolution.json
```

最小解析输出：

```json
{
  "symbol": "NVDA.US",
  "status": "ok|degraded",
  "profile_used": "tech_growth_pm",
  "optional_profiles": ["options_flow_trader"],
  "profile_file_paths": [
    "agents/profiles/tech_growth_pm.md",
    "agents/profiles/options_flow_trader.md"
  ],
  "profile_source": "manual|rule|default",
  "profile_confidence": 0.9,
  "profile_warnings": []
}
```

解析规则：

- `style_profile` 是 primary profile，必须且只能有一个；
- `optional_profiles` 是 overlay profile，最多 2 个；
- overlay 只能补充关注点和风险提示，不得推翻 primary 的核心 mandate；
- 若 primary 与 overlay 权重冲突，PM 必须在输出中说明冲突处理；
- 找不到 profile 文件时，当前标的至少 `degraded`，不得默默回落到 `default`；
- 未配置 `symbol_profile.json` 时允许使用规则推断，但必须写明 `profile_source: "rule"`；
- 无法可靠推断时使用 `profile_used: "default"`，同时写入 `profile_warnings`。

后续 Phase 4/5 可将上述字段并入：

```text
scripts/build_analysis_packet.py
```

和：

```text
data/<symbol>/analysis_packet.json
```

在 Phase 3 结束前，不把 `analysis_packet.json` 作为硬依赖，避免与 Phase 4 typed artifacts 责任重叠。

## 主 Agent 调度变化

主 agent 在调度 worker 时传入：

```text
symbol
profile_used
optional_profiles
profile_file_paths
profile_source
required_skills
optional_skills
```

阶段二/三输入白名单在 Phase 3 实施时必须增加：

```text
data/<symbol>/symbol_profile.json
agents/profiles/<profile_used>.md
agents/profiles/<optional_profile>.md
```

PM / reasoning agent 必须实际读取 profile 文件，不能只接收 profile 名称。

worker 输出：

```json
{
  "profile_used": "tech_growth_pm",
  "profile_effect": {
    "weight_bias_applied": {
      "growth": "up",
      "valuation_absolute_cheapness": "down",
      "earnings_catalyst": "up"
    },
    "hard_concerns_triggered": [
      "财报预期已经过满",
      "事件前 IV 处于高位"
    ],
    "preferred_setups_considered": [
      "earnings_gap_follow_through",
      "high_base_breakout"
    ],
    "profile_not_applicable_risk": "low"
  },
  "warnings": []
}
```

`profile_effect` 的要求：

- 必须描述 profile 如何改变证据权重，而不是只记录布尔值；
- 若未发生权重差异，必须解释原因；
- hard concern 被触发时，只能压制结论或降低仓位，不能绕过全局规则；
- `profile_not_applicable_risk` 为 `medium|high` 时，当前 worker 至少 `degraded`。

## 验收标准

- 至少建立 3 个 profiles；
- PM / reasoning agent 调用时必须记录 `profile_used`；
- PM / reasoning agent 必须读取对应 `agents/profiles/*.md`；
- 同一 worker 在不同 profile 下能体现权重差异；
- profile 不重复通用方法论；
- profile 不覆盖全局 rules。
- 标准回归标的 profile 映射必须可解释：
  - `NVDA.US -> tech_growth_pm`，可选 `options_flow_trader`；
  - `0700.HK -> hk_liquidity_pm`；
  - `600900.SH -> dividend_defensive_pm`。
- profile 文件必须满足模板章节完整、文件存在、每个文件不超过 80 行。
- 必须运行 baseline agent 并得到 `PASS`，报告写入 `data/_baseline/phase3-after/baseline_agent_report.md`：
```bash
.venv/bin/python test/baseline_agent/run.py --phase 3 --base-label phase2-after --strict
```

必须运行轻量校验：

```bash
.venv/bin/python scripts/validate_profiles.py
```

职责：

- 校验 `agents/profiles/*.md` 是否存在；
- 校验必须章节：`Mandate`、`Evidence Priority`、`Weight Bias`、`Hard Concerns`、`Preferred Setups`、`Common Mistakes`；
- 校验每个 profile 行数不超过 80；
- 校验 `data/<symbol>/symbol_profile.json` 中的 profile 文件存在；
- 校验标准回归标的的 profile 映射。

必须运行真实 worker profile-effect 校验：

```bash
.venv/bin/python scripts/validate_phase3_profile_effect.py \
  --symbols NVDA.US,600900.SH \
  --phase reasoning \
  --run-id <run_id>
```

职责：

- 校验真实 `data/_runs/<run_id>/worker_results/<symbol>_reasoning.json` 能通过 worker result 合约；
- 校验至少 2 个非 default profile；
- 校验同一 worker phase 下 `profile_effect.weight_bias_applied` 至少有 2 套不同权重变化；
- 校验 worker result 与 `data/<symbol>/profile_resolution.json` 中的 profile 解析结果一致；
- 校验对应 Markdown 产物包含 Profile 段、权重影响和 hard concerns。

baseline agent 只能证明核心链路未退化，不能单独证明 profile 生效；Phase 3 完成必须同时提供 profile 文件校验和真实 worker profile-effect 校验结果。

## 风险与控制

### 风险：profile 变成另一个大 prompt

控制：

- 每个 profile 控制在 80 行以内；
- 只写差异化 mandate；
- 不重复 skills 中的方法。

### 风险：profile 误选

控制：

- 初期允许手工覆盖；
- `symbol_profile.json` 或 Phase 4 的 `analysis_packet.json` 记录 profile 来源；
- PM agent 可在输出中标注 profile 不适配风险。

### 风险：只记录 profile 名称但不影响结论

控制：

- worker 输出必须包含结构化 `profile_effect`；
- 至少用 2 个不同 profile 的同一 worker 输出样例证明权重差异；
- validator 或 profile 校验脚本至少检查 profile 文件存在与章节完整；
- PM / reasoning agent 输出中必须说明 primary profile 的 hard concern 是否触发。

## 交接给下一阶段

Phase 3 结束后，Phase 4 agent 应读取：

```text
docs/agent-modernization-phase-3-profiles-mandates.md
data/_baseline/phase3-after/baseline_agent_report.md
agents/profiles/*.md
agents/skills/*.md
data/<symbol>/symbol_profile.json
```

然后建设 typed artifacts 和 validator，让 profile 影响结果可以被结构化记录。
