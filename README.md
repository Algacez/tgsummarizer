# Telegram群组消息总结机器人

一个功能强大（）的Telegram机器人，用于自动收集群组消息并生成智能总结。

## 功能特性

- 🔄 **自动消息收集**: 自动保存群组中的所有消息
- 📊 **每日自动总结**: 每天定时生成当日消息总结
- 🎯 **手动总结**: 支持按需生成最近消息的总结
- 🔧 **灵活配置**: 可自定义API地址、模型和总结参数
- 📁 **结构化存储**: 每个群组按日期独立存储消息
- 📈 **统计信息**: 提供群组活跃度统计

## 安装使用

### 1. 克隆项目
```bash
git clone https://github.com/Algacez/tgsummarizer.git
cd tgsummarizer
```

### 2. 安装依赖
```bash
uv venv
uv pip install -r requirements.txt
```

```bash
pip install -r requirements.txt
```

### 3. 配置机器人
```bash
uv run python main.py 
```

首次运行会自动生成`config.json`配置文件，需要填写以下信息：

```json
{
  "telegram": {
    "bot_token": "YOUR_BOT_TOKEN",
    "allowed_chats": [123456789, 987654321]
  },
  "ai": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "YOUR_API_KEY",
    "model": "gpt-3.5-turbo",
    "max_tokens": 1000,
    "temperature": 0.7
  },
  "summary": {
    "daily_summary_enabled": true,
    "daily_summary_time": "23:59",
    "manual_summary_message_count": 100,
    "manual_summary_hours": 24
  }
}
```

### 4. 获取Bot Token
1. 与 @BotFather 对话
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称和用户名
4. 获得Token并填入配置文件

### 5. 获取群组ID
1. 将机器人添加到群组
2. 发送消息后查看日志或使用 @userinfobot 获取群组ID
3. 将群组ID添加到`allowed_chats`列表

### 6. 运行机器人
```bash
python main.py
```

## 机器人命令

- `/start` - 启动机器人，显示欢迎信息
- `/summary` - 生成最近消息总结
- `/summary [数量]` - 总结指定数量的最近消息
- `/summary [数量] [小时数]` - 总结指定小时内指定数量的消息
- `/stats` - 显示今日群组统计信息
- `/help` - 显示帮助信息

## 配置说明

### Telegram配置
- `bot_token`: 机器人Token（必填）
- `allowed_chats`: 允许工作的群组ID列表（空则允许所有群组）

### AI配置
- `api_base`: API地址，支持OpenAI兼容接口
- `api_key`: API密钥（必填）
- `model`: 使用的模型名称
- `max_tokens`: 生成总结的最大token数
- `temperature`: 生成的创造性程度（0-1）

### 总结配置
- `daily_summary_enabled`: 是否启用每日自动总结
- `daily_summary_time`: 每日总结发送时间
- `manual_summary_message_count`: 手动总结的默认消息数量
- `manual_summary_hours`: 手动总结的时间范围

### 存储配置
- `data_dir`: 消息存储目录
- `file_format`: 文件格式（目前支持json）

## 项目结构

```
tgsummarizer/
├── main.py                 # 主程序入口
├── config.json            # 配置文件
├── requirements.txt       # 依赖列表
├── src/
│   ├── config.py         # 配置管理
│   ├── bot/
│   │   └── telegram_bot.py # Telegram机器人客户端
│   ├── storage/
│   │   └── message_storage.py # 消息存储
│   ├── ai/
│   │   └── summary.py    # AI总结功能
│   └── scheduler.py      # 定时任务
├── data/                  # 消息数据目录
└── README.md             # 项目说明
```

## API兼容性

机器人支持任何OpenAI API兼容的接口，包括：
- OpenAI官方API
- Azure OpenAI
- 本地部署的模型API
- 第三方兼容服务

## 注意事项

1. **安全性**: 请妥善保管API密钥和Bot Token
2. **隐私**: 消息内容将存储在本地，请注意数据安全
3. **费用**: 使用AI API可能产生费用，请注意使用量
4. **权限**: 确保机器人有足够的群组权限

## 故障排除

### 常见问题

1. **机器人无响应**
   - 检查Bot Token是否正确
   - 确认群组ID在允许列表中
   - 查看日志输出

2. **AI总结失败**
   - 检查API密钥是否正确
   - 确认API地址可访问
   - 查看网络连接

3. **定时总结不工作**
   - 确认`daily_summary_enabled`为true
   - 检查时间格式是否正确
   - 查看机器人是否正常运行

## 许可证

[查看LICENSE文件](LICENSE)

## 贡献

欢迎提交Issue和Pull Request！
