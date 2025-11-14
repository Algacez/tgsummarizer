import asyncio
import threading
from datetime import time, datetime, date
from typing import Optional, Callable

from src.config import config
from src.storage import MessageStorage


class DailySummaryScheduler:
    def __init__(self, bot_instance):
        self.bot_instance = bot_instance
        self.storage = MessageStorage()
        self.running = False
        self.scheduler_thread = None
        self.target_time = self.parse_time(config.daily_summary_time)

    @staticmethod
    def parse_time(time_str: str) -> time:
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except (ValueError, AttributeError):
            return time(23, 59)

    def seconds_until_target_time(self) -> int:
        now = datetime.now()
        target = datetime.combine(date.today(), self.target_time)

        if now.time() > target.time():
            target = datetime.combine(date.today(), self.target_time)
            target = target.replace(day=target.day + 1)

        delta = target - now
        return int(delta.total_seconds())

    async def send_daily_summaries(self):
        try:
            chat_ids = self.storage.get_chat_list()

            for chat_id in chat_ids:
                await self.bot_instance.send_daily_summary(chat_id)
                await asyncio.sleep(1)

        except Exception as e:
            print(f"Error sending daily summaries: {e}")

    def scheduler_loop(self):
        while self.running:
            try:
                seconds_to_wait = self.seconds_until_target_time()

                if seconds_to_wait <= 60:
                    asyncio.run(self.send_daily_summaries())

                    seconds_to_wait = self.seconds_until_target_time()

                if seconds_to_wait > 0:
                    if seconds_to_wait > 3600:
                        check_interval = 3600
                    else:
                        check_interval = 60

                    for _ in range(seconds_to_wait // check_interval):
                        if not self.running:
                            break
                        threading.Event().wait(check_interval)

                    remaining = seconds_to_wait % check_interval
                    if remaining > 0 and self.running:
                        threading.Event().wait(remaining)

            except Exception as e:
                print(f"Scheduler error: {e}")
                if self.running:
                    threading.Event().wait(300)

    def start(self):
        if self.running:
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self.scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        print(f"Daily summary scheduler started for {config.daily_summary_time}")

    def stop(self):
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        print("Daily summary scheduler stopped")


__all__ = ['DailySummaryScheduler']