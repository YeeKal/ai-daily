# 技术架构

## 核心架构

### 双循环设计

```
┌─────────────────────────────────────────────────────────────┐
│                     Config (config.json)                    │
├─────────────────────────────────────────────────────────────┤
│  sources          filter           schedule      llm/push  │
│  ├── base_opml    ├── min_score    ├── push_cron            │
│  ├── add[]        ├── context_days ├── fetch_interval       │
│  ├── block[]      └── hot_threshold                        │
│  └── block_domains[]                                       │
└─────────────────────────────────────────────────────────────┘
                            │
           ┌────────────────┴────────────────┐
           ▼                                 ▼
┌─────────────────────┐           ┌─────────────────────┐
│   Fetch Loop        │           │   Push Loop         │
│   (每30分钟)        │           │   (croniter定时)    │
│                     │           │                     │
│  • 抓取RSS          │           │  • 收集条目         │
│  • LLM评分          │           │  • 生成汇总         │
│  • 保存JSON         │           │  • 推送+存档        │
│  • 热点即时推送     │           │                     │
└─────────────────────┘           └─────────────────────┘
           │                                 │
           └────────────────┬────────────────┘
                            ▼
                 ┌─────────────────────┐
                 │   news-data/        │
                 │   ├── fetch-*.json  │
                 │   └── push-*.md     │
                 └─────────────────────┘
```

### 数据流

```
RSS Sources → Fetch Loop → LLM评分 → fetch-YYYY-MM-DD.json
                                      ↓
                                [score >= 90] → 即时推送
                                      ↓
                                [定时触发] → Push Loop → push-*.md
```

## 关键模块

### 1. main.py

入口与双循环：

```python
await asyncio.gather(
    fetch_loop(config),    # 定时抓取
    push_loop(config)      # cron定时推送
)
```

**collect_entries_for_push()** - 条目收集核心：

```python
def collect_entries_for_push(
    last_push_time: Optional[datetime],
    context_days: int = 2,
    min_score: int = 60,
) -> tuple[List[Dict], List[Dict]]:
    """
    返回 (待推送条目, 上下文条目)

    逻辑：
    1. 获取 context_days 天的所有条目
    2. 按 min_score 过滤
    3. push_cutoff = max(last_push_time, now - 24h)
    4. 晚于 push_cutoff → 待推送
    5. 早于 push_cutoff → 上下文（用于LLM去重）
    """
```

### 2. push_loop() - 使用 croniter

```python
async def push_loop(config: Dict):
    cron_list = config['schedule']['push_cron']
    valid_crons = [c for c in cron_list if croniter.is_valid(c)]

    while True:
        next_push = min(
            croniter(cron, now).get_next(datetime)
            for cron in valid_crons
        )
        await asyncio.sleep(wait_seconds)
        await run_push_job(config)
        await asyncio.sleep(1)
```

关键设计:
- 无状态：每次循环重新计算时间
- croniter：专业 cron 解析，自动处理跨天
- 优雅退出：asyncio.sleep 可被 CancelledError 打断

### 3. fetcher.py

HTTP 请求头（避免 403）:

```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
```

域名屏蔽: config.json 中的 `block_domains` 支持通配符 `*.substack.com`

### 4. llm.py

批量评分：

```python
async def score_batch(entries: List[Dict], config: Dict) -> List[Dict]:
    """
    智能分批评分：
    1. 根据 max_prompt_chars 自动分批
    2. 多批次并行处理（限制并发数）
    3. 通过 link 字段关联结果
    """
```

### 5. storage.py

JSON 格式:

```json
{
  "meta": {"date": "2024-01-15"},
  "entries": [
    {
      "title": "...",
      "link": "...",
      "published": "...",
      "fetched_at": "...",
      "score": 85,
      "tags": ["AI"],
      "summary": "...",
      "content": "..."
    }
  ]
}
```

## 配置详解

### config.json

