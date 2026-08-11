"""
交易日历单元测试

测试目的：验证交易日和节假日判断逻辑
依据文档：docs/测试/模块一_市场数据接入_测试文档.md 第3.2节
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from datetime import date
from src.calendar.trading_calendar import TradingCalendar


class TestTradingCalendar:
    """交易日历单元测试类"""

    def test_is_trading_day_monday(self):
        """
        测试用例1：交易日判断（周一）

        测试目的：判断是否为交易日
        输入：周一
        预期：返回True
        """
        calendar = TradingCalendar()

        # 2026年8月10日是周一
        monday = date(2026, 8, 10)
        is_trading = calendar.is_trading_day(monday)

        assert is_trading == True, "周一应该是交易日"

    def test_is_trading_day_saturday(self):
        """
        测试用例1：交易日判断（周六）

        输入：周六
        预期：返回False
        """
        calendar = TradingCalendar()

        # 2026年8月9日是周六
        saturday = date(2026, 8, 9)
        is_trading = calendar.is_trading_day(saturday)

        assert is_trading == False, "周六不是交易日"

    def test_is_trading_day_sunday(self):
        """
        测试用例1：交易日判断（周日）

        输入：周日
        预期：返回False
        """
        calendar = TradingCalendar()

        # 2026年8月9日的次日是周日
        sunday = date(2026, 8, 16)
        is_trading = calendar.is_trading_day(sunday)

        assert is_trading == False, "周日不是交易日"

    def test_is_holiday_christmas(self):
        """
        测试用例2：节假日识别（圣诞节）

        测试目的：识别美国节假日
        输入：圣诞节日期
        预期：返回False（非交易日）
        """
        calendar = TradingCalendar()

        # 圣诞节
        christmas = date(2026, 12, 25)
        is_trading = calendar.is_trading_day(christmas)

        assert is_trading == False, "圣诞节不是交易日"

    def test_is_holiday_thanksgiving(self):
        """
        测试用例2：节假日识别（感恩节）

        输入：感恩节日期
        预期：返回False（非交易日）
        """
        calendar = TradingCalendar()

        # 2026年感恩节（11月第四个周四）
        thanksgiving = date(2026, 11, 26)
        is_trading = calendar.is_trading_day(thanksgiving)

        assert is_trading == False, "感恩节不是交易日"

    def test_get_trading_days(self):
        """
        测试用例3：获取交易日列表

        测试目的：获取时间范围内所有交易日
        输入：2026年8月1日到8月31日
        预期：返回约21个交易日
        验证点：列表长度、日期格式
        """
        calendar = TradingCalendar()

        start_date = date(2026, 8, 1)
        end_date = date(2026, 8, 31)

        trading_days = calendar.get_trading_days(start_date, end_date)

        # 8月约有21个交易日（排除周末）
        assert len(trading_days) >= 20, "8月应该有至少20个交易日"
        assert len(trading_days) <= 23, "8月交易日不应超过23天"

        # 验证返回的都是date对象
        for day in trading_days:
            assert isinstance(day, date), "应该返回date对象"

        # 验证没有周末
        for day in trading_days:
            assert day.weekday() < 5, "不应该包含周末"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
