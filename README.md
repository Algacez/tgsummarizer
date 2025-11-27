# Telegram Group Message Summary Bot

A powerful Telegram bot for automatically collecting group messages and generating intelligent summaries.

## Features

- 🔄 **Automatic Message Collection**: Automatically saves all messages in the group
- 📊 **Daily Auto-Summary**: Generates a daily summary of messages at scheduled times
- 🎯 **Manual Summary**: Supports on-demand generation of summaries for recent messages
- 🔧 **Flexible Configuration**: Customizable API endpoints, models, and summary parameters
- 📁 **Structured Storage**: Stores messages for each group independently by date
- 📈 **Statistics**: Provides group activity statistics

## Installation and Usage

### 1. Clone the Project
```bash
git clone https://github.com/Algacez/tgsummarizer.git
cd tgsummarizer
```

### 2. Install Dependencies
```bash
uv venv
uv pip install -r requirements.txt
```

```bash
pip install -r requirements.txt
```

### 3. Configure the Bot
```bash
uv run python main.py 
```

The first run will automatically generate a `config.json` configuration file. You need to fill in the following information:

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

### 4. Obtain Bot Token
1. Chat with @BotFather
2. Send `/newbot` to create a new bot
3. Follow the prompts to set the bot's name and username
4. Obtain the Token and fill it into the configuration file

### 5. Obtain Group ID
1. Add the bot to the group
2. After sending a message, check the logs or use @userinfobot to get the group ID
3. Add the group ID to the `allowed_chats` list

### 6. Run the Bot
```bash
python main.py
```

## Bot Commands

- `/start` - Start the bot and display welcome message
- `/summary` - Generate a summary of recent messages
- `/summary [count]` - Summarize a specified number of recent messages
- `/summary [count] [hours]` - Summarize a specified number of messages within a specified number of hours
- `/stats` - Display today's group statistics
- `/help` - Display help information

## Configuration Details

### Telegram Configuration
- `bot_token`: Bot Token (required)
- `allowed_chats`: List of group IDs allowed to work (empty allows all groups)

### AI Configuration
- `api_base`: API endpoint, supports OpenAI-compatible interfaces
- `api_key`: API key (required)
- `model`: Name of the model to use
- `max_tokens`: Maximum tokens for generating summaries
- `temperature`: Creativity level of generation (0-1)

### Summary Configuration
- `daily_summary_enabled`: Whether to enable daily auto-summary
- `daily_summary_time`: Time for daily summary delivery
- `manual_summary_message_count`: Default number of messages for manual summary
- `manual_summary_hours`: Time range for manual summary

### Storage Configuration
- `data_dir`: Message storage directory
- `file_format`: File format (currently supports json)

## Project Structure

```
tgsummarizer/
├── main.py                 # Main program entry
├── config.json            # Configuration file
├── requirements.txt       # Dependency list
├── src/
│   ├── config.py         # Configuration management
│   ├── bot/
│   │   └── telegram_bot.py # Telegram bot client
│   ├── storage/
│   │   └── message_storage.py # Message storage
│   ├── ai/
│   │   └── summary.py    # AI summary functionality
│   └── scheduler.py      # Scheduled tasks
├── data/                  # Message data directory
└── README.md             # Project description
```

## API Compatibility

The bot supports any OpenAI API-compatible interfaces, including:
- Official OpenAI API
- Azure OpenAI
- Locally deployed model APIs
- Third-party compatible services

## Notes

1. **Security**: Please keep API keys and Bot Token secure
2. **Privacy**: Message content will be stored locally; pay attention to data security
3. **Costs**: Using AI APIs may incur fees; monitor usage
4. **Permissions**: Ensure the bot has sufficient group permissions

## Testing

### Running Tests

To test the daily summary functionality, run:

```bash
python run_tests.py
```

This will execute unit tests for:
- Message time filtering
- Period summary generation
- Error handling scenarios
- Scheduler functionality

### Test Coverage

The tests cover:
- Normal summary generation
- Edge cases (no messages, API errors)
- Time range filtering (including cross-day periods)
- Error reporting and handling

## Troubleshooting

### Common Issues

1. **Bot Not Responding**
   - Check if the Bot Token is correct
   - Confirm the group ID is in the allowed list
   - Check log output

2. **AI Summary Failure**
   - Check if the API key is correct
   - Confirm the API endpoint is accessible
   - Check network connection

3. **Scheduled Summary Not Working**
   - Confirm `daily_summary_enabled` is true
   - Check if the time format is correct
   - Verify the bot is running normally

## License

[View LICENSE file](LICENSE)

## Contributing

Contributions via Issues and Pull Requests are welcome!