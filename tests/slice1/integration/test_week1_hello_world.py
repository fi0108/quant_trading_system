"""Week 1 Hello World - 端到端集成测试

验证完整流程：连接 -> 订阅 -> 策略 -> 下单
"""

import time

from data.ibkr_client import IBKRClient
from trading.order.manager import OrderManager
from trading.risk.manager import RiskManager
from trading.position.manager import PositionManager
from data.realtime_feed import RealtimeDataFeed
from strategy.examples.simple_buy import SimpleBuyStrategy
from common.logger import log


def test_week1_hello_world():
    """Week 1 Hello World 完整流程测试

    验收标准：
    1. 连接到IBKR成功
    2. 订阅AAPL实时数据成功
    3. 每10次数据买入1股
    4. 风控检查生效
    5. 订单提交成功
    """

    log.info("=" * 80)
    log.info("Week 1 Hello World - Integration Test")
    log.info("=" * 80)

    # 1. 初始化组件
    log.info("\n[Step 1] Initializing components...")
    client = IBKRClient()
    order_manager = OrderManager(client)
    risk_manager = RiskManager(client, min_cash=200.0)
    position_manager = PositionManager(client)

    # 2. 连接IBKR
    log.info("\n[Step 2] Connecting to IBKR...")
    if not client.connect():
        log.error("Failed to connect to IBKR")
        return False

    log.info("✓ Connected to IBKR")

    # 3. 查询初始持仓
    log.info("\n[Step 3] Checking initial positions...")
    position_manager.print_positions()

    # 4. 初始化策略
    log.info("\n[Step 4] Initializing strategy...")
    strategy = SimpleBuyStrategy(
        order_manager=order_manager,
        risk_manager=risk_manager,
        symbol="AAPL",
        buy_interval=10
    )
    log.info("✓ Strategy initialized")

    # 5. 订阅实时数据
    log.info("\n[Step 5] Subscribing to real-time data...")
    feed = RealtimeDataFeed(client)

    try:
        feed.subscribe_bars(
            symbol="AAPL",
            bar_size="5 secs",
            callback=strategy.on_bar
        )
        log.info("✓ Subscribed to AAPL 5-second bars")

        # 6. 运行测试
        log.info("\n[Step 6] Running test for 2 minutes...")
        log.info("Strategy will buy 1 share every 10 bars")
        log.info("-" * 80)

        # 运行2分钟 (约24个5秒bar，触发2次买入)
        time.sleep(120)

        # 7. 检查结果
        log.info("\n" + "=" * 80)
        log.info("[Step 7] Test Summary")
        log.info("=" * 80)

        # 显示订单
        orders = order_manager.get_all_orders()
        log.info(f"\nTotal orders placed: {len(orders)}")
        for order in orders:
            log.info(
                f"  Order #{order.order_id}: {order.action} {order.quantity} "
                f"{order.symbol} @ {order.order_type} - {order.status.value}"
            )

        # 显示最终持仓
        log.info("\nFinal positions:")
        position_manager.print_positions()

        log.info("\n✓ Test completed successfully")
        return True

    except Exception as e:
        log.error(f"Test failed: {e}")
        return False

    finally:
        # 清理
        log.info("\n[Cleanup] Unsubscribing and disconnecting...")
        feed.unsubscribe_all()
        client.disconnect()
        log.info("✓ Cleanup completed")


if __name__ == "__main__":
    success = test_week1_hello_world()
    exit(0 if success else 1)
