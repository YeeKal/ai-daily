# AI Daily 安装问题总结

## 安装过程中遇到的问题

### 1. sgmllib3k 依赖问题

**问题现象**：
- 安装依赖后运行项目时出现 `ModuleNotFoundError: No module named 'sgmllib3k'` 错误
- 即使已安装 sgmllib3k 包，仍出现同样错误

**原因分析**：
- Windows 环境下使用 `uv` 安装 `sgmllib3k` 时，会生成一个错误的 `sgmllib.py` shim 文件
- 该 shim 文件尝试导入 `sgmllib3k` 模块，但实际上 `sgmllib3k` 包提供的就是 `sgmllib` 模块

**解决方案**：
- 使用 `pip` 替代 `uv` 安装依赖
- 具体步骤：
  1. 创建虚拟环境：`uv venv --python 3.10`
  2. 安装 pip：`uv pip install pip`
  3. 使用 pip 安装依赖：`.venv\Scripts\python.exe -m pip install -r requirements.txt`

### 2. LLM API 配置问题

**问题现象**：
- 项目启动时显示 `LLM接口不可用: LLM API错误: 401 - User not found`

**原因分析**：
- 未配置正确的 LLM API Key
- 环境变量未正确设置

**解决方案**：
- 在项目根目录创建 `.env` 文件
- 添加以下配置：
  ```bash
  OPENROUTER_API_KEY=your_api_key_here
  FEISHU_WEBHOOK_URL=your_feishu_webhook_url_here
  ```

## 其他常见问题

### 1. 虚拟环境创建失败
- **原因**：Python 版本不兼容
- **解决**：确保使用 Python 3.10+ 版本

### 2. 依赖安装缓慢
- **原因**：网络问题或依赖源问题
- **解决**：使用国内镜像源，如：
  ```bash
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
  ```

## 总结

Windows 环境下安装 AI Daily 项目时，主要需要注意以下几点：
1. 使用 `pip` 安装依赖以避免 sgmllib3k 兼容性问题
2. 正确配置 LLM API Key 和推送平台 Webhook
3. 确保网络连接正常，必要时使用代理

---

*创建时间：2026-03-18*