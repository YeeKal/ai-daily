# Debian 系统安装 AI Daily 教程

## 1. 系统要求
- Debian 10+ 系统
- Python 3.10+
- 网络连接（用于安装依赖和抓取 RSS）

## 2. 克隆项目

```bash
git clone https://github.com/tabortao/ai-daily.git
cd ai-daily
```

## 4. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装项目依赖
pip install -r requirements.txt
```

![20260318203548](https://img.sdgarden.top/blog/2026/03/20260318203750288.webp)

![20260318203654](https://img.sdgarden.top/blog/2026/03/20260318203832278.webp)

## 5. 配置环境变量

创建 `.env` 文件并配置相关参数：

```bash
cp .env.example .env
nano .env
```

在 `.env` 文件中添加以下内容：

```
# LLM API 配置
OPENROUTER_API_KEY=your_api_key_here

# Feishu Webhook
FEISHU_WEBHOOK_URL=your_feishu_webhook_url_here

# Proxy Configuration (如果需要)
HTTP_PROXY=http://your_proxy:port
```

## 6. 配置系统服务

### 6.1 复制服务文件

```bash
sudo cp ai-daily.service /etc/systemd/system/
```

### 6.2 修改服务文件

编辑服务文件，替换占位符：

```bash
sudo nano /etc/systemd/system/ai-daily.service
```

将以下内容替换为实际值：
- `your_username` - 运行服务的用户名
- `/path/to/ai-daily` - 项目的实际路径

### 6.3 重新加载 systemd 配置

```bash
sudo systemctl daemon-reload
```

### 6.4 启用服务（设置开机自启）

```bash
sudo systemctl enable ai-daily.service
```

### 6.5 启动服务

```bash
sudo systemctl start ai-daily.service
```

## 7. 验证服务

### 7.1 查看服务状态

```bash
sudo systemctl status ai-daily.service
```

### 7.2 查看服务日志

```bash
sudo journalctl -u ai-daily.service -f
```

## 8. 服务管理命令

### 8.1 启动服务
```bash
sudo systemctl start ai-daily.service
```

### 8.2 停止服务
```bash
sudo systemctl stop ai-daily.service
```

### 8.3 重启服务
```bash
sudo systemctl restart ai-daily.service
```

### 8.4 查看服务状态
```bash
sudo systemctl status ai-daily.service
```

## 9. 卸载服务

### 9.1 停止服务
```bash
sudo systemctl stop ai-daily.service
```

### 9.2 禁用服务
```bash
sudo systemctl disable ai-daily.service
```

### 9.3 删除服务文件
```bash
sudo rm /etc/systemd/system/ai-daily.service
```

### 9.4 重新加载 systemd 配置
```bash
sudo systemctl daemon-reload
```

## 10. 常见问题

### 10.1 服务启动失败
- 检查 `.env` 文件配置是否正确
- 检查虚拟环境是否正确创建
- 查看日志获取详细错误信息：
  ```bash
  sudo journalctl -u ai-daily.service
  ```

### 10.2 代理配置
- 在 `.env` 文件中设置 `HTTP_PROXY` 环境变量
- 确保代理服务器可访问

### 10.3 LLM API 错误
- 检查 `OPENROUTER_API_KEY` 是否正确
- 确保 API Key 有足够的配额

## 11. 手动运行项目（可选）

如果需要手动运行项目，可以使用以下命令：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行项目
python3 -m src.main
```

## 总结

通过以上步骤，你可以在 Debian 系统中成功安装和运行 AI Daily 项目，并通过 systemd 服务实现开机自动启动和后台运行。如果遇到任何问题，请查看日志文件获取详细信息。