# Phase 5：DAG 编排与冲突处理

## 目标

把 prompt 驱动的线性流程升级为显式 DAG，减少主 agent 自由发挥空间，并建立结构化冲突处理。

Phase 5 不要求马上引入 LangGraph。可以先基于现有 `pipeline_state.py` 和 run manifest 扩展 DAG 节点。

## 当前问题

现有流程虽然有阶段，但依赖主 agent 按 prompt 自觉执行：

```text
阶段一 -> 阶段二 -> 阶段三
```

问题：

- 中间节点状态不够细；
- 失败恢复粒度偏粗；
- PM 与 analyst 的依赖关系不够显式；
- 基本面、技术面、期权面冲突时缺少结构化处理；
- 主 agent 容易被迫阅读长文判断是否进入下一步。

## 目标 DAG

```text
create_run
  -> fetch_market_data
  -> fetch_fundamental_data
  -> calculate_indicators
  -> build_analysis_packet
  -> fundamental_view
  -> technical_view
  -> optional_options_view
  -> pm_decision
  -> validate_pm_decision
  -> execution_report
  -> sync_feishu
  -> record_prediction
```

Review 旁路：

```text
completed_predictions
  -> evaluate_prediction
  -> review_attribution
  -> rule_candidate
  -> learned_rules_update
```

## Run Manifest 扩展

建议将 manifest 从阶段级扩展到节点级。

示例：

```json
{
  "run_id": "2026-05-01_210000",
  "symbols": ["NVDA.US", "0700.HK"],
  "nodes": {
    "NVDA.US": {
      "fetch_market_data": {"status": "ok", "output_files": []},
      "fundamental_view": {"status": "ok", "output_files": []},
      "technical_view": {"status": "ok", "output_files": []},
      "pm_decision": {"status": "degraded", "warnings": []}
    }
  }
}
```

## 并发策略

沿用现有原则：

- 数据阶段可按市场分组，每 agent 最多 4 标的；
- 推理阶段固定 `1 标的 = 1 agent`；
- 每批最多并行 4；
- 标的上下文隔离。

新增原则：

- 同一标的内，`fundamental_view` 和 `technical_view` 可以并行；
- `pm_decision` 必须等待 required views；
- `options_view` 仅美股或存在期权数据时启用；
- `execution_report` 必须等待 `pm_decision` validator 通过；
- review 不阻塞当日分析。

## 冲突类型

结构化记录冲突：

```text
fundamental_bullish_technical_bearish
fundamental_bearish_technical_strong_long
short_term_long_long_term_short
options_bearish_price_breakout
learned_rule_conflict
rr_failed_but_direction_high
data_freshness_mismatch
```

## 冲突处理等级

### Level 1：轻冲突

PM agent 在 `pm_decision.json` 中解释。

适用：

- 技术面短期偏多，基本面中性；
- 基本面强，但短期动量未确认。

### Level 2：中冲突

触发 `agents/skills/conflict_resolution.md`。

适用：

- 基本面 bullish + 技术面 bearish；
- 港股估值便宜但流动性持续恶化；
- 期权流偏空但价格趋势偏多。

### Level 3：重冲突

自动降级为 `neutral` 或触发 review。

适用：

- 多空证据差异 <10 分；
- PM 方向与 learned_rules 明显冲突；
- RR 不达标但仍输出交易计划。

### Level 4：硬冲突

validator 直接 failed。

适用：

- stop 方向错误；
- target 方向错误；
- 必需产物缺失；
- 数据过期仍输出强结论；
- LongPort 核心数据失败后切换其他源。

## Conflict JSON

建议 PM 输出：

```json
{
  "conflicts": [
    {
      "type": "fundamental_bullish_technical_bearish",
      "level": 2,
      "resolution": "以日线空排为短期主导，基本面只限制做空仓位",
      "effect_on_decision": "direction changed from long to neutral"
    }
  ]
}
```

## 主 Agent 行为

主 agent 只处理状态：

```text
1. 检查 DAG 依赖是否满足
2. 调度可运行节点
3. 调 validator
4. 根据冲突等级决定继续、降级、重跑或 failed
5. 更新 manifest
```

不做：

- 不自行改交易方向；
- 不读完整报告推翻 PM；
- 不跨标的读取上下文。

## 验收标准

- manifest 能表达节点级状态；
- 任一节点失败不会污染其他标的；
- 可从中间节点恢复；
- `pm_decision.json` 有结构化 conflicts 字段；
- Level 4 硬冲突能被 validator 阻断；
- 主 agent 不靠口头总结判断流程完成。
- 必须运行 baseline agent 并得到 `PASS`，报告写入 `data/_baseline/phase5-after/baseline_agent_report.md`：
```bash
.venv/bin/python test/baseline_agent/run.py --phase 5 --base-label phase4-after --strict
```

## 风险与控制

### 风险：DAG 工程化过重

控制：

- 先扩展 `pipeline_state.py`；
- 不急于引入 LangGraph；
- DAG 节点先覆盖关键路径，不追求全量。

### 风险：冲突过多导致全部 neutral

控制：

- 冲突分级；
- 只有 Level 3/4 才强制降级或 failed；
- PM 可解释 Level 1/2 冲突并保留方向。

## 交接给下一阶段

Phase 5 结束后，Phase 6 agent 应读取：

```text
docs/agent-modernization-phase-5-dag-conflict-routing.md
data/_baseline/phase5-after/baseline_agent_report.md
data/_runs/<run_id>/run_manifest.json
deduction/<symbol>/pm_decision_*.json
report/<symbol>/execution_summary_*.json
data/performance/predictions.csv
```

然后建设后验 review 与规则进化机制。
