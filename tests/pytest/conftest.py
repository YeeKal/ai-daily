"""pytest fixtures for daily-news project"""

import json
import pytest
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def temp_dir(tmp_path):
    """临时目录fixture"""
    return tmp_path


@pytest.fixture
def sample_config():
    """示例配置"""
    return {
        "sources": {
            "base_opml": "resources/rss.opml",
            "add": [],
            "block": [],
            "block_domains": ["*.substack.com"],
        },
        "filter": {
            "min_score": 60,
            "hot_threshold": 90,
            "context_days": 2,
            "keep_days": 7,
        },
        "schedule": {
            "fetch_interval_minutes": 30,
            "push_cron": ["0 8 * * *", "0 17 * * *"],
            "timezone_hours": 8,
        },
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "baseUrl": "https://api.openai.com/v1",
            "apiKeyName": "OPENAI_API_KEY",
            "max_prompt_chars": 10000,
            "max_concurrent_batches": 3,
        },
        "push": {
            "discord": {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test/abc",
            },
            "feishu": {"enabled": False, "apiKeyName": "FEISHU_WEBHOOK_URL"},
        },
    }


@pytest.fixture
def sample_opml(temp_dir):
    """示例OPML文件"""
    opml_content = """<?xml version="1.0"?>
<opml version="2.0">
    <body>
        <outline title="Feed1" xmlUrl="http://feed1.com/rss" type="rss" category="tech"/>
        <outline title="Feed2" xmlUrl="http://feed2.com/rss" type="rss" category="ai"/>
    </body>
</opml>"""
    opml_file = temp_dir / "test.opml"
    opml_file.write_text(opml_content)
    return str(opml_file)


@pytest.fixture
def sample_entry():
    """示例新闻条目"""
    return {
        "title": "Test Article Title",
        "link": "https://example.com/article",
        "published": datetime.now(timezone.utc).isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "Test Source",
        "content": "<p>Test content</p>",
        "summary": "Test summary",
        "tags": ["AI", "Tech"],
        "score": 85,
    }


@pytest.fixture
def sample_entries():
    """示例新闻条目列表"""
    now = datetime.now(timezone.utc)
    return [
        {
            "title": "Article 1",
            "link": "https://example.com/1",
            "published": now.isoformat(),
            "fetched_at": now.isoformat(),
            "source": "Source1",
            "content": "Content 1",
            "summary": "Summary 1",
            "tags": ["AI"],
            "score": 85,
        },
        {
            "title": "Article 2",
            "link": "https://example.com/2",
            "published": (now - timedelta(hours=1)).isoformat(),
            "fetched_at": now.isoformat(),
            "source": "Source2",
            "content": "Content 2",
            "summary": "Summary 2",
            "tags": ["Tech"],
            "score": 70,
        },
        {
            "title": "Article 3",
            "link": "https://example.com/3",
            "published": (now - timedelta(hours=2)).isoformat(),
            "fetched_at": now.isoformat(),
            "source": "Source3",
            "content": "Content 3",
            "summary": "Summary 3",
            "tags": ["News"],
            "score": 55,
        },
    ]


@pytest.fixture
def sample_fetch_json(temp_dir, sample_entries):
    """示例fetch JSON文件"""
    data = {
        "meta": {"date": datetime.now().date().isoformat()},
        "entries": sample_entries,
    }
    json_file = temp_dir / "fetch-test.json"
    json_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return str(json_file)


@pytest.fixture
def mock_httpx_session():
    """Mock httpx/aiohttp session"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = "<rss></rss>"

    mock_session = MagicMock()
    mock_session.__aenter__ = MagicMock(return_value=mock_session)
    mock_session.__aexit__ = MagicMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_response)

    return mock_session
