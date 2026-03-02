#!/usr/bin/env python3
"""测试LLM评分和推送功能 - 独立运行脚本

Usage:
    # 先激活虚拟环境
    source ../.venv/bin/activate

    # 测试评分
    python tests/run_llm_test.py --score

    # 测试即时推送
    python tests/run_llm_test.py --immediate-push --push
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 检查是否在虚拟环境中
if not hasattr(sys, "real_prefix") and not (
    hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
):
    print("⚠️  建议先激活虚拟环境: source .venv/bin/activate")
    print("")

# 加载 .env 文件
from dotenv import load_dotenv

load_dotenv()

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_timezone, load_config
from src.llm import compose_digest, generate_immediate_push, score_batch
from src.push import send_to_platforms
from src.storage import read_fetch_data, save_fetch_file


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="测试LLM评分和推送")
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="tests/news-data/fetch-{date}.json",
        help="输入文件路径，支持{date}占位符 (默认: tests/news-data/fetch-{date}.json)",
    )
    parser.add_argument(
        "--date",
        "-d",
        type=str,
        default=datetime.now(get_timezone()).strftime("%Y-%m-%d"),
        help="日期，格式YYYY-MM-DD (默认: 今天)",
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=0, help="测试的消息数量 (默认: 0表示全部)"
    )

    # 测试模式选择
    parser.add_argument("--score", action="store_true", help="测试评分")
    parser.add_argument("--immediate-push", action="store_true", help="测试即时推送")
    parser.add_argument("--digest", action="store_true", help="测试汇总推送")
    parser.add_argument("--push", action="store_true", help="推送到Discord")
    parser.add_argument("--all", action="store_true", help="运行所有测试")

    return parser.parse_args()


def should_run(args, mode: str) -> bool:
    """判断是否运行某个模式"""
    # 如果没有任何特定模式指定，默认运行评分
    if args.all:
        return True

    # 检查是否指定了任何模式
    any_mode = args.score or args.immediate_push or args.digest

    if mode == "score":
        return args.score or not any_mode  # 默认运行评分
    elif mode == "immediate_push":
        return args.immediate_push
    elif mode == "digest":
        return args.digest
    return False


async def test_llm():
    """主函数"""
    args = parse_args()

    print("=" * 60)
    print("🤖 LLM测试脚本")
    print("=" * 60)

    # 构建输入文件路径
    input_path = args.input.format(date=args.date)
    print(f"\n📂 输入文件: {input_path}")

    # 读取数据
    if not Path(input_path).exists():
        print(f"❌ 文件不存在: {input_path}")
        print("\n💡 提示: 先运行 fetch_news.py 获取新闻数据")
        print("   python tests/fetch_news.py --hours 1")
        return False

    print(input_path)
    data = read_fetch_data(input_path)
    entries = data.get("entries", [])
    meta = data.get("meta", {})

    print(f"   ✓ 共 {len(entries)} 条")

    if not entries:
        print("❌ 没有条目可测试")
        return False

    # 限制测试数量 (0表示全部)
    if args.limit > 0:
        test_entries = entries[: args.limit]
        print(f"   测试前 {len(test_entries)} 条")
    else:
        test_entries = entries
        print(f"   测试全部 {len(test_entries)} 条")

    # 显示待评分条目
    print(f"\n📄 测试条目:")
    for i, e in enumerate(test_entries[:5], 1):
        print(f"   [{i}] {e.get('title', 'N/A')[:45]}...")
        print(f"       来源: {e.get('source', 'N/A')}")

    # 加载配置
    print("\n⚙️  加载配置...")
    config = load_config()
    llm_config = config["llm"]

    print(f"   ✓ 提供商: {llm_config.get('provider', 'openai')}")
    print(f"   ✓ 模型: {llm_config.get('model', 'N/A')}")
    print(f"   ✓ BaseURL: {llm_config.get('baseUrl', 'N/A')}")

    # 检查API key
    api_key_name = llm_config.get("apiKeyName", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_name)
    if not api_key:
        print(f"\n❌ 未设置环境变量: {api_key_name}")
        return False

    print(f"   ✓ API Key: {api_key[:10]}...")

    # 检查是否启用推送
    push_enabled = args.push and config.get("push")
    if push_enabled:
        print("\n🔌 推送已启用 (将推送到所有已配置的平台)")

    # ========== 测试评分 ==========
    if should_run(args, "score"):
        print("\n" + "-" * 60)
        print("🎯 测试: 评分 (score_batch)")
        print("-" * 60)

        try:
            scored = await score_batch(test_entries, llm_config)
            print("\n✅ 评分完成!")

            # 显示评分结果
            print("\n📊 评分结果:")
            for i, e in enumerate(scored[:5], 1):
                print(f"\n   [{i}] {e['title'][:40]}...")
                print(f"       评分: {e.get('score', 'N/A')}/100")
                print(f"       标签: {e.get('tags', [])}")
                print(f"       摘要: {e.get('summary', 'N/A')[:60]}...")

            # 保存评分结果到JSON文件
            print(f"\n💾 保存评分结果到: {input_path}")

            # 构建link到评分的映射
            score_map = {e.get("link"): e for e in scored if e.get("link")}

            # 更新所有entries的评分
            all_entries = data.get("entries", [])
            for i, entry in enumerate(all_entries):
                link = entry.get("link")
                if link in score_map:
                    all_entries[i] = score_map[link]

            save_fetch_file(input_path, meta, all_entries)
            print(f"   ✅ 已保存 {len(scored)} 条评分结果")

            # 更新test_entries为评分后的数据
            test_entries = scored

        except Exception as e:
            print(f"\n❌ 评分失败: {e}")
            import traceback

            traceback.print_exc()
            return False

    # ========== 测试即时推送 ==========
    if should_run(args, "immediate_push"):
        print("\n" + "-" * 60)
        print("🔥 测试: 即时推送 (generate_immediate_push)")
        print("-" * 60)

        # 筛选高分条目 (>=80分)用于推送
        hot_entries = [e for e in test_entries if e.get("score", 0) >= 90]
        if not hot_entries:
            hot_entries = test_entries[:2]  # 如果没有高分，取前2条

        print(f"\n使用 {len(hot_entries)} 条高分消息生成推送...")

        # 加载近期推送上下文用于测试
        context_days = config.get("filter", {}).get("context_days", 3)
        from src.storage import (
            get_notify_file,
            load_recent_notify_content,
            load_recent_push_content,
            save_notify_file,
        )

        recent_notify = load_recent_notify_content(context_days)
        recent_push = load_recent_push_content(context_days)
        recent_context = f"=== 近期即时推送 ===\n{recent_notify}\n\n=== 近期汇总推送 ===\n{recent_push}"

        try:
            # 传入上下文参数
            push_content = await generate_immediate_push(
                hot_entries, llm_config, recent_push_context=recent_context
            )
            print(f"\n✅ 推送内容生成完成!")
            print(f"\n📤 推送内容预览:")
            print("-" * 40)
            print(
                push_content[:500] + "..." if len(push_content) > 500 else push_content
            )
            print("-" * 40)

            # 检查是否有实际内容需要推送
            no_content_marker = config.get("filter", {}).get(
                "no_content_marker", "[NO_NEW_CONTENT]"
            )
            if no_content_marker in push_content:
                print(f"\nℹ️ 无新内容需要推送 (LLM判定为重复内容)")
            else:
                # 推送到所有启用的平台
                if push_enabled:
                    print("\n📤 推送消息...")
                    await send_to_platforms(
                        push_content, config["push"], title="🔥 AI 重磅资讯"
                    )
                    print("   ✅ 推送成功!")

                # 保存到 notify 文件
                notify_file = get_notify_file()
                save_notify_file(notify_file, push_content)
                print(f"\n💾 已保存即时推送到 {notify_file}")

        except Exception as e:
            print(f"\n❌ 即时推送生成失败: {e}")
            import traceback

            traceback.print_exc()

    # ========== 测试汇总推送 ==========
    if should_run(args, "digest"):
        print("\n" + "-" * 60)
        print("📰 测试: 汇总推送 (compose_digest)")
        print("-" * 60)

        # 构建上下文（从 fetch 文件读取的历史数据）
        context = test_entries[:10]  # 使用前10条作为模拟上下文

        print(f"\n使用 {len(test_entries)} 条消息生成汇总...")

        # 加载近期推送上下文
        push_context_days = config.get("filter", {}).get("push_context_days", 5)
        from src.storage import get_push_file, load_recent_push_content, save_push_file

        recent_push_context_str = load_recent_push_content(push_context_days)

        try:
            digest_content = await compose_digest(
                test_entries,
                context,
                llm_config,
                recent_push_context=recent_push_context_str,
            )
            print(f"\n✅ 汇总内容生成完成!")
            print(f"\n📰 汇总内容预览:")
            print("-" * 40)
            print(
                digest_content[:500] + "..."
                if len(digest_content) > 500
                else digest_content
            )
            print("-" * 40)

            # 推送到所有启用的平台
            if push_enabled:
                print("\n📤 推送消息...")
                await send_to_platforms(
                    digest_content, config["push"], title="📰 AI 资讯汇总"
                )
                print("   ✅ 推送成功!")

            # 保存到 push 文件
            push_file = get_push_file()
            save_push_file(
                push_file, digest_content, len(test_entries), len(test_entries)
            )
            print(f"\n💾 已保存汇总到 {push_file}")

        except Exception as e:
            print(f"\n❌ 汇总推送生成失败: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print("✅ LLM测试完成!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_llm())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
