#!/usr/bin/env python3
import asyncio
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.bot import TelegramBot


def signal_handler(_signum, _frame):
    print("\nReceived interrupt signal, shutting down...")
    sys.exit(0)


def main():
    bot = TelegramBot()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, shutting down...")
    except Exception as e:
        print(f"Bot error: {e}")
    finally:
        bot.stop()


if __name__ == "__main__":
    if not config.bot_token:
        print("错误：未配置机器人token！")
        print("请在config.json中设置telegram.bot_token")
        sys.exit(1)

    main()