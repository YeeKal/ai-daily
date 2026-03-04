"""AI每日资讯推送系统 - 主程序"""

import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

# 加载 .env 文件
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from croniter import croniter

from src.config import get_timezone, load_config, merge_sources
from src.fetcher import fetch_all_feeds
from src.llm import compose_digest, generate_immediate_push, score_batch
from src.processor import html_to_markdown
from src.push import send_to_platforms
from src.storage import (
    append_entries,
    cleanup_old_files,
    extract_push_time,
    get_fetch_file,
    get_last_push_file,
    get_notify_file,
    get_push_file,
    load_existing_links,
    load_recent_notify_content,
    load_recent_push_content,
    read_entries,
    save_notify_file,
    save_push_file,
)


def now_local(config: Dict = None) -> datetime:
    """获取配置时区的当前时间"""
    return datetime.now(get_timezone(config))


def parse_time_to_local(time_str: str, config: Dict = None) -> Optional[datetime]:
    """解析时间字符串为配置时区的datetime"""
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.astimezone(get_timezone(config))
    except (ValueError, TypeError):
        return None


def calculate_push_times(
    cron_list: List[str], offset_days: int = 0, config: Dict = None
) -> List[datetime]:
    base_date = datetime.now(get_timezone(config)).date() + timedelta(days=offset_days)
    times = []
    for cron in cron_list:
        try:
            minute, hour, _, _, _ = cron.split()
            t = datetime.combine(
                base_date,
                datetime.strptime(f"{hour}:{minute}", "%H:%M").time(),
                tzinfo=get_timezone(config),
            )
            times.append(t)
        except ValueError:
            continue
    return sorted(times)


def collect_entries_for_push(
    last_push_time: Optional[datetime],
    context_days: int = 2,
    min_score: int = 60,
    data_dir: str = "news-data",
) -> tuple[List[Dict], List[Dict]]:
    """
    收集推送所需的条目，返回 (待推送条目, 上下文条目)

    逻辑：
    1. 获取 context_days 天内的所有条目
    2. 按 min_score 过滤
    3. push_time = max(last_push_time, now - 24h)
    4. 晚于 push_time 的 → 待推送条目
    5. 早于 push_time 的 → 上下文条目（用于LLM去重参考）
    """
    tz = get_timezone()
    now = datetime.now(tz)

    # 获取 context_days 天的所有条目
    all_entries = []
    today = now.date()
    for i in range(context_days):
        d = today - timedelta(days=i)
        fetch_file = get_fetch_file(d, data_dir)
        for entry in read_entries(fetch_file):
            all_entries.append(entry)

    print(
        f"📋 收集总条目: {len(all_entries)} 条 , concollect_entries_for_pushtext_days: {context_days}, min_score:{min_score}"
    )

    # 按 min_score 过滤
    qualified_entries = [e for e in all_entries if (e.get("score") or 0) >= min_score]
    print(f"📋 过滤后条目: {len(qualified_entries)} 条 ")

    # 计算推送时间边界：max(last_push_time, now - 24h)
    past_24h = now - timedelta(hours=24)
    push_cutoff = (
        last_push_time if last_push_time and last_push_time > past_24h else past_24h
    )

    print(f"推送时间边界: {push_cutoff.strftime('%Y-%m-%d %H:%M:%S')}")

    # 分割条目
    to_push = []
    context = []

    for entry in qualified_entries:
        entry_time = parse_time_to_local(entry.get("fetched_at", ""))
        if entry_time and entry_time > push_cutoff:
            to_push.append(entry)
        else:
            # 上下文条目只保留必要字段
            context.append(entry)

    # 上下文按分数排序，取前50
    context = sorted(context, key=lambda x: x.get("score", 0), reverse=True)[:50]

    return to_push, context


