"""
订单生命周期集成测试

测试订单从创建到成交的完整流程
"""

import time
from datetime import datetime

import pytest

from common.logger import log
from common.models import OrderStatus
from data.ibkr_client import IBKRClient
from data.storage.order_repository import OrderRepository
from tests.slice2.conftest import requires_database
from trading.order.manager import OrderManager


@pytest.fixture(scope="module")
def ibkr_client():
    """IBKR 客户端"""
    client = IBKRClient()
    connected = client.connect()

    if not connected:
        pytest.skip("IBKR not connected")

    yield client

    client.disconnect()


@pytest.fixture(scope="module")
def order_manager(ibkr_client):
    """订单管理器（启用跟踪）"""
    repo = OrderRepository()
    manager = OrderManager(ibkr_client, repo, enable_tracking=True)

    yield manager

    manager.stop()


@pytest.mark.integration
@pytest.mark.slow
@requires_database
def test_market_order_lifecycle(order_manager):
    """测试市价单完整生命周期

    流程：
    1. 创建市价单
    2. 订单提交成功
    3. 等待成交
    4. 验证订单状态更新
    5. 验证数据库持久化
    """
    log.info("=" * 80)
    log.info("Integration Test: Market Order Lifecycle")
    log.info("=" * 80)

    # 1. 创建市价单（买入1股AAPL）
    log.info("\n[1/5] Creating market order...")
    order = order_manager.create_market_order(symbol="AAPL", quantity=1, action="BUY")

    assert order is not None, "Order creation failed"
    assert order.order_id > 0
    assert order.status == OrderStatus.SUBMITTED
    log.info(f"✓ Order created: ID={order.order_id}")

    # 2. 验证订单在数据库中
    log.info("\n[2/5] Verifying order persistence...")
    db_order = order_manager.get_order(order.order_id)
    assert db_order is not None
    assert db_order.order_id == order.order_id
    log.info("✓ Order persisted to database")

    # 3. 等待订单成交（市价单通常很快）
    log.info("\n[3/5] Waiting for order to fill...")
    max_wait = 30  # 最多等待30秒
    start_time = time.time()
    filled = False

    while time.time() - start_time < max_wait:
        # 重新获取订单状态
        current_order = order_manager.get_order(order.order_id)

        if current_order and current_order.status == OrderStatus.FILLED:
            filled = True
            order = current_order
            break

        time.sleep(1)

    if not filled:
        log.warning(f"Order not filled within {max_wait}s, test may be running outside market hours")
        pytest.skip("Order not filled (market may be closed)")

    log.info(f"✓ Order filled: {order.filled_quantity} shares @ ${order.avg_fill_price:.2f}")

    # 4. 验证订单状态
    log.info("\n[4/5] Verifying order status...")
    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 1
    assert order.avg_fill_price is not None
    assert order.avg_fill_price > 0
    assert order.filled_at is not None
    log.info("✓ Order status verified")

    # 5. 验证数据库更新
    log.info("\n[5/5] Verifying database update...")
    final_order = order_manager.repo.get_by_id(order.order_id)
    assert final_order is not None
    assert final_order.status == OrderStatus.FILLED
    assert final_order.filled_quantity == 1
    log.info("✓ Database updated correctly")

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


@pytest.mark.integration
@pytest.mark.slow
@requires_database
def test_limit_order_lifecycle(order_manager):
    """测试限价单完整生命周期

    流程：
    1. 创建限价单（价格设置很低，不会成交）
    2. 验证订单状态
    3. 取消订单
    4. 验证订单被取消
    """
    log.info("=" * 80)
    log.info("Integration Test: Limit Order Lifecycle")
    log.info("=" * 80)

    # 1. 创建限价单（价格设为1美元，不会成交）
    log.info("\n[1/4] Creating limit order...")
    order = order_manager.create_limit_order(
        symbol="AAPL", quantity=1, limit_price=1.0, action="BUY"  # 极低价格，不会成交
    )

    assert order is not None
    assert order.order_type == "LIMIT"
    assert order.limit_price == 1.0
    log.info(f"✓ Limit order created: ID={order.order_id}")

    # 2. 等待订单提交
    log.info("\n[2/4] Waiting for order submission...")
    time.sleep(2)

    current_order = order_manager.get_order(order.order_id)
    assert current_order is not None
    assert current_order.status == OrderStatus.SUBMITTED
    log.info("✓ Order submitted")

    # 3. 取消订单
    log.info("\n[3/4] Cancelling order...")
    result = order_manager.cancel_order(order.order_id)
    assert result is True
    log.info("✓ Order cancel requested")

    # 4. 等待取消确认
    log.info("\n[4/4] Waiting for cancellation confirmation...")
    time.sleep(3)

    cancelled_order = order_manager.get_order(order.order_id)
    assert cancelled_order is not None
    assert cancelled_order.status == OrderStatus.CANCELLED
    log.info("✓ Order cancelled")

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


@pytest.mark.integration
@requires_database
def test_order_history_query(order_manager):
    """测试订单历史查询功能

    验证：
    1. 按标的查询
    2. 按状态查询
    3. 查询所有订单
    """
    log.info("=" * 80)
    log.info("Integration Test: Order History Query")
    log.info("=" * 80)

    # 1. 查询AAPL订单
    log.info("\n[1/3] Querying AAPL orders...")
    aapl_orders = order_manager.get_orders_by_symbol("AAPL")
    log.info(f"✓ Found {len(aapl_orders)} AAPL orders")

    # 2. 查询已成交订单
    log.info("\n[2/3] Querying filled orders...")
    filled_orders = order_manager.get_orders_by_status(OrderStatus.FILLED)
    log.info(f"✓ Found {len(filled_orders)} filled orders")

    # 3. 查询所有订单
    log.info("\n[3/3] Querying all orders...")
    all_orders = order_manager.get_all_orders()
    log.info(f"✓ Found {len(all_orders)} total orders")

    assert len(all_orders) >= len(filled_orders)

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


@pytest.mark.integration
@requires_database
def test_order_filled_callback(order_manager):
    """测试订单成交回调功能

    验证：
    1. 注册回调
    2. 创建订单
    3. 等待成交
    4. 验证回调被触发
    """
    log.info("=" * 80)
    log.info("Integration Test: Order Filled Callback")
    log.info("=" * 80)

    # 回调标记
    callback_triggered = {"value": False, "order": None}

    def on_filled(order):
        """成交回调"""
        callback_triggered["value"] = True
        callback_triggered["order"] = order
        log.info(f"✓ Callback triggered for order {order.order_id}")

    # 1. 注册回调
    log.info("\n[1/3] Registering callback...")
    order_manager.register_filled_callback(on_filled)
    log.info("✓ Callback registered")

    # 2. 创建市价单
    log.info("\n[2/3] Creating market order...")
    order = order_manager.create_market_order(symbol="AAPL", quantity=1, action="BUY")

    assert order is not None
    log.info(f"✓ Order created: ID={order.order_id}")

    # 3. 等待成交和回调
    log.info("\n[3/3] Waiting for order fill and callback...")
    max_wait = 30
    start_time = time.time()

    while time.time() - start_time < max_wait:
        if callback_triggered["value"]:
            break
        time.sleep(1)

    if not callback_triggered["value"]:
        log.warning("Callback not triggered (market may be closed)")
        pytest.skip("Order not filled (market may be closed)")

    # 验证回调参数
    assert callback_triggered["order"] is not None
    assert callback_triggered["order"].order_id == order.order_id
    assert callback_triggered["order"].status == OrderStatus.FILLED
    log.info("✓ Callback triggered with correct order")

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
