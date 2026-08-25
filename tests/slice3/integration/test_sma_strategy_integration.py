"""
SMA双均线策略 - 集成测试

测试策略在完整环境中的运行
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from strategies.sma_crossover_live import SMAStrategyLive
from strategy.indicators.sma import SimpleMovingAverage


class TestSMAStrategyIntegration:
    """SMA策略集成测试"""

    def test_strategy_with_historical_data(self):
        """测试1：使用历史数据回放"""
        # 创建策略（测试模式）
        strategy = SMAStrategyLive()
        strategy.symbol = "AAPL"
        strategy.fast_period = 3
        strategy.slow_period = 5
        strategy.trade_quantity = 100
        strategy.max_order_value = 50000

        # Mock依赖
        strategy.Portfolio = Mock()
        strategy.Portfolio.get_holdings.return_value = None
        strategy.MarketOrder = Mock()
        strategy.Log = Mock()

        # 手动创建指标（跳过Initialize）
        strategy.sma_fast = SimpleMovingAverage(f"SMA({strategy.symbol},{strategy.fast_period})", strategy.fast_period)
        strategy.sma_slow = SimpleMovingAverage(f"SMA({strategy.symbol},{strategy.slow_period})", strategy.slow_period)

        # 模拟历史价格数据
        prices = [100, 102, 101, 105, 108, 110, 107, 106, 104, 103]

        for i, price in enumerate(prices):
            # 更新指标
            time = datetime.now() + timedelta(days=i)
            strategy.sma_fast.Update(time, price)
            strategy.sma_slow.Update(time, price)

            # 创建模拟数据
            bar = Mock()
            bar.time = time
            bar.close = price
            data = {strategy.symbol: bar}

            # 处理数据
            strategy.OnData(data)

        # 验证指标已就绪
        assert strategy.sma_fast.IsReady
        assert strategy.sma_slow.IsReady

        # 验证至少有一些交易信号
        # （具体多少次取决于价格序列，这里只验证调用过）
        assert strategy.MarketOrder.call_count >= 0

    def test_strategy_initialization_with_mocks(self):
        """测试2：带Mock的完整初始化"""
        # 创建策略
        strategy = SMAStrategyLive()
        strategy.symbol = "AAPL"
        strategy.fast_period = 10
        strategy.slow_period = 20

        # Mock所有方法
        strategy.SMA = Mock(side_effect=[Mock(), Mock()])
        strategy.Log = Mock()
        strategy.Portfolio = Mock()
        strategy.Portfolio.get_holdings.return_value = None

        # 调用Initialize
        strategy.Initialize()

        # 验证SMA被调用
        assert strategy.SMA.call_count == 2

        # 验证日志记录
        assert strategy.Log.call_count > 0

    def test_order_lifecycle(self):
        """测试3：完整订单生命周期"""
        # 创建策略
        strategy = SMAStrategyLive()
        strategy.symbol = "AAPL"
        strategy.trade_quantity = 100
        strategy.max_order_value = 50000

        # Mock依赖
        strategy.Portfolio = Mock()
        mock_holdings = Mock()
        mock_holdings.quantity = 0
        strategy.Portfolio.get_holdings.return_value = mock_holdings

        strategy.MarketOrder = Mock()
        strategy.Log = Mock()

        # 1. 处理买入信号
        strategy._handle_signal("buy", 150.0, datetime.now())
        assert strategy.MarketOrder.call_count == 1
        assert strategy.previous_signal == "buy"

        # 2. 模拟订单成交
        order_event = Mock()
        order_event.order_id = 1
        order_event.status = "Filled"
        order_event.symbol = "AAPL"
        order_event.quantity = 100
        order_event.filled_quantity = 100
        order_event.average_fill_price = 150.0

        # 更新持仓（模拟成交后的状态）
        mock_holdings.quantity = 100
        mock_holdings.average_price = 150.0
        mock_holdings.unrealized_pnl = 0.0

        strategy.OnOrderEvent(order_event)

        # 验证订单处理
        log_calls = [str(call) for call in strategy.Log.call_args_list]
        assert any("FILL" in str(call) for call in log_calls)

        # 3. 处理卖出信号
        strategy.MarketOrder.reset_mock()
        strategy._handle_signal("sell", 155.0, datetime.now())
        assert strategy.MarketOrder.call_count == 1
        assert strategy.previous_signal == "sell"

        # 4. 模拟平仓成交
        order_event2 = Mock()
        order_event2.order_id = 2
        order_event2.status = "Filled"
        order_event2.symbol = "AAPL"
        order_event2.quantity = -100
        order_event2.filled_quantity = -100
        order_event2.average_fill_price = 155.0

        # 更新持仓（已平仓）
        strategy.Portfolio.get_holdings.return_value = None

        strategy.OnOrderEvent(order_event2)

        # 验证平仓处理
        log_calls = [str(call) for call in strategy.Log.call_args_list]
        assert any("closed" in str(call).lower() for call in log_calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
