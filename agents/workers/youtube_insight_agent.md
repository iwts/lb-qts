# YouTube Insight Worker Agent

## 读取

1. `agents/policies/common_rules.md`
2. `agents/policies/runtime_contract.md`
3. `agents/policies/report_specs.md`

## 输入

- `.config/youtube_sync_config.json`（本地配置，已加入忽略文件）
- `data/youtube_insights/`

## 执行

1. 增量扫描：
```bash
.venv/bin/python scripts/sync_youtube_insights.py --action list-pending
```
2. 对未处理页面执行飞书读取并提炼内容：
```bash
lark-cli wiki nodes list --params '{"space_id":"<space_id>","parent_node_token":"<node_token>","page_size":200}'
lark-cli docs +fetch --doc <docx_url_or_token>
```
3. 标记已处理：
```bash
.venv/bin/python scripts/sync_youtube_insights.py --action mark-done --page-id <id> --blogger <name> --date <date>
```
4. 更新 `knowledge_base.md`。
5. 生成 `challenges.md`。

## 产物

- `data/youtube_insights/knowledge_base.md`
- `data/youtube_insights/challenges.md`
- `data/youtube_insights/processed_log.json`

## JSON

```json
{
  "symbol": "YOUTUBE_INSIGHTS",
  "status": "ok|degraded|failed",
  "phase": "youtube",
  "output_files": [
    "data/youtube_insights/knowledge_base.md",
    "data/youtube_insights/challenges.md",
    "data/youtube_insights/processed_log.json"
  ],
  "line_count": 0,
  "summary": "博主知识更新结果",
  "metrics": {
    "processed_pages": 0,
    "new_challenges": 0
  },
  "warnings": []
}
```
