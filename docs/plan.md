## TODO

当前待办
- [ ] 早报内容格式优化：参考appso / xiaohu / ai gap
- [ ] 添加更多信息源，如 TechCrunch、GitHub Trending
- [ ] x 用户post提取： DAIR.AI
- [ ] 允许fetch链接中的内容对信息进行扩展

长期待办

- [ ] 增加图片/信息图
- [ ] 推送到知乎 / 小红书 / 网站

## 技术决策

| 决策 | 方案 | 原因 |
|------|------|------|
| 定时调度 | croniter | 专业、准确、自动跨天处理 |
| 数据格式 | JSON | 结构清晰、易处理、支持嵌套 |
| 推送文件 | Markdown+YAML | 人工可读、Frontmatter 元数据 |
| 循环模式 | asyncio.gather | 简单、无锁、Pythonic |
| LLM 评分 | 批量 JSON | 减少 API 调用次数 |
| 状态追踪 | 文件时间戳 | 无需外部数据库 |
| RSS延迟防护 | fetch_lookback_minutes | 防止RSS延迟导致漏读 |

## 开发进度

**2026-03-02**
- 修复RSS延迟漏读问题：新增 fetch_lookback_minutes 参数，fetch时读取过去更长一段时间的RSS条目进行去重
- 新增飞书 Webhook 推送支持：使用卡片消息格式，支持 Markdown 渲染
- 新增测试脚本 test_fetch_lookback.py
- 更新 cleanup_old_files 函数支持 notify 文件清理

**2026-03-01**
- 优化评分系统：通过更新 score 提示词提升评分质量
- 即时推送去重：新增 notify-*.md 文件存储即时推送，LLM 调用时传入近期推送上下文避免重复
- 汇总推送优化：新增 push_context_days 配置，汇总推送时传入近期推送上下文进行去重
- 修复 score 类型问题：确保 LLM 返回的 score 为整数类型
- 完善测试脚本：添加上下文参数和保存功能

**2026-02-28**
- 初始化项目，MVP 已完成，支持 RSS 抓取、LLM 评分、定时推送、即时推送。
