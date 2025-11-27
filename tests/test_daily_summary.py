import unittest
import os
import sys
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot.telegram_bot import TelegramBot
from src.storage.message_storage import MessageStorage
from src.ai.summary import AISummary


class TestDailySummary(unittest.TestCase):
    def setUp(self):
        """测试前的准备工作"""
        # 创建测试配置
        self.test_chat_id = -1001234567890
        self.test_messages = [
            {
                "user": "测试用户1",
                "text": "这是一条测试消息1",
                "timestamp": datetime.now().isoformat()
            },
            {
                "user": "测试用户2",
                "text": "这是一条测试消息2",
                "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat()
            }
        ]

    def test_filter_messages_by_time_range(self):
        """测试消息时间范围过滤功能"""
        bot = TelegramBot()

        # 测试正常时间范围
        messages = [
            {"timestamp": "2023-01-01T08:30:00"},
            {"timestamp": "2023-01-01T10:30:00"},
            {"timestamp": "2023-01-01T14:30:00"},
        ]

        filtered = bot._filter_messages_by_time_range(messages, "08:00", "12:00")
        self.assertEqual(len(filtered), 2)

        # 测试跨日时间范围
        messages = [
            {"timestamp": "2023-01-01T23:30:00"},
            {"timestamp": "2023-01-01T01:30:00"},
            {"timestamp": "2023-01-01T14:30:00"},
        ]

        filtered = bot._filter_messages_by_time_range(messages, "22:00", "06:00")
        self.assertEqual(len(filtered), 2)

    @patch('src.ai.summary.AISummary._make_api_request')
    def test_generate_period_summary_success(self, mock_api_request):
        """测试生成时段总结成功的情况"""
        mock_api_request.return_value = "测试总结内容"

        ai_summary = AISummary()
        result = ai_summary.generate_period_summary(self.test_messages, "早晨")

        self.assertEqual(result, "测试总结内容")
        mock_api_request.assert_called_once()

    @patch('src.ai.summary.AISummary._make_api_request')
    def test_generate_period_summary_empty_messages(self, mock_api_request):
        """测试生成时段总结时没有消息的情况"""
        ai_summary = AISummary()
        result = ai_summary.generate_period_summary([], "早晨")

        self.assertEqual(result, "没有消息可以总结")
        mock_api_request.assert_not_called()

    @patch('src.ai.summary.AISummary._make_api_request')
    def test_generate_period_summary_api_error(self, mock_api_request):
        """测试生成时段总结时API错误的情况"""
        mock_api_request.return_value = "错误：API请求失败"

        ai_summary = AISummary()
        result = ai_summary.generate_period_summary(self.test_messages, "早晨")

        self.assertEqual(result, "错误：API请求失败")

    @patch('src.ai.summary.AISummary._make_api_request')
    def test_generate_period_summary_exception(self, mock_api_request):
        """测试生成时段总结时发生异常的情况"""
        mock_api_request.side_effect = Exception("测试异常")

        ai_summary = AISummary()
        result = ai_summary.generate_period_summary(self.test_messages, "早晨")

        self.assertTrue(result.startswith("错误：生成早晨时段总结时发生异常"))

    def test_scheduler_seconds_until_target_time(self):
        """测试计算到目标时间的秒数"""
        from src.scheduler import DailySummaryScheduler
        scheduler = DailySummaryScheduler(Mock())

        # 测试目标时间在未来的情况
        scheduler.target_time = (datetime.now() + timedelta(hours=1)).time()
        seconds = scheduler.seconds_until_target_time()
        self.assertGreater(seconds, 0)
        self.assertLess(seconds, 7200)  # 应该小于2小时


if __name__ == '__main__':
    unittest.main()