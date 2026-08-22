"""订单管理器功能测试"""

import pytest
from unittest.mock import Mock, MagicMock

from trading.order.manager import OrderManager
from data.ibkr_client import IBKRClient
from common.models import OrderStatus


def test_create_market_order_success():
    """测试成功创建市价单"""
    # Mock客户端
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    # Mock IB对象
    mock_ib = MagicMock()
    mock_trade = MagicMock()
    mock_trade.order.orderId = 12345
    mock_ib.placeOrder.return_value = mock_trade
    client.ib = mock_ib

    # 创建订单管理器
    manager = OrderManager(client)

    # 创建订单
    order = manager.create_market_order("AAPL", 10, "BUY")

    # 验证
    assert order is not None
    assert order.symbol == "AAPL"
    assert order.quantity == 10
    assert order.action == "BUY"
    assert order.order_type == "MARKET"
    assert order.status == OrderStatus.SUBMITTED
    assert order.order_id == 12345


def test_create_order_not_connected():
    """测试未连接时创建订单"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = False

    manager = OrderManager(client)
    order = manager.create_market_order("AAPL", 10, "BUY")

    assert order is None


def test_get_order():
    """测试获取订单"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    mock_ib = MagicMock()
    mock_trade = MagicMock()
    mock_trade.order.orderId = 12345
    mock_ib.placeOrder.return_value = mock_trade
    client.ib = mock_ib

    manager = OrderManager(client)

    # 创建订单
    order = manager.create_market_order("AAPL", 10, "BUY")

    # 获取订单
    retrieved = manager.get_order(12345)

    assert retrieved is not None
    assert retrieved.order_id == 12345
    assert retrieved.symbol == "AAPL"


def test_get_all_orders():
    """测试获取所有订单"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    mock_ib = MagicMock()
    client.ib = mock_ib

    manager = OrderManager(client)

    # 创建多个订单
    for i in range(3):
        mock_trade = MagicMock()
        mock_trade.order.orderId = 1000 + i
        mock_ib.placeOrder.return_value = mock_trade
        manager.create_market_order("AAPL", 1, "BUY")

    # 获取所有订单
    orders = manager.get_all_orders()

    assert len(orders) == 3
    assert all(o.symbol == "AAPL" for o in orders)
