# Data Agent

## 读取

1. `agents/policies/common_rules.md`
2. `agents/policies/runtime_contract.md`

## 输入

- 调用方显式传入的标的列表（最多 4 个）。

## 工具

- 优先使用已加载的官方 Longbridge hosted MCP（`mcp__longbridge__`）获取其已暴露的数据，例如 `quote`、`option_quote`、`option_volume`、`stock_positions`。
- hosted MCP 未暴露的核心行情数据，通过本地已登录的 `longbridge` CLI 获取，并统一走 `scripts/fetch_longbridge_data.py`：
  - K 线：`longbridge kline <symbol> --period <period> --count <count> --adjust forward --session all --format json`
  - 资金流：`longbridge capital <symbol> --flow --format json`
  - 资金分布：`longbridge capital <symbol> --format json`
  - 市场温度：`longbridge market-temp --format json`

## 执行

1. 对每标的执行：
```bash
.venv/bin/python scripts/check_data_freshness.py --symbol <symbol> --periods 1h,1d,1w
```
2. 对 `stale/missing` 周期调用 Longbridge 数据适配脚本，写入 `data/<symbol>/tmp/*_mcp.json`：
```bash
.venv/bin/python scripts/fetch_longbridge_data.py --symbol <symbol> --periods 1h,1d,1w --count <count> --fetch kline,quote,capital_flow,capital_distribution,market_temperature
```
3. 合并：
```bash
.venv/bin/python scripts/parse_mcp_data.py --symbol <symbol> --hourly ... --daily ... --weekly ...
```
4. 若 `parse_mcp_data.py` 返回 exit code 2：全周期 `count=1000` 重拉并重合并。
5. 拉取并解析 `capital_flow/capital_distribution/quote`。若 hosted MCP 能直接返回等价数据，可使用 MCP；否则使用 `scripts/fetch_longbridge_data.py` 生成兼容 JSON。
6. 每批只拉一次三市场温度并写入各标的目录。
7. 执行：
```bash
.venv/bin/python scripts/calc_factors.py --symbol <symbol>
```
8. 校验关键文件非空，清理 `tmp`。
9. 禁止使用 yfinance 或其他非 Longbridge 官方路径替代 K 线 / 报价 / 资金流 / 资金分布 / 市场温度。允许的官方路径仅限 hosted MCP、`longbridge` CLI、Longbridge SDK。

## 门禁

- 必须输出每周期 freshness 状态。
- `stale` 周期必须有对应 Longbridge MCP/CLI 调用记录。
- Longbridge 核心调用重试后仍失败时，立即返回 `failed`，不得写入替代行情数据。
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
