"""
订单仓库单元测试
"""

import pytest
from datetime import datetime

from data.storage.models import init_database, create_tables, drop_tables, database
from data.storage.order_repository import OrderRepository
from common.models import Order, OrderStatus


@pytest.fixture(scope='module')
def setup_database():
    """设置测试数据库"""
    database.init('test_quant_trading', host='localhost', user='postgres', password='')
    with database:
        create_tables()
    yield
    with database:
        drop_tables()
    database.close()


@pytest.fixture
def clean_orders(setup_database):
    """每个测试前清空订单表"""
    from data.storage.models import OrderModel
    with database.atomic():
        OrderModel.delete().execute()
    yield


def test_save_order(clean_orders):
    """测试保存订单"""
    order = Order(
        order_id=12345,
        symbol='AAPL',
        action='BUY',
        order_type='MARKET',
        quantity=100,
        status=OrderStatus.SUBMITTED
    )

    result = OrderRepository.save(order)

    assert result is True

    # 验证保存成功
    retrieved = OrderRepository.get_by_id(12345)
    assert retrieved is not None
    assert retrieved.symbol == 'AAPL'
    assert retrieved.quantity == 100


def test_update_order(clean_orders):
    """测试更新订单"""
    # 先保存订单
    order = Order(
        order_id=12345,
        symbol='AAPL',
        action='BUY',
        order_type='MARKET',
        quantity=100,
        status=OrderStatus.SUBMITTED
    )
    OrderRepository.save(order)

    # 更新状态
    order.status = OrderStatus.FILLED
    order.filled_quantity = 100
    order.avg_fill_price = 150.50
    order.filled_at = datetime.now()

    result = OrderRepository.update(order)

    assert result is True

    # 验证更新成功
    retrieved = OrderRepository.get_by_id(12345)
    assert retrieved.status == OrderStatus.FILLED
    assert retrieved.filled_quantity == 100
    assert retrieved.avg_fill_price == 150.50


def test_get_by_id(clean_orders):
    """测试根据ID查询订单"""
    order = Order(
        order_id=12345,
        symbol='AAPL',
        action='BUY',
        order_type='MARKET',
        quantity=100,
        status=OrderStatus.SUBMITTED
    )
    OrderRepository.save(order)

    # 查询存在的订单
    retrieved = OrderRepository.get_by_id(12345)
    assert retrieved is not None
    assert retrieved.order_id == 12345

    # 查询不存在的订单
    not_found = OrderRepository.get_by_id(99999)
    assert not_found is None


def test_get_all_orders(clean_orders):
    """测试获取所有订单"""
    # 创建多个订单
    for i in range(5):
        order = Order(
            order_id=10000 + i,
            symbol='AAPL',
            action='BUY',
            order_type='MARKET',
            quantity=100,
            status=OrderStatus.SUBMITTED
        )
        OrderRepository.save(order)

    # 获取所有订单
    orders = OrderRepository.get_all()

    assert len(orders) == 5


def test_get_by_symbol(clean_orders):
    """测试按标的查询订单"""
    # 创建不同标的的订单
    OrderRepository.save(Order(
        order_id=1, symbol='AAPL', action='BUY',
        order_type='MARKET', quantity=100, status=OrderStatus.SUBMITTED
    ))
    OrderRepository.save(Order(
        order_id=2, symbol='TSLA', action='BUY',
        order_type='MARKET', quantity=50, status=OrderStatus.SUBMITTED
    ))
    OrderRepository.save(Order(
        order_id=3, symbol='AAPL', action='SELL',
        order_type='MARKET', quantity=50, status=OrderStatus.FILLED
    ))

    # 查询AAPL订单
    aapl_orders = OrderRepository.get_by_symbol('AAPL')
    assert len(aapl_orders) == 2
    assert all(o.symbol == 'AAPL' for o in aapl_orders)


def test_get_by_status(clean_orders):
    """测试按状态查询订单"""
    # 创建不同状态的订单
    OrderRepository.save(Order(
        order_id=1, symbol='AAPL', action='BUY',
        order_type='MARKET', quantity=100, status=OrderStatus.SUBMITTED
    ))
    OrderRepository.save(Order(
        order_id=2, symbol='TSLA', action='BUY',
        order_type='MARKET', quantity=50, status=OrderStatus.FILLED
    ))
    OrderRepository.save(Order(
        order_id=3, symbol='GOOGL', action='BUY',
        order_type='MARKET', quantity=10, status=OrderStatus.FILLED
    ))

    # 查询FILLED状态的订单
    filled_orders = OrderRepository.get_by_status(OrderStatus.FILLED)
    assert len(filled_orders) == 2
    assert all(o.status == OrderStatus.FILLED for o in filled_orders)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
