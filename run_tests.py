#!/usr/bin/env python3
"""
每日总结功能测试脚本
"""

import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_daily_summary import TestDailySummary


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDailySummary)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回测试结果
    return result.wasSuccessful()


if __name__ == '__main__':
    print("开始运行每日总结功能测试...")
    success = run_tests()
    if success:
        print("所有测试通过！")
        sys.exit(0)
    else:
        print("部分测试失败！")
        sys.exit(1)