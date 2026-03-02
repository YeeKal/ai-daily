# AI Daily 每日资讯推送系统

AI 驱动的 RSS 新闻聚合与推送系统，支持 400+ 信息源，使用 LLM 智能评分筛选，推送到 Discord/飞书。热门消息实时推送，每日消息定时推送

## 项目概述

AIDaily 是一个面向 AI 领域从业者和爱好者的资讯聚合工具，通过抓取全球主流 AI 媒体、博客、社交平台的信息，借助 LLM 进行智能评分和内容整理，最终将高质量资讯推送到用户指定的平台。

**核心功能：**
- 400+ RSS 源聚合（热门Twitter、大厂博客(google,anthropic, openai,deepseek)，ai类公众等）
- LLM 智能评分筛选，自动过滤低质量内容
- 热点即时推送 + 每日定时汇总，双模式运行

## 两大核心优势

### 1. 即时推送 —— 避免错过重要信息

当系统检测到评分极高（≥90分）的热点新闻时，会立即推送到指定平台，确保重要信息不过时。

**适用场景：** 重大发布、突破性技术进展、行业重磅新闻

### 2. 每日汇总 —— 把握 AI 全局近况

每天定时（如早8点、晚5点）汇总近期高评分资讯，帮助用户快速了解 AI 领域整体动态。

**适用场景：** 碎片化时间回顾、行业趋势把握

---

## 快速开始

### 环境要求

- Python 3.10+

### 1. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件，添加以下配置：

```bash
# LLM API（支持 OpenRouter 等兼容 OpenAI API 的服务）
OPENROUTER_API_KEY=your_api_key_here

# Discord Webhook（即时推送和定时汇总都通过此渠道）
DISCORD_WEBHOOK_URL=your_webhook_url_here

# 飞书 Webhook
FEISHU_WEBHOOK_URL=your_feishu_webhook_url_here
```

**获取 Discord Webhook：**
1. 进入 Discord 服务器设置 → 整合 → Webhooks
2. 创建新 Webhook，复制 URL

### 4. 运行程序

```bash
python -m src.main
```

首次运行会自动创建 `news-data/` 目录并开始抓取数据。

> 若未配置推送渠道，则可以在 news-data 目录查看生成的push信息

---

## 配置详解（config.json）

完整的配置文件结构如下，每个字段都有详细说明：

```json
{
    // 订阅源管理
    "sources": {
        "base_opml": "resources/rss.opml",  // 基础OPML文件，包含400+预设源
        "add": [  // 自定义添加的RSS源
            {
                "title": "OpenAI News",
                "xmlUrl": "https://openai.com/news/rss.xml",
                "category": "AI"
            }
        ],
        "block": [  // 手动屏蔽的源，精确匹配xmlUrl
            {
                "title": "Google Developers Blog",
                "xmlUrl": "https://developers.googleblog.com/feeds/posts/default"
            }
        ],
        "block_domains": ["*.substack.com", "*.youtube.com"]  // 域名屏蔽，支持通配符
    },

    // 内容过滤
    "filter": {
        "min_score": 60,  // 最低评分阈值，低于此分不推送
        "hot_threshold": 90,  // 热点阈值，达到立即即时推送
        "context_days": 3,  // 汇总时参考的历史天数
        "keep_days": 7,  // 数据保留天数
        "push_context_days": 5,  // 汇总推送去重的上下文有效天数
        "no_content_marker": "[NO_NEW_CONTENT]"  // LLM返回的无内容标记，用于判断是否跳过推送
    },

    // 调度配置
    "schedule": {
        "fetch_interval_minutes": 30,  // RSS抓取间隔（分钟）
        "fetch_lookback_minutes": 120,  // RSS冗余缓存时间（分钟），必须大于fetch_interval_minutes，用于防止RSS延迟导致漏读
        "push_cron": ["0 8 * * *", "0 17 * * *"],  // 定时推送cron表达式
        "timezone_hours": 8  // 时区偏移（8=北京时间）
    },

    // 抓取配置
    "fetch": {
        "max_workers": 10,  // 最大并发数
        "timeout": 10  // 单请求超时（秒）
    },

    // LLM配置
    "llm": {
        "provider": "openai",  // 提供商类型
        "model": "x-ai/grok-4.1-fast",  // 模型名称
        "baseUrl": "https://openrouter.ai/api/v1",  // API端点
        "apiKeyName": "OPENROUTER_API_KEY",  // 环境变量名
        "max_prompt_chars": 128000,  // 单次prompt最大字符数
        "max_concurrent_batches": 3,  // 最大并发批次数
        "prompts": {  // prompt文件路径
            "score": "prompts/score.txt",
            "score_batch": "prompts/score_batch.txt",
            "immediate_push": "prompts/immediate_push.txt",
            "digest": "prompts/digest.txt"
        }
    },

    // 推送配置
    "push": {
        "discord": {
            "enabled": true,  // 是否启用
            "apiKeyName": "DISCORD_WEBHOOK_URL"  // Webhook环境变量名
        },
        "feishu": {
            "enabled": false,
            "apiKeyName": "FEISHU_WEBHOOK_URL"
        }
    }
}
```

