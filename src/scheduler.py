import asyncio
import threading
from datetime import time, datetime, date, timedelta
from typing import Optional, Callable
import logging
import pytz

from src.config import config
from src.storage import MessageStorage


class DailySummaryScheduler:
    def __init__(self, bot_instance):
        self.bot_instance = bot_instance
        self.storage = MessageStorage()
        self.running = False
        self.scheduler_thread = None
        self.target_time = self.parse_time(config.daily_summary_time)
        self.beijing_tz = pytz.timezone('Asia/Shanghai')
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def parse_time(time_str: str) -> time:
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except (ValueError, AttributeError):
            return time(23, 59)

    def get_beijing_time(self) -> datetime:
        """获取北京时间"""
        utc_now = datetime.now(pytz.UTC)
        beijing_now = utc_now.astimezone(self.beijing_tz)
        return beijing_now

    def seconds_until_target_time(self) -> int:
        """计算距离下次北京时间的目标时间还有多少秒"""
        beijing_now = self.get_beijing_time()
        beijing_date = beijing_now.date()

        # 创建北京时间的目标时间
        target_dt = self.beijing_tz.localize(datetime.combine(beijing_date, self.target_time))

        # 如果目标时间已经过了，设置为明天
        if beijing_now >= target_dt:
            target_dt = target_dt + timedelta(days=1)

        delta = target_dt - beijing_now
        return int(delta.total_seconds())

    async def send_daily_summaries(self):
        try:
            beijing_now = self.get_beijing_time()
            self.logger.info(f"Starting daily summaries at Beijing time: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")

            chat_ids = self.storage.get_chat_list()
            self.logger.info(f"Found {len(chat_ids)} chats to process")

            for chat_id in chat_ids:
                try:
                    await self.bot_instance.send_daily_summary(chat_id)
                    self.logger.info(f"Daily summary sent to chat {chat_id}")
                    await asyncio.sleep(2)  # 增加间隔避免触发限制
                except Exception as e:
                    self.logger.error(f"Failed to send summary to chat {chat_id}: {e}")

        except Exception as e:
            self.logger.error(f"Error sending daily summaries: {e}")

    def scheduler_loop(self):
        self.logger.info("Scheduler loop started (Beijing Time)")
        while self.running:
            try:
                seconds_to_wait = self.seconds_until_target_time()
                target_datetime = self.get_beijing_time() + timedelta(seconds=seconds_to_wait)

                self.logger.info(f"Next summary scheduled for Beijing time: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"Waiting {seconds_to_wait} seconds...")

                # 等待直到目标时间前1分钟
                wait_time = max(0, seconds_to_wait - 60)

                if wait_time > 0:
                    # 分段等待，每60秒检查一次是否仍在运行
                    while wait_time > 0 and self.running:
                        chunk = min(60, wait_time)
                        threading.Event().wait(chunk)
                        wait_time -= chunk

                if not self.running:
                    break

                # 等待到精确时间
                remaining_seconds = self.seconds_until_target_time()
                if remaining_seconds <= 60 and remaining_seconds > 0:
                    threading.Event().wait(remaining_seconds)

                # 执行总结任务
                if self.running:
                    beijing_now = self.get_beijing_time()
                    self.logger.info(f"Executing daily summary task at Beijing time: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
                    try:
                        # 在新的事件循环中运行
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.send_daily_summaries())
                        loop.close()
                    except Exception as e:
                        self.logger.error(f"Error in summary task execution: {e}")

            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                if self.running:
                    # 出错后等待5分钟再重试
                    threading.Event().wait(300)

    def start(self):
        if self.running:
            self.logger.warning("Scheduler is already running")
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self.scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        beijing_time = self.get_beijing_time()
        self.logger.info(f"Daily summary scheduler started for {config.daily_summary_time} (Beijing Time)")
        self.logger.info(f"Current Beijing time: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')}")

    def stop(self):
        self.logger.info("Stopping scheduler...")
        self.running = False
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10)
        self.logger.info("Daily summary scheduler stopped")

    def update_time(self, time_str: str):
        """更新每日总结时间"""
        self.target_time = self.parse_time(time_str)
        beijing_time = self.get_beijing_time()
        self.logger.info(f"Daily summary time updated to {time_str} (Beijing Time)")
        self.logger.info(f"Current Beijing time: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')}")


__all__ = ['DailySummaryScheduler']