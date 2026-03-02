"""数据存储模块 - JSON文件读写"""

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src.config import get_timezone


def get_fetch_file(d: date = None, data_dir: str = "news-data") -> str:
    """获取fetch文件路径 (使用配置时区)"""
    if d is None:
        d = datetime.now(get_timezone()).date()
    return f"{data_dir}/fetch-{d.isoformat()}.json"


def get_push_file(push_time: datetime = None, data_dir: str = "news-data") -> str:
    """生成push文件路径"""
    if push_time is None:
        push_time = datetime.now()
    time_str = push_time.strftime("%Y-%m-%d-%H-%M-%S")
    return f"{data_dir}/push-{time_str}.md"


def get_notify_file(d: date = None, data_dir: str = "news-data") -> str:
    """获取notify文件路径 (使用配置时区)"""
    if d is None:
        d = datetime.now(get_timezone()).date()
    return f"{data_dir}/notify-{d.isoformat()}.md"


def save_notify_file(filepath: str, content: str):
    """保存即时推送文件（Markdown格式），同一天的内容追加到同一文件"""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    notify_time = datetime.now(get_timezone()).isoformat()

    new_content = f"""---
pushTime: "{notify_time}"
---

{content}

------
"""

    with open(path, "a", encoding="utf-8") as f:
        f.write(new_content)


def load_recent_notify_content(
    context_days: int = 3, data_dir: str = "news-data"
) -> str:
    """加载最近context_days天的所有notify文件内容"""
    data_path = Path(data_dir)
    if not data_path.exists():
        return ""

    tz = get_timezone()
    today = datetime.now(tz).date()

    contents = []
    loaded_files = []
    for i in range(context_days):
        d = today - timedelta(days=i)
        notify_file = data_path / f"notify-{d.isoformat()}.md"
        if notify_file.exists():
            try:
                if notify_file.stat().st_size == 0:
                    print(f"   ⚠️ 跳过空文件: {notify_file.name}")
                    continue
                with open(notify_file, "r", encoding="utf-8") as f:
                    contents.append(f.read())
                    loaded_files.append(notify_file.name)
            except Exception:
                continue

    if loaded_files:
        print(
            f"   📂 已加载 {len(loaded_files)} 个 notify 文件: {', '.join(loaded_files)}"
        )

    return "\n\n".join(contents)


