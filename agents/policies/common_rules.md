# Common Rules

## 入口约束

1. 主流程唯一入口：`agents/main/router.md`。
2. 不得新增并行入口替代 orchestrator。
3. 运行协议以 `agents/policies/runtime_contract.md` 为准。
4. **交易分析方法论以 `agents/policies/trading_playbook.md` 为准——所有分析类 worker 必读。**
5. 报告结构与评分映射以 `agents/policies/report_specs.md` 为准。
6. 位阶顺序（冲突时由高到低）：`learned_rules.md` > `trading_playbook.md` > `report_specs.md` > `agents/profiles/*.md` > 各 worker 自身描述。
7. Profile 只能调整关注点、证据权重和风险敏感度，不得覆盖数据源、输出格式、风控门禁、评分等级或 worker JSON 协议。

## 文件系统纪律

1. 运行时不得在项目根目录创建新目录或新文件；运行产物统一落在 `data/`、`deduction/`、`report/` 及其子目录。
2. 运行时不得临时创建新的 Python 脚本；工程化能力应复用已入库的 `scripts/*.py`。
3. 禁止创建 staging/cache/payload 目录。
4. 禁止拆分 Markdown 为 chunk 文件。
5. 禁止创建 JSON payload 中间文件；唯一例外是结构化运行状态与校验产物：`data/_runs/<run_id>/`、`data/performance/`。

## MCP 临时文件规范

临时文件统一路径：`data/<symbol>/tmp/<type>_mcp.json`

命名：
- K线：`1h_mcp.json`、`1d_mcp.json`、`1w_mcp.json`
- 资金流：`capital_flow_mcp.json`
- 资金分布：`capital_dist_mcp.json`
- 报价：`quote_mcp.json`

`parse_mcp_data.py` 成功后立即清理：
```bash
rm -f data/<symbol>/tmp/*_mcp.json
```

批次结束清理残留：
```bash
rm -rf data/*/tmp/
```

## 标的入参

1. 调用方必须显式提供标的代码及中文名。
2. 仅处理显式传入标的，不从历史上下文猜测。
3. 标的不存在本地数据时可补拉，不得擅自替换标的。

## 项目路径

- 根目录：`<PROJECT_ROOT>`
- Python：`.venv/bin/python`
- 数据：`data/<symbol>/`
- 推理：`deduction/<symbol>/`
- 报告：`report/<symbol>/`

## 序号规则

1. 报告文件使用 `_<seq>` 后缀。
2. 序号由 `scripts/utils.py` 的 `next_seq()` 计算。
3. 同一天可多次生成，不覆盖历史。

## 上下文控制

1. 优先使用 `scripts/extract_llm_context.py` 生成 `data/<symbol>/llm_context.md`。
2. 禁止直接读取 `*_indicators.csv`，除非 `llm_context.md` 缺失且已记录原因。

## 报告质量纪律（交易员视角）

1. 报告必须服务交易决策，不得只做泛化描述。
2. 必须明确输出 long/short/neutral 方向与触发条件。
3. 必须提供关键价位与执行参数：`entry`、`stop`、`target`、`RR`、`position_size`。
4. 禁止使用重复句子、重复清单、模板化填充凑行数。
5. 当多空证据冲突且优势不明显时，优先输出"观望"而不是强行给单边结论。
6. **Token 预算**：分析类输出中，至少 70% 的 token 必须用于"体制识别 / 证据梳理 / 决策构造 / 风险数学"，数据复述 ≤10%。
7. **段落等级**：C 级段落（仅复述数据或泛泛描述）占比 >30% 自动 `degraded`（见 `trading_playbook.md` §10）。
8. 放弃"最低行数"作为硬性门槛，改以"信息密度"衡量质量。
