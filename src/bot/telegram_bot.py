import asyncio
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from ..config import config
from ..storage import MessageStorage, get_local_time_with_offset, get_local_date_with_offset
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

        # 获取发送者信息
        if message.from_user:
            user_name = message.from_user.full_name
        else:
            user_name = "Unknown"

        chat_id = message.chat.id

        if not self.is_allowed_chat(chat_id):
            return None

        return {
            "user": user_name,
            "text": message.text,
            "chat_id": chat_id
        }

    def _should_respond(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Check if the bot should respond to the command.
        In private chats: Always respond (no @ mention needed).
        In group chats:
            - For commands (starting with /): Always respond
            - For regular messages: Only respond when @bot_username is mentioned
        """
        chat = update.effective_chat
        if not self.is_allowed_chat(chat.id):
            return False

        # Private chats always allowed if chat_id is allowed
        if chat.type == 'private':
            return True

        message_text = update.message.text if update.message and update.message.text else ""

        # For group chats, check if it's a command
        if message_text.startswith('/'):
            # Commands always work in group chats (no @ mention required)
            return True

        # For non-command messages in group chats, require @ mention
        bot_username = context.bot.username if context.bot else None

        # If we can't get bot username, be conservative and don't respond
        if not bot_username:
            self.logger.warning(f"Cannot determine bot username, not responding in group chat {chat.id}")
            return False

        # Check if message contains @bot_username mention
        target_mention = f"@{bot_username}".lower()
        text_lower = message_text.lower() if message_text else ""

        if target_mention in text_lower:
            self.logger.debug(f"Found bot mention in message, responding")
            return True
        else:
            self.logger.debug(f"No bot mention found in group chat for non-command message, not responding")
            return False

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._should_respond(update, context):
            return

        welcome_text = """
🤖 Telegram群组总结机器人已启动！

可用命令：
/summary - 生成最近100条消息总结（默认）
/summary n 100 - 生成最近100条消息总结
/summary h 12 - 生成最近12小时内的消息总结
/dailysummary - 手动触发生成今日总结
/stats - 查看今日统计
/schedulerstatus - 查看调度器状态
/help - 显示帮助信息

机器人的功能：
• 自动保存群组消息
• 每日自动生成总结（配置文件中设置时间）
• 支持手动总结最近消息
• 支持手动触发每日总结
• 可配置AI API地址和模型
• 详细的任务执行报告

⚠️重要使用说明：
• 在群组中，命令可以直接使用
• 在群组中，普通消息需要 @机器人用户名 才会触发
• 在私聊中所有消息都可以直接触发，无需 @ 提及
• 每日总结时间需在配置文件中设置
• 所有时间都使用计算机默认时间
        """

        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._should_respond(update, context):
            return

        help_text = """
📋 **命令帮助**

/start - 启动机器人
/summary - 总结最近100条消息（默认）
/summary n 100 - 总结最近指定数量的消息
/summary h 12 - 总结最近指定小时内的消息
/dailysummary - 手动触发生成今日总结（按时段生成）
/schedulerstatus - 查看调度器状态（显示下次执行时间、时区偏移、AI模型等）
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
• 支持手动触发每日总结
• 支持自定义API地址
• 消息按日期分文件存储
• 总结按时段分类生成（早晨、下午、晚上、深夜）
• 详细的执行报告和错误通知
• 调度器状态监控（显示时区、AI模型配置）

**重要说明：**
• 📌 **在群组中，命令可以直接使用，普通消息需要 @机器人用户名 才会触发**
• 📌 **在私聊中所有消息都可以直接触发，无需 @ 提及**
• 每日总结时间需在配置文件的 daily_summary_time 字段中设置
• 所有时间都使用计算机默认时间
• 格式示例：\"23:59\" 或 \"08:00\"
• 每日总结会发送到所有允许的群组
• 任务执行过程中会发送详细的进度通知
• /summary 默认总结100条消息，而非按时间筛选
        """

        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._should_respond(update, context):
            return

        chat_id = update.effective_chat.id

        # 发送状态消息并保存消息ID
        status_message = await update.message.reply_text("🔄 正在生成总结，请稍候...")
        status_message_id = status_message.message_id

        try:
            # 默认配置
            message_count = 100  # 默认总结100条消息
            hours = 24  # 默认不超过24小时

            # 解析参数
            if context.args:
                try:
                    if len(context.args) == 2:
                        # 格式: /summary n 100 或 /summary h 12
                        prefix = context.args[0].lower()
                        value = int(context.args[1])

                        if prefix == 'n':
                            # n: 指定消息数量
                            message_count = value
                        elif prefix == 'h':
                            # h: 指定小时数
                            hours = value
                        else:
                            # 如果前缀不认识，尝试解析为小时
                            hours = int(context.args[0])
                    elif len(context.args) == 1:
                        # 单个参数，默认作为小时数
                        hours = int(context.args[0])
                except (ValueError, IndexError):
                    # 如果解析失败，使用默认值
                    pass

            print(f"Looking for messages: count={message_count}, hours={hours}")

            # 先加载消息（使用较大的数量，确保能获取到足够的历史消息）
            messages = self.storage.get_latest_messages(chat_id, max(message_count * 2, 1000))
            print(f"Found {len(messages)} total messages")

            if not messages:
                # 删除状态消息并发送无消息提示
                await self.delete_message_safely(chat_id, status_message_id)
                await update.message.reply_text("📭 没有找到可以总结的消息")
                return

            # 先按时间筛选
            recent_messages = [msg for msg in messages
                             if (get_local_time_with_offset() - datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))).total_seconds() <= hours * 3600]

            # 再按数量限制
            if len(recent_messages) > message_count:
                recent_messages = recent_messages[-message_count:]  # 取最新的N条

            print(f"Found {len(recent_messages)} messages (limited to {message_count} within {hours} hours)")

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
        if not self._should_respond(update, context):
            return

        chat_id = update.effective_chat.id

        try:
            stats = self.storage.get_daily_stats(chat_id, get_local_date_with_offset())
            recent_count = self.storage.get_message_count(chat_id, 24)

            stats_text = f"""
📊 **今日群组统计** ({get_local_date_with_offset().strftime('%Y-%m-%d')})

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

    async def daily_summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """手动触发今日总结的命令处理器"""
        if not self._should_respond(update, context):
            return

        chat_id = update.effective_chat.id

        # 发送状态消息
        status_message = await update.message.reply_text("🔄 正在执行今日总结任务，请稍候...")
        status_message_id = status_message.message_id

        try:
            # 调用发送每日总结的方法，并获取结果报告
            result = await self.send_daily_summary(chat_id)

            # 删除状态消息
            await self.delete_message_safely(chat_id, status_message_id)

            # 根据结果发送简短的反馈
            if result.get('status') == 'success':
                await update.message.reply_text(f"✅ 每日总结任务完成!")
            elif result.get('status') == 'partial':
                await update.message.reply_text(f"⚠️ 每日总结部分完成，有 {len(result.get('errors', []))} 个错误")
            elif result.get('status') == 'no_messages':
                await update.message.reply_text(f"ℹ️ 今日没有消息记录")
            else:
                await update.message.reply_text(f"❌ 生成总结时发生错误")

        except Exception as e:
            self.logger.error(f"Error in daily_summary command: {e}")
            await self.delete_message_safely(chat_id, status_message_id)
            await update.message.reply_text(f"❌ 生成今日总结时出错: {str(e)}")

    async def scheduler_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """查询调度器状态的命令"""
        if not self._should_respond(update, context):
            return

        chat_id = update.effective_chat.id

        try:
            is_running = self.scheduler.running if self.scheduler else False
            target_time = config.daily_summary_time if hasattr(config, 'daily_summary_time') else "未配置"
            is_enabled = config.daily_summary_enabled if hasattr(config, 'daily_summary_enabled') else False
            timezone_offset = config.timezone_offset_hours if hasattr(config, 'timezone_offset_hours') else 0
            ai_model = config.model if hasattr(config, 'model') else "未配置"
            api_base = config.api_base if hasattr(config, 'api_base') else "未配置"

            from datetime import datetime, timedelta

            # 计算下次执行时间
            next_time_str = "N/A"
            if is_running and is_enabled:
                try:
                    seconds_remaining = self.scheduler.seconds_until_target_time()
                    next_time = datetime.now() + timedelta(seconds=seconds_remaining)
                    next_time_str = next_time.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass

            # 格式化时区偏移显示
            if timezone_offset >= 0:
                tz_display = f"UTC+{timezone_offset}"
            else:
                tz_display = f"UTC{timezone_offset}"

            status_text = f"""
🤖 调度器状态报告

📊 运行状态:
{'🟢 正在运行' if is_running else '🔴 已停止'}
⏰ 计划时间: {target_time}
{'✅ 已启用' if is_enabled else '❌ 已禁用'}

⏲ 时区设置:
🌍 时区偏移: {tz_display} 小时
⚠️ 注意: 调度器按本地时间运行

🤖 AI 配置:
📝 模型: {ai_model}
🔗 API地址: {api_base[:30]}{'...' if len(api_base) > 30 else ''}

🗓 下次执行:
{next_time_str if is_running and is_enabled else 'N/A (调度器未运行或未启用)'}

ℹ️ 使用说明:
• 调度器使用本地计算机时间
• 每日总结将在计划时间自动触发
• 使用 /dailysummary 可手动触发今日总结
• 时区偏移仅用于日志记录
            """

            await update.message.reply_text(status_text)

        except Exception as e:
            self.logger.error(f"Error getting scheduler status: {e}")
            await update.message.reply_text(f"❌ 获取调度器状态时出错: {str(e)}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message_info = self.extract_message_info(update)

        if not message_info:
            return



        try:
            self.storage.save_message(message_info['chat_id'], message_info)

        except Exception as e:
            self.logger.error(f"Error saving message: {e}")

    async def send_daily_summary(self, chat_id: int) -> dict:
        """
        发送每日总结，返回详细的执行报告
        返回值: {
            'status': 'success'|'partial'|'failed'|'no_messages',
            'total_messages': int,
            'periods_processed': int,
            'errors': [error_messages],
            'summary_sent': bool
        }
        """

        # 起始状态通知
        start_time = datetime.now()
        check_point_msg = await self.safe_send_message(chat_id, f"🔔 **每日总结任务启动**\n⏰ 开始时间: {start_time.strftime('%H:%M:%S')}\n📊 正在处理消息并生成总结...")
        check_point_msg_id = check_point_msg.message_id if check_point_msg else None

        result = {
            'status': 'failed',
            'total_messages': 0,
            'periods_processed': 0,
            'errors': [],
            'summary_sent': False
        }

        try:
            # 使用考虑偏移量的本地时间获取当天的所有消息
            local_now = get_local_time_with_offset()
            local_today = local_now.date()

            await self.safe_send_message(chat_id, f"⏳ **阶段1: 加载消息**\n📅 处理日期: {local_today}\n正在加载今日消息...")

            messages = self.storage.load_messages(chat_id, local_today)
            self.logger.info(f"Loaded {len(messages)} messages for chat {chat_id} on {local_today}")

            await self.safe_send_message(chat_id, f"✅ 加载完成! 共 {len(messages)} 条消息")

            if not messages:
                # 发送无消息提示
                date_str = local_today.strftime("%Y-%m-%d")
                no_msg_summary = f"📊 **群组每日总结** ({date_str})\n\n📭 今日没有消息记录"
                await self.safe_send_message(chat_id, no_msg_summary)
                result['status'] = 'no_messages'
                result['summary_sent'] = True

                # 删除检查点消息
                if check_point_msg_id:
                    await self.delete_message_safely(chat_id, check_point_msg_id)

                return result

            result['total_messages'] = len(messages)

            # 按时间段分批总结（分为4个时段：早上、下午、晚上、深夜）
            time_periods = [
                {"name": "早晨", "start": "06:00", "end": "12:00"},
                {"name": "下午", "start": "12:00", "end": "18:00"},
                {"name": "晚上", "start": "18:00", "end": "23:59"},
                {"name": "深夜", "start": "00:00", "end": "06:00"}
            ]

            period_summaries = []
            total_messages_processed = 0
            error_messages = []

            await self.safe_send_message(chat_id, f"⏳ **阶段2: 分时段生成总结**\n共 {len(time_periods)} 个时段...")

            for i, period in enumerate(time_periods, 1):
                try:
                    await self.safe_send_message(chat_id, f"💬 **正在处理时段 {i}/{len(time_periods)}**: {period['name']} ({period['start']}-{period['end']})")

                    period_messages = self._filter_messages_by_time_range(messages, period["start"], period["end"])

                    if period_messages:
                        await self.safe_send_message(chat_id, f"  └─ 发现 {len(period_messages)} 条消息，正在请求AI生成总结...")

                        # 不再限制消息数量，让AI处理所有消息以生成更全面的总结
                        summary = self.ai_summary.generate_period_summary(period_messages, period['name'])

                        if summary:
                            if summary.startswith("错误"):
                                # 记录错误但继续处理其他时段
                                error_msg = f"{period['name']}时段总结错误: {summary}"
                                error_messages.append(error_msg)
                                result['errors'].append(error_msg)
                                self.logger.error(f"Summary error for chat {chat_id}, period {period['name']}: {summary}")
                                await self.safe_send_message(chat_id, f"  ❌ 总结生成失败: {summary[:100]}")
                            elif not summary.startswith("没有消息"):
                                period_summary = f"**{period['name']} ({period['start']}-{period['end']})**\n{summary}"
                                period_summaries.append(period_summary)
                                total_messages_processed += len(period_messages)
                                result['periods_processed'] += 1
                                await self.safe_send_message(chat_id, f"  ✅ 总结生成成功! ({len(summary)} 字符)")
                            else:
                                await self.safe_send_message(chat_id, f"  ℹ️ 该时段无有效讨论")
                        else:
                            error_msg = f"{period['name']}时段总结返回空结果"
                            error_messages.append(error_msg)
                            result['errors'].append(error_msg)
                            self.logger.warning(f"Empty summary for chat {chat_id}, period {period['name']}")
                            await self.safe_send_message(chat_id, f"  ❌ 返回空结果")

                        # 在每个时间段总结请求后添加延迟
                        await asyncio.sleep(config.daily_summary_period_interval)
                    else:
                        await self.safe_send_message(chat_id, f"  ℹ️ 无消息")

                except Exception as e:
                    error_msg = f"{period['name']}时段处理异常: {str(e)}"
                    error_messages.append(error_msg)
                    result['errors'].append(error_msg)
                    self.logger.error(f"Error processing period {period['name']} for chat {chat_id}: {e}")
                    await self.safe_send_message(chat_id, f"  ❌ 异常错误: {str(e)}")
                    continue

            result['total_messages'] = total_messages_processed

            await self.safe_send_message(chat_id, f"⏳ **阶段3: 生成活跃用户统计**")

            # 生成活跃成员排行
            user_stats = {}
            for msg in messages:
                user = msg.get('user', 'Unknown')
                user_stats[user] = user_stats.get(user, 0) + 1

            # 排序获取前10名活跃用户
            top_users = sorted(user_stats.items(), key=lambda x: x[1], reverse=True)[:10]

            await self.safe_send_message(chat_id, f"✅ 统计完成! 今日活跃用户: {len(user_stats)} 人")

            # 合并所有时段的总结
            date_str = local_today.strftime("%Y-%m-%d")
            header = f"📊 **群组每日总结** ({date_str})\n"
            header += f"📝 消息总数: {total_messages_processed} 条\n"
            header += f"👥 活跃用户: {len(user_stats)} 人\n\n"

            # 添加活跃成员排行
            if top_users:
                header += "🏆 **今日活跃用户排行:**\n"
                for i, (user, count) in enumerate(top_users, 1):
                    header += f"{i}. {user}: {count} 条消息\n"
                header += "\n"

            # 构建最终总结内容
            if period_summaries:
                combined_summary = header + "\n\n".join(period_summaries)
                result['status'] = 'success' if not error_messages else 'partial'
            else:
                combined_summary = header.rstrip() + "\n\n📭 今日无有效话题讨论"
                result['status'] = 'success' if not error_messages else 'partial'

            # 添加错误信息（如果有）
            if error_messages:
                combined_summary += "\n\n⚠️ **处理过程中遇到的问题:**\n" + "\n".join([f"- {err}" for err in error_messages[:5]])  # 限制显示前5个错误

            # 删除检查点消息
            if check_point_msg_id:
                await self.delete_message_safely(chat_id, check_point_msg_id)

            await self.safe_send_message(chat_id, f"⏳ **阶段4: 发送总结**")

            # 使用安全发送方法，自动处理Markdown错误
            await self.safe_send_message(chat_id, combined_summary)
            result['summary_sent'] = True

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # 发送完成报告
            report = f"""
✅ **每日总结任务完成**

⏱ 总耗时: {duration:.1f} 秒
📊 处理消息: {result['total_messages']} 条
💬 成功时段: {result['periods_processed']}/{len(time_periods)}
✅ 状态: {"全部成功" if result['status'] == 'success' else "部分成功" if result['status'] == 'partial' else "失败"}
"""

            if result['errors']:
                report += f"\n⚠️ 错误数: {len(result['errors'])} 个"

            await self.safe_send_message(chat_id, report)

            self.logger.info(f"Daily summary sent to chat {chat_id}, result: {result}")

            return result

        except Exception as e:
            error_msg = f"生成每日总结时发生严重错误: {str(e)}"
            self.logger.error(f"Error sending daily summary to chat {chat_id}: {e}")

            result['errors'].append(error_msg)

            try:
                # 删除检查点消息
                if check_point_msg_id:
                    await self.delete_message_safely(chat_id, check_point_msg_id)

                # 发送错误信息到群组
                error_notification = f"""
❌ **每日总结生成失败**

🕒 开始时间: {start_time.strftime('%H:%M:%S')}
⚠️ 错误: {str(e)}
"""
                if result['errors']:
                    error_notification += "\n📋 详细错误:\n" + "\n".join([f"- {err}" for err in result['errors'][:5]])

                await self.safe_send_message(chat_id, error_notification)
            except Exception as send_error:
                self.logger.error(f"Failed to send error message to chat {chat_id}: {send_error}")

            return result

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
        self.application.add_handler(CommandHandler("dailysummary", self.daily_summary_command))
        self.application.add_handler(CommandHandler("schedulerstatus", self.scheduler_status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))

        # 处理文本消息
        # 移除 filters.Bot，在 handle_message 中手动过滤
        message_filter = filters.TEXT & ~filters.COMMAND
        self.application.add_handler(MessageHandler(message_filter, self.handle_message))

    async def start(self) -> None:
        if not self.bot_token:
            self.logger.error("Bot token not configured!")
            return

        try:
            # 创建Application
            builder = Application.builder().token(self.bot_token)
            self.application = builder.build()

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