# YouTube Main Agent

## 读取

1. `agents/policies/common_rules.md`
2. `agents/policies/runtime_contract.md`
3. `agents/policies/report_specs.md`
4. `agents/workers/youtube_insight_agent.md`

## 触发

- `学习博主`
- `同步博主`

## 执行

1. 调度 `youtube_insight_agent` 执行增量同步。
2. 聚合结构化 JSON 结果。

## 最终输出

- `knowledge_base.md` 更新结果
- `challenges.md` 更新结果
- 增量处理统计
