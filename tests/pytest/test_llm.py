"""LLM模块测试"""

import json
import pytest
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from llm import (
    load_prompt,
    _parse_llm_json_response,
    _split_entries_for_batch,
    _build_batch_prompt,
    _merge_scores,
    _score_single_batch,
    call_llm,
    check_llm_available,
    generate_immediate_push,
    score_batch,
)


class TestLoadPrompt:
    """测试提示词加载"""

    def test_load_prompt_basic(self, temp_dir):
        prompt_file = temp_dir / "test.txt"
        prompt_file.write_text("Hello {name}!")

        result = load_prompt(str(prompt_file), name="World")
        assert result == "Hello World!"

    def test_load_prompt_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent.txt")

    def test_load_prompt_with_braces(self, temp_dir):
        prompt_file = temp_dir / "test.txt"
        prompt_file.write_text("Hello {name}, curly braces: { }")

        result = load_prompt(str(prompt_file), name="World")
        assert result == "Hello World, curly braces: { }"

    def test_load_prompt_multiple_vars(self, temp_dir):
        prompt_file = temp_dir / "test.txt"
        prompt_file.write_text("{greeting} {name}, you have {count} messages")

        result = load_prompt(str(prompt_file), greeting="Hi", name="Alice", count=5)
        assert result == "Hi Alice, you have 5 messages"


class TestParseLlmJsonResponse:
    """测试LLM响应解析"""

    def test_parse_json_array(self):
        response = '[{"link": "https://example.com", "score": 80}]'
        result = _parse_llm_json_response(response)
        assert len(result) == 1
        assert result[0]["link"] == "https://example.com"
        assert result[0]["score"] == 80

    def test_parse_with_markdown_codeblock(self):
        response = """```json
[{"link": "https://example.com", "score": 80}]
```"""
        result = _parse_llm_json_response(response)
        assert len(result) == 1

    def test_parse_with_codeblock(self):
        response = """```
[{"link": "https://example.com", "score": 80}]
```"""
        result = _parse_llm_json_response(response)
        assert len(result) == 1

    def test_parse_invalid_response(self):
        response = "This is not JSON at all"
        with pytest.raises(ValueError):
            _parse_llm_json_response(response)


class TestSplitEntriesForBatch:
    """测试条目分批"""

    def test_split_empty(self):
        result = _split_entries_for_batch([])
        assert result == []

    def test_split_single_batch(self):
        entries = [
            {
                "link": f"https://example.com/{i}",
                "title": f"Title{i}",
                "content": "x" * 100,
            }
            for i in range(5)
        ]
        result = _split_entries_for_batch(entries, max_prompt_chars=10000)
        assert len(result) == 1

    def test_split_multiple_batches(self):
        entries = [
            {
                "link": f"https://example.com/{i}",
                "title": f"Title{i}",
                "content": "x" * 5000,
            }
            for i in range(10)
        ]
        result = _split_entries_for_batch(entries, max_prompt_chars=10000)
        assert len(result) > 1


class TestBuildBatchPrompt:
    """测试构建批量提示词"""

    def test_build_batch_prompt_basic(self):
        entries = [
            {
                "link": "https://example.com/1",
                "title": "Title1",
                "source": "Source1",
                "published": "2024-01-15",
                "content": "Content",
            }
        ]
        result = _build_batch_prompt(entries)
        assert "Title1" in result
        assert "https://example.com/1" in result


class TestMergeScores:
    """测试评分合并"""

    def test_merge_scores_basic(self):
        entries = [
            {"link": "https://example.com/1", "title": "Title1"},
            {"link": "https://example.com/2", "title": "Title2"},
        ]
        scores = [
            {
                "link": "https://example.com/1",
                "score": 85,
                "tags": ["AI"],
                "summary": "Summary1",
            },
            {
                "link": "https://example.com/2",
                "score": 70,
                "tags": ["Tech"],
                "summary": "Summary2",
            },
        ]
        result = _merge_scores(entries, scores)

        assert result[0]["score"] == 85
        assert result[0]["tags"] == ["AI"]
        assert result[1]["score"] == 70

    def test_merge_scores_partial(self):
        entries = [
            {"link": "https://example.com/1", "title": "Title1", "score": 50},
            {"link": "https://example.com/2", "title": "Title2", "score": 60},
        ]
        scores = [{"link": "https://example.com/1", "score": 85}]
        result = _merge_scores(entries, scores)

        assert result[0]["score"] == 85
        assert result[1]["score"] == 60


