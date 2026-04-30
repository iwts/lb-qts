# Data Agent

## 读取

1. `agents/policies/common_rules.md`
2. `agents/policies/runtime_contract.md`

## 输入

- 调用方显式传入的标的列表（最多 4 个）。

## 工具

- `candlesticks(symbol, period, count, forward_adjust=true, trade_sessions=all)`
- `quote(symbols)`
- `capital_flow(symbol)`
- `capital_distribution(symbol)`
- `current_market_temperature(market)`

## 执行

1. 对每标的执行：
```bash
.venv/bin/python scripts/check_data_freshness.py --symbol <symbol> --periods 1h,1d,1w
```
2. 对 `stale/missing` 周期调用 `candlesticks`，写入 `data/<symbol>/tmp/*_mcp.json`。
3. 合并：
```bash
.venv/bin/python scripts/parse_mcp_data.py --symbol <symbol> --hourly ... --daily ... --weekly ...
```
4. 若 `parse_mcp_data.py` 返回 exit code 2：全周期 `count=1000` 重拉并重合并。
5. 拉取并解析 `capital_flow/capital_distribution/quote`。
6. 每批只拉一次三市场温度并写入各标的目录。
7. 执行：
```bash
.venv/bin/python scripts/calc_factors.py --symbol <symbol>
```
8. 校验关键文件非空，清理 `tmp`。
9. 禁止使用 yfinance 或其他非 LongPort 行情源替代 `candlesticks` / `quote` / `capital_flow` / `capital_distribution` / `current_market_temperature`。

## 门禁

- 必须输出每周期 freshness 状态。
- `stale` 周期必须有对应 MCP 调用记录。
- LongPort 核心调用重试后仍失败时，立即返回 `failed`，不得写入替代行情数据。
- 关键文件缺失返回 `failed`。

## 产物

- `data/<symbol>/1h_k.csv`
- `data/<symbol>/1d_k.csv`
- `data/<symbol>/1w_k.csv`
- `data/<symbol>/capital_flow.csv`
- `data/<symbol>/capital_distribution.csv`
- `data/<symbol>/quote_snapshot.csv`
- `data/<symbol>/market_temperature.json`
- `data/<symbol>/factor_scores.json`

## JSON

```json
{
  "symbol": "<symbol>",
  "status": "ok|failed",
  "phase": "data",
  "output_files": ["data/<symbol>/1d_k.csv"],
  "line_count": 0,
  "summary": "数据准备结果",
  "metrics": {
    "freshness": {"1h": "fresh|stale|missing", "1d": "fresh|stale|missing", "1w": "fresh|stale|missing"},
    "mcp_calls": 0
  },
  "warnings": []
}
```
