import asyncio
import threading
from datetime import time, datetime, date, timedelta
from typing import Optional, Callable
import logging

from src.config import config
from src.storage import MessageStorage


class DailySummaryScheduler:
    def __init__(self, bot_instance):
        self.bot_instance = bot_instance
        self.storage = MessageStorage()
        self.running = False
        self.scheduler_thread = None
        self.target_time = self.parse_time(config.daily_summary_time)
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def parse_time(time_str: str) -> time:
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except (ValueError, AttributeError):
            return time(23, 59)

    def seconds_until_target_time(self) -> int:
        """计算距离下次本地时间的目标时间还有多少秒"""
        local_now = datetime.now()
        local_date = local_now.date()

        # 创建本地时间的目标时间
        target_dt = datetime.combine(local_date, self.target_time)

        # 如果目标时间已经过了，设置为明天
        if local_now >= target_dt:
            target_dt = target_dt + timedelta(days=1)

        delta = target_dt - local_now
        return int(delta.total_seconds())

    async def send_daily_summaries(self):
        try:
            local_now = datetime.now()
            self.logger.info(f"Starting daily summaries at local time: {local_now.strftime('%Y-%m-%d %H:%M:%S')}")

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
        self.logger.info("Scheduler loop started (Local Time)")
        while self.running:
            try:
                seconds_to_wait = self.seconds_until_target_time()
                target_datetime = datetime.now() + timedelta(seconds=seconds_to_wait)

                self.logger.info(f"Next summary scheduled for local time: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"Waiting {seconds_to_wait} seconds...")

                # 如果等待时间小于60秒，直接等待到目标时间
                if seconds_to_wait <= 60:
                    if seconds_to_wait > 0:
                        threading.Event().wait(seconds_to_wait)

                    if not self.running:
                        break

                    # 执行总结任务
                    local_now = datetime.now()
                    self.logger.info(f"Executing daily summary task at local time: {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
                    try:
                        # 在新的事件循环中运行
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.send_daily_summaries())
                        loop.close()
                    except Exception as e:
                        self.logger.error(f"Error in summary task execution: {e}")

                    # 执行完成后等待至少1分钟，避免立即重复执行
                    threading.Event().wait(60)
                else:
                    # 等待到目标时间前1分钟
                    wait_time = seconds_to_wait - 60

                    # 分段等待，每60秒检查一次是否仍在运行
                    while wait_time > 0 and self.running:
                        chunk = min(60, wait_time)
                        threading.Event().wait(chunk)
                        wait_time -= chunk

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
        local_now = datetime.now()
        self.logger.info(f"Daily summary scheduler started for {config.daily_summary_time} (Local Time)")
        self.logger.info(f"Current local time: {local_now.strftime('%Y-%m-%d %H:%M:%S')}")

    def stop(self):
        self.logger.info("Stopping scheduler...")
        self.running = False
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10)
        self.logger.info("Daily summary scheduler stopped")


__all__ = ['DailySummaryScheduler']