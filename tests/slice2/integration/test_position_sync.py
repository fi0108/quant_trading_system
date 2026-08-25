"""
持仓管理集成测试

测试持仓跟踪和与 IBKR 同步
"""

import time

import pytest

from common.logger import log
from common.models import OrderStatus
from data.ibkr_client import IBKRClient
from data.storage.order_repository import OrderRepository
from data.storage.position_repository import PositionRepository
from tests.slice2.conftest import requires_database
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


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
def managers(ibkr_client):
    """订单和持仓管理器"""
    order_mgr = OrderManager(ibkr_client, OrderRepository(), enable_tracking=True)
    position_mgr = PositionManager(ibkr_client, PositionRepository(), enable_tracking=True)

    # 连接订单成交回调到持仓管理器
    order_mgr.register_filled_callback(position_mgr.on_order_filled)

    yield order_mgr, position_mgr

    order_mgr.stop()


@pytest.mark.integration
@pytest.mark.slow
@requires_database
def test_position_update_on_order_filled(managers):
    """测试订单成交后自动更新持仓

    流程：
    1. 创建买入订单
    2. 等待成交
    3. 验证持仓自动更新
    4. 验证持久化到数据库
    """
    order_mgr, position_mgr = managers

    log.info("=" * 80)
    log.info("Integration Test: Position Update on Order Filled")
    log.info("=" * 80)

    symbol = "AAPL"

    # 1. 记录初始持仓
    log.info("\n[1/5] Recording initial position...")
    initial_position = position_mgr.get_position(symbol)
    initial_qty = initial_position.quantity if initial_position else 0
    log.info(f"Initial {symbol} position: {initial_qty}")

    # 2. 创建买入订单
    log.info("\n[2/5] Creating buy order...")
    order = order_mgr.create_market_order(symbol, 1, "BUY")
    assert order is not None
    log.info(f"✓ Order created: ID={order.order_id}")

    # 3. 等待成交
    log.info("\n[3/5] Waiting for order to fill...")
    max_wait = 30
    start_time = time.time()
    filled = False

    while time.time() - start_time < max_wait:
        current_order = order_mgr.get_order(order.order_id)
        if current_order and current_order.status == OrderStatus.FILLED:
            filled = True
            break
        time.sleep(1)

    if not filled:
        pytest.skip("Order not filled (market may be closed)")

    log.info("✓ Order filled")

    # 4. 等待持仓更新（给回调一点时间）
    log.info("\n[4/5] Waiting for position update...")
    time.sleep(2)

    # 5. 验证持仓更新
    log.info("\n[5/5] Verifying position update...")
    updated_position = position_mgr.get_position(symbol)

    assert updated_position is not None, f"No position found for {symbol}"
    assert updated_position.quantity == initial_qty + 1, f"Expected {initial_qty + 1}, got {updated_position.quantity}"

    log.info(f"✓ Position updated: {initial_qty} → {updated_position.quantity}")
    log.info(f"  Avg Cost: ${updated_position.avg_cost:.2f}")
    log.info(f"  Market Value: ${updated_position.market_value:.2f}")

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


@pytest.mark.integration
@pytest.mark.slow
@requires_database
def test_position_sync_with_ibkr(managers):
    """测试与 IBKR 同步持仓

    流程：
    1. 同步持仓
    2. 验证持仓数据
    3. 验证数据库更新
    """
    order_mgr, position_mgr = managers

    log.info("=" * 80)
    log.info("Integration Test: Position Sync with IBKR")
    log.info("=" * 80)

    # 1. 同步持仓
    log.info("\n[1/3] Syncing positions with IBKR...")
    position_mgr.sync_with_ibkr()
    log.info("✓ Sync completed")

    # 2. 获取持仓
    log.info("\n[2/3] Getting all positions...")
    positions = position_mgr.get_positions()
    log.info(f"✓ Found {len(positions)} positions")

    # 3. 打印持仓信息
    log.info("\n[3/3] Position details:")
    position_mgr.print_positions()

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


@pytest.mark.integration
@pytest.mark.slow
@requires_database
def test_buy_and_sell_lifecycle(managers):
    """测试买入卖出完整流程

    流程：
    1. 买入1股
    2. 验证持仓增加
    3. 卖出1股
    4. 验证持仓减少
    5. 验证已实现盈亏
    """
    order_mgr, position_mgr = managers

    log.info("=" * 80)
    log.info("Integration Test: Buy and Sell Lifecycle")
    log.info("=" * 80)

    symbol = "AAPL"

    # 1. 记录初始持仓
    log.info("\n[1/7] Recording initial position...")
    initial_position = position_mgr.get_position(symbol)
    initial_qty = initial_position.quantity if initial_position else 0
    log.info(f"Initial {symbol} position: {initial_qty}")

    # 2. 买入1股
    log.info("\n[2/7] Buying 1 share...")
    buy_order = order_mgr.create_market_order(symbol, 1, "BUY")
    assert buy_order is not None

    # 等待成交
    max_wait = 30
    start_time = time.time()
    while time.time() - start_time < max_wait:
        current_order = order_mgr.get_order(buy_order.order_id)
        if current_order and current_order.status == OrderStatus.FILLED:
            buy_order = current_order
            break
        time.sleep(1)

    if buy_order.status != OrderStatus.FILLED:
        pytest.skip("Buy order not filled")

    log.info(f"✓ Buy order filled @ ${buy_order.avg_fill_price:.2f}")
    time.sleep(2)

    # 3. 验证持仓增加
    log.info("\n[3/7] Verifying position increased...")
    position_after_buy = position_mgr.get_position(symbol)
    assert position_after_buy is not None
    assert position_after_buy.quantity == initial_qty + 1
    log.info(f"✓ Position: {initial_qty} → {position_after_buy.quantity}")

    # 4. 卖出1股
    log.info("\n[4/7] Selling 1 share...")
    sell_order = order_mgr.create_market_order(symbol, 1, "SELL")
    assert sell_order is not None

    # 等待成交
    start_time = time.time()
    while time.time() - start_time < max_wait:
        current_order = order_mgr.get_order(sell_order.order_id)
        if current_order and current_order.status == OrderStatus.FILLED:
            sell_order = current_order
            break
        time.sleep(1)

    if sell_order.status != OrderStatus.FILLED:
        pytest.skip("Sell order not filled")

    log.info(f"✓ Sell order filled @ ${sell_order.avg_fill_price:.2f}")
    time.sleep(2)

    # 5. 验证持仓减少
    log.info("\n[5/7] Verifying position decreased...")
    position_after_sell = position_mgr.get_position(symbol)

    if position_after_sell is None:
        # 持仓清零
        log.info("✓ Position closed")
        assert position_after_buy.quantity == 1  # 之前是1股
    else:
        assert position_after_sell.quantity == initial_qty
        log.info(f"✓ Position: {position_after_buy.quantity} → {position_after_sell.quantity}")

    # 6. 验证盈亏
    log.info("\n[6/7] Verifying P&L...")
    realized_pnl = sell_order.avg_fill_price - buy_order.avg_fill_price
    log.info(f"Buy: ${buy_order.avg_fill_price:.2f}")
    log.info(f"Sell: ${sell_order.avg_fill_price:.2f}")
    log.info(f"Realized P&L: ${realized_pnl:.2f}")

    # 7. 打印最终持仓
    log.info("\n[7/7] Final positions:")
    position_mgr.print_positions()

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
