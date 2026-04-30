#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="$ROOT_DIR/.config/feishu_sync_config.json"
SYMBOL=""
REPORT_FILE=""
DEDUCTION_FILE=""
FUNDAMENTAL_FILE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/sync_feishu_docs.sh \
    --symbol AAPL.US \
    --report report/AAPL.US/report_2026_04_16_2.md \
    --deduction deduction/AAPL.US/deduction_2026_04_16_2.md \
    --fundamental deduction/AAPL.US/fundamental_analysis_2026_04_16_2.md \
    [--config .config/feishu_sync_config.json]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --symbol)
      SYMBOL="$2"
      shift 2
      ;;
    --report)
      REPORT_FILE="$2"
      shift 2
      ;;
    --deduction)
      DEDUCTION_FILE="$2"
      shift 2
      ;;
    --fundamental)
      FUNDAMENTAL_FILE="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$SYMBOL" || -z "$REPORT_FILE" || -z "$DEDUCTION_FILE" || -z "$FUNDAMENTAL_FILE" ]]; then
  usage >&2
  exit 2
fi

mkdir -p "$HOME/.lark-cli/locks"

REPORT_PATH="$ROOT_DIR/$REPORT_FILE"
DEDUCTION_PATH="$ROOT_DIR/$DEDUCTION_FILE"
FUNDAMENTAL_PATH="$ROOT_DIR/$FUNDAMENTAL_FILE"

for path in "$CONFIG_PATH" "$REPORT_PATH" "$DEDUCTION_PATH" "$FUNDAMENTAL_PATH"; do
  if [[ ! -f "$path" ]]; then
    echo "Missing file: $path" >&2
    exit 2
  fi
done

CFG_RAW="$("$ROOT_DIR/.venv/bin/python" - "$CONFIG_PATH" <<'PY'
import json, sys
from pathlib import Path

cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
parent = cfg["parent"]
layout = cfg["layout"]
sync_mode = cfg.get("sync_mode", {})
print(parent["space_id"])
print(parent["node_token"])
print(layout["symbol_page_title_template"])
print(layout["report_page_title"])
print(layout["deduction_page_title"])
print(layout["fundamental_page_title"])
print("true" if sync_mode.get("create_missing_page", True) else "false")
print(sync_mode.get("update_mode", "overwrite"))
PY
)"

SPACE_ID="$(printf '%s\n' "$CFG_RAW" | sed -n '1p')"
PARENT_NODE_TOKEN="$(printf '%s\n' "$CFG_RAW" | sed -n '2p')"
SYMBOL_TEMPLATE="$(printf '%s\n' "$CFG_RAW" | sed -n '3p')"
REPORT_TITLE="$(printf '%s\n' "$CFG_RAW" | sed -n '4p')"
DEDUCTION_TITLE="$(printf '%s\n' "$CFG_RAW" | sed -n '5p')"
FUNDAMENTAL_TITLE="$(printf '%s\n' "$CFG_RAW" | sed -n '6p')"
CREATE_MISSING="$(printf '%s\n' "$CFG_RAW" | sed -n '7p')"
UPDATE_MODE="$(printf '%s\n' "$CFG_RAW" | sed -n '8p')"
SYMBOL_TITLE="${SYMBOL_TEMPLATE/\{symbol\}/$SYMBOL}"

run_with_retry() {
  local attempt output status
  for attempt in 1 2 3; do
    if output="$("$@" 2>&1)"; then
      printf '%s' "$output"
      return 0
    fi
    status=$?
    if [[ "$attempt" -eq 3 ]]; then
      printf '%s' "$output" >&2
      return "$status"
    fi
    sleep 1
  done
}

list_children_json() {
  run_with_retry lark-cli wiki nodes list --params "{\"space_id\":\"$SPACE_ID\",\"parent_node_token\":\"$1\",\"page_size\":50}"
}

