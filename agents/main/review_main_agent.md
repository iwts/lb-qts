# Review Main Agent

## 读取

1. `agents/policies/common_rules.md`
2. `agents/policies/runtime_contract.md`
3. `agents/policies/report_specs.md`
4. `agents/workers/review_agent.md`

## 触发

- `复盘 <symbols>`

## 执行

1. 解析显式传入的标的。
2. 按标的调度 `review_agent`，每批最多 4。
3. 聚合各标的 JSON 结果。

## 最终输出

- 每标的复盘结论
- 新增规则候选
- 废弃规则候选
- 质量统计
