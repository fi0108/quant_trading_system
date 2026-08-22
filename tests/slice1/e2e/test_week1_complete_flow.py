"""
Week 1 端到端测试 - 完整流程验证

验证 Hello World 的完整业务场景
"""

import time
import pytest

from data.ibkr_client import IBKRClient
from trading.order.manager import OrderManager
from trading.risk.manager import RiskManager
from trading.position.manager import PositionManager
from data.realtime_feed import RealtimeDataFeed
from strategy.examples.simple_buy import SimpleBuyStrategy
from common.logger import log


@pytest.mark.e2e
@pytest.mark.slow
def test_week1_complete_flow():
    """
    Week 1 Hello World 完整流程测试

    验收标准：
    1. 连接到IBKR成功
    2. 订阅AAPL实时数据成功
    3. 每10次数据买入1股
    4. 风控检查生效
    5. 订单提交成功
    6. 运行2分钟无异常
    """

    log.info("=" * 80)
    log.info("Week 1 E2E Test - Complete Flow")
    log.info("=" * 80)

    # 初始化组件
    log.info("\n[1/7] Initializing components...")
    client = IBKRClient()
    order_manager = OrderManager(client)
    risk_manager = RiskManager(client, min_cash=200.0)
    position_manager = PositionManager(client)

    try:
        # 连接IBKR
        log.info("\n[2/7] Connecting to IBKR...")
        assert client.connect(), "Failed to connect to IBKR"
        log.info("✓ Connected to IBKR successfully")

        # 查询初始持仓
        log.info("\n[3/7] Checking initial positions...")
        initial_positions = position_manager.get_positions()
        log.info(f"Initial positions: {len(initial_positions)}")

        # 初始化策略
        log.info("\n[4/7] Initializing strategy...")
        strategy = SimpleBuyStrategy(
            order_manager=order_manager,
            risk_manager=risk_manager,
            symbol="AAPL",
            buy_interval=10
        )
        log.info("✓ Strategy initialized")

        # 订阅实时数据
        log.info("\n[5/7] Subscribing to real-time data...")
        feed = RealtimeDataFeed(client)

        success = feed.subscribe_bars(
            symbol="AAPL",
            bar_size="5 secs",
            callback=strategy.on_bar
        )
        assert success, "Failed to subscribe to real-time data"
        log.info("✓ Subscribed to AAPL 5-second bars")

        # 运行测试
        log.info("\n[6/7] Running test for 2 minutes...")
        log.info("Strategy will buy 1 share every 10 bars")
        log.info("-" * 80)

        # 运行2分钟 (约24个5秒bar，触发2次买入)
        time.sleep(120)

        # 检查结果
        log.info("\n[7/7] Checking results...")
        log.info("=" * 80)

        # 验证订单
        orders = order_manager.get_all_orders()
        log.info(f"Total orders placed: {len(orders)}")

        for order in orders:
            log.info(
                f"  Order #{order.order_id}: {order.action} {order.quantity} "
                f"{order.symbol} @ {order.order_type} - {order.status.value}"
            )

        # 验证至少有订单被创建
        assert len(orders) >= 1, "Expected at least 1 order to be placed"

        # 显示最终持仓
        final_positions = position_manager.get_positions()
        log.info(f"\nFinal positions: {len(final_positions)}")
        position_manager.print_positions()

        log.info("\n" + "=" * 80)
        log.info("✓ E2E Test PASSED")
        log.info("=" * 80)

    except AssertionError as e:
        log.error(f"Test assertion failed: {e}")
        raise

    except Exception as e:
        log.error(f"Test failed with exception: {e}")
        raise

    finally:
        # 清理
        log.info("\n[Cleanup] Unsubscribing and disconnecting...")
        if 'feed' in locals():
            feed.unsubscribe_all()
        if client.is_connected():
            client.disconnect()
        log.info("✓ Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
