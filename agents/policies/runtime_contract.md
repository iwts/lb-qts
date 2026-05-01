# Agent Runtime Contract

## 执行前置

1. 必须先读取 `agents/policies/common_rules.md`。
2. 仅处理调用方显式传入的标的或任务对象。
3. 禁止跨标的读取原始数据，除非任务定义明确允许。
4. 涉及交易结论与评分的任务，必须读取 `agents/learned_rules.md`。

## 上下文策略

1. 优先读取精简上下文文件，避免直接读取大体积原始 CSV。
2. 单 Agent 只加载完成任务所需最小文件集。
3. 当输入缺失时，先尝试按既有脚本补齐；涉及行情/报价/资金流/市场温度的核心市场数据时，仅允许使用 Longbridge 官方路径补齐，重试后仍失败则直接返回 `failed`。官方路径包括 hosted MCP（`mcp__longbridge__`）、`longbridge` CLI、Longbridge SDK。

## 执行策略

1. 先做可验证的数据准备，再做推理与写入。
2. 写入本地文件后必须做存在性与非空校验。
3. 可重试错误必须重试；Longbridge 核心调用重试后仍失败时，当前标的直接 `failed`，不得切换到其他行情源继续执行。
4. 当基础流程与 `learned_rules` 冲突时，以 `learned_rules` 为准。
5. 若主任务定义包含阶段二/三产物，则在这些产物未落盘前，不得把任务视为完成。
6. “口头总结”“终端输出”“数据已刷新”都不能替代必需的 Markdown 产物。
7. 新的批量运行必须创建 `data/_runs/<run_id>/run_manifest.json`；每个阶段完成后用结构化结果更新 manifest，失败重跑时优先读取 manifest 只补跑失败/缺失阶段。
8. Worker 返回 JSON 应先通过 `scripts/validate_worker_result.py` 校验，再进入下一阶段；校验失败时当前阶段至少 `degraded`，关键产物缺失时 `failed`。
9. Execution 阶段若产出结构化 execution summary，应调用 `scripts/record_prediction.py` 追加 `data/performance/predictions.csv`，供 Review Agent 做 N+1/N+5/N+20 后验统计。

## 交易员质量门禁

> 方法论细节见 `agents/policies/trading_playbook.md`，本节只列"刚性门禁"。

1. 推理/执行报告必须同时包含 long 与 short 双侧评估（至少各 3 条量化证据）。
2. 推理报告必须显式完成"交易员六步决策链"：体制识别 → 多周期共振 → 双侧证据 → 机会类型选择 → 交易计划（≥2 套）→ 规则引用 → 最终方向与失效条件。
3. 推理/执行报告必须包含至少 2 套交易计划，且每套计划具备 `entry/stop/target_1/target_2/RR/position_size/invalidation/time_horizon`。
4. 每套计划必须通过：
   - `|entry − stop| ≥ 1.5 × 日线 ATR`（除非结构止损且 ≥1× ATR 并解释）
   - 做多 stop < entry；做空 stop > entry
   - `RR_at_target_1 ≥ 1.5`
   - 两档止盈（保守 + 趋势）
5. 若 `best_rr < 1.5`、多空差异 <10 分、或证据不足 → 强制输出 `neutral`，不得强行给方向。
6. 报告必须含"失效条件（invalidation）"。
7. 报告禁止重复清单/同义改写凑行，C 级段落（仅复述数据）占比 >30% → `degraded`。
8. 报告需给出可追溯数值证据；无法追溯时标记 `degraded`。
9. 基本面报告必须给出 `fundamental_direction` 与 Technical×Fundamental 整合提示，供推理阶段四象限决策（见 playbook §8）。
10. Token 预算：分析类输出中数据复述 ≤10%，分析与决策 ≥70%。

## 状态定义

- `ok`：目标完成，质量门禁通过。
- `degraded`：目标完成但存在质量缺口或部分子项失败。
- `failed`：目标未完成或关键产物不存在。
- 对 `market_main_agent` 而言，若缺少 `fundamental_analysis`、`deduction`、`report` 中任一关键产物，则至少为 `failed`。
- 本地报告已生成但飞书同步失败：`degraded`。
- 仅完成数据准备或摘要整理：`failed`。

## 统一回传协议

```json
{
  "symbol": "<标的或任务ID>",
  "status": "ok|degraded|failed",
  "phase": "data|fundamental|strategy|reasoning|execution|review|youtube",
  "output_files": ["<path>"],
  "line_count": 0,
  "summary": "一句话结果",
  "metrics": {},
  "warnings": []
}
```

- `metrics` 应包含规则执行信息（至少 `rules_applied_count`，可选 `rules_applied_ids`）。
- 若规则缺失或未应用导致结论不可信，应返回 `degraded`。
- 推理/执行阶段建议补充：
  - `trade_plans_count`
  - `best_rr`
  - `direction`
  - `numeric_evidence_count`

## 失败与降级处理

1. 单任务失败不阻塞同批其他任务。
2. 关键文件不存在时必须返回 `failed`。
3. 非关键子步骤失败时返回 `degraded` 并记录 `warnings`。
4. Longbridge K 线 / 报价 / 资金流 / 资金分布 / 市场温度任一失败且重试后仍未恢复，属于关键失败。hosted MCP 未暴露的接口应通过 `scripts/fetch_longbridge_data.py` 调用 `longbridge` CLI 补齐，不得切换到非 Longbridge 行情源。

## 编排约束

1. 并行由 Orchestrator 统一控制。
2. 阶段二/三固定 `1标的=1Agent`。
3. 每批并行上限 4。
