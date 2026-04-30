# Market Main Agent

## 执行契约

- 当用户说 `分析 <symbols>`、`更新 <symbols>`，或提供仅包含标的的任务文件时，默认执行**完整三阶段**，不要求用户补充“生成报告”“同步飞书”等细节。
- 除非遇到真实阻塞，否则不得在阶段一或阶段二提前结束。

## 读取

1. `agents/policies/common_rules.md`
2. `agents/policies/runtime_contract.md`
3. `agents/policies/trading_playbook.md` ← 所有分析类 worker 的方法论来源
4. `agents/policies/report_specs.md`
5. `agents/learned_rules.md`（位阶最高）

## Workers

- `agents/workers/data_agent.md`
- `agents/workers/fundamental_master_agent.md`
- `agents/workers/strategy_agent.md`（技术面分析，在进入 reasoning 前先跑一次以生成 narrative）
- `agents/workers/reasoning_agent.md`
- `agents/workers/execution_agent.md`

## 触发

- `分析 <symbols>`
- `更新 <symbols>`

## 完成定义

每个标的必须完成：

1. `deduction/<symbol>/fundamental_analysis_*.md`
2. `deduction/<symbol>/deduction_*.md`
3. `report/<symbol>/report_*.md`
4. 若存在 `.config/feishu_sync_config.json`，必须尝试飞书同步

最终答复必须返回：

- 标的
- 状态
- 报告路径
- 飞书同步状态
- 失败或降级原因

## 编排

### 阶段 0：运行状态初始化

1. 为每次完整市场分析创建运行清单：
```bash
.venv/bin/python scripts/pipeline_state.py create --symbols <comma_symbols> --run-id <yyyy-mm-dd_HHMMSS>
```
2. 清单路径固定为 `data/_runs/<run_id>/run_manifest.json`。
3. 若用户要求续跑或存在未完成 run，优先读取该 manifest，只补跑 `failed/degraded/pending` 阶段；已 `ok` 且产物仍存在的阶段不得重复生成。
4. 每个 worker 完成后，将其 JSON 结果保存到 `data/_runs/<run_id>/worker_results/<symbol>_<phase>.json`（如可用），先执行：
```bash
.venv/bin/python scripts/validate_worker_result.py data/_runs/<run_id>/worker_results/<symbol>_<phase>.json
```
5. 校验通过后再更新 manifest：
```bash
.venv/bin/python scripts/pipeline_state.py update \
  --manifest data/_runs/<run_id>/run_manifest.json \
  --symbol <symbol> --phase <phase> --status <ok|degraded|failed> \
  --output-file <artifact_path>
```

### 阶段一：数据准备

1. 按市场分组并行调度 Data Agent，每实例最多 4 标的。
2. 并行调度 Fundamental Agent。
3. 对每标的执行：
```bash
.venv/bin/python scripts/calc_indicators.py --symbol <symbol> --periods 1h,1d,1w
.venv/bin/python scripts/extract_llm_context.py --symbol <symbol>
```
4. 门禁：
```bash
.venv/bin/python scripts/verify_data_freshness.py --symbols <comma_symbols> --critical-only
```
5. FAIL 仅补拉失败标的，最多 2 轮。
6. 若 LongPort 核心数据调用在重试后仍失败，该标的立即标记 `failed`，中断后续阶段，并明确告知用户“无法通过 LongPort 获取数据”。
7. 记录数据质量摘要。
8. 阶段一结束后**不得直接输出最终结论**；必须继续进入阶段二，除非遇到真实阻塞。

### 阶段一.5：规则快照与方法论校验

进入阶段二前必须确认：

1. `agents/learned_rules.md` 存在且非空 —— 缺失时全局标记 `degraded`，暂停推理。
2. `agents/policies/trading_playbook.md` 存在且非空 —— 缺失时全局标记 `degraded`。
3. 每个标的的 `data/<symbol>/llm_context.md` 与 `signals_summary.json` 齐全。

### 阶段一.75：技术面分析（Strategy narrative 预生成，可选但推荐）

对每个标的按需调度 `strategy_agent`：
- 输出：`signals_summary.json` 追加 `narrative` 字段。
- 推理阶段将优先读取 narrative，可显著减少重复分析。
- 并行上限与阶段二一致（每批 4）。

### 阶段二：推理

- 固定 `1标的=1Agent`。
- 每批最多并行 4。
- 输入白名单：
  - `data/<symbol>/llm_context.md`
  - `data/<symbol>/signals_summary.json`（含 narrative）
  - `deduction/<symbol>/fundamental_analysis_*.md` 最新
  - `agents/policies/trading_playbook.md`
  - `agents/learned_rules.md`
  - `deduction/<symbol>/review_*.md` 最新（可选）
- 阶段二结束后，若 Markdown 文件尚未实际写入 `deduction/<symbol>/`，视为阶段二未完成。
- Reasoning Agent 必须完成"六步决策链"（见 `workers/reasoning_agent.md`），缺任一步直接 `failed` 或 `degraded`。

### 阶段三：执行

- 固定 `1标的=1Agent`。
- 每批最多并行 4。
- 输入白名单：
  - `deduction/<symbol>/deduction_*.md` 最新
  - `deduction/<symbol>/fundamental_analysis_*.md` 最新
  - `data/<symbol>/signals_summary.json`
  - `.config/feishu_sync_config.json`
- 阶段三结束后，若本地 `report/<symbol>/report_*.md` 不存在，则整个标的任务不能标记为完成。
- 若飞书配置存在，则默认必须尝试同步；同步失败可降级，但不能跳过而不说明。

## 汇总

按 `runtime_contract` 返回 JSON 汇总。
