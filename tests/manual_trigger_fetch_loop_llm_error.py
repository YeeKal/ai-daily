#!/usr/bin/env python3
"""手工触发 LLM 错误告警。

用法：
    source ../.venv/bin/activate
    python tests/manual_trigger_fetch_loop_llm_error.py --scenario score
    python tests/manual_trigger_fetch_loop_llm_error.py --scenario immediate
    python tests/manual_trigger_fetch_loop_llm_error.py --scenario digest
    python tests/manual_trigger_fetch_loop_llm_error.py --scenario all

场景说明：
- score: 走 fetch_loop -> run_fetch_job -> score_batch，触发评分错误通知
- immediate: 走 run_fetch_job -> generate_immediate_push，触发即时推送生成错误通知
- digest: 走 run_push_job -> compose_digest，触发汇总生成错误通知
- all: 依次触发以上三类真实通知
"""

import argparse
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.main import fetch_loop, run_fetch_job, run_push_job

MOCK_FETCH_ENTRIES = [
    {
        "title": "Manual Mock News 1",
        "link": "https://example.com/mock-1",
        "published": "2026-03-08T20:00:00+08:00",
        "source": "Manual Mock Source",
        "content": "<p>Mock content 1</p>",
        "tags": [],
        "score": 0,
        "summary": "",
    },
    {
        "title": "Manual Mock News 2",
        "link": "https://example.com/mock-2",
        "published": "2026-03-08T20:05:00+08:00",
        "source": "Manual Mock Source",
        "content": "<p>Mock content 2</p>",
        "tags": [],
        "score": 0,
        "summary": "",
    },
]

MOCK_HOT_SCORED_ENTRIES = [
    {
        "title": "Manual Hot News",
        "link": "https://example.com/hot-1",
        "published": "2026-03-08T21:00:00+08:00",
        "source": "Manual Mock Source",
        "content": "mock content",
        "tags": ["AI"],
        "score": 95,
        "summary": "manual hot summary",
    }
]

MOCK_DIGEST_ENTRIES = [
    {
        "title": "Manual Digest News",
        "link": "https://example.com/digest-1",
        "published": "2026-03-08T19:00:00+08:00",
        "fetched_at": "2026-03-08T21:00:00+08:00",
        "source": "Manual Mock Source",
        "content": "mock digest content",
        "tags": ["AI"],
        "score": 88,
        "summary": "manual digest summary",
    }
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="手工触发 LLM 错误告警")
    parser.add_argument(
        "--scenario",
        choices=["score", "immediate", "digest", "all"],
        default="score",
        help="要触发的错误场景，默认 score",
    )
    return parser.parse_args()


async def _trigger_score_error(config):
    mock_sources = [
        {
            "title": "Manual Mock Feed",
            "xmlUrl": "https://example.com/rss.xml",
            "category": "AI",
        }
    ]

    tmp_dir = Path("test/news-data")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fetch_file = tmp_dir / "manual-fetch-loop-error.json"

    async def fake_fetch_all_feeds(*args, **kwargs):
        return MOCK_FETCH_ENTRIES

    async def fake_sleep(seconds: float):
        if seconds <= 0:
            return
        raise asyncio.CancelledError()

    with (
        patch("src.main.merge_sources", return_value=mock_sources),
        patch("src.main.fetch_all_feeds", side_effect=fake_fetch_all_feeds),
        patch("src.main.load_existing_links", return_value=set()),
        patch("src.main.get_fetch_file", return_value=str(fetch_file)),
        patch(
            "src.llm.call_llm",
            side_effect=RuntimeError("manual mock llm scoring error"),
        ),
        patch("src.main.asyncio.sleep", side_effect=fake_sleep),
    ):
        await fetch_loop(config)


async def _trigger_immediate_push_error(config):
    tmp_dir = Path("test/news-data")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fetch_file = tmp_dir / "manual-immediate-push-error.json"

    async def fake_fetch_all_feeds(*args, **kwargs):
        return [dict(entry) for entry in MOCK_HOT_SCORED_ENTRIES]

    with (
        patch(
            "src.main.merge_sources",
            return_value=[
                {
                    "title": "Manual",
                    "xmlUrl": "https://example.com/rss.xml",
                    "category": "AI",
                }
            ],
        ),
        patch("src.main.fetch_all_feeds", side_effect=fake_fetch_all_feeds),
        patch("src.main.load_existing_links", return_value=set()),
        patch("src.main.get_fetch_file", return_value=str(fetch_file)),
        patch(
            "src.main.score_batch",
            return_value=([dict(entry) for entry in MOCK_HOT_SCORED_ENTRIES], []),
        ),
        patch(
            "src.main.generate_immediate_push",
            return_value=("", "manual mock immediate push error"),
        ),
    ):
        await run_fetch_job(config)


async def _trigger_digest_error(config):
    with (
        patch(
            "src.main.collect_entries_for_push",
            return_value=([dict(entry) for entry in MOCK_DIGEST_ENTRIES], []),
        ),
        patch("src.main.get_last_push_file", return_value=None),
        patch(
            "src.main.compose_digest",
            side_effect=RuntimeError("manual mock compose digest error"),
        ),
    ):
        await run_push_job(config)


async def _run_selected_scenarios(scenario: str) -> None:
    config = load_config()

    if scenario in {"score", "all"}:
        print("\n🚨 触发 score_batch 错误通知")
        await _trigger_score_error(config)

    if scenario in {"immediate", "all"}:
        print("\n🚨 触发 generate_immediate_push 错误通知")
        await _trigger_immediate_push_error(config)

    if scenario in {"digest", "all"}:
        print("\n🚨 触发 compose_digest 错误通知")
        await _trigger_digest_error(config)


def main() -> int:
    args = parse_args()

    print("🚨 即将触发真实的 LLM 错误提醒")
    print(f"   - 场景: {args.scenario}")
    print("   - 推送: 使用当前 config.json 和环境变量中的真实渠道")

    try:
        asyncio.run(_run_selected_scenarios(args.scenario))
    except KeyboardInterrupt:
        print("\n已取消")
        return 130

    print("✅ 脚本执行完成；如果推送配置正确，你应该已经收到对应错误提醒。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
