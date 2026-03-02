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
        return bool(webhook)

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
        """
        构建飞书卡片消息 payload，支持 Markdown，
        参考  https://open.feishu.cn/document/feishu-cards/card-json-v2-structure
        """

        header = {}
        if title:
            header = {
                "title": {"content": title, "tag": "plain_text"},
                "template": "blue",
            }

        return {
            "msg_type": "interactive",
            "card": {
                "schema": "2.0",  # 【重点1】显式声明使用 V2 版本结构
                "header": header,
                "body": {  # 【重点2】V2 中，所有的内容元素都必须放在 body 里面
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": content,
                            "text_align": "left",  # 可选：left / center / right
                        },
                    ],
                },
            },
        }

    def _split_content(self, content: str, limit: int = 8000) -> list:
        """飞书卡片消息 markdown 元素限制 8000 字符"""
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
