"""主程序逻辑测试"""

import json
import pytest
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from main import (
    now_local,
    parse_time_to_local,
    calculate_push_times,
    collect_entries_for_push,
    main as run_main,
)


class TestNowLocal:
    """测试获取本地时间"""

    def test_now_local_with_config(self, sample_config):
        result = now_local(sample_config)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_now_local_without_config(self):
        result = now_local()
        assert isinstance(result, datetime)


class TestParseTimeToLocal:
    """测试时间解析"""

    def test_parse_iso_format(self, sample_config):
        result = parse_time_to_local("2024-01-15T10:30:00+00:00", sample_config)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_with_z_suffix(self, sample_config):
        result = parse_time_to_local("2024-01-15T10:30:00Z", sample_config)
        assert result is not None
        assert result.year == 2024

    def test_parse_invalid_format(self, sample_config):
        result = parse_time_to_local("not-a-date", sample_config)
        assert result is None

    def test_parse_none(self, sample_config):
        result = parse_time_to_local("", sample_config)
        assert result is None


class TestCalculatePushTimes:
    """测试推送时间计算"""

    def test_calculate_single_cron(self, sample_config):
        times = calculate_push_times(["30 8 * * *"], config=sample_config)
        assert len(times) == 1
        assert times[0].hour == 8
        assert times[0].minute == 30

    def test_calculate_multiple_crons(self, sample_config):
        times = calculate_push_times(["0 8 * * *", "0 17 * * *"], config=sample_config)
        assert len(times) == 2
        hours = [t.hour for t in times]
        assert 8 in hours
        assert 17 in hours

    def test_calculate_with_offset(self, sample_config):
        times = calculate_push_times(["0 8 * * *"], offset_days=1, config=sample_config)
        assert len(times) == 1
        expected_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        assert times[0].date() == expected_date

    def test_calculate_invalid_cron(self, sample_config):
        times = calculate_push_times(["invalid cron"], config=sample_config)
        assert times == []


