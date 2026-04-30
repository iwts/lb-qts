#!/usr/bin/env python3
"""
Youtube 财经博主知识同步脚本。

功能：
1. 读取本地已处理记录（processed_log.json）
2. 输出待处理摘要，供 Agent 判断是否需要继续同步（不在 stdout 中暴露 Wiki/文档标识符）
3. 处理完成后更新 processed_log.json

用法:
    # 查看待处理列表（Agent 先调用此命令，根据输出调用 lark-cli 读取内容）
    python sync_youtube_insights.py --action list-pending

    # 标记某个视频已处理
    python sync_youtube_insights.py --action mark-done --page-id <page_id> --blogger <博主名> --date <日期>

    # 查看全部已处理记录
    python sync_youtube_insights.py --action show-log

    # 获取知识库状态摘要
    python sync_youtube_insights.py --action status
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOUTUBE_DATA_DIR = os.path.join(BASE_DIR, "data", "youtube_insights")
PROCESSED_LOG_PATH = os.path.join(YOUTUBE_DATA_DIR, "processed_log.json")
KNOWLEDGE_BASE_PATH = os.path.join(YOUTUBE_DATA_DIR, "knowledge_base.md")
CHALLENGES_PATH = os.path.join(YOUTUBE_DATA_DIR, "challenges.md")

LOCAL_CONFIG_PATH = os.path.join(BASE_DIR, ".config", "youtube_sync_config.json")


def _load_local_config() -> dict:
    """读取本地 Wiki 定位配置；真实值放在 .config/，不使用环境变量。"""
    if not os.path.exists(LOCAL_CONFIG_PATH):
        return {}
    with open(LOCAL_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_YOUTUBE_CONFIG = _load_local_config().get("youtube", {})
YOUTUBE_ROOT_NODE_TOKEN = _YOUTUBE_CONFIG.get("root_node_token", "")
YOUTUBE_SPACE_ID = _YOUTUBE_CONFIG.get("space_id", "")


def _ensure_dir():
    os.makedirs(YOUTUBE_DATA_DIR, exist_ok=True)


def _read_log() -> dict:
    _ensure_dir()
    if not os.path.exists(PROCESSED_LOG_PATH):
        return {"processed": [], "last_sync": None}
    with open(PROCESSED_LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_log(data: dict):
    _ensure_dir()
    with open(PROCESSED_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _display_path(path: str) -> str:
    return os.path.relpath(path, BASE_DIR)


def _redact(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def mark_done(page_id: str, blogger: str, date: str, title: str = ""):
    data = _read_log()
    existing_ids = {p["page_id"] for p in data["processed"]}
    if page_id in existing_ids:
        log.info("页面已存在于处理记录中")
        return
    data["processed"].append({
        "page_id": page_id,
        "blogger": blogger,
        "date": date,
        "title": title,
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    data["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_log(data)
    log.info(f"已标记完成: {blogger}/{date}")


def show_log():
    data = _read_log()
    sanitized = {
        "processed_count": len(data.get("processed", [])),
        "last_sync": data.get("last_sync"),
        "processed": [
            {
                "blogger": item.get("blogger", ""),
                "date": item.get("date", ""),
                "title": item.get("title", ""),
                "processed_at": item.get("processed_at", ""),
            }
            for item in data.get("processed", [])
        ],
    }
    print(json.dumps(sanitized, ensure_ascii=False, indent=2))


def status():
    data = _read_log()
    processed_count = len(data["processed"])
    bloggers = set(p["blogger"] for p in data["processed"])
    kb_exists = os.path.exists(KNOWLEDGE_BASE_PATH)
    ch_exists = os.path.exists(CHALLENGES_PATH)

    result = {
        "processed_videos": processed_count,
        "bloggers": sorted(bloggers),
        "last_sync": data.get("last_sync"),
        "knowledge_base_exists": kb_exists,
        "challenges_exists": ch_exists,
        "youtube_configured": bool(YOUTUBE_ROOT_NODE_TOKEN and YOUTUBE_SPACE_ID),
        "local_config_path": _display_path(LOCAL_CONFIG_PATH),
        "knowledge_base_path": _display_path(KNOWLEDGE_BASE_PATH),
        "challenges_path": _display_path(CHALLENGES_PATH),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def list_pending():
    """输出待处理摘要，供 Agent 判断是否需要继续同步；不输出任何 Wiki 标识符。"""
    data = _read_log()
    processed_count = len(data.get("processed", []))
    if not YOUTUBE_ROOT_NODE_TOKEN or not YOUTUBE_SPACE_ID:
        instruction = (
            "缺少必要的 YouTube Wiki 本地配置。"
            "请先在 .config/youtube_sync_config.json 中填写后再执行。"
        )
    else:
        instruction = (
            "请使用本地 .config/youtube_sync_config.json 中的 YouTube Wiki 配置在内部读取待处理页面；"
            "不要在日志或终端输出任何 Wiki 标识符或文档标识符；"
            "跳过本地处理记录中已存在的页面；"
            "对新的日期页面读取内容并提炼观点，最后调用 mark-done 标记。"
        )
    result = {
        "youtube_configured": bool(YOUTUBE_ROOT_NODE_TOKEN and YOUTUBE_SPACE_ID),
        "processed_page_count": processed_count,
        "instruction": instruction,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Youtube 财经博主知识同步")
    parser.add_argument("--action", required=True,
                        choices=["list-pending", "mark-done", "show-log", "status"])
    parser.add_argument("--page-id", help="页面 ID（mark-done 时必填）")
    parser.add_argument("--blogger", help="博主名称（mark-done 时必填）")
    parser.add_argument("--date", help="视频日期（mark-done 时必填）")
    parser.add_argument("--title", default="", help="视频标题（可选）")
    args = parser.parse_args()

    if args.action == "list-pending":
        list_pending()
    elif args.action == "mark-done":
        if not all([args.page_id, args.blogger, args.date]):
            parser.error("mark-done 需要 --page-id, --blogger, --date")
        mark_done(args.page_id, args.blogger, args.date, args.title)
    elif args.action == "show-log":
        show_log()
    elif args.action == "status":
        status()
