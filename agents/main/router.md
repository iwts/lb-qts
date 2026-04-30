# Main Agent Router

## 最小触发原则

- 用户提问应保持简洁，不要求用户手工声明“三阶段”“生成报告”“同步飞书”。
- 只要用户请求围绕一个或多个**明确标的**展开，默认进入完整市场分析主链路。
- 只有当用户显式说明“只看结论 / 只更新数据 / 不生成报告 / 不同步飞书”时，才允许降级为部分流程。

## 路由规则

- `学习博主` / `同步博主` → `agents/main/youtube_main_agent.md`
- `复盘 <symbols>` → `agents/main/review_main_agent.md`
- `分析 <symbols>` / `更新 <symbols>` → `agents/main/market_main_agent.md`
- 出现明确标的代码、标的文件或标的列表，且无相反限定 → `agents/main/market_main_agent.md`
- 多意图输入按顺序执行：market → review
- 未命中其他入口时，默认走 `agents/main/market_main_agent.md`

## 统一约束

1. `agents/policies/common_rules.md`
2. `agents/policies/runtime_contract.md`
3. `agents/policies/trading_playbook.md`（所有分析类 worker 的方法论来源）
4. `agents/policies/report_specs.md`
5. `agents/learned_rules.md`（位阶最高：与 playbook 冲突时以 learned_rules 为准）
