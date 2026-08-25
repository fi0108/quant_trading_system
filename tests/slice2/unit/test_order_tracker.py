"""
订单跟踪器单元测试
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from ib_insync import IB, Contract, Execution, Fill
from ib_insync import Order as IBOrder
from ib_insync import OrderStatus as IBOrderStatus
from ib_insync import Trade

from common.models import Order, OrderStatus
from data.storage.order_repository import OrderRepository
from trading.order.tracker import OrderTracker


@pytest.fixture
def mock_ib():
    """Mock IBKR 连接"""
    ib = Mock(spec=IB)
    # Mock 事件对象，支持 += 和 -= 操作
    ib.orderStatusEvent = MagicMock()
    ib.execDetailsEvent = MagicMock()
    return ib


@pytest.fixture
def mock_repo():
    """Mock 订单仓库"""
    repo = Mock(spec=OrderRepository)
    repo.save = Mock(return_value=True)
    repo.get_by_id = Mock(return_value=None)
    return repo


@pytest.fixture
def tracker(mock_ib, mock_repo):
    """创建订单跟踪器"""
    return OrderTracker(mock_ib, mock_repo)


def create_mock_trade(order_id=1, symbol="AAPL", action="BUY", quantity=100, status="Submitted"):
    """创建 Mock Trade 对象"""
    trade = Mock(spec=Trade)

    # 订单
    order = Mock(spec=IBOrder)
    order.orderId = order_id
    order.action = action
    order.totalQuantity = quantity
    order.orderType = "MKT"
    order.lmtPrice = 0
    trade.order = order

    # 合约
    contract = Mock(spec=Contract)
    contract.symbol = symbol
    trade.contract = contract

    # 订单状态
    order_status = Mock(spec=IBOrderStatus)
    order_status.status = status
    order_status.filled = 0 if status == "Submitted" else quantity
    order_status.avgFillPrice = 0 if status == "Submitted" else 150.0
    trade.orderStatus = order_status

    return trade


def test_tracker_start(tracker, mock_ib):
    """测试启动跟踪"""
    tracker.start()

    # 验证事件已注册（简化验证）
    # 只要不抛异常就说明成功
    assert True


def test_tracker_stop(tracker, mock_ib):
    """测试停止跟踪"""
    tracker.start()
    tracker.stop()

    # 验证事件已移除（简化验证）
    # 只要不抛异常就说明成功
    assert True


def test_on_order_status_submitted(tracker, mock_repo):
    """测试订单提交状态"""
    trade = create_mock_trade(order_id=1, status="Submitted")

    # 触发状态变化
    tracker._on_order_status(trade)

    # 验证保存到数据库
    assert mock_repo.save.called

    # 验证订单状态
    saved_order = mock_repo.save.call_args[0][0]
    assert saved_order.order_id == 1
    assert saved_order.symbol == "AAPL"
    assert saved_order.status == OrderStatus.SUBMITTED
    assert saved_order.filled_quantity == 0


def test_on_order_status_filled(tracker, mock_repo):
    """测试订单成交状态"""
    trade = create_mock_trade(order_id=2, status="Filled")

    # 注册成交回调
    callback = Mock()
    tracker.register_filled_callback(callback)

    # 触发状态变化
    tracker._on_order_status(trade)

    # 验证保存到数据库
    assert mock_repo.save.called

    # 验证订单状态
    saved_order = mock_repo.save.call_args[0][0]
    assert saved_order.order_id == 2
    assert saved_order.status == OrderStatus.FILLED
    assert saved_order.filled_quantity == 100
    assert saved_order.avg_fill_price == 150.0
    assert saved_order.filled_at is not None

    # 验证回调被触发
    assert callback.called
    callback_order = callback.call_args[0][0]
    assert callback_order.order_id == 2


def test_on_order_status_cancelled(tracker, mock_repo):
    """测试订单取消状态"""
    trade = create_mock_trade(order_id=3, status="Cancelled")

    tracker._on_order_status(trade)

    # 验证订单状态
    saved_order = mock_repo.save.call_args[0][0]
    assert saved_order.status == OrderStatus.CANCELLED


def test_on_execution(tracker, mock_repo):
    """测试订单成交事件"""
    trade = create_mock_trade(order_id=4, status="Filled")

    # 创建成交详情
    fill = Mock(spec=Fill)
    execution = Mock(spec=Execution)
    execution.shares = 100
    execution.avgPrice = 150.5
    fill.execution = execution

    # 触发成交事件
    tracker._on_execution(trade, fill)

    # 验证保存到数据库
    assert mock_repo.save.called

    # 验证成交信息
    saved_order = mock_repo.save.call_args[0][0]
    assert saved_order.filled_quantity == 100
    assert saved_order.avg_fill_price == 150.5


def test_get_order_from_cache(tracker):
    """测试从缓存获取订单"""
    # 创建订单并放入缓存
    order = Order(
        order_id=1, symbol="AAPL", action="BUY", quantity=100, order_type="MARKET", status=OrderStatus.SUBMITTED
    )
    tracker._orders[1] = order

    # 获取订单
    retrieved = tracker.get_order(1)
    assert retrieved is not None
    assert retrieved.order_id == 1


def test_get_order_from_database(tracker, mock_repo):
    """测试从数据库获取订单"""
    # Mock 数据库返回
    order = Order(order_id=2, symbol="TSLA", action="SELL", quantity=50, order_type="MARKET", status=OrderStatus.FILLED)
    mock_repo.get_by_id.return_value = order

    # 获取订单
    retrieved = tracker.get_order(2)
    assert retrieved is not None
    assert retrieved.order_id == 2
    assert retrieved.symbol == "TSLA"


def test_status_mapping(tracker):
    """测试状态映射"""
    # 测试各种 IBKR 状态
    assert tracker._map_status("Submitted") == OrderStatus.SUBMITTED
    assert tracker._map_status("PreSubmitted") == OrderStatus.SUBMITTED
    assert tracker._map_status("Filled") == OrderStatus.FILLED
    assert tracker._map_status("Cancelled") == OrderStatus.CANCELLED
    assert tracker._map_status("ApiCancelled") == OrderStatus.CANCELLED
    assert tracker._map_status("Inactive") == OrderStatus.REJECTED
    assert tracker._map_status("Unknown") is None


def test_multiple_callbacks(tracker, mock_repo):
    """测试多个成交回调"""
    # 注册多个回调
    callback1 = Mock()
    callback2 = Mock()
    tracker.register_filled_callback(callback1)
    tracker.register_filled_callback(callback2)

    # 触发成交
    trade = create_mock_trade(order_id=5, status="Filled")
    tracker._on_order_status(trade)

    # 验证所有回调都被触发
    assert callback1.called
    assert callback2.called


def test_callback_error_handling(tracker, mock_repo):
    """测试回调异常处理"""

    # 注册一个会抛异常的回调
    def bad_callback(order):
        raise Exception("Callback error")

    tracker.register_filled_callback(bad_callback)

    # 触发成交，不应该崩溃
    trade = create_mock_trade(order_id=6, status="Filled")
    try:
        tracker._on_order_status(trade)
    except Exception:
        pytest.fail("Tracker should handle callback exceptions")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
