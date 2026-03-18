"""RSS抓取模块"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp
import feedparser

# 默认超时配置（秒）
DEFAULT_FEED_TIMEOUT = 5


def parse_entry_time(entry) -> Optional[datetime]:
    """解析条目的发布时间 (返回带 UTC 时区的 datetime)"""
    from datetime import timezone

    published_parsed = getattr(entry, "published_parsed", None)
    if published_parsed is not None:
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)

    updated_parsed = getattr(entry, "updated_parsed", None)
    if updated_parsed is not None:
        return datetime(*updated_parsed[:6], tzinfo=timezone.utc)

    return None


async def fetch_single_feed_async(
    feed_info: Dict,
    cutoff_time: datetime,
    timeout: int = 5,
    session: aiohttp.ClientSession = None,
    proxy: str = None,
    use_proxy: bool = True,
) -> List[Dict]:
    """异步获取单个源的条目"""
    entries = []
    try:
        # 设置超时，默认5秒
        if timeout is None:
            timeout = DEFAULT_FEED_TIMEOUT

        url = feed_info["xmlUrl"]
        # 使用完整浏览器请求头，避免被识别为爬虫
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        # 优化SSL配置
        connector = aiohttp.TCPConnector(
            ssl=False,  # 禁用SSL验证以避免证书问题
            limit=100,  # 增加连接池大小
            keepalive_timeout=30
        )
        proxy_auth = None

        # 使用 aiohttp 获取 RSS 内容（支持超时和代理）
        if session:
            # 使用传入的 session
            try:
                if use_proxy and proxy:
                    print(f"🔗 使用代理获取: {url}")
                    async with session.get(
                        url, 
                        headers=headers, 
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        proxy=proxy,
                        proxy_auth=proxy_auth
                    ) as resp:
                        if resp.status != 200:
                            print(f"⚠️ HTTP {resp.status}: {url}")
                            return []
                        content = await resp.text()
                else:
                    print(f"🔗 直接获取: {url}")
                    async with session.get(
                        url, 
                        headers=headers, 
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        if resp.status != 200:
                            print(f"⚠️ HTTP {resp.status}: {url}")
                            return []
                        content = await resp.text()
            except Exception as e:
                # 尝试不使用代理
                print(f"⚠️ 连接失败，尝试备用方式: {url} - {str(e)[:50]}")
                # 创建新的session，避免使用已关闭的session
                try:
                    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
                        ssl=False,  # 禁用SSL验证以避免证书问题
                        limit=100,  # 增加连接池大小
                        keepalive_timeout=30
                    )) as backup_sess:
                        async with backup_sess.get(
                            url, 
                            headers=headers, 
                            timeout=aiohttp.ClientTimeout(total=timeout)
                        ) as resp:
                            if resp.status != 200:
                                print(f"⚠️ HTTP {resp.status}: {url}")
                                return []
                            content = await resp.text()
                except Exception as e2:
                    print(f"⚠️ 备用连接也失败: {url} - {str(e2)[:50]}")
                    return []
        else:
            # 创建临时 session
            try:
                if use_proxy and proxy:
                    print(f"🔗 使用代理获取: {url}")
                    async with aiohttp.ClientSession(connector=connector) as sess:
                        async with sess.get(
                            url, 
                            headers=headers, 
                            timeout=aiohttp.ClientTimeout(total=timeout),
                            proxy=proxy,
                            proxy_auth=proxy_auth
                        ) as resp:
                            if resp.status != 200:
                                print(f"⚠️ HTTP {resp.status}: {url}")
                                return []
                            content = await resp.text()
                else:
                    print(f"🔗 直接获取: {url}")
                    async with aiohttp.ClientSession(connector=connector) as sess:
                        async with sess.get(
                            url, 
                            headers=headers, 
                            timeout=aiohttp.ClientTimeout(total=timeout)
                        ) as resp:
                            if resp.status != 200:
                                print(f"⚠️ HTTP {resp.status}: {url}")
                                return []
                            content = await resp.text()
            except Exception as e:
                # 尝试不使用代理
                print(f"⚠️ 连接失败，尝试备用方式: {url} - {str(e)[:50]}")
                try:
                    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
                        ssl=False,  # 禁用SSL验证以避免证书问题
                        limit=100,  # 增加连接池大小
                        keepalive_timeout=30
                    )) as backup_sess:
                        async with backup_sess.get(
                            url, 
                            headers=headers, 
                            timeout=aiohttp.ClientTimeout(total=timeout)
                        ) as resp:
                            if resp.status != 200:
                                print(f"⚠️ HTTP {resp.status}: {url}")
                                return []
                            content = await resp.text()
                except Exception as e2:
                    print(f"⚠️ 备用连接也失败: {url} - {str(e2)[:50]}")
                    return []

        # 使用 feedparser 解析内容
        feed = feedparser.parse(content)

        for entry in feed.entries:
            pub_date = parse_entry_time(entry)

            # 时间过滤 - RSS通常按时间倒序排列，一旦发现过期直接跳出
            if pub_date and pub_date < cutoff_time:
                break

            # 提取内容
            content = ""
            if hasattr(entry, "description"):
                content = entry.description
            elif hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content"):
                content = entry.content[0].value if entry.content else ""

            entries.append(
                {
                    "title": entry.get("title", "无标题"),
                    "link": entry.get("link", ""),
                    "published": pub_date,
                    "source": feed_info["title"],
                    "content": content,
                    "tags": [],
                    "score": 0,
                    "summary": "",
                }
            )
    except Exception as e:
        import traceback
        print(f"⚠️ 获取失败 {feed_info['title']}: {e}")
        # 打印详细错误信息
        print(f"详细错误: {traceback.format_exc()}")

    return entries


async def fetch_all_feeds(
    feeds: List[Dict], 
    cutoff_time: datetime, 
    max_workers: int = 10, 
    timeout: int = None,
    proxy: str = None,
    use_proxy: bool = True
) -> List[Dict]:
    """并发获取所有源的条目"""
    all_entries = []

    # 设置默认超时
    if timeout is None:
        timeout = DEFAULT_FEED_TIMEOUT

    # 使用 asyncio.Semaphore 限制并发数
    semaphore = asyncio.Semaphore(max_workers)

    async def fetch_with_limit(feed):
        async with semaphore:
            return await fetch_single_feed_async(feed, cutoff_time, timeout, proxy=proxy, use_proxy=use_proxy)

    # 创建所有任务
    tasks = [fetch_with_limit(feed) for feed in feeds]

    # 并发执行所有任务
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for feed, result in zip(feeds, results):
        if isinstance(result, Exception):
            print(f"⚠️ 获取失败 {feed['title']}: {result}")
        else:
            all_entries.extend(result)

    return all_entries
