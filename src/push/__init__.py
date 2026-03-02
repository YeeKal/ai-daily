"""推送平台模块"""

from typing import Dict, Optional

from .base import PushPlatform
from .discord import DiscordPlatform
from .feishu import FeishuPlatform


def create_platform(name: str, config: Dict) -> Optional[PushPlatform]:
    """工厂函数，创建推送平台实例"""
    platforms = {
        "discord": DiscordPlatform,
        "feishu": FeishuPlatform,
    }

    if name not in platforms:
        raise ValueError(f"未知推送平台: {name}")

    platform_class = platforms[name]
    platform = platform_class(config)

    if not platform.validate_config(config):
        return None

    return platform


async def send_to_platforms(content: str, push_config: Dict, title: str = None):
    """发送内容到所有已启用且配置有效的平台"""
    for platform_name, platform_conf in push_config.items():
        platform = create_platform(platform_name, platform_conf)
        if platform is None:
            continue

        try:
            await platform.send(content, title)
            print(f"✅ 已推送到 {platform_name}")
        except Exception as e:
            print(f"❌ 推送到 {platform_name} 失败: {e}")
