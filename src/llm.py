"""LLM模块 - 评分和汇总"""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def load_prompt(prompt_path: str, **kwargs) -> str:
    """加载提示词模板并填充变量"""
    path = Path(prompt_path)
    if not path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {prompt_path}")

    with open(path, "r", encoding="utf-8") as f:
        template = f.read()

    # 先把模板中的 {{ 和 }} 替换成占位符，避免与format冲突
    template = template.replace("{{", "\x00LEFT_BRACE\x00").replace(
        "}}", "\x00RIGHT_BRACE\x00"
    )

    # 替换变量
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))

    # 恢复 {{ 和 }}
    template = template.replace("\x00LEFT_BRACE\x00", "{").replace(
        "\x00RIGHT_BRACE\x00", "}"
    )

    return template


async def call_llm(prompt: str, config: Dict) -> str:
    """调用LLM API - 统一使用OpenAI兼容接口"""
    model = config.get("model", "gpt-4o-mini")
    base_url = config.get("baseUrl", "https://api.openai.com/v1")
    api_key_name = config.get("apiKeyName", "OPENAI_API_KEY")

    api_key = os.environ.get(api_key_name)
    if not api_key:
        raise ValueError(f"未设置{api_key_name}环境变量")

    import aiohttp

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    url = f"{base_url}/chat/completions"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"LLM API错误: {resp.status} - {text}")

            data = await resp.json()
            return data["choices"][0]["message"]["content"]


def _build_batch_prompt(entries: List[Dict], prompt_path: str = None) -> str:
    """构建批量评分prompt"""
    # 构建entries JSON列表（只包含必要字段）
    entries_for_llm = []
    for e in entries:
        entries_for_llm.append(
            {
                "link": e.get("link", ""),
                "title": e.get("title", "无标题"),
                "source": e.get("source", "未知来源"),
                "published": e.get("published", ""),
                "content": e.get("content", "")[:2000],  # 限制内容长度
            }
        )

    entries_json = json.dumps(entries_for_llm, ensure_ascii=False, indent=2)

    # 从文件加载提示词模板，如果未指定则使用默认路径
    if prompt_path is None:
        prompt_path = "prompts/score_batch.md"

    return load_prompt(prompt_path, entries_json=entries_json)


def _parse_llm_json_response(response: str) -> List[Dict]:
    """解析LLM返回的JSON响应"""
    text = response.strip()

    # 尝试去除markdown代码块
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    # 尝试查找JSON数组
    if text.startswith("[") and text.endswith("]"):
        return json.loads(text)

    # 尝试从文本中提取JSON数组
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return json.loads(match.group())

    raise ValueError(f"无法从响应中解析JSON: {response[:200]}...")


def _split_entries_for_batch(
    entries: List[Dict], max_prompt_chars: int = 10000
) -> List[List[Dict]]:
    """将entries分成多个批次，每批不超过max_prompt_chars字符"""
    if not entries:
        return []

    batches = []
    current_batch = []
    current_chars = 0

    # 预留prompt模板和JSON包装的空间
    overhead = len(_build_batch_prompt([])) + 500

    for entry in entries:
        # 估算该entry在JSON中的字符数
        entry_chars = len(
            json.dumps(
                {
                    "link": entry.get("link", ""),
                    "title": entry.get("title", "")[:100],
                    "source": entry.get("source", ""),
                    "published": entry.get("published", ""),
                    "content": entry.get("content", "")[:2000],
                },
                ensure_ascii=False,
            )
        )

        # 如果当前批次加上这个entry会超出限制，且当前批次不为空，则创建新批次
        if current_chars + entry_chars + overhead > max_prompt_chars and current_batch:
            batches.append(current_batch)
            current_batch = [entry]
            current_chars = entry_chars
        else:
            current_batch.append(entry)
            current_chars += entry_chars

    # 添加最后一个批次
    if current_batch:
        batches.append(current_batch)

    return batches


async def _score_single_batch(entries: List[Dict], config: Dict) -> List[Dict]:
    """对单批entries进行评分"""
    # 从config获取批量评分提示词路径
    prompt_path = config.get("prompts", {}).get("score_batch", "prompts/score_batch.md")
    prompt = _build_batch_prompt(entries, prompt_path)

    try:
        response = await call_llm(prompt, config)
        results = _parse_llm_json_response(response)

        if not isinstance(results, list):
            raise ValueError(f"LLM返回的不是数组: {type(results)}")

        if len(results) != len(entries):
            raise ValueError(f"返回数量不匹配: 输入{len(entries)}, 返回{len(results)}")

        return results

    except Exception as e:
        print(f"⚠️ 批次评分失败: {e}")
        # 返回默认评分
        return [
            {
                "link": e.get("link", ""),
                "tags": [],
                "score": 50,
                "summary": e.get("content", "")[:100] + "..."
                if e.get("content")
                else "",
            }
            for e in entries
        ]


