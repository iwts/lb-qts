# Phase 7：公司化运行模型、PM 责任制与风控否决

## 目标

把多 Agent 系统从“多个 worker 协作”升级成清晰的投研组织模型：

```text
岗位分工清楚
观点责任清楚
风控否决清楚
复盘归因清楚
```

Phase 7 解决的是治理问题，不是单个 prompt 的能力问题。

## 推荐组织模型

```text
Chief Orchestrator
  - 只负责调度、状态、并发、恢复

Data Desk
  - 数据拉取、清洗、新鲜度、数据门禁

Research Analysts
  - Fundamental Analyst
  - Technical Analyst
  - Options Flow Analyst
  - Macro / Market Temperature Analyst

Portfolio Manager
  - 负责最终方向、评分、仓位、交易计划

Risk Officer
  - 负责硬规则否决、RR、stop、仓位上限、冲突降级

Execution Publisher
  - 负责正式报告、飞书同步、prediction 记录

Review Committee
  - 负责后验统计、归因、规则进化
```

## 主 Agent 定位

主 agent 是 Chief Orchestrator。

它做：

- 解析任务；
- 创建 run manifest；
- 选择 profiles；
- 装配 required skills；
- 调度 worker；
- 调 validator；
- 处理 failed/degraded；
- 汇总结果。

它不做：

- 不生成交易观点；
- 不读长报告重新判断方向；
- 不替 PM 改交易计划；
- 不绕过 risk officer。

## PM Agent 定位

PM agent 是最终观点负责人。

它必须：

- 综合 fundamental / technical / options view；
- 判断当前体制下哪个证据更重要；
- 处理多空冲突；
- 给出最终方向；
- 给出不交易的理由；
- 给出 entry / stop / target / RR / position_size；
- 明确 invalidation；
- 承担后续 review 归因。

它不能：

- 只汇总 analyst 观点；
- 在 RR 不达标时强行输出方向；
- 忽略 learned_rules；
- 把责任推给 analyst。

## Risk Officer 定位

Risk officer 不负责方向，只负责否决。

初期可以由 validator + risk skill 实现，不一定需要独立 agent。

Risk officer 检查：

- 数据缺失；
- 数据过期；
- RR 不达标；
- stop 方向错误；
- target 方向错误；
- 仓位超限；
- learned_rules 硬冲突；
- 多空差异不足却强结论；
- 单日极端波动后未重评；
- 关键产物缺失。

Risk officer 输出：

```json
{
  "risk_status": "pass|degraded|blocked",
  "blocking_rules": [],
  "required_action": "continue|revise_pm_decision|force_neutral|failed"
}
```

## Execution Publisher 定位

Execution 只负责发布，不负责改变结论。

它可以：

- 把 PM decision 转成正式报告；
- 同步飞书；
- 记录 prediction；
- 标注同步失败。

它不能：

- 修改方向；
- 修改 entry/stop/target；
- 忽略 PM invalidation；
- 用更漂亮文案掩盖 degraded。

## Review Committee 定位

Review Committee 独立于 market main。

它做：

- 后验统计；
- 判断 PM decision 是否有效；
- 错误归因；
- rule candidate；
- deprecated rule 建议；
- profile/skill 改进建议。

它不做：

- 不参与当日交易决策；
- 不直接覆盖 learned_rules；
- 不因为单例新增硬规则。

## 责任链路

每份正式报告必须能追溯：

```text
report
  -> execution_summary.json
  -> pm_decision.json
  -> fundamental_view.json
  -> technical_view.json
  -> analysis_packet.json
  -> run_manifest.json
```

review 时按这个链路归因。

## 关键治理规则

### PM 有最终观点责任

analyst 可以提供冲突观点，但最终交易方向只能由 PM 输出。

### Risk 有否决权

任何违反硬规则的 PM decision 不能进入 execution。

### Execution 不能改观点

报告生成阶段不得改变 PM 的核心交易计划。

### Review 不污染当日流程

review 产生的是 candidate，只有升级为 active learned rule 后才影响未来分析。

## 验收标准

- 每份最终报告能追溯 PM decision；
- 每次 failed/degraded 有明确责任节点；
- 风控否决不会被 execution 覆盖；
- review 能评价 PM，而不只评价报告文风；
- 不同 profile 下的 PM 行为明显差异化；
- 主 agent 不再承担观点责任。

## 长期演进

Phase 7 稳定后，可评估：

- LangGraph：更明确的 agent graph；
- Prefect / Temporal：更强运行和恢复；
- dashboard：performance 和 review 可视化；
- portfolio layer：多标的组合相关性、仓位聚合、风险预算；
- model routing：不同任务使用不同模型。

## 最终目标状态

一次：

```text
分析 NVDA.US, 0700.HK, 600900.SH
```

应执行为：

```text
Router:
  解析标的

Orchestrator:
  创建 run_manifest
  选择 profiles:
    NVDA.US -> tech_growth_pm + optional options_flow_trader
    0700.HK -> hk_liquidity_pm
    600900.SH -> dividend_defensive_pm

Data Desk:
  拉取和校验数据
  生成 analysis_packet.json

Analysts:
  生成 fundamental_view.json
  生成 technical_view.json
  可选生成 options_view.json

PM:
  加载 profile 和 required skills
  输出 pm_decision.json + deduction markdown

Risk:
  校验 RR、stop、证据、规则

Execution:
  生成正式报告
  同步飞书
  记录 prediction

Review:
  后续按 N+1/N+5/N+20 归因
  形成 rule candidates
```

这个形态下，复杂度不会消失，但会被放到正确的位置：

- 流程复杂度由 manifest / DAG 管；
- 方法复杂度由 skills 管；
- 风格差异由 profiles 管；
- 风控约束由 rules / validator 管；
- 观点责任由 PM agent 承担；
- 进化由 review agent 承担。