def load_recent_push_content(context_days: int = 3, data_dir: str = "news-data") -> str:
    """加载最近context_days天的所有push文件内容"""
    data_path = Path(data_dir)
    if not data_path.exists():
        return ""

    tz = get_timezone()
    today = datetime.now(tz).date()

    contents = []
    loaded_files = []
    for i in range(context_days):
        d = today - timedelta(days=i)
        pattern = f"push-{d.isoformat()}-*.md"
        for push_file in sorted(data_path.glob(pattern)):
            try:
                if push_file.stat().st_size == 0:
                    print(f"   ⚠️ 跳过空文件: {push_file.name}")
                    continue
                with open(push_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    contents.append(content)
                    loaded_files.append(push_file.name)
            except Exception:
                continue

    if loaded_files:
        print(
            f"   📂 已加载 {len(loaded_files)} 个 push 文件: {', '.join(loaded_files)}"
        )

    return "\n\n".join(contents)


def get_last_push_file(data_dir: str = "news-data") -> Optional[str]:
    """从news-data目录找到最新的push文件"""
    data_path = Path(data_dir)
    if not data_path.exists():
        return None

    push_files = sorted(data_path.glob("push-*.md"))
    return str(push_files[-1]) if push_files else None


def extract_push_time(filepath: str) -> Optional[datetime]:
    """从push文件名提取时间"""
    try:
        basename = Path(filepath).name
        time_str = basename.replace("push-", "").replace(".md", "")
        dt = datetime.strptime(time_str, "%Y-%m-%d-%H-%M-%S")
        return dt.replace(tzinfo=get_timezone())
    except (ValueError, AttributeError):
        return None


def read_entries(filepath: str) -> List[Dict]:
    """读取fetch文件，返回entries列表"""
    path = Path(filepath)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("entries", [])


def read_fetch_data(filepath: str) -> Dict:
    """读取完整的fetch文件数据（包含meta和entries）"""
    path = Path(filepath)
    if not path.exists():
        return {"meta": {}, "entries": []}

    # 检查文件是否为空
    if path.stat().st_size == 0:
        return {"meta": {}, "entries": []}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_fetch_file(filepath: str, meta: Dict, entries: List[Dict]):
    """保存fetch文件（JSON格式）"""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {"meta": meta, "entries": entries}

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_entries(filepath: str, new_entries: List[Dict], meta: Dict = None):
    """追加条目到fetch文件"""
    path = Path(filepath)

    # 读取现有数据
    if path.exists():
        data = read_fetch_data(filepath)
    else:
        data = {"meta": meta or {}, "entries": []}

    # 更新meta（如果提供了）
    if meta:
        data["meta"].update(meta)

    # 去重：基于link字段
    existing_links = {e.get("link") for e in data["entries"]}
    for entry in new_entries:
        if entry.get("link") not in existing_links:
            data["entries"].append(entry)
            existing_links.add(entry.get("link"))

    # 保存
    save_fetch_file(filepath, data["meta"], data["entries"])
    return len(new_entries)


def format_entry(entry: Dict) -> str:
    """格式化单条条目为Markdown字符串"""
    tags = entry.get("tags", [])
    tags_str = json.dumps(tags, ensure_ascii=False) if tags else "[]"
    score = entry.get("score", "")
    summary = entry.get("summary", "")

    return f"""## {entry["title"]}

---
source: {entry["source"]}
link: {entry["link"]}
published: {entry["published"]}
fetched_at: {entry["fetched_at"]}
tags: {tags_str}
score: {score}
summary: {summary}
---

{entry["content"]}

------
"""


def json_to_md(data: Dict) -> str:
    """
    将JSON格式的fetch数据转换为Markdown格式，便于阅读

    Args:
        data: {"meta": {...}, "entries": [...]}

    Returns:
        Markdown格式的字符串
    """
    meta = data.get("meta", {})
    entries = data.get("entries", [])

    lines = []

    # 文件头部YAML frontmatter
    if meta.get("date"):
        lines.append("---")
        lines.append(f'date: "{meta["date"]}"')
        lines.append("---")
        lines.append("")

    # 条目
    for entry in entries:
        lines.append(format_entry(entry))

    return "\n".join(lines)


def convert_fetch_json_to_md(json_filepath: str, md_filepath: str = None) -> str:
    """
    将fetch JSON文件转换为Markdown文件

    Args:
        json_filepath: JSON文件路径
        md_filepath: 输出MD文件路径，默认为同名.md

    Returns:
        生成的Markdown内容
    """
    data = read_fetch_data(json_filepath)
    md_content = json_to_md(data)

    if md_filepath:
        path = Path(md_filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md_content)

    return md_content


def save_push_file(filepath: str, content: str, source_count: int, total_entries: int):
    """保存推送文件（Markdown格式）"""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    push_time = datetime.now(get_timezone())
    frontmatter = f"""---
pushDate: "{push_time.isoformat()}"
sourceCount: {source_count}
totalEntries: {total_entries}
---

"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter + content)


def load_existing_links(filepath: str) -> set:
    """加载文件中已有的链接（用于去重）"""
    if not filepath or not Path(filepath).exists():
        return set()

    # 检查是JSON还是旧版Markdown
    if filepath.endswith(".json"):
        entries = read_entries(filepath)
        return {e.get("link") for e in entries if e.get("link")}
    else:
        # 旧版Markdown格式
        try:
            entries = read_entries(filepath)
            return {e.get("link") for e in entries if e.get("link")}
        except Exception:
            return set()


def cleanup_old_files(days: int = 7, data_dir: str = "news-data"):
    """清理超过days天的旧文件"""
    data_path = Path(data_dir)
    if not data_path.exists():
        return

    cutoff = datetime.now() - timedelta(days=days)

    for pattern in ["fetch-*.json", "fetch-*.md", "push-*.md"]:
        for file in data_path.glob(pattern):
            try:
                # 从文件名提取日期
                date_str = (
                    file.name.replace("fetch-", "")
                    .replace("push-", "")
                    .replace(".json", "")
                    .replace(".md", "")
                )
                # 处理带时间的文件名 push-YYYY-MM-DD-HH-MM-SS
                date_parts = date_str.split("-")
                if len(date_parts) >= 3:
                    file_date = date(
                        int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                    )
                    if file_date < cutoff.date():
                        file.unlink()
            except (ValueError, OSError):
                continue