### sources —— 订阅源管理

| 字段 | 类型 | 说明 |
|------|------|------|
| `base_opml` | string | 基础 OPML 文件路径，包含 400+ 预设 RSS 源 |
| `add` | array | 自定义添加的 RSS 源，结构为 `{title, xmlUrl, category}` |
| `block` | array | 手动屏蔽的 RSS 源，精确匹配 `xmlUrl` |
| `block_domains` | array | 域名级别屏蔽，支持通配符（如 `*.substack.com`） |

### filter —— 内容过滤

| 字段 | 类型 | 说明 |
|------|------|------|
| `min_score` | number | 最低评分阈值，低于此分数的内容不参与推送（默认60） |
| `hot_threshold` | number | 热点阈值，达到此分数立即触发即时推送（默认90） |
| `context_days` | number | 上下文天数，汇总推送时参考的fetch数据历史天数（默认3天） |
| `keep_days` | number | 数据保留天数，超过天数的 JSON 文件会被清理 |
| `push_context_days` | number | 汇总推送去重的历史push文件有效天数（默认5天） |
| `no_content_marker` | string | LLM 返回的无内容标记，当推送内容包含此字符串时跳过推送（默认"[NO_NEW_CONTENT]"） |

### schedule —— 调度配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `fetch_interval_minutes` | number | RSS 抓取间隔，单位分钟（默认30分钟） |
| `fetch_lookback_minutes` | number | RSS 冗余缓存时间（分钟），必须大于 `fetch_interval_minutes`，用于防止 RSS 延迟导致漏读（默认120分钟） |
| `push_cron` | array | 定时推送的 cron 表达式数组，支持多个时间点 |
| `timezone_hours` | number | 时区偏移小时数，用于时间显示（8 = UTC+8 北京时间） |

**cron 表达式说明：**

| 表达式 | 含义 |
|--------|------|
| `0 8 * * *` | 每天早上 8:00 |
| `0 17 * * *` | 每天下午 5:00 |
| `0 9,17 * * *` | 每天早上 9:00 和下午 5:00 |

格式：`minute hour day month weekday`

### fetch —— 抓取配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `max_workers` | number | 最大并发数，同时抓取的 RSS 源数量 |
| `timeout` | number | 单个请求超时时间，单位秒 |

### llm —— 大语言模型配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string | LLM 提供商（支持 openai 兼容接口） |
| `model` | string | 模型名称，如 `x-ai/grok-4.1-fast` |
| `baseUrl` | string | API 端点，如 `https://openrouter.ai/api/v1` |
| `apiKeyName` | string | 环境变量名称，系统会自动读取其值 |
| `max_prompt_chars` | number | 单次 prompt 最大字符数，用于分批控制 |
| `max_concurrent_batches` | number | 最大并发批次数 |
| `prompts` | object | prompt 文件路径配置 |

### push —— 推送平台配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `discord.enabled` | boolean | 是否启用 Discord 推送 |
| `discord.apiKeyName` | string | Discord Webhook 的环境变量名 |
| `feishu.enabled` | boolean | 是否启用飞书推送 |
| `feishu.apiKeyName` | string | 飞书 Webhook 的环境变量名 |

---

## 实用测试脚本

项目提供了一套完整的测试脚本，用于验证各模块功能：

### 1. fetch_news.py —— RSS 抓取测试

```bash
# 获取过去 1 小时的新闻
python tests/fetch_news.py

# 获取过去 30 分钟的新闻
python tests/fetch_news.py --minutes 30

# 获取过去 24 小时的新闻
python tests/fetch_news.py --hours 24

# 指定输出目录
python tests/fetch_news.py --output-dir my-data
```

### 2. push_news.py —— 推送测试

```bash
# 默认模式：从 fetch 数据读取发送
python tests/push_news.py

# 模拟真实推送：从 news-data/push-*.md 最新文件发送
python tests/push_news.py --real
```

### 3. test_push_loop.py —— 推送时间逻辑测试

```bash
# 测试 push 循环时间逻辑（约 90 秒）
python tests/test_push_loop.py
```

### 4. run_llm_test.py —— LLM 综合测试

```bash
# 测试评分功能
python tests/run_llm_test.py --score

# 测试即时推送
python tests/run_llm_test.py --immediate-push --push

# 测试汇总推送
python tests/run_llm_test.py --digest --push

# 完整测试并推送
python tests/run_llm_test.py --all --push
```

### 5. pytest 单元测试

```bash
# 运行所有测试
pytest tests/pytest/ -v

# 运行特定模块
pytest tests/pytest/test_config.py -v
pytest tests/pytest/test_llm.py -v
```

---

## 扩展指南

### 添加新的 RSS 源

在 `config.json` 的 `sources.add` 中添加：

```json
"add": [
    {
        "title": "我的自定义源",
        "xmlUrl": "https://example.com/feed.xml",
        "category": "AI"
    }
]
```

### 添加新的推送平台

