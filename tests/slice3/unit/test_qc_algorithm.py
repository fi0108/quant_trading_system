"""
QCAlgorithm 单元测试
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from common.models import Order, OrderStatus, Position
from data.ibkr_client import IBKRClient
from strategy.qc_algorithm import QCAlgorithm
from strategy.resolution import Resolution
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


@pytest.fixture
def mock_ibkr_client():
    """Mock IBKR 客户端"""
    return Mock(spec=IBKRClient)


@pytest.fixture
def mock_order_manager():
    """Mock 订单管理器"""
    mgr = Mock(spec=OrderManager)
    mgr.register_filled_callback = Mock()
    mgr.create_market_order = Mock(return_value=Mock(spec=Order))
    mgr.create_limit_order = Mock(return_value=Mock(spec=Order))
    return mgr


@pytest.fixture
def mock_position_manager():
    """Mock 持仓管理器"""
    mgr = Mock(spec=PositionManager)
    mgr.get_position = Mock(return_value=None)
    mgr.get_positions = Mock(return_value=[])
    mgr.get_total_market_value = Mock(return_value=0.0)
    mgr.get_total_unrealized_pnl = Mock(return_value=0.0)
    mgr.get_total_realized_pnl = Mock(return_value=0.0)
    return mgr


class TestStrategy(QCAlgorithm):
    """测试策略"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initialize_called = False
        self.on_data_called = False
        self.on_order_event_called = False

    def Initialize(self):
        self.initialize_called = True
        self.AddEquity("AAPL", Resolution.Minute)

    def OnData(self, data):
        self.on_data_called = True

    def OnOrderEvent(self, order_event):
        self.on_order_event_called = True


@pytest.fixture
def strategy(mock_ibkr_client, mock_order_manager, mock_position_manager):
    """创建测试策略"""
    return TestStrategy(
        ibkr_client=mock_ibkr_client, order_manager=mock_order_manager, position_manager=mock_position_manager
    )


def test_initialization(strategy):
    """测试策略初始化"""
    assert not strategy._initialized
    assert strategy.Portfolio is not None


def test_run_initialize(strategy):
    """测试运行初始化"""
    strategy._run_initialize()

    assert strategy._initialized
    assert strategy.initialize_called
    assert "AAPL" in strategy._securities


def test_add_equity(strategy):
    """测试添加股票"""
    strategy.AddEquity("TSLA", Resolution.Daily)

    assert "TSLA" in strategy._securities
    assert strategy._securities["TSLA"] == Resolution.Daily


def test_market_order_buy(strategy, mock_order_manager):
    """测试市价买入"""
    order = strategy.MarketOrder("AAPL", 100)

    assert mock_order_manager.create_market_order.called
    call_args = mock_order_manager.create_market_order.call_args
    assert call_args[1]["symbol"] == "AAPL"
    assert call_args[1]["quantity"] == 100
    assert call_args[1]["action"] == "BUY"


def test_market_order_sell(strategy, mock_order_manager):
    """测试市价卖出"""
    order = strategy.MarketOrder("AAPL", -50)

    assert mock_order_manager.create_market_order.called
    call_args = mock_order_manager.create_market_order.call_args
    assert call_args[1]["quantity"] == 50
    assert call_args[1]["action"] == "SELL"


def test_limit_order(strategy, mock_order_manager):
    """测试限价单"""
    order = strategy.LimitOrder("AAPL", 100, 150.5)

    assert mock_order_manager.create_limit_order.called
    call_args = mock_order_manager.create_limit_order.call_args
    assert call_args[1]["symbol"] == "AAPL"
    assert call_args[1]["quantity"] == 100
    assert call_args[1]["limit_price"] == 150.5
    assert call_args[1]["action"] == "BUY"


def test_liquidate_with_position(strategy, mock_position_manager):
    """测试平仓（有持仓）"""
    # Mock 持仓
    position = Position(symbol="AAPL", quantity=100.0, avg_cost=150.0, market_value=15000.0, unrealized_pnl=0.0)
    mock_position_manager.get_position.return_value = position

    order = strategy.Liquidate("AAPL")

    assert order is not None


def test_liquidate_without_position(strategy, mock_position_manager):
    """测试平仓（无持仓）"""
    mock_position_manager.get_position.return_value = None

    order = strategy.Liquidate("AAPL")

    assert order is None


def test_on_data_callback(strategy):
    """测试 OnData 回调"""
    strategy._run_initialize()

    data = {"AAPL": Mock()}
    strategy._process_data(data)

    assert strategy.on_data_called


def test_on_order_event_callback(strategy):
    """测试 OnOrderEvent 回调"""
    order = Mock(spec=Order)

    strategy._on_order_filled_internal(order)

    assert strategy.on_order_event_called


def test_portfolio_access(strategy):
    """测试 Portfolio 访问"""
    holding = strategy.Portfolio["AAPL"]

    assert holding is not None
    assert holding.Quantity == 0.0
    assert not holding.Invested


def test_portfolio_cash(strategy):
    """测试账户现金"""
    assert strategy.Portfolio.Cash > 0


def test_portfolio_total_value(strategy):
    """测试总资产"""
    total_value = strategy.Portfolio.TotalPortfolioValue

    assert total_value >= strategy.Portfolio.Cash


def test_time_property(strategy):
    """测试 Time 属性"""
    time = strategy.Time

    assert isinstance(time, datetime)


def test_is_warming_up(strategy):
    """测试预热状态"""
    assert strategy.IsWarmingUp is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