async def run_fetch_job(config: Dict):
    print(f"\n{'=' * 50}")
    print(f"🔄 Fetch Job | {now_local().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}")

    interval = config["schedule"]["fetch_interval_minutes"]
    lookback = config["schedule"].get("fetch_lookback_minutes", 120)
    lookback = max(lookback, interval)
    threshold = lookback + interval
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback)

    sources = merge_sources(config["sources"])
    print(f"📂 共 {len(sources)} 个订阅源")

    if not sources:
        print("⚠️ 没有可用的订阅源")
        return

    max_workers = config.get("fetch", {}).get("max_workers", 20)
    timeout = config.get("fetch", {}).get("timeout", 30)
    entries = await fetch_all_feeds(
        sources, cutoff, max_workers=max_workers, timeout=timeout
    )
    print(f"📥 抓取到 {len(entries)} 条原始消息")

    if not entries:
        return

    for entry in entries:
        entry["content"] = html_to_markdown(
            entry.get("content", ""), entry.get("link", "")
        )

    fetch_file = get_fetch_file()
    existing_links = load_existing_links(fetch_file, threshold)
    new_entries = [
        e for e in entries if e.get("link") and e["link"] not in existing_links
    ]
    print(f"🆕 新消息 {len(new_entries)} 条 | 链接数：{len(existing_links)}")

    if not new_entries:
        return

    print("🤖 LLM评分中...")
    # 预处理：将所有 datetime 转换为字符串，避免 JSON 序列化错误
    for entry in new_entries:
        if isinstance(entry.get("published"), datetime):
            entry["published"] = (
                entry["published"].astimezone(get_timezone(config)).isoformat()
            )

    scored = await score_batch(new_entries, config["llm"])

    is_new_file = not os.path.exists(fetch_file)
    if is_new_file:
        cleanup_old_files(days=config["filter"]["keep_days"])

    # 添加 fetched_at 时间戳
    for entry in scored:
        entry["fetched_at"] = now_local().isoformat()
        if isinstance(entry.get("published"), datetime):
            entry["published"] = (
                entry["published"].astimezone(get_timezone(config)).isoformat()
            )

    # 批量保存到 JSON 文件
    from datetime import date

    meta = {"date": date.today().isoformat()}
    append_entries(fetch_file, scored, meta)

    print(f"💾 已保存到 {fetch_file}")

    hot_threshold = config["filter"]["hot_threshold"]
    no_content_marker = config["filter"].get("no_content_marker", "[NO_NEW_CONTENT]")
    hot_entries = [e for e in scored if (e.get("score") or 0) >= hot_threshold]
    if hot_entries:
        print(f"🔥 发现 {len(hot_entries)} 条热点消息，即时推送...")

        # 加载近期推送上下文用于去重
        context_days = config["filter"]["context_days"]
        recent_notify = load_recent_notify_content(context_days)
        recent_push = load_recent_push_content(context_days)
        recent_context = f"=== 近期即时推送 ===\n{recent_notify}\n\n=== 近期汇总推送 ===\n{recent_push}"

        push_content = await generate_immediate_push(
            hot_entries, config["llm"], recent_push_context=recent_context
        )

        # 检查是否有实际内容需要推送
        if no_content_marker in push_content:
            print(f"ℹ️ 无新内容需要推送 (LLM判定为重复内容)")
        else:
            await send_to_platforms(push_content, config["push"])
            # 保存即时推送内容到notify文件
            notify_file = get_notify_file()
            save_notify_file(notify_file, push_content)
            print(f"💾 已保存即时推送到 {notify_file}")

    print(f"✅ Fetch Job 完成 | 新消息: {len(scored)} 条 | 热点: {len(hot_entries)} 条")


async def run_push_job(config: Dict):
    print(f"\n{'=' * 50}")
    print(f"📤 Push Job | {now_local().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}")

    last_push_file = get_last_push_file()
    last_push_time = extract_push_time(last_push_file) if last_push_file else None

    if last_push_time:
        print(f"📌 上次推送: {last_push_time.strftime('%Y-%m-%d %H:%M')}")

    # 收集条目：待推送条目 和 上下文条目
    min_score = config["filter"]["min_score"]
    context_days = config["filter"]["context_days"]

    # 已经根据min_score 去除得分较低的数据
    to_push, context = collect_entries_for_push(
        last_push_time=last_push_time,
        context_days=context_days,
        min_score=min_score,
    )

    total_qualified = len(to_push) + len(context)
    print(
        f"📋 符合标准条目: {total_qualified} 条 (待推送: {len(to_push)}, 上下文参考: {len(context)})"
    )

    if not to_push:
        print("ℹ️ 没有新消息需要推送")
        return

    print(f"✅ 符合推送标准(≥{min_score}分): {len(to_push)} 条")

    # 加载近期推送上下文用于去重
    push_context_days = config["filter"].get("push_context_days", 5)
    recent_push_context_str = load_recent_push_content(push_context_days)

    print("🤖 生成推送内容...")
    try:
        push_content = await compose_digest(
            to_push, context, config["llm"], recent_push_context=recent_push_context_str
        )
    except Exception as e:
        print(f"生成汇总推送失败: {e}")
        return

    await send_to_platforms(push_content, config["push"])

    push_file = get_push_file()
    save_push_file(push_file, push_content, len(to_push), len(to_push))
    print(f"💾 已保存到 {push_file}")

    print(f"✅ Push Job 完成 | 推送: {len(to_push)} 条")


