"""飞书推送平台"""

import os
from typing import Dict

import aiohttp

from .base import PushPlatform


class FeishuPlatform(PushPlatform):
    """飞书 Webhook 推送"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key_name = config.get("apiKeyName", "FEISHU_WEBHOOK_URL")
        self.webhook_url = os.environ.get(self.api_key_name, "")

    def validate_config(self, config: Dict) -> bool:
        """检查飞书配置是否有效"""
        if not config.get("enabled", False):
            return False
        api_key_name = config.get("apiKeyName", "FEISHU_WEBHOOK_URL")
        webhook = os.environ.get(api_key_name, "")
        return bool(webhook and "feishu.cn" in webhook)

    async def send(self, content: str, title: str = None):
        """发送到飞书"""
        chunks = self._split_content(content, limit=8000)

        async with aiohttp.ClientSession() as session:
            for chunk in chunks:
                payload = self._build_payload(chunk, title)
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"飞书推送失败: {resp.status} - {text}")
                    data = await resp.json()
                    if data.get("code") != 0:
                        raise RuntimeError(f"飞书推送失败: {data.get('msg')}")

    def _build_payload(self, content: str, title: str = None) -> Dict:
        """构建飞书消息 payload"""
        if title:
            content = f"**{title}**\n{content}"

        return {"msg_type": "text", "content": {"text": content}}

    def _split_content(self, content: str, limit: int = 8000) -> list:
        """飞书文本消息限制8000字符"""
        if len(content) <= limit:
            return [content]

        chunks = []
        lines = content.split("\n")
        current = ""

        for line in lines:
            if len(current) + len(line) + 1 > limit:
                if current:
                    chunks.append(current)
                current = line
            else:
                current += "\n" + line if current else line

        if current:
            chunks.append(current)

        return chunks