find_node_token_by_title() {
  local parent_token="$1"
  local title="$2"
  local payload
  payload="$(list_children_json "$parent_token")"
  JSON_PAYLOAD="$payload" "$ROOT_DIR/.venv/bin/python" - "$title" node_token <<'PY'
import json, os, sys

title = sys.argv[1]
field = sys.argv[2]
data = json.loads(os.environ["JSON_PAYLOAD"])
for item in data.get("data", {}).get("items", []):
    if item.get("title") == title:
        print(item.get(field, ""))
        break
PY
}

find_obj_token_by_title() {
  local parent_token="$1"
  local title="$2"
  local payload
  payload="$(list_children_json "$parent_token")"
  JSON_PAYLOAD="$payload" "$ROOT_DIR/.venv/bin/python" - "$title" obj_token <<'PY'
import json, os, sys

title = sys.argv[1]
field = sys.argv[2]
data = json.loads(os.environ["JSON_PAYLOAD"])
for item in data.get("data", {}).get("items", []):
    if item.get("title") == title:
        print(item.get(field, ""))
        break
PY
}

create_node() {
  local parent_token="$1"
  local title="$2"
  run_with_retry lark-cli wiki +node-create --space-id "$SPACE_ID" --parent-node-token "$parent_token" --obj-type docx --title "$title" >/dev/null
}

ensure_symbol_node() {
  local node
  node="$(find_node_token_by_title "$PARENT_NODE_TOKEN" "$SYMBOL_TITLE")"
  if [[ -z "$node" && "$CREATE_MISSING" == "true" ]]; then
    create_node "$PARENT_NODE_TOKEN" "$SYMBOL_TITLE"
    node="$(find_node_token_by_title "$PARENT_NODE_TOKEN" "$SYMBOL_TITLE")"
  fi
  [[ -n "$node" ]] || { echo "Failed to ensure symbol page: $SYMBOL_TITLE" >&2; exit 1; }
  printf '%s' "$node"
}

ensure_child_doc() {
  local parent_token="$1"
  local title="$2"
  local obj
  obj="$(find_obj_token_by_title "$parent_token" "$title")"
  if [[ -z "$obj" && "$CREATE_MISSING" == "true" ]]; then
    create_node "$parent_token" "$title"
    obj="$(find_obj_token_by_title "$parent_token" "$title")"
  fi
  [[ -n "$obj" ]] || { echo "Failed to ensure child page: $title" >&2; exit 1; }
  printf '%s' "$obj"
}

update_doc() {
  local doc_token="$1"
  local file_path="$2"
  run_with_retry lark-cli docs +update --doc "$doc_token" --mode "$UPDATE_MODE" --markdown "@$file_path" >/dev/null
}

SYMBOL_NODE="$(ensure_symbol_node)"
REPORT_DOC="$(ensure_child_doc "$SYMBOL_NODE" "$REPORT_TITLE")"
DEDUCTION_DOC="$(ensure_child_doc "$SYMBOL_NODE" "$DEDUCTION_TITLE")"
FUNDAMENTAL_DOC="$(ensure_child_doc "$SYMBOL_NODE" "$FUNDAMENTAL_TITLE")"

update_doc "$REPORT_DOC" "$REPORT_FILE"
update_doc "$DEDUCTION_DOC" "$DEDUCTION_FILE"
update_doc "$FUNDAMENTAL_DOC" "$FUNDAMENTAL_FILE"

"$ROOT_DIR/.venv/bin/python" - <<PY
import json
print(json.dumps({
    "symbol": "$SYMBOL",
    "status": "ok",
    "symbol_page_title": "$SYMBOL_TITLE",
    "update_mode": "$UPDATE_MODE",
    "docs": {
        "report": {"title": "$REPORT_TITLE", "file": "$REPORT_FILE", "status": "ok"},
        "deduction": {"title": "$DEDUCTION_TITLE", "file": "$DEDUCTION_FILE", "status": "ok"},
        "fundamental": {"title": "$FUNDAMENTAL_TITLE", "file": "$FUNDAMENTAL_FILE", "status": "ok"},
    }
}, ensure_ascii=False, indent=2))
PY
