"""
持仓跟踪器单元测试
"""

from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest
from ib_insync import IB

from common.models import Order, OrderStatus, Position
from data.storage.position_repository import PositionRepository
from trading.position.tracker import PositionTracker


@pytest.fixture
def mock_ib():
    """Mock IBKR 连接"""
    return Mock(spec=IB)


@pytest.fixture
def mock_repo():
    """Mock 持仓仓库"""
    repo = Mock(spec=PositionRepository)
    repo.get_all = Mock(return_value=[])
    repo.save_or_update = Mock(return_value=True)
    repo.delete = Mock(return_value=True)
    repo.get_by_symbol = Mock(return_value=None)
    return repo


@pytest.fixture
def tracker(mock_ib, mock_repo):
    """创建持仓跟踪器"""
    return PositionTracker(mock_ib, mock_repo)


def create_order(order_id, symbol, action, quantity, price):
    """创建测试订单"""
    return Order(
        order_id=order_id,
        symbol=symbol,
        action=action,
        quantity=quantity,
        order_type="MARKET",
        status=OrderStatus.FILLED,
        filled_quantity=quantity,
        avg_fill_price=price,
    )


def test_handle_buy_new_position(tracker, mock_repo):
    """测试买入创建新持仓"""
    order = create_order(1, "AAPL", "BUY", 100, 150.0)

    tracker.on_order_filled(order)

    # 验证保存到数据库
    assert mock_repo.save_or_update.called
    saved_position = mock_repo.save_or_update.call_args[0][0]

    assert saved_position.symbol == "AAPL"
    assert saved_position.quantity == 100
    assert saved_position.avg_cost == 150.0
    assert saved_position.market_value == 15000.0
    assert saved_position.unrealized_pnl == 0.0


def test_handle_buy_increase_position(tracker, mock_repo):
    """测试买入增加持仓"""
    # 先创建初始持仓
    initial_position = Position(symbol="AAPL", quantity=100.0, avg_cost=150.0, market_value=15000.0, unrealized_pnl=0.0)
    tracker._positions["AAPL"] = initial_position

    # 再次买入
    order = create_order(2, "AAPL", "BUY", 50, 160.0)
    tracker.on_order_filled(order)

    # 验证持仓更新
    position = tracker._positions["AAPL"]
    assert position.quantity == 150.0  # 100 + 50
    assert position.avg_cost == pytest.approx(153.33, 0.01)  # (100*150 + 50*160) / 150


def test_handle_sell_partial(tracker, mock_repo):
    """测试部分卖出"""
    # 创建初始持仓
    initial_position = Position(
        symbol="TSLA", quantity=100.0, avg_cost=200.0, market_value=20000.0, unrealized_pnl=0.0, realized_pnl=0.0
    )
    tracker._positions["TSLA"] = initial_position

    # 卖出50股
    order = create_order(3, "TSLA", "SELL", 50, 210.0)
    tracker.on_order_filled(order)

    # 验证持仓更新
    position = tracker._positions["TSLA"]
    assert position.quantity == 50.0  # 100 - 50
    assert position.avg_cost == 200.0  # 平均成本不变
    assert position.realized_pnl == 500.0  # 50 * (210 - 200)


def test_handle_sell_close_position(tracker, mock_repo):
    """测试卖出清仓"""
    # 创建初始持仓
    initial_position = Position(
        symbol="GOOGL", quantity=100.0, avg_cost=2500.0, market_value=250000.0, unrealized_pnl=0.0, realized_pnl=0.0
    )
    tracker._positions["GOOGL"] = initial_position

    # 全部卖出
    order = create_order(4, "GOOGL", "SELL", 100, 2600.0)
    tracker.on_order_filled(order)

    # 验证持仓被清空
    assert "GOOGL" not in tracker._positions

    # 验证数据库删除被调用
    assert mock_repo.delete.called


def test_handle_sell_without_position(tracker, mock_repo):
    """测试卖出时没有持仓"""
    order = create_order(5, "MSFT", "SELL", 100, 300.0)

    # 不应该抛异常
    tracker.on_order_filled(order)

    # 不应该保存
    assert not mock_repo.save_or_update.called


def test_get_position(tracker):
    """测试获取持仓"""
    position = Position(symbol="AMZN", quantity=10.0, avg_cost=3000.0, market_value=30000.0, unrealized_pnl=0.0)
    tracker._positions["AMZN"] = position

    retrieved = tracker.get_position("AMZN")
    assert retrieved is not None
    assert retrieved.symbol == "AMZN"


def test_get_all_positions(tracker):
    """测试获取所有持仓"""
    pos1 = Position("AAPL", 100.0, 150.0, 15000.0, 0.0)
    pos2 = Position("TSLA", 50.0, 200.0, 10000.0, 0.0)

    tracker._positions["AAPL"] = pos1
    tracker._positions["TSLA"] = pos2

    positions = tracker.get_all_positions()
    assert len(positions) == 2


def test_get_total_market_value(tracker):
    """测试获取总市值"""
    pos1 = Position("AAPL", 100.0, 150.0, 15000.0, 0.0)
    pos2 = Position("TSLA", 50.0, 200.0, 10000.0, 0.0)

    tracker._positions["AAPL"] = pos1
    tracker._positions["TSLA"] = pos2

    total = tracker.get_total_market_value()
    assert total == 25000.0


def test_get_total_pnl(tracker):
    """测试获取总盈亏"""
    pos1 = Position("AAPL", 100.0, 150.0, 16000.0, 1000.0, realized_pnl=500.0)
    pos2 = Position("TSLA", 50.0, 200.0, 9000.0, -1000.0, realized_pnl=300.0)

    tracker._positions["AAPL"] = pos1
    tracker._positions["TSLA"] = pos2

    unrealized = tracker.get_total_unrealized_pnl()
    realized = tracker.get_total_realized_pnl()

    assert unrealized == 0.0  # 1000 + (-1000)
    assert realized == 800.0  # 500 + 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