```json
{
  "sources": {
    "base_opml": "resources/rss.opml",
    "add": [{"title": "...", "xmlUrl": "...", "category": "..."}],
    "block": [{"title": "...", "xmlUrl": "..."}],
    "block_domains": ["*.substack.com", "*.youtube.com"]
  },
  "filter": {
    "min_score": 60,
    "hot_threshold": 90,
    "context_days": 2,
    "keep_days": 7,
    "push_context_days": 5,
    "no_content_marker": "[NO_NEW_CONTENT]"
  },
  "schedule": {
    "fetch_interval_minutes": 30,
    "fetch_lookback_minutes": 120,
    "push_cron": ["0 8 * * *", "0 17 * * *"],
    "timezone_hours": 8
  },
  "llm": {
    "provider": "openai",
    "model": "x-ai/grok-4.1-fast",
    "baseUrl": "https://openrouter.ai/api/v1",
    "apiKeyName": "OPENROUTER_API_KEY",
    "max_prompt_chars": 128000,
    "max_concurrent_batches": 3
  },
  "push": {
    "discord": {
      "enabled": true,
      "apiKeyName": "DISCORD_WEBHOOK_URL"
    },
    "feishu": {
      "enabled": false,
      "apiKeyName": "FEISHU_WEBHOOK_URL"
    }
  }
}
```

**schedule 配置**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `fetch_interval_minutes` | int | 30 | fetch 频率（分钟） |
| `fetch_lookback_minutes` | int | 120 | RSS 冗余缓存时间（分钟），必须大于 `fetch_interval_minutes`，用于防止 RSS 延迟导致漏读 |
| `push_cron` | list | - | 推送时间 cron 表达式 |
| `timezone_hours` | int | 8 | 时区偏移（小时） |

### 环境变量

敏感信息通过环境变量管理：

| 配置项 | 环境变量 | 说明 |
|--------|----------|------|
| LLM API Key | `OPENROUTER_API_KEY` | 在 `llm.apiKeyName` 中指定 |
| Discord Webhook | `DISCORD_WEBHOOK_URL` | 在 `push.discord.apiKeyName` 中指定 |
| 飞书 Webhook | `FEISHU_WEBHOOK_URL` | 在 `push.feishu.apiKeyName` 中指定 |

## 目录结构

```
daily-news/
├── src/
│   ├── main.py          # 入口 + 双循环
│   ├── config.py        # 配置加载 + 源合并
│   ├── fetcher.py       # RSS 抓取
│   ├── llm.py           # LLM 评分/汇总
│   ├── processor.py     # HTML → Markdown
│   ├── storage.py       # JSON 读写
│   └── push/            # 推送平台
│       ├── __init__.py
│       ├── base.py      # 基类
│       ├── discord.py
│       └── feishu.py
├── tests/
│   ├── conftest.py         # pytest fixtures
│   ├── test_config.py      # 配置模块测试
│   ├── test_push.py        # 推送平台测试
│   ├── test_push_loop.py   # 推送循环集成测试
│   ├── fetch_news.py       # RSS抓取脚本
│   ├── push_news.py        # 推送测试脚本
│   ├── score_batch.py      # LLM批量评分脚本
│   ├── run_llm_test.py    # LLM综合测试脚本
│   ├── news-data/          # 测试数据目录
│   └── fixtures/           # 测试fixtures
├── config.json             # 主配置
├── requirements.txt
├── news-data/           # 数据目录
│   ├── fetch-*.json
│   └── push-*.md
├── prompts/             # LLM 提示词
│   ├── score.txt
│   ├── immediate_push.txt
│   └── digest.txt
└── resources/
    └── rss.opml         # RSS 订阅源
```

## 扩展指南

### 添加新推送平台

1. 在 `src/push/` 创建新文件
2. 继承 `PushPlatform` 基类
3. 实现 `validate_config()` 和 `send()`
4. 在 `create_platform()` 中注册

### 修改评分逻辑

编辑 `prompts/score.txt`，调整评分标准。

### 添加新源

编辑 `config.json` 的 `sources.add` 列表。


## 测试指南

### 实用测试脚本

项目提供了一套完整的测试脚本，用于实际数据测试：