1. 在 `src/push/` 目录下创建新文件，继承 `PushPlatform` 基类
2. 实现 `validate_config()` 和 `send()` 方法
3. 在 `src/push/__init__.py` 中注册

### 修改评分逻辑

编辑 `prompts/score.txt`，调整评分标准和权重。

### 自定义 LLM 模型

修改 `config.json` 中的 `llm` 配置：

```json
"llm": {
    "model": "anthropic/claude-3-opus",
    "baseUrl": "https://openrouter.ai/api/v1",
    "apiKeyName": "OPENROUTER_API_KEY"
}
```

---

## 常见问题

### Q1: 如何只运行抓取而不推送？

编辑 `config.json`，暂时关闭推送：

```json
"push": {
    "discord": {
        "enabled": false
    }
}
```

### Q2: LLM API 配额不足怎么办？

- 降低 `fetch_interval_minutes`（如改为 60 分钟）减少调用频率

### Q3: 如何查看抓取了多少条数据？

查看 `news-data/fetch-YYYY-MM-DD.json` 文件，每条记录的 `score` 字段即为 LLM 评分。

### Q4: 即时推送没有触发？

检查：
1. `hot_threshold` 设置是否合理（默认90分较高）
2. 查看日志中是否有 "🔥 发现 X 条热点消息，即时推送" 输出

### Q5: 定时推送没有收到？

- 检查 `push_cron` 表达式是否正确
- 确认 `timezone_hours` 与你所在时区一致
- 查看日志中是否有 "✅ Push Job 完成" 输出
- 检查 `push` 配置是否正确

### Q6: 如何查看推送了多少条数据？

查看 `news-data/push-YYYY-MM-DD.json` 文件

---

## 数据示例

### fetch-*.json 格式（原始抓取数据）

```json
{
  "meta": { "date": "2026-03-01" },
  "entries": [
    {
      "title": "Google AI 发布 Nano Banana 2 SOTA图像模型",
      "link": "https://x.com/berryxia/status/2027777950851187020",
      "published": "2026-02-28T23:30:05+08:00",
      "source": "Berry(@berryxia)",
      "content": "...",
      "tags": ["AI", "模型"],
      "score": 95,
      "summary": "Google AI 发布最新图像生成模型，支持多语言文本渲染。",
      "fetched_at": "2026-03-01T00:00:41+08:00"
    }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `title` | 内容标题 |
| `link` | 原始链接 |
| `published` | 发布时间 |
| `source` | 来源（Twitter 账号或博客名） |
| `content` | Markdown 格式的正文内容 |
| `tags` | LLM 识别的标签 |
| `score` | LLM 评分（0-100） |
| `summary` | LLM 生成的中文摘要 |
| `fetched_at` | 抓取时间 |

### push-*.md 格式（推送内容）

```markdown
---
pushDate: "2026-03-01T08:00:22+08:00"
sourceCount: 24
totalEntries: 24
---

# 📰 AI资讯精选 | 2025-03-01

## 🚀 模型与产品更新

### [Google AI 发布 Nano Banana 2 SOTA图像模型](https://x.com/berryxia/status/...)
Google AI 发布 Nano Banana 2，支持多语言文本渲染的顶级图像模型...
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `pushDate` | 推送时间 |
| `sourceCount` | 参考的来源数量 |
| `totalEntries` | 推送的总条目数 |

---

## RSS 源说明

### 源文件

RSS 订阅源文件位于 `resources/rss.opml`，目前包含约 420 个订阅源。

### 源分类

| 类别 | 数量 | 说明 |
|------|------|------|
| 微信公众号 | ~120 | 通过 `https://wechat2rss.bestblogs.dev/` 接入 |
| Twitter/X | ~160 | 通过 `https://api.xgo.ing/` 接入 |
| 视频类 | ~40 | YouTube 视频源 |
| 播客类 | ~30 | AI 相关播客 |
| 文章类 | ~170 | 主流科技博客、新闻网站 |

### 源更新

订阅源来源于 [BestBlogs](https://www.bestblogs.dev/en/sources)

---

## 目录结构

```
daily-news/
├── src/
│   ├── main.py          # 入口 + 双循环（抓取/推送）
│   ├── config.py        # 配置加载 + 源合并
│   ├── fetcher.py       # RSS 抓取
│   ├── llm.py           # LLM 评分/汇总
│   ├── processor.py     # HTML → Markdown
│   ├── storage.py       # JSON 读写
│   └── push/            # 推送平台
│       ├── base.py      # 基类
│       ├── discord.py
│       └── feishu.py
├── tests/               # 测试脚本
│   ├── fetch_news.py
│   ├── push_news.py
│   ├── run_llm_test.py
│   └── pytest/          # 单元测试
├── config.json          # 主配置文件
├── requirements.txt     # Python 依赖
├── news-data/           # 数据存储
│   ├── fetch-*.json    # 抓取的原始数据
│   └── push-*.md      # 推送的汇总内容
├── prompts/            # LLM 提示词
└── resources/          # RSS 源文件
    └── rss.opml
```