async def score_batch(entries: List[Dict], config: Dict) -> List[Dict]:
    """
    批量评分 - 智能分批处理

    根据数据量自动决定分批策略：
    - 小批量：一次性发送
    - 大批量：分成多个批次并行处理
    """
    if not entries:
        return []

    # 获取分批配置
    max_prompt_chars = config.get("max_prompt_chars", 10000)
    max_concurrent_batches = config.get("max_concurrent_batches", 3)

    # 分批
    batches = _split_entries_for_batch(entries, max_prompt_chars)
    print(f"📦 分成 {len(batches)} 个批次评分 (共 {len(entries)} 条)")

    # 如果只有一批，直接处理
    if len(batches) == 1:
        scores = await _score_single_batch(batches[0], config)
        return _merge_scores(entries, scores)

    # 多批并行处理（限制并发数）
    semaphore = asyncio.Semaphore(max_concurrent_batches)

    async def score_with_limit(batch):
        async with semaphore:
            return await _score_single_batch(batch, config)

    # 并发处理所有批次
    batch_tasks = [score_with_limit(batch) for batch in batches]
    batch_results = await asyncio.gather(*batch_tasks)

    # 合并所有评分结果
    all_scores = []
    for scores in batch_results:
        all_scores.extend(scores)

    return _merge_scores(entries, all_scores)


def _merge_scores(entries: List[Dict], scores: List[Dict]) -> List[Dict]:
    """将评分结果合并到原始entries中"""
    # 构建link到score的映射
    score_map = {s.get("link"): s for s in scores if s.get("link")}

    merged = []
    for entry in entries:
        link = entry.get("link")
        score_data = score_map.get(link, {})

        # 确保 score 为整数类型
        score_value = score_data.get("score", entry.get("score"))
        if isinstance(score_value, str):
            try:
                score_value = int(score_value)
            except (ValueError, TypeError):
                score_value = 0

        merged.append(
            {
                **entry,
                "tags": score_data.get("tags", entry.get("tags", [])),
                "score": score_value,
                "summary": score_data.get("summary", entry.get("summary", "")),
            }
        )

    return merged


async def generate_immediate_push(
    entries: List[Dict], config: Dict, recent_push_context: str = ""
) -> str:
    """生成即时推送内容

    Args:
        entries: 原始entries列表（调用方已筛选好高分条目）
        config: LLM配置
        recent_push_context: 近期推送上下文，用于去重
    """
    prompt_path = config.get("prompts", {}).get(
        "immediate_push", "prompts/immediate_push.txt"
    )

    # 直接使用传入的entries，转为JSON格式传给prompt
    prompt = load_prompt(
        prompt_path,
        count=len(entries),
        entries=json.dumps(entries, ensure_ascii=False, indent=2),
        recent_push_context=recent_push_context,
    )

    try:
        return await call_llm(prompt, config)
    except Exception as e:
        print(f"⚠️ 生成即时推送失败: {e}")
        lines = ["🔥 AI 重磅资讯", ""]
        for e in entries:
            lines.append(f"### {e['title']}")
            lines.append(f"**来源**: {e['source']} | **评分**: {e.get('score', 0)}")
            lines.append(f"{e.get('summary', '')}")
            lines.append(f"[查看原文]({e['link']})")
            lines.append("")
        return "\n".join(lines)


async def compose_digest(
    entries: List[Dict],
    context: List[Dict],
    config: Dict,
    recent_push_context: str = "",
) -> str:
    """生成定时汇总推送内容

    Args:
        entries: 原始entries列表
        context: 历史碎片化信息（用于去重参考），只保留 title, published, tags, summary, source
        config: LLM配置
        recent_push_context: 近期汇总推送上下文，用于去重
    """
    prompt_path = config.get("prompts", {}).get("digest", "prompts/digest.md")

    # context 只保留必要字段，拼接成字符串
    context_text = []
    for c in context:
        tags_str = ", ".join(c.get("tags", [])) if c.get("tags") else ""
        context_text.append(
            f"[score: {c.get('score', 0)}] title:{c.get('title', '')}\n"
            f"published: {c.get('published', '')}\n"
            f"tags: {tags_str}\n"
            f"source: {c.get('source', '')}\n"
            f"summary: {c.get('summary', '')}"
        )

    prompt = load_prompt(
        prompt_path,
        count=len(entries),
        entries=json.dumps(entries, ensure_ascii=False, indent=2),
        context="\n\n".join(context_text),
        recent_push_context=recent_push_context,
        date=datetime.now().strftime("%Y-%m-%d"),
    )

    try:
        return await call_llm(prompt, config)
    except Exception:
        raise
