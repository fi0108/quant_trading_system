"""
数据库模型单元测试
"""

from datetime import datetime
from decimal import Decimal

import pytest

from common.models import OrderStatus
from data.storage.models import BarModel, OrderModel, PositionModel, create_tables, database, drop_tables
from tests.slice2.conftest import requires_database, setup_test_database


@pytest.fixture(scope="module")
def setup_database(setup_test_database):
    """设置测试数据库"""
    # 创建表
    with database:
        create_tables()

    yield

    # 清理：删除表
    with database:
        drop_tables()

    database.close()


@pytest.fixture
def clean_tables(setup_database):
    """每个测试前清空表"""
    with database.atomic():
        OrderModel.delete().execute()
        PositionModel.delete().execute()
        BarModel.delete().execute()
    yield


@requires_database
def test_order_model_create(clean_tables):
    """测试创建订单记录"""
    order = OrderModel.create(
        order_id=12345, symbol="AAPL", action="BUY", order_type="MARKET", quantity=100, status="SUBMITTED"
    )

    assert order.id is not None
    assert order.order_id == 12345
    assert order.symbol == "AAPL"
    assert order.action == "BUY"
    assert order.status == "SUBMITTED"


def test_order_model_update(clean_tables):
    """测试更新订单状态"""
    # 创建订单
    order = OrderModel.create(
        order_id=12345, symbol="AAPL", action="BUY", order_type="MARKET", quantity=100, status="SUBMITTED"
    )

    # 更新状态
    order.status = "FILLED"
    order.filled_quantity = 100
    order.avg_fill_price = Decimal("150.50")
    order.filled_at = datetime.now()
    order.save()

    # 验证更新
    updated = OrderModel.get(OrderModel.order_id == 12345)
    assert updated.status == "FILLED"
    assert updated.filled_quantity == 100
    assert updated.avg_fill_price == Decimal("150.50")


def test_order_model_query(clean_tables):
    """测试查询订单"""
    # 创建多个订单
    OrderModel.create(order_id=1, symbol="AAPL", action="BUY", order_type="MARKET", quantity=100, status="FILLED")
    OrderModel.create(order_id=2, symbol="TSLA", action="BUY", order_type="MARKET", quantity=50, status="SUBMITTED")
    OrderModel.create(order_id=3, symbol="AAPL", action="SELL", order_type="LIMIT", quantity=50, status="FILLED")

    # 按标的查询
    aapl_orders = OrderModel.select().where(OrderModel.symbol == "AAPL")
    assert aapl_orders.count() == 2

    # 按状态查询
    filled_orders = OrderModel.select().where(OrderModel.status == "FILLED")
    assert filled_orders.count() == 2


def test_position_model_create(clean_tables):
    """测试创建持仓记录"""
    position = PositionModel.create(
        symbol="AAPL",
        quantity=100,
        avg_cost=Decimal("150.00"),
        current_price=Decimal("155.00"),
        market_value=Decimal("15500.00"),
        unrealized_pnl=Decimal("500.00"),
    )

    assert position.id is not None
    assert position.symbol == "AAPL"
    assert position.quantity == 100
    assert position.avg_cost == Decimal("150.00")


def test_position_model_update(clean_tables):
    """测试更新持仓"""
    position = PositionModel.create(symbol="AAPL", quantity=100, avg_cost=Decimal("150.00"))

    # 更新价格和盈亏
    position.current_price = Decimal("155.00")
    position.market_value = Decimal("15500.00")
    position.unrealized_pnl = Decimal("500.00")
    position.save()

    # 验证更新
    updated = PositionModel.get(PositionModel.symbol == "AAPL")
    assert updated.current_price == Decimal("155.00")
    assert updated.unrealized_pnl == Decimal("500.00")


def test_position_model_unique_symbol(clean_tables):
    """测试symbol唯一性约束"""
    PositionModel.create(symbol="AAPL", quantity=100, avg_cost=Decimal("150.00"))

    # 尝试创建重复symbol应该失败
    with pytest.raises(Exception):
        PositionModel.create(symbol="AAPL", quantity=50, avg_cost=Decimal("160.00"))


def test_bar_model_create(clean_tables):
    """测试创建K线记录"""
    bar = BarModel.create(
        symbol="AAPL",
        timestamp=datetime.now(),
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.00"),
        close=Decimal("151.00"),
        volume=1000000,
        bar_size="1min",
    )

    assert bar.id is not None
    assert bar.symbol == "AAPL"
    assert bar.volume == 1000000


def test_bar_model_unique_constraint(clean_tables):
    """测试K线唯一性约束（symbol, timestamp, bar_size）"""
    timestamp = datetime.now()

    BarModel.create(
        symbol="AAPL",
        timestamp=timestamp,
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.00"),
        close=Decimal("151.00"),
        volume=1000000,
        bar_size="1min",
    )

    # 尝试创建相同的K线应该失败
    with pytest.raises(Exception):
        BarModel.create(
            symbol="AAPL",
            timestamp=timestamp,
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=1000000,
            bar_size="1min",
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
