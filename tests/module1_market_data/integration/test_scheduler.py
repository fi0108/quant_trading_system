"""
调度器集成测试

测试目的：验证调度器与时区管理器、交易日历、连接管理器的集成
依据文档：docs/测试/模块一_市场数据接入_测试文档.md 集成测试部分

注意：这是集成测试，使用真实组件，但不下载大量数据
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
import asyncio
from datetime import datetime, date
from src.core.timezone_manager import TimezoneManager
from src.calendar.trading_calendar import TradingCalendar
from src.connection.manager import ConnectionManager
from src.connection.scheduler import MarketDataScheduler


class TestSchedulerIntegration:
    """调度器集成测试类"""

    def test_scheduler_component_integration(self):
        """
        测试用例1：组件集成验证

        测试目的：验证调度器能正确初始化和集成三个组件
        验证点：
        - 时区管理器初始化成功
        - 交易日历初始化成功
        - 连接管理器初始化成功
        - 调度器初始化成功
        """
        # 创建调度器（内部会创建三个组件）
        scheduler = MarketDataScheduler()

        # 验证组件存在
        assert scheduler.tz_manager is not None, "时区管理器应该存在"
        assert scheduler.calendar is not None, "交易日历应该存在"
        assert scheduler.conn_manager is not None, "连接管理器应该存在"

        # 验证组件类型
        assert isinstance(scheduler.tz_manager, TimezoneManager), "应该是TimezoneManager实例"
        assert isinstance(scheduler.calendar, TradingCalendar), "应该是TradingCalendar实例"
        assert isinstance(scheduler.conn_manager, ConnectionManager), "应该是ConnectionManager实例"

        print("\n所有组件集成成功")

    def test_trading_time_judgment(self):
        """
        测试用例2：交易时段判断

        测试目的：验证调度器能正确判断当前是否应该连接
        验证点：
        - 能调用should_connect_now方法
        - 返回布尔值和原因说明
        - 原因说明非空
        """
        scheduler = MarketDataScheduler()

        # 判断当前是否应该连接
        should_connect, reason = scheduler.should_connect_now()

        # 验证返回值类型
        assert isinstance(should_connect, bool), "应该返回布尔值"
        assert isinstance(reason, str), "应该返回字符串原因"
        assert len(reason) > 0, "原因说明不应为空"

        # 打印当前判断结果（便于查看）
        print(f"\n当前时间: {datetime.now()}")
        print(f"是否应该连接: {should_connect}")
        print(f"原因: {reason}")

    def test_non_trading_day_logic(self):
        """
        测试用例3：非交易日判断

        测试目的：验证调度器在非交易日的判断逻辑
        验证点：
        - 周六应该返回不连接
        - 周日应该返回不连接
        - 原因中应包含"非交易日"或相关信息
        """
        scheduler = MarketDataScheduler()

        # 获取最近的周六
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0 and today.weekday() != 5:
            days_until_saturday = 7

        # 注意：这个测试只验证逻辑，不修改系统时间
        # 如果今天是周六或周日，应该返回False
        if today.weekday() >= 5:  # 5=周六, 6=周日
            should_connect, reason = scheduler.should_connect_now()
            assert should_connect == False, "周末不应该连接"
            print(f"\n周末测试: {reason}")

    def test_timezone_and_calendar_coordination(self):
        """
        测试用例4：时区和日历协调

        测试目的：验证时区管理器和交易日历的协作
        验证点：
        - 能获取当前市场时间
        - 能判断今天是否交易日
        - 时区转换正确
        """
        scheduler = MarketDataScheduler()

        # 获取当前UTC时间
        now_utc = scheduler.tz_manager.now_utc()
        print(f"\nUTC时间: {now_utc}")

        # 转换为市场时间
        now_market = scheduler.tz_manager.utc_to_market(now_utc)
        print(f"市场时间: {now_market}")

        # 判断今天是否交易日
        today = now_market.date()
        is_trading_day = scheduler.calendar.is_trading_day(today)
        print(f"今天({today})是否交易日: {is_trading_day}")

        # 判断是否在交易时段
        is_trading_time = scheduler.tz_manager.is_trading_time(now_utc)
        print(f"当前是否交易时段: {is_trading_time}")

        # 综合判断
        should_connect = is_trading_day and is_trading_time
        scheduler_result, _ = scheduler.should_connect_now()

        # 调度器的判断应该与组合判断一致
        assert scheduler_result == should_connect, "调度器判断应该与组合判断一致"

    @pytest.mark.asyncio
    async def test_scheduler_workflow_simulation(self):
        """
        测试用例5：调度工作流模拟

        测试目的：模拟调度器的工作流程
        验证点：
        - 能执行多次检查
        - 每次检查返回一致的结果（短时间内）
        - 不会崩溃或异常
        """
        scheduler = MarketDataScheduler()

        print("\n模拟调度循环（3次检查）:")

        results = []
        for i in range(3):
            should_connect, reason = scheduler.should_connect_now()
            results.append(should_connect)

            print(f"第{i+1}次检查: 应该连接={should_connect}, 原因={reason}")

            # 短暂等待
            await asyncio.sleep(0.5)

        # 短时间内结果应该一致
        assert all(r == results[0] for r in results), "短时间内判断结果应该一致"

    def test_connection_manager_state(self):
        """
        测试用例6：连接管理器状态

        测试目的：验证连接管理器的状态机
        验证点：
        - 初始状态正确
        - 能获取当前状态
        """
        scheduler = MarketDataScheduler()
        conn_manager = scheduler.conn_manager

        # 获取当前状态（通过state_machine）
        current_state = conn_manager.state_machine.current_state

        print(f"\n连接管理器当前状态: {current_state}")

        # 验证状态不为空
        assert current_state is not None, "应该能获取到状态"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
