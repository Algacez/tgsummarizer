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
        """发送每日总结到所有群组，返回所有群组的执行结果"""
        execution_report = {
            'start_time': datetime.now(),
            'total_chats': 0,
            'successful': 0,
            'partial': 0,
            'failed': 0,
            'no_messages': 0,
            'chat_results': {},
            'errors': []
        }

        try:
            local_now = datetime.now()
            self.logger.info(f"Starting daily summaries at local time: {local_now.strftime('%Y-%m-%d %H:%M:%S')}")

            # 获取所有群组列表
            chat_ids = self.storage.get_chat_list()
            execution_report['total_chats'] = len(chat_ids)

            self.logger.info(f"Found {len(chat_ids)} chats to process")

            if not chat_ids:
                error_msg = "No chats configured, cannot send daily summaries"
                self.logger.error(error_msg)
                execution_report['errors'].append(error_msg)
                return execution_report

            # 通知所有群组，每日总结任务已开始
            for chat_id in chat_ids:
                try:
                    await self.bot_instance.safe_send_message(chat_id, f"🔔 **每日总结任务已启动**\n\n⏰ 计划时间: {config.daily_summary_time}\n🤖 任务开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n📊 正在为群组生成今日总结...")
                except Exception as e:
                    self.logger.error(f"Failed to send start notification to chat {chat_id}: {e}")
                    execution_report['errors'].append(f"Chat {chat_id}: Failed to send start notification: {e}")

            # 为每个群组生成总结
            for idx, chat_id in enumerate(chat_ids, 1):
                try:
                    self.logger.info(f"[{idx}/{len(chat_ids)}] Processing chat {chat_id}")

                    # 获取保存的群组信息用于日志
                    chat_info = f"chat_{chat_id}"
                    try:
                        # 尝试获取群组名称等信息（如果可用）
                        pass
                    except:
                        pass

                    # 发送处理中通知
                    try:
                        await self.bot_instance.safe_send_message(chat_id, f"🔄 **[{idx}/{len(chat_ids)}]** 正在处理当前群组总结...")
                    except:
                        pass

                    # 发送每日总结并获取结果报告
                    result = await self.bot_instance.send_daily_summary(chat_id)

                    # 记录结果
                    execution_report['chat_results'][chat_id] = result

                    # 统计汇总
                    if result.get('status') == 'success':
                        execution_report['successful'] += 1
                    elif result.get('status') == 'partial':
                        execution_report['partial'] += 1
                    elif result.get('status') == 'no_messages':
                        execution_report['no_messages'] += 1
                    else:
                        execution_report['failed'] += 1

                    if result.get('errors'):
                        execution_report['errors'].extend([f"Chat {chat_id}: {err}" for err in result['errors']])

                    self.logger.info(f"[{idx}/{len(chat_ids)}] Completed chat {chat_id}, status: {result.get('status')}")

                    # 群组间增加间隔避免触发限制
                    if idx < len(chat_ids):
                        await asyncio.sleep(3)

                except Exception as e:
                    error_msg = f"Failed to send summary to chat {chat_id}: {e}"
                    self.logger.error(error_msg)
                    execution_report['failed'] += 1
                    execution_report['errors'].append(error_msg)

                    # 尝试发送错误信息到群组
                    try:
                        await self.bot_instance.safe_send_message(chat_id, f"❌ **每日总结任务执行失败**\n\n{error_msg}")
                    except Exception as send_error:
                        self.logger.error(f"Failed to send error message to chat {chat_id}: {send_error}")

            # 计算执行统计
            execution_report['end_time'] = datetime.now()
            execution_report['duration_seconds'] = (execution_report['end_time'] - execution_report['start_time']).total_seconds()

            self.logger.info(f"Daily summary task completed: {execution_report}")

            # 向所有群组发送执行总结报告
            total_processed = execution_report['successful'] + execution_report['partial'] + execution_report['failed']
            report_message = f"""
📊 **每日总结任务执行报告**

⏰ 执行时间: {execution_report['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
⏱ 总耗时: {execution_report['duration_seconds']:.1f} 秒
📋 处理群组: 共 {execution_report['total_chats']} 个

📈 **执行结果:**
✅ 完全成功: {execution_report['successful']} 个群组
⚠️ 部分成功: {execution_report['partial']} 个群组
❌ 处理失败: {execution_report['failed']} 个群组
📭 无消息记录: {execution_report['no_messages']} 个群组
"""

            if execution_report['errors']:
                report_message += f"\n🐛 **错误/警告数**: {len(execution_report['errors'])} 条"

            report_message += f"\n📊 **成功率**: {(execution_report['successful'] / execution_report['total_chats'] * 100):.1f}%"

            if total_processed > 0:
                report_message += f"\n\n✅ **任务状态**: {'执行成功' if execution_report['failed'] == 0 else '部分失败'}"
            else:
                report_message += f"\n\n❌ **任务状态**: 执行失败"

            # 向所有群组发送最终报告
            for chat_id in chat_ids:
                try:
                    await self.bot_instance.safe_send_message(chat_id, report_message)
                except Exception as e:
                    self.logger.error(f"Failed to send execution report to chat {chat_id}: {e}")

            return execution_report

        except Exception as e:
            error_msg = f"Critical error in daily summary task: {e}"
            self.logger.error(error_msg)
            execution_report['errors'].append(error_msg)

            # 如果是全局错误，尝试通知所有群组
            try:
                chat_ids = self.storage.get_chat_list()
                if not chat_ids:
                    self.logger.error("No chats to notify about global error")
                    return execution_report

                for chat_id in chat_ids:
                    try:
                        global_error_msg = f"""
🚨 **每日总结任务严重错误**

⚠️ 错误信息: {str(e)}

这个错误影响了整个每日总结任务，可能是配置问题或系统错误，请检查日志文件获取详细信息。
"""
                        await self.bot_instance.safe_send_message(chat_id, global_error_msg)
                    except Exception as send_error:
                        self.logger.error(f"Failed to send global error message to chat {chat_id}: {send_error}")
            except Exception as global_error:
                self.logger.error(f"Failed to send global error notifications: {global_error}")

            return execution_report

    def scheduler_loop(self):
        self.logger.info("Scheduler loop started (Local Time)")
        last_error_time = None
        error_count = 0

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
                        self.logger.info("Scheduler stopped during wait, exiting")
                        break

                    # 执行总结任务
                    local_now = datetime.now()
                    self.logger.info(f"Executing daily summary task at local time: {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(f"Scheduler running state: {self.running}")

                    # 重置错误计数（成功执行后）
                    error_count = 0
                    last_error_time = None

                    try:
                        # 在新的事件循环中运行
                        self.logger.info("Creating new event loop for daily summaries")
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        # 运行并获取执行报告
                        execution_report = loop.run_until_complete(self.send_daily_summaries())

                        self.logger.info(f"Daily summary task completed, report: {execution_report}")

                        # 记录到调度器日志
                        if execution_report['errors']:
                            self.logger.warning(f"Daily summary completed with {len(execution_report['errors'])} errors/warnings")
                        else:
                            self.logger.info("Daily summary task completed successfully")

                        loop.close()

                    except Exception as e:
                        error_count += 1
                        last_error_time = datetime.now()
                        self.logger.error(f"Error in summary task execution (error #{error_count}): {e}")

                        # 如果连续错误超过3次，增加等待时间
                        if error_count >= 3:
                            self.logger.warning(f"Encountered {error_count} consecutive errors, waiting 10 minutes before retry")
                            threading.Event().wait(600)

                    # 执行完成后等待至少1分钟，避免立即重复执行
                    self.logger.info("Waiting 60 seconds before scheduling next task")
                    threading.Event().wait(60)
                else:
                    # 等待到目标时间前1分钟
                    wait_time = seconds_to_wait - 60

                    self.logger.info(f"Preparing for execution, will wait in {wait_time} second chunks")

                    # 分段等待，每60秒检查一次是否仍在运行
                    while wait_time > 0 and self.running:
                        chunk = min(60, wait_time)
                        threading.Event().wait(chunk)
                        wait_time -= chunk

                        # 定期检查点日志
                        if wait_time % 600 == 0 and wait_time > 0:
                            self.logger.info(f"Still waiting... {wait_time} seconds remaining until target time")

            except Exception as e:
                error_count += 1
                last_error_time = datetime.now()
                self.logger.error(f"Scheduler error (error #{error_count}): {e}")

                # 如果连续错误超过5次，停止调度器
                if error_count >= 5:
                    self.logger.critical(f"Too many consecutive errors ({error_count}), stopping scheduler")
                    self.running = False
                    break

                if self.running:
                    # 出错后等待5分钟再重试
                    self.logger.info("Waiting 5 minutes before retrying scheduler loop")
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