| 文件 | 类型 | 说明 |
|------|------|------|
| `tests/fetch_news.py` |  RSS抓取测试 | 根据时间抓取过去一定时间内的信息，并存放到 tests/news-data 文件夹内 |
| `tests/push_news.py` |   依赖fetch_news.py。 根据抓取的信息源测试推送功能是否正常 |
| `tests/test_push_loop.py` |  push循环时间逻辑（约90秒） |测试push循环时间逻辑 应在运行时刻接下来的30s和90s各调用一次push |
| `tests/run_llm_test.py` |  LLM综合测试 | 依赖fetch_news.py。 根据抓取的信息源，测试llm打分/推送等功能是否正常|
| `tests/test_fetch_lookback.py` | fetch_lookback_minutes功能测试 | 测试 cutoff 时间计算、阈值逻辑、跨天边界去重 |
| `tests/test_cleanup_old_files.py` | 旧文件清理测试 | 测试 cleanup_old_files 函数，自动创建/清理不同日期的测试文件 |

#### 1. fetch_news.py - RSS抓取

```bash
# 获取过去1小时的新闻
python tests/fetch_news.py

# 获取过去30分钟的新闻
python tests/fetch_news.py --minutes 30

# 获取过去24小时的新闻
python tests/fetch_news.py --hours 24

# 指定输出目录
python tests/fetch_news.py --output-dir my-data

# 限制每域名最大源数量
python tests/fetch_news.py --max-per-domain 10
```

#### 2. push_news.py - 推送测试

```bash
# 测试推送到Discord
python tests/push_news.py
```

#### 3. test_push_loop.py - push循环时间逻辑

```bash
# 测试push循环时间逻辑 应在运行时刻接下来的30s和90s各调用一次push
python tests/test_push_loop.py
```

#### 4. run_llm_test.py - LLM综合测试

```bash
# 测试评分功能
python tests/run_llm_test.py --score

# 测试即时推送
python tests/run_llm_test.py --immediate-push --push

# 测试汇总推送
python tests/run_llm_test.py --digest --push

# 推送到Discord
python tests/run_llm_test.py --all --push

# 运行所有测试
python tests/run_llm_test.py --all
```

#### 5. test_fetch_lookback.py - fetch_lookback_minutes功能测试

```bash
# 运行测试
python tests/test_fetch_lookback.py
```

#### 6. test_cleanup_old_files.py - 旧文件清理测试

```bash
# 运行测试
python tests/test_cleanup_old_files.py
```

## pytest 集成测试

### 运行测试

```bash
# 激活虚拟环境
source ../.venv/bin/activate

# 运行所有 pytest 测试
pytest tests/pytest/ -v

# 运行特定模块测试
pytest tests/pytest/test_config.py
pytest tests/pytest/test_llm.py

# 查看详细输出
pytest tests/pytest/ -v --tb=short

# 测试 push 循环时间逻辑（约90秒）
python tests/test_push_loop.py
```

### 测试覆盖

| 模块 | 测试文件 | 测试数 | 测试内容 |
|------|----------|--------|----------|
| config.py | `test_config.py` | 18 | 配置加载、OPML解析、源合并(block/add/去重)、域名屏蔽、时区获取 |
| fetcher.py | `test_fetcher.py` | 10 | RSS抓取、时间解析、超时处理、并发控制 |
| storage.py | `test_storage.py` | 24 | JSON读写、条目追加去重、文件路径、过期清理 |
| llm.py | `test_llm.py` | 16 | prompt加载、JSON解析、分批处理、评分合并 |
| processor.py | `test_processor.py` | 14 | HTML→Markdown、相对链接、xgo.ing移除 |
| main.py | `test_main.py` | 16 | 时间解析、推送时间计算、条目收集 |
| push/ | `test_push.py` | 17 | Discord/企业微信配置、消息分割、推送验证 |
| timezone/ | `test_timezone.py` | 11 | 时区转换、datetime操作 |
| fixtures | `conftest.py` | - | 共享fixtures |
| **合计** | | **132** | |
