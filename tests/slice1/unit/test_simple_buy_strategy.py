"""固定买入策略功能测试"""

from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from common.models import Bar, Order, OrderStatus
from strategy.examples.simple_buy import SimpleBuyStrategy
from trading.order.manager import OrderManager
from trading.risk.manager import RiskManager


def test_strategy_initialization():
    """测试策略初始化"""
    order_mgr = Mock(spec=OrderManager)
    risk_mgr = Mock(spec=RiskManager)

    strategy = SimpleBuyStrategy(order_mgr, risk_mgr, symbol="AAPL", buy_interval=10)

    assert strategy.symbol == "AAPL"
    assert strategy.buy_interval == 10
    assert strategy.bar_count == 0


def test_on_bar_count():
    """测试Bar计数"""
    order_mgr = Mock(spec=OrderManager)
    risk_mgr = Mock(spec=RiskManager)

    strategy = SimpleBuyStrategy(order_mgr, risk_mgr, buy_interval=10)

    # 模拟5个Bar
    for i in range(5):
        bar = Bar(symbol="AAPL", timestamp=datetime.now(), open=150.0, high=151.0, low=149.0, close=150.5, volume=1000)
        strategy.on_bar(bar)

    assert strategy.bar_count == 5


def test_buy_trigger():
    """测试买入触发"""
    order_mgr = Mock(spec=OrderManager)
    risk_mgr = Mock(spec=RiskManager)

    # 风控通过
    risk_mgr.can_place_order.return_value = True

    # Mock订单创建
    mock_order = Order(
        order_id=12345, symbol="AAPL", action="BUY", quantity=1, order_type="MARKET", status=OrderStatus.SUBMITTED
    )
    order_mgr.create_market_order.return_value = mock_order

    strategy = SimpleBuyStrategy(order_mgr, risk_mgr, buy_interval=10)

    # 模拟10个Bar，应该触发1次买入
    for i in range(10):
        bar = Bar(symbol="AAPL", timestamp=datetime.now(), open=150.0, high=151.0, low=149.0, close=150.5, volume=1000)
        strategy.on_bar(bar)

    # 验证买入被调用
    order_mgr.create_market_order.assert_called_once_with(symbol="AAPL", quantity=1, action="BUY")


def test_buy_risk_rejected():
    """测试买入被风控拒绝"""
    order_mgr = Mock(spec=OrderManager)
    risk_mgr = Mock(spec=RiskManager)

    # 风控不通过
    risk_mgr.can_place_order.return_value = False

    strategy = SimpleBuyStrategy(order_mgr, risk_mgr, buy_interval=10)

    # 模拟10个Bar
    for i in range(10):
        bar = Bar(symbol="AAPL", timestamp=datetime.now(), open=150.0, high=151.0, low=149.0, close=150.5, volume=1000)
        strategy.on_bar(bar)

    # 订单创建不应该被调用
    order_mgr.create_market_order.assert_not_called()


def test_multiple_buy_triggers():
    """测试多次买入触发"""
    order_mgr = Mock(spec=OrderManager)
    risk_mgr = Mock(spec=RiskManager)
    risk_mgr.can_place_order.return_value = True

    mock_order = Order(
        order_id=12345, symbol="AAPL", action="BUY", quantity=1, order_type="MARKET", status=OrderStatus.SUBMITTED
    )
    order_mgr.create_market_order.return_value = mock_order

    strategy = SimpleBuyStrategy(order_mgr, risk_mgr, buy_interval=10)

    # 模拟25个Bar，应该触发2次买入（第10个和第20个）
    for i in range(25):
        bar = Bar(symbol="AAPL", timestamp=datetime.now(), open=150.0, high=151.0, low=149.0, close=150.5, volume=1000)
        strategy.on_bar(bar)

    # 验证买入被调用2次
    assert order_mgr.create_market_order.call_count == 2
