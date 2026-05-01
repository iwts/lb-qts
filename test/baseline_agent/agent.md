# Baseline Regression Agent

## 定位

这是一个独立的测试/基线 agent，只负责现代化改造过程中的回归保障，不参与正式投研观点生成，也不挂到 `agents/main/` 或 `agents/workers/` 的生产流水线。

## 职责

1. 自动检测本地 K 线是否过期；
2. 自动拉取回归标的最新 K 线；
3. 增量合并 K 线 CSV；
4. 重算技术指标与 LLM context；
5. 采集 baseline snapshot；
6. 与既有 baseline 做回归比较；
7. 输出可读结论，明确是否可以进入下一 Phase。

## 不做事项

- 不生成 `deduction/<symbol>/deduction_*.md`；
- 不生成 `report/<symbol>/report_*.md`；
- 不调用 reasoning / execution worker；
- 不同步飞书；
- 不修改 `agents/learned_rules.md`；
- 不参与正式交易结论。

## 默认回归标的

```text
NVDA.US
0700.HK
600900.SH
600036.SH
```

## 自动化入口

```bash
.venv/bin/python test/baseline_agent/run.py \
  --symbols NVDA.US,0700.HK,600900.SH,600036.SH \
  --base-label phase0-before \
  --candidate-label phase1-after
```

## 阶段

### 1. Refresh K-line

先执行数据门禁定位过期标的：

```bash
.venv/bin/python scripts/verify_data_freshness.py --symbols <symbols> --critical-only
```

默认只刷新过期标的。若需要强制全部刷新，运行入口增加 `--refresh-all`。

对需要刷新的标的执行：

```bash
.venv/bin/python scripts/fetch_longbridge_data.py --symbol <symbol> --periods 1h,1d,1w --count <count> --fetch kline
.venv/bin/python scripts/parse_mcp_data.py --symbol <symbol> --hourly ... --daily ... --weekly ...
```

若 `parse_mcp_data.py` 返回 `2`，表示前复权或结构漂移，自动用 `--full-count` 重新拉取并解析。

刷新后再次执行数据门禁；若仍有标的过期，再自动用 `--full-count` 对失败标的重拉一轮。

### 2. Rebuild Derived Data

对每个标的执行：

```bash
.venv/bin/python scripts/calc_indicators.py --symbol <symbol> --periods 1h,1d,1w
.venv/bin/python scripts/extract_llm_context.py --symbol <symbol>
```

### 3. Data Gate

批量执行：

```bash
.venv/bin/python scripts/verify_data_freshness.py --symbols <symbols> --critical-only
```

### 4. Sample Baseline

执行：

```bash
.venv/bin/python scripts/collect_baseline.py --symbols <symbols> --run-date <candidate-label>
```

### 5. Regression

若提供 `--base-label`，执行：

```bash
.venv/bin/python scripts/compare_baseline.py --base <base-label> --candidate <candidate-label>
```

## 输出

运行完成后写入：

```text
data/_baseline/<candidate-label>/baseline_agent_report.md
data/_baseline/<candidate-label>/baseline_agent_result.json
```

结论等级：

| 结论 | 含义 |
| --- | --- |
| `PASS` | 无回归，且采样无 failed |
| `DEGRADED` | 无回归，但存在数据门禁失败、采样 degraded 或刷新失败 |
| `FAIL` | 出现 baseline 回归或采样 failed |

## 使用原则

- 改造前先保存一个稳定 base label；
- 每次改造后生成一个新的 candidate label；
- 不直接覆盖历史 baseline；
- 只把本 agent 当作回归闸门，不把它的结论当作投资建议。
