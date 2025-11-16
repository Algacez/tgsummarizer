import asyncio
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from ..config import config
from ..storage import MessageStorage
from ..ai import AISummary
from ..scheduler import DailySummaryScheduler


class TelegramBot:
    def __init__(self):
        self.bot_token = config.bot_token
        self.allowed_chats = config.allowed_chats
        self.storage = MessageStorage()
        self.ai_summary = AISummary()
        self.scheduler = DailySummaryScheduler(self)
        self.application = None

        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=getattr(logging, config.get("logging.level", "INFO"))
        )
        self.logger = logging.getLogger(__name__)

    async def safe_send_message(self, chat_id, text, update=None):
        """安全发送消息，自动处理Markdown错误"""
        try:
            # 首先尝试带Markdown格式
            if update:
                return await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            else:
                return await self.application.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger.warning(f"Markdown parse error, sending as plain text: {e}")
            try:
                # 如果Markdown失败，移除特殊字符后发送纯文本
                clean_text = self.simple_markdown_clean(text)
                if update:
                    return await update.message.reply_text(clean_text)
                else:
                    return await self.application.bot.send_message(chat_id=chat_id, text=clean_text)
            except Exception as e2:
                self.logger.error(f"Failed to send message: {e2}")
                return None

    def simple_markdown_clean(self, text):
        """简单的Markdown清理，移除特殊标记但保留可读性"""
        # 将 **粗体** 替换为普通文本
        import re
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        # 将 *斜体* 替换为普通文本
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        # 移除 `代码` 标记
        text = re.sub(r'`(.*?)`', r'\1', text)
        return text

    async def delete_message_safely(self, chat_id: int, message_id: int) -> None:
        """安全删除消息，忽略权限错误"""
        try:
            await self.application.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            # 忽略删除失败的情况（如没有权限、消息已删除等）
            self.logger.debug(f"Failed to delete message {message_id} in chat {chat_id}: {e}")
            pass

    async def split_and_send(self, chat_id, text, update=None):
        """分割长消息并发送"""
        if len(text) > 4000:
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, chunk in enumerate(chunks):
                await self.safe_send_message(chat_id, chunk, update)
                if i < len(chunks) - 1:
                    await asyncio.sleep(1)  # 避免发送太快
        else:
            await self.safe_send_message(chat_id, text, update)

    def is_allowed_chat(self, chat_id: int) -> bool:
        return not self.allowed_chats or chat_id in self.allowed_chats

    def extract_message_info(self, update: Update) -> Optional[dict]:
        if not update.message or not update.message.text:
            return None

        message = update.message
        user_name = message.from_user.full_name if message.from_user else "Unknown"
        chat_id = message.chat.id

        if not self.is_allowed_chat(chat_id):
            return None

        return {
            "user": user_name,
            "text": message.text,
            "chat_id": chat_id,
            "message_id": message.message_id,
            "type": "text"
        }

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_allowed_chat(update.effective_chat.id):
            return

        welcome_text = """
🤖 Telegram群组总结机器人已启动！

可用命令：
/summary - 生成最近消息总结
/stats - 查看今日统计
/help - 显示帮助信息

机器人的功能：
• 自动保存群组消息
• 每日自动生成总结（配置文件中设置时间）
• 支持手动总结最近消息
• 可配置AI API地址和模型
• 手动总结不显示时间标题

注意：
• 每日总结时间需在配置文件中设置
• 所有时间都使用计算机默认时间
        """

        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_allowed_chat(update.effective_chat.id):
            return

        help_text = """
📋 **命令帮助**

/start - 启动机器人
/summary - 总结最近消息（默认100条，24小时内）
/summary [数量] - 总结指定数量的最近消息
/summary [数量] [小时] - 总结指定数量和时间范围内的消息
/stats - 显示今日群组统计信息
/help - 显示此帮助信息

**配置说明：**
• 在config.json中设置机器人token
• 配置允许的群组ID
• 设置AI API地址和密钥
• 自定义总结参数

**功能特性：**
• 每个群组消息独立存储
• 每日自动生成总结（配置文件中设置时间）
• 支持自定义API地址
• 消息按日期分文件存储
• 手动总结不显示时间标题

**注意：**
• 每日总结时间需在配置文件的 daily_summary_time 字段中设置
• 所有时间都使用计算机默认时间
• 格式示例：\"23:59\" 或 \"08:00\"
        """

        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id

        if not self.is_allowed_chat(chat_id):
            return

        # 发送状态消息并保存消息ID
        status_message = await update.message.reply_text("🔄 正在生成总结，请稍候...")
        status_message_id = status_message.message_id

        try:
            message_count = config.manual_summary_message_count
            hours = config.manual_summary_hours

            if context.args:
                try:
                    if len(context.args) == 1:
                        message_count = int(context.args[0])
                    elif len(context.args) == 2:
                        message_count = int(context.args[0])
                        hours = int(context.args[1])
                except ValueError:
                    pass

            print(f"Looking for messages: count={message_count}, hours={hours}")
            messages = self.storage.get_latest_messages(chat_id, message_count)
            print(f"Found {len(messages)} total messages")

            if not messages:
                # 删除状态消息并发送无消息提示
                await self.delete_message_safely(chat_id, status_message_id)
                await update.message.reply_text("📭 没有找到可以总结的消息")
                return

            recent_messages = [msg for msg in messages
                             if (datetime.now() - datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))).total_seconds() <= hours * 3600]
            print(f"Found {len(recent_messages)} messages in last {hours} hours")

            if not recent_messages:
                # 删除状态消息并发送无消息提示
                await self.delete_message_safely(chat_id, status_message_id)
                await update.message.reply_text(f"📭 最近{hours}小时内没有消息")
                return

            print("Calling AI summary...")
            summary = self.ai_summary.generate_manual_summary(chat_id, recent_messages, hours)
            print(f"Summary generated: {summary[:100] if summary else 'None'}...")

            if summary:
                # 发送总结
                await self.split_and_send(chat_id, summary, update)
                # 删除状态消息
                await self.delete_message_safely(chat_id, status_message_id)
            else:
                # 删除状态消息并发送失败提示
                await self.delete_message_safely(chat_id, status_message_id)
                await update.message.reply_text("❌ 生成总结失败")

        except Exception as e:
            self.logger.error(f"Error in summary command: {e}")
            # 删除状态消息并发送错误提示
            await self.delete_message_safely(chat_id, status_message_id)
            await update.message.reply_text(f"❌ 生成总结时出错: {str(e)}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id

        if not self.is_allowed_chat(chat_id):
            return

        try:
            stats = self.storage.get_daily_stats(chat_id, date.today())
            recent_count = self.storage.get_message_count(chat_id, 24)

            stats_text = f"""
📊 **今日群组统计** ({date.today().strftime('%Y-%m-%d')})

💬 消息总数: {stats['message_count']} 条
👥 活跃用户: {stats['user_count']} 人
📈 24小时消息: {recent_count} 条
"""

            if stats['users']:
                stats_text += "\n🏆 **活跃用户排行:**\n"
                for i, (user, count) in enumerate(stats['users'][:10], 1):
                    stats_text += f"{i}. {user}: {count} 条消息\n"

            await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            self.logger.error(f"Error in stats command: {e}")
            await update.message.reply_text(f"❌ 获取统计信息时出错: {str(e)}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message_info = self.extract_message_info(update)

        if not message_info:
            return

        try:
            self.storage.save_message(message_info['chat_id'], message_info)

        except Exception as e:
            self.logger.error(f"Error saving message: {e}")

    async def send_daily_summary(self, chat_id: int) -> None:
        try:
            # 使用计算机本地时间获取当天的所有消息
            local_now = datetime.now()
            local_today = local_now.date()

            messages = self.storage.load_messages(chat_id, local_today)
            self.logger.info(f"Loaded {len(messages)} messages for chat {chat_id} on {local_today}")

            if not messages:
                return

            # 按时间段分批总结（分为4个时段：早上、下午、晚上、深夜）
            time_periods = [
                {"name": "早晨", "start": "06:00", "end": "12:00"},
                {"name": "下午", "start": "12:00", "end": "18:00"},
                {"name": "晚上", "start": "18:00", "end": "23:59"},
                {"name": "深夜", "start": "00:00", "end": "06:00"}
            ]

            period_summaries = []
            total_messages = 0

            for period in time_periods:
                period_messages = self._filter_messages_by_time_range(messages, period["start"], period["end"])
                if period_messages:
                    # 限制每个时段最多100条消息，避免token超限
                    if len(period_messages) > 100:
                        period_messages = period_messages[-100:]  # 取最新的100条

                    summary = self.ai_summary.generate_period_summary(period_messages, period['name'])
                    if summary and not summary.startswith("错误") and not summary.startswith("没有消息"):
                        period_summary = f"**{period['name']} ({period['start']}-{period['end']})**\n{summary}"
                        period_summaries.append(period_summary)
                        total_messages += len(period_messages)

            # 合并所有时段的总结
            if period_summaries:
                date_str = local_today.strftime("%Y-%m-%d")
                header = f"📊 **群组每日总结** ({date_str})\n"
                header += f"📝 消息总数: {total_messages} 条\n\n"

                combined_summary = header + "\n\n".join(period_summaries)

                # 使用安全发送方法，自动处理Markdown错误
                await self.safe_send_message(chat_id, combined_summary)
                self.logger.info(f"Daily summary sent to chat {chat_id}")
            else:
                self.logger.info(f"No meaningful conversations found for chat {chat_id}")

        except Exception as e:
            self.logger.error(f"Error sending daily summary to chat {chat_id}: {e}")

    def _filter_messages_by_time_range(self, messages: List[Dict[str, Any]], start_time: str, end_time: str) -> List[Dict[str, Any]]:
        """根据时间范围过滤消息"""
        from datetime import datetime, time

        # 解析时间
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))

        start_dt = time(start_hour, start_minute)
        end_dt = time(end_hour, end_minute)

        filtered_messages = []

        for msg in messages:
            try:
                # 解析消息时间
                msg_time_str = msg.get('timestamp', '')
                if msg_time_str:
                    try:
                        # 解析消息时间戳，保持时区信息或添加UTC时区
                        if 'Z' in msg_time_str or '+' in msg_time_str:
                            # 如果有时区信息，直接解析并转换为本地时间
                            utc_time = datetime.fromisoformat(msg_time_str.replace('Z', '+00:00'))
                            local_time = utc_time.astimezone().replace(tzinfo=None)
                        else:
                            # 如果没有时区信息，假设为本地时间
                            local_time = datetime.fromisoformat(msg_time_str)

                        msg_time_only = local_time.time()

                        # 检查消息是否在时间范围内
                        if start_time <= end_time:
                            # 正常情况：06:00-12:00 或 18:00-23:59
                            if start_dt <= msg_time_only <= end_dt:
                                filtered_messages.append(msg)
                        else:
                            # 跨日情况：00:00-06:00
                            if msg_time_only >= start_dt or msg_time_only < end_dt:
                                filtered_messages.append(msg)
                    except Exception as e:
                        self.logger.debug(f"Error parsing message time {msg_time_str}: {e}")
                        continue

            except Exception as e:
                self.logger.debug(f"Error processing message time: {e}")
                continue

        return filtered_messages

    def setup_handlers(self) -> None:
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("summary", self.summary_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))

        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def start(self) -> None:
        if not self.bot_token:
            self.logger.error("Bot token not configured!")
            return

        try:
            self.application = Application.builder().token(self.bot_token).build()

            self.setup_handlers()

            if config.daily_summary_enabled:
                self.scheduler.start()
                self.logger.info(f"Daily summary scheduled at {config.daily_summary_time}")

            self.logger.info("Bot started successfully!")

            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)

            # 保持机器人运行
            self.logger.info("Bot is now running. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            # 简化异常处理，避免在异常时进行复杂清理
            self.logger.info("Bot will exit due to error")

    def stop(self) -> None:
        self.logger.info("Stopping bot...")

        if self.scheduler:
            self.scheduler.stop()

        if self.application:
            try:
                # 尝试获取当前事件循环，但不强制
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    pass

                if loop and not loop.is_closed():
                    if loop.is_running():
                        loop.create_task(self._cleanup())
                    else:
                        loop.run_until_complete(self._cleanup())
                else:
                    # 事件循环已关闭，只进行简单清理
                    self.logger.info("Event loop closed, skipping async cleanup")

            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")

        self.logger.info("Bot stopped")

    async def _cleanup(self):
        if self.application:
            try:
                # 只关闭updater，避免完全关闭application
                if hasattr(self.application, 'updater') and self.application.updater:
                    await self.application.updater.stop()
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")


__all__ = ['TelegramBot']