async def fetch_loop(config: Dict):
    """Fetch循环 - 修复时间漂移并支持优雅退出"""
    import time

    interval_seconds = config["schedule"]["fetch_interval_minutes"] * 60
    print(f"🔄 Fetch循环已启动 | 严格间隔: {interval_seconds / 60}分钟")

    while True:
        start_time = time.monotonic()  # 使用 monotonic 避免系统时间修改影响

        try:
            await run_fetch_job(config)
        except asyncio.CancelledError:
            print("⚠️ Fetch循环被外部取消，正在安全退出...")
            break  # 允许外部取消任务
        except Exception as e:
            print(f"❌ Fetch Job 失败: {e}")

        # 计算任务耗时
        elapsed = time.monotonic() - start_time
        # 计算还需要睡多久（如果任务耗时超过间隔，则不睡，立刻进入下一次）
        sleep_time = max(0.0, interval_seconds - elapsed)

        if sleep_time > 0:
            print(f"⏰ 下次抓取: {sleep_time / 60:.1f}分钟后")

        try:
            await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            print("⚠️ 睡眠被中断，Fetch循环安全退出...")
            break


async def push_loop(config: Dict):
    """Push循环 - 无状态 croniter + 原生异步睡眠"""
    cron_list = config["schedule"]["push_cron"]
    tz = get_timezone(config)

    # 1. 启动前预校验 cron 表达式，过滤掉无效配置
    valid_crons = []
    for cron in cron_list:
        if croniter.is_valid(cron):
            valid_crons.append(cron)
        else:
            print(f"⚠️ 忽略无效的 cron 表达式: '{cron}'")

    if not valid_crons:
        print("❌ 没有有效的推送时间配置，Push循环退出")
        return

    print(f"📤 Push循环已启动 | 定时: {', '.join(valid_crons)} | 时区: {tz}")

    # 2. 主循环
    while True:
        try:
            now = datetime.now(tz)

            # 💡 核心优化：无状态计算。
            # 每次都基于此刻的真实时间，动态计算所有有效 cron 的下一次时间，取最近的一个。
            # 这样无论 run_push_job 执行多久，或者系统休眠过，永远都不会算错。
            next_push = min(
                croniter(cron, now).get_next(datetime) for cron in valid_crons
            )

            wait_seconds = (next_push - datetime.now(tz)).total_seconds()

            if wait_seconds > 0:
                print(
                    f"⏰ 下次推送: {next_push.strftime('%Y-%m-%d %H:%M:%S')} (等待 {wait_seconds / 60:.1f} 分钟)"
                )

                # 💡 核心优化：直接 Sleep。asyncio 天生支持被 CancelledError 瞬间打断
                await asyncio.sleep(wait_seconds)

            # 到达推送时间，执行推送
            print(f"📤 执行推送: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}")
            await run_push_job(config)

            # 增加 1 秒缓冲：防止 run_push_job 执行过快（不到 1 秒），
            # 导致下一个循环的 now 仍停留在当前秒，croniter 算出重复的时间点。
            await asyncio.sleep(1)

        except asyncio.CancelledError:
            print("⚠️ Push循环收到取消信号，安全退出...")
            break  # 直接 break 退出循环即可
        except Exception as e:
            print(f"❌ Push 循环异常: {e}")
            # 遇到未知异常时休眠 60 秒，防止死循环疯狂报错打满日志
            await asyncio.sleep(60)


async def main():
    print("🚀 AI每日资讯推送系统启动")
    try:
        config = load_config()
        print("✅ 配置加载成功")
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        return

    await asyncio.gather(fetch_loop(config), push_loop(config))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
