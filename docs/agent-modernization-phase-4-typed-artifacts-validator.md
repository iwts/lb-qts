# Phase 4：Typed Artifacts 与 Validator

## 目标

把“长 Markdown 报告”从主监督对象降级为人类阅读产物，系统内部监督以结构化 JSON 为主。

Phase 4 是整个现代化方案的关键阶段。没有 typed artifacts，主 agent 和 review agent 仍然只能阅读长文，监督成本高且不稳定。

## 当前问题

如果主 agent 依赖 Markdown 判断质量，会遇到：

- token 成本高；
- 容易被漂亮文风误导；
- 难以自动识别 RR 错误；
- 难以校验 stop 方向；
- 难以统计证据数量；
- review agent 做后验统计困难。

## 设计原则

```text
Markdown 给人看
JSON 给系统看
Validator 给风控看
```

主 agent 的监督逻辑应变成：

```text
读取 worker JSON
  -> 调 validator
  -> 校验失败则 failed/degraded
  -> 校验通过再进入下一阶段
```

## 推荐目录

```text
schemas/
  worker_result.schema.json
  analysis_packet.schema.json
  fundamental_view.schema.json
  technical_view.schema.json
  options_view.schema.json
  pm_decision.schema.json
  execution_summary.schema.json

scripts/
  build_analysis_packet.py
  validate_typed_artifact.py
  validate_trade_plan.py
```

如果暂时不引入 `schemas/` 目录，也可以先把 schema 内置在 validator 脚本中，但长期建议独立。

## 核心 Typed Artifacts

### analysis_packet.json

由数据阶段生成，作为下游统一输入。

路径：

```text
data/<symbol>/analysis_packet.json
```

示例：

```json
{
  "symbol": "NVDA.US",
  "as_of": "2026-05-01",
  "market": "US",
  "asset_type": "equity",
  "profile": "tech_growth_pm",
  "data_freshness": {
    "1d": "ok",
    "1h": "ok",
    "1w": "ok",
    "fundamental": "ok"
  },
  "input_files": {
    "llm_context": "data/NVDA.US/llm_context.md",
    "signals_summary": "data/NVDA.US/signals_summary.json",
    "fundamental": "data/NVDA.US/fundamental.json",
    "earnings": "data/NVDA.US/earnings.json"
  }
}
```

### fundamental_view.json

路径：

```text
deduction/<symbol>/fundamental_view_<yyyy_mm_dd>_<seq>.json
```

示例：

```json
{
  "symbol": "NVDA.US",
  "phase": "fundamental",
  "profile_used": "tech_growth_pm",
  "final_score": 78,
  "direction": "bullish",
  "confidence": 0.72,
  "bull_evidence": [],
  "bear_evidence": [],
  "key_risks": [],
  "catalysts": [],
  "skills_used": ["fundamental_quality", "growth_analysis", "valuation_context"],
  "rules_applied": [],
  "markdown_report": "deduction/NVDA.US/fundamental_analysis_2026_05_01_01.md"
}
```

### technical_view.json

路径：

```text
deduction/<symbol>/technical_view_<yyyy_mm_dd>_<seq>.json
```

示例：

```json
{
  "symbol": "NVDA.US",
  "phase": "technical",
  "regime": "strong_trend_up",
  "mtf_resonance": "aligned_long",
  "short_term_score": 72,
  "long_term_score": 76,
  "support_levels": [],
  "resistance_levels": [],
  "feasible_entries": [],
  "skills_used": ["market_regime", "multi_timeframe_resonance"],
  "warnings": []
}
```

### pm_decision.json

路径：

```text
deduction/<symbol>/pm_decision_<yyyy_mm_dd>_<seq>.json
```

示例：

```json
{
  "symbol": "NVDA.US",
  "phase": "pm_decision",
  "profile_used": "tech_growth_pm",
  "direction": "long",
  "rating": "推荐做多",
  "short_score": 72,
  "long_score": 78,
  "evidence_balance": {
    "bull_score": 74,
    "bear_score": 42,
    "difference": 32
  },
  "trade_plans": [
    {
      "name": "主计划",
      "side": "long",
      "entry": 0,
      "stop": 0,
      "target_1": 0,
      "target_2": 0,
      "rr_target_1": 0,
      "position_size": 0,
      "invalidation": ""
    }
  ],
  "skills_used": ["market_regime", "long_short_thesis", "risk_first_trade_plan"],
  "rules_applied": [],
  "markdown_report": "deduction/NVDA.US/deduction_2026_05_01_01.md"
}
```

### execution_summary.json

路径：

```text
report/<symbol>/execution_summary_<yyyy_mm_dd>_<seq>.json
```

示例：

```json
{
  "symbol": "NVDA.US",
  "phase": "execution",
  "report_file": "report/NVDA.US/report_2026_05_01_01.md",
  "feishu_sync": "ok|degraded|skipped",
  "prediction_recorded": true,
  "source_pm_decision": "deduction/NVDA.US/pm_decision_2026_05_01_01.json"
}
```

## Validator 设计

### validate_typed_artifact.py

职责：

- JSON 可解析；
- 必填字段存在；
- enum 合法；
- 引用文件存在；
- `markdown_report` 存在且非空；
- `skills_used` 非空；
- `profile_used` 存在；
- `rules_applied` 字段存在。

### validate_trade_plan.py

职责：

- `trade_plans` 数量达标；
- long stop < entry；
- short stop > entry；
- `rr_target_1 >= 1.5`；
- target 方向正确；
- position_size 合理；
- invalidation 非空。

## 主 Agent 行为变化

Phase 4 后，主 agent 不再主要阅读 deduction Markdown，而是：

```text
1. 等待 worker 输出 typed JSON
2. 调用 validator
3. validator 通过后更新 manifest
4. validator 失败则重试当前 worker 或标记 failed/degraded
5. execution 阶段再读取 pm_decision 生成正式报告
```

## 验收标准

- 每个关键 worker 至少输出一个 typed JSON；
- validator 能独立发现 stop 方向错误；
- validator 能发现 RR 不达标；
- Markdown 缺失时直接 failed；
- 主流程可以只凭 JSON 判断阶段状态；
- review agent 可以读取 `pm_decision.json` 做后验统计。

## 风险与控制

### 风险：agent 生成 JSON 不稳定

控制：

- schema 简洁；
- 先写 JSON，再写 Markdown；
- validator 输出明确错误路径；
- 失败时只重写 JSON，不重跑全部流程。

### 风险：JSON 和 Markdown 不一致

控制：

- execution 以 `pm_decision.json` 为准；
- Markdown 只允许解释 JSON，不允许改变方向；
- validator 检查 report 是否引用 source decision。

## 交接给下一阶段

Phase 4 结束后，Phase 5 agent 应读取：

```text
docs/agent-modernization-phase-4-typed-artifacts-validator.md
data/<symbol>/analysis_packet.json
deduction/<symbol>/*_view_*.json
deduction/<symbol>/pm_decision_*.json
```

然后把流程组织成显式 DAG 和冲突处理机制。

