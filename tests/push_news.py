#!/usr/bin/env python3
"""推送功能测试 (Step 2)

测试内容：
1. 读取已获取的新闻数据
2. 测试推送到所有已启用的平台
3. 验证推送格式和内容

使用方法:
    python tests/push_news.py                  # 默认从 fetch 数据读取发送 (--fake)
    python tests/push_news.py --fake           # 从 fetch 数据读取发送
    python tests/push_news.py --real           # 从 news-data/push-*.md 最新文件发送
"""

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.config import load_config
from src.push import send_to_platforms
from src.storage import (
    convert_fetch_json_to_md,
    get_fetch_file,
    get_last_push_file,
    read_entries,
)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="推送功能测试")
    parser.add_argument(
        "--fake", action="store_true", help="从 fetch 数据读取发送（默认）"
    )
    parser.add_argument(
        "--real", action="store_true", help="从 news-data/push-*.md 最新文件发送"
    )
    return parser.parse_args()


def load_push_content() -> Optional[str]:
    """从 news-data 获取最新的 push 文件内容（去掉 frontmatter）"""
    last_file = get_last_push_file(data_dir="tests/news-data")
    if not last_file:
        print("   ❌ 未找到 push 文件")
        return None

    print(f"   📂 读取文件: {last_file}")

    with open(last_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 去掉 frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()

    return content


async def test_push(mode: str = "fake"):
    """测试推送功能"""
    print("=" * 60)
    print("📤 推送功能测试 (Step 2)")
    print(f"   模式: {'real' if mode == 'real' else 'fake (fetch数据)'}")
    print("=" * 60)

    # 加载配置
    print("\n📋 加载配置...")
    config = load_config()

    content: Optional[str] = None
    title: Optional[str] = None

    if mode == "real":
        # 从 push 文件读取
        content = load_push_content()
        if content:
            # 提取标题
            first_line = content.split("\n")[0] if content else ""
            if first_line.startswith("# "):
                title = first_line.replace("# ", "").strip()
            print(f"   📝 内容长度: {len(content)} 字符")
            print(f"   📝 标题: {title}")
    else:
        # 从 fetch 数据读取（默认）
        print("\n📖 读取新闻数据...")
        fetch_file = get_fetch_file(date.today(), data_dir="tests/news-data")
        entries = read_entries(fetch_file)
        print(f"   文件: {fetch_file}")
        print(f"   获取到 {len(entries)} 条新闻")

        # 同时生成 Markdown 版本便于阅读
        md_file = str(fetch_file).replace(".json", ".md")
        convert_fetch_json_to_md(fetch_file, md_file)
        print(f"   Markdown版本: {md_file}")

        if not entries:
            print("\n⚠️ 没有新闻数据，请先运行 fetch_news.py")
            return

        # 构建测试消息
        print("\n📝 构建推送消息...")
        content = build_test_message(entries[:5])
        print(f"   消息长度: {len(content)} 字符")

    if not content:
        print("\n⚠️ 没有内容可推送")
        return

    # 推送到所有已启用平台
    print("\n📤 推送消息...")
    try:
        await send_to_platforms(content, config["push"])
    except Exception as e:
        print(f"   ❌ 推送失败: {e}")
        raise

    print("\n" + "=" * 60)
    print("✅ Step 2 完成: 推送测试")
    print("=" * 60)


def build_test_message(entries: list) -> str:
    """构建测试消息"""
    lines = [
        "📰 **新闻推送测试**",
        "",
        f"共获取 {len(entries)} 条新闻：",
        "",
    ]

    for i, entry in enumerate(entries, 1):
        title = entry.get("title", "无标题")
        source = entry.get("source", "未知来源")
        link = entry.get("link", "")
        published = entry.get("published", "")
        content = entry.get("content", "")[:100]

        lines.append(f"**{i}. {title}**")
        lines.append(f"   📰 来源: {source}")
        if published:
            lines.append(f"   ⏰ 时间: {published}")
        if link:
            lines.append(f"   🔗 链接: {link}")
        if content:
            lines.append(f"   📝 内容: {content}...")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    args = parse_args()
    mode = "real" if args.real else "fake"
    asyncio.run(test_push(mode))
