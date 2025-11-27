#!/usr/bin/env python3
"""
每日总结功能完整流程测试脚本
用于测试整个每日总结功能的工作流程
"""

import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.bot.telegram_bot import TelegramBot
from src.scheduler import DailySummaryScheduler
from src.ai.summary import AISummary


def test_full_daily_summary_flow():
    """测试完整的每日总结流程"""
    print("开始测试完整的每日总结流程...")

    # 创建测试数据
    test_messages = [
        {
            "user": "用户A",
            "text": "大家早上好！今天天气不错",
            "timestamp": datetime.now().isoformat()
        },
        {
            "user": "用户B",
            "text": "确实不错，适合出去走走",
            "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat()
        },
        {
            "user": "用户C",
            "text": "我推荐去公园散步",
            "timestamp": (datetime.now() - timedelta(minutes=10)).isoformat()
        }
    ]

    print(f"测试数据准备完成，共 {len(test_messages)} 条消息")

    # 测试AI总结功能
    print("\n1. 测试AI总结功能...")
    with patch('src.ai.summary.AISummary._make_api_request') as mock_api:
        mock_api.return_value = "**测试话题**\n- 时间：09:00-09:10\n- 群成员：用户A, 用户B, 用户C\n- 总结：用户们在讨论早上的天气和出行建议\n- 高热发言：用户A说'大家早上好！今天天气不错'"

        ai_summary = AISummary()
        result = ai_summary.generate_period_summary(test_messages, "早晨")

        if result and not result.startswith("错误"):
            print("PASS: AI总结功能测试通过")
            print(f"  生成的总结: {result[:50]}...")
        else:
            print("FAIL: AI总结功能测试失败")
            print(f"  错误信息: {result}")
            return False

    # 测试消息时间过滤功能
    print("\n2. 测试消息时间过滤功能...")
    bot = TelegramBot()

    # 测试正常时间范围
    messages = [
        {"timestamp": "2023-01-01T08:30:00"},
        {"timestamp": "2023-01-01T10:30:00"},
        {"timestamp": "2023-01-01T14:30:00"},
    ]

    filtered = bot._filter_messages_by_time_range(messages, "08:00", "12:00")
    if len(filtered) == 2:
        print("PASS: 消息时间过滤功能测试通过")
    else:
        print("FAIL: 消息时间过滤功能测试失败")
        return False

    # 测试调度器功能
    print("\n3. 测试调度器功能...")
    scheduler = DailySummaryScheduler(Mock())

    # 测试时间计算
    scheduler.target_time = (datetime.now() + timedelta(minutes=5)).time()
    seconds = scheduler.seconds_until_target_time()

    if seconds > 0:
        print("PASS: 调度器时间计算功能测试通过")
        print(f"  距离下次执行还有 {seconds} 秒")
    else:
        print("FAIL: 调度器时间计算功能测试失败")
        return False

    print("\nSUCCESS: 所有测试通过！每日总结功能工作正常")
    return True


def test_error_handling():
    """测试错误处理功能"""
    print("\n开始测试错误处理功能...")

    # 测试API错误情况
    print("\n1. 测试API错误处理...")
    with patch('src.ai.summary.AISummary._make_api_request') as mock_api:
        mock_api.return_value = "错误：API密钥无效"

        ai_summary = AISummary()
        result = ai_summary.generate_period_summary([{"user": "test", "text": "test", "timestamp": "2023-01-01T08:30:00"}], "早晨")

        if result and result.startswith("错误"):
            print("PASS: API错误处理测试通过")
            print(f"  错误信息: {result}")
        else:
            print("FAIL: API错误处理测试失败")
            return False

    # 测试异常处理
    print("\n2. 测试异常处理...")
    with patch('src.ai.summary.AISummary._make_api_request') as mock_api:
        mock_api.side_effect = Exception("网络连接超时")

        ai_summary = AISummary()
        result = ai_summary.generate_period_summary([{"user": "test", "text": "test", "timestamp": "2023-01-01T08:30:00"}], "早晨")

        if result and "异常" in result:
            print("PASS: 异常处理测试通过")
            print(f"  异常信息: {result}")
        else:
            print("FAIL: 异常处理测试失败")
            return False

    print("\nSUCCESS: 错误处理功能测试通过！")
    return True


if __name__ == '__main__':
    print("=" * 50)
    print("Telegram群组每日总结功能测试脚本")
    print("=" * 50)

    success1 = test_full_daily_summary_flow()
    success2 = test_error_handling()

    if success1 and success2:
        print("\nALL TESTS PASSED: 所有测试都通过了！每日总结功能工作正常")
        sys.exit(0)
    else:
        print("\nTESTS FAILED: 部分测试失败，请检查代码")
        sys.exit(1)