class TestCollectEntriesForPush:
    """测试收集推送条目"""

    def test_collect_no_files(self, temp_dir):
        to_push, context = collect_entries_for_push(
            last_push_time=None, context_days=2, min_score=60, data_dir=str(temp_dir)
        )
        assert to_push == []
        assert context == []

    def test_collect_with_low_score(self, temp_dir):
        now = datetime.now(timezone.utc)

        data = {
            "meta": {"date": now.date().isoformat()},
            "entries": [
                {
                    "title": "Low Score",
                    "link": "https://example.com/1",
                    "score": 30,
                    "fetched_at": now.isoformat(),
                }
            ],
        }

        fetch_file = temp_dir / f"fetch-{now.date().isoformat()}.json"
        with open(fetch_file, "w") as f:
            json.dump(data, f)

        to_push, context = collect_entries_for_push(
            last_push_time=None, context_days=2, min_score=60, data_dir=str(temp_dir)
        )

        assert len(to_push) == 0

    def test_collect_with_high_score(self, temp_dir):
        now = datetime.now(timezone.utc)

        data = {
            "meta": {"date": now.date().isoformat()},
            "entries": [
                {
                    "title": "High Score",
                    "link": "https://example.com/1",
                    "score": 85,
                    "fetched_at": now.isoformat(),
                }
            ],
        }

        fetch_file = temp_dir / f"fetch-{now.date().isoformat()}.json"
        with open(fetch_file, "w") as f:
            json.dump(data, f)

        to_push, context = collect_entries_for_push(
            last_push_time=None, context_days=2, min_score=60, data_dir=str(temp_dir)
        )

        assert len(to_push) == 1
        assert to_push[0]["score"] == 85

    def test_collect_with_last_push_time(self, temp_dir):
        now = datetime.now(timezone.utc)
        last_push = now - timedelta(hours=2)

        data = {
            "meta": {"date": now.date().isoformat()},
            "entries": [
                {
                    "title": "New Entry",
                    "link": "https://example.com/1",
                    "score": 80,
                    "fetched_at": now.isoformat(),
                },
                {
                    "title": "Old Entry",
                    "link": "https://example.com/2",
                    "score": 80,
                    "fetched_at": last_push.isoformat(),
                },
            ],
        }

        fetch_file = temp_dir / f"fetch-{now.date().isoformat()}.json"
        with open(fetch_file, "w") as f:
            json.dump(data, f)

        to_push, context = collect_entries_for_push(
            last_push_time=last_push,
            context_days=2,
            min_score=60,
            data_dir=str(temp_dir),
        )

        assert len(to_push) == 1
        assert to_push[0]["title"] == "New Entry"

    def test_collect_context_limit(self, temp_dir):
        now = datetime.now(timezone.utc)

        entries = [
            {
                "title": f"Entry{i}",
                "link": f"https://example.com/{i}",
                "score": 50 + i,
                "fetched_at": now.isoformat(),
            }
            for i in range(60)
        ]

        data = {"meta": {"date": now.date().isoformat()}, "entries": entries}

        fetch_file = temp_dir / f"fetch-{now.date().isoformat()}.json"
        with open(fetch_file, "w") as f:
            json.dump(data, f)

        to_push, context = collect_entries_for_push(
            last_push_time=None, context_days=2, min_score=60, data_dir=str(temp_dir)
        )

        assert len(context) <= 50

    def test_collect_multi_day(self, temp_dir):
        from src.config import get_timezone

        tz = get_timezone()
        today = datetime.now(tz)
        yesterday = today - timedelta(days=1)

        today_data = {
            "meta": {"date": today.date().isoformat()},
            "entries": [
                {
                    "title": "Today Entry",
                    "link": "https://example.com/1",
                    "score": 80,
                    "fetched_at": today.isoformat(),
                }
            ],
        }

        yesterday_data = {
            "meta": {"date": yesterday.date().isoformat()},
            "entries": [
                {
                    "title": "Yesterday Entry",
                    "link": "https://example.com/2",
                    "score": 75,
                    "fetched_at": yesterday.isoformat(),
                }
            ],
        }

        (temp_dir / f"fetch-{today.date().isoformat()}.json").write_text(
            json.dumps(today_data)
        )
        (temp_dir / f"fetch-{yesterday.date().isoformat()}.json").write_text(
            json.dumps(yesterday_data)
        )

        to_push, context = collect_entries_for_push(
            last_push_time=None, context_days=2, min_score=60, data_dir=str(temp_dir)
        )

        assert len(to_push) >= 1


class TestMainStartup:
    """测试主程序启动流程"""

    @pytest.mark.asyncio
    async def test_main_checks_llm_before_starting_loops(self, sample_config):
        with patch("main.load_config", return_value=sample_config), patch(
            "main.check_llm_available", new_callable=AsyncMock
        ) as mock_check, patch(
            "main.fetch_loop", new_callable=AsyncMock
        ) as mock_fetch_loop, patch(
            "main.push_loop", new_callable=AsyncMock
        ) as mock_push_loop:
            await run_main()

        mock_check.assert_awaited_once_with(sample_config["llm"])
        mock_fetch_loop.assert_awaited_once_with(sample_config)
        mock_push_loop.assert_awaited_once_with(sample_config)

    @pytest.mark.asyncio
    async def test_main_exits_when_llm_health_check_fails(self, sample_config):
        with patch("main.load_config", return_value=sample_config), patch(
            "main.check_llm_available", new_callable=AsyncMock
        ) as mock_check, patch(
            "main.fetch_loop", new_callable=AsyncMock
        ) as mock_fetch_loop, patch(
            "main.push_loop", new_callable=AsyncMock
        ) as mock_push_loop:
            mock_check.side_effect = RuntimeError("health failed")

            await run_main()

        mock_check.assert_awaited_once_with(sample_config["llm"])
        mock_fetch_loop.assert_not_called()
        mock_push_loop.assert_not_called()