class TestCallLlm:
    """测试LLM调用"""

    @pytest.mark.asyncio
    async def test_call_llm_success(self):
        config = {
            "model": "gpt-4",
            "baseUrl": "https://api.openai.com/v1",
            "apiKeyName": "OPENAI_API_KEY",
        }

        with patch("llm.call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Test response"

            result = await mock_call("Test prompt", config)

        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_call_llm_missing_key(self):
        config = {"model": "gpt-4", "apiKeyName": "MISSING_KEY"}

        with pytest.raises(ValueError, match="未设置MISSING_KEY"):
            await call_llm("Test prompt", config)


class TestLlmHealthCheck:
    """测试LLM可用性检查"""

    @pytest.mark.asyncio
    async def test_check_llm_available_success(self, sample_config):
        with patch("llm.call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "OK"

            result = await check_llm_available(sample_config["llm"])

        assert result == "OK"

    @pytest.mark.asyncio
    async def test_check_llm_available_empty_response(self, sample_config):
        with patch("llm.call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "   "

            with pytest.raises(RuntimeError, match="返回空响应"):
                await check_llm_available(sample_config["llm"])


class TestImmediatePush:
    """测试即时推送生成"""

    @pytest.mark.asyncio
    async def test_generate_immediate_push_failure_returns_error(
        self, sample_entries, sample_config
    ):
        with patch("llm.load_prompt", return_value="prompt"), patch(
            "llm.call_llm", new_callable=AsyncMock
        ) as mock_call:
            mock_call.side_effect = RuntimeError("boom")

            content, error = await generate_immediate_push(
                sample_entries[:1], sample_config["llm"], recent_push_context=""
            )

        assert content == ""
        assert error == "生成即时推送失败: boom"


class TestScoreBatch:
    """测试批量评分"""

    @pytest.mark.asyncio
    async def test_score_batch_empty(self, sample_config):
        result, errors = await score_batch([], sample_config["llm"])
        assert result == []
        assert errors == []

    @pytest.mark.asyncio
    async def test_score_batch_single(self, sample_entries, sample_config):
        entries = sample_entries[:1]

        mock_scores = [
            {
                "link": entries[0]["link"],
                "score": 85,
                "tags": ["AI"],
                "summary": "Test summary",
            }
        ]

        with patch("llm._score_single_batch", new_callable=AsyncMock) as mock_score:
            mock_score.return_value = (mock_scores, [])
            result, errors = await score_batch(entries, sample_config["llm"])

        assert len(result) == 1
        assert result[0]["score"] == 85
        assert errors == []

    @pytest.mark.asyncio
    async def test_score_single_batch_failure_returns_empty_results(
        self, sample_entries, sample_config
    ):
        with patch("llm.call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = RuntimeError("boom")
            results, errors = await _score_single_batch(
                sample_entries[:2], sample_config["llm"]
            )

        assert results == []
        assert errors == ["批次1 评分失败: boom"]

    @pytest.mark.asyncio
    async def test_score_single_batch_reconcile_partial_results(
        self, sample_entries, sample_config
    ):
        entries = sample_entries[:2]
        llm_results = [
            {
                "link": entries[0]["link"],
                "score": 91,
                "tags": ["AI"],
                "summary": "Matched result",
            }
        ]

        with patch("llm.call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = json.dumps(llm_results, ensure_ascii=False)
            results, errors = await _score_single_batch(entries, sample_config["llm"])

        assert len(results) == 1
        assert results[0]["score"] == 91
        assert len(errors) == 1
        assert "评分结果异常" in errors[0]
        assert "输入2" in errors[0]
        assert "返回1" in errors[0]
        assert "匹配1" in errors[0]
