"""
策略生命周期集成测试
"""

from unittest.mock import Mock

import pytest

from common.logger import log
from data.ibkr_client import IBKRClient
from strategy.qc_algorithm import QCAlgorithm
from strategy.resolution import Resolution
from strategy.runner import StrategyRunner
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


class TestLifecycleStrategy(QCAlgorithm):
    """测试策略生命周期"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []

    def Initialize(self):
        self.events.append("Initialize")
        self.AddEquity("AAPL", Resolution.Minute)

    def OnData(self, data):
        self.events.append("OnData")

    def OnOrderEvent(self, order_event):
        self.events.append("OnOrderEvent")


@pytest.fixture
def mocked_dependencies():
    """Mock 依赖"""
    ibkr_client = Mock(spec=IBKRClient)
    order_manager = Mock(spec=OrderManager)
    order_manager.register_filled_callback = Mock()
    order_manager.create_market_order = Mock()

    position_manager = Mock(spec=PositionManager)
    position_manager.get_position = Mock(return_value=None)
    position_manager.get_positions = Mock(return_value=[])
    position_manager.get_total_market_value = Mock(return_value=0.0)
    position_manager.get_total_unrealized_pnl = Mock(return_value=0.0)
    position_manager.get_total_realized_pnl = Mock(return_value=0.0)

    return ibkr_client, order_manager, position_manager


def test_strategy_lifecycle(mocked_dependencies):
    """测试策略完整生命周期"""
    ibkr_client, order_manager, position_manager = mocked_dependencies

    # 创建运行器
    runner = StrategyRunner(
        strategy_class=TestLifecycleStrategy,
        ibkr_client=ibkr_client,
        order_manager=order_manager,
        position_manager=position_manager,
    )

    # 启动策略
    runner.start()

    # 验证初始化被调用
    assert "Initialize" in runner.strategy.events
    assert runner.strategy._initialized

    # 模拟数据到达
    data = {"AAPL": Mock()}
    runner.process_data(data)

    # 验证 OnData 被调用
    assert "OnData" in runner.strategy.events

    # 停止策略
    runner.stop()

    log.info("✓ Strategy lifecycle test passed")


def test_strategy_add_equity(mocked_dependencies):
    """测试添加股票"""
    ibkr_client, order_manager, position_manager = mocked_dependencies

    strategy = TestLifecycleStrategy(
        ibkr_client=ibkr_client, order_manager=order_manager, position_manager=position_manager
    )

    strategy._run_initialize()

    # 验证股票被添加
    assert "AAPL" in strategy._securities
    assert strategy._securities["AAPL"] == Resolution.Minute


def test_strategy_market_order(mocked_dependencies):
    """测试市价单"""
    ibkr_client, order_manager, position_manager = mocked_dependencies

    strategy = TestLifecycleStrategy(
        ibkr_client=ibkr_client, order_manager=order_manager, position_manager=position_manager
    )

    strategy._run_initialize()

    # 下市价单
    strategy.MarketOrder("AAPL", 100)

    # 验证订单管理器被调用
    assert order_manager.create_market_order.called


def test_strategy_portfolio_access(mocked_dependencies):
    """测试持仓访问"""
    ibkr_client, order_manager, position_manager = mocked_dependencies

    strategy = TestLifecycleStrategy(
        ibkr_client=ibkr_client, order_manager=order_manager, position_manager=position_manager
    )

    # 访问持仓
    holding = strategy.Portfolio["AAPL"]

    # 验证持仓对象
    assert holding is not None
    assert holding.Symbol == ""  # 无持仓
    assert holding.Quantity == 0.0
    assert not holding.Invested


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
