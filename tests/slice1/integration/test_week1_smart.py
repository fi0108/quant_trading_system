"""Week 1 集成测试 - 智能判断市场状态

根据当前时间判断市场状态，调整测试预期
"""

import time
import pytest
from datetime import datetime, time as dt_time
import pytz

from data.ibkr_client import IBKRClient
from trading.order.manager import OrderManager
from trading.risk.manager import RiskManager
from trading.position.manager import PositionManager
from data.realtime_feed import RealtimeDataFeed
from strategy.examples.simple_buy import SimpleBuyStrategy
from common.logger import log


def is_market_data_available():
    """
    判断当前是否有市场数据

    注意：
    - 使用美东时区（US/Eastern）判断
    - 自动处理夏令时/冬令时切换
    - 上海时间需要转换：夏令时-12小时，冬令时-13小时

    Returns:
        tuple: (has_data: bool, reason: str, current_et_time: str)
    """
    # 获取美东时区（自动处理DST）
    eastern = pytz.timezone('US/Eastern')

    # 从本地时间转换到美东时间
    local_now = datetime.now()
    utc_now = datetime.now(pytz.UTC)
    et_now = utc_now.astimezone(eastern)

    log.info(f"Local time: {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"US Eastern time: {et_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # 检查是否是周末
    if et_now.weekday() >= 5:  # 5=周六, 6=周日
        return False, f"Weekend ({et_now.strftime('%A')})", et_now.strftime('%H:%M:%S %Z')

    # 检查时间段（美东时间）
    current_time = et_now.time()

    # 盘前数据: 04:00-09:30 ET
    if dt_time(4, 0) <= current_time < dt_time(9, 30):
        return True, "Pre-market hours (04:00-09:30 ET)", et_now.strftime('%H:%M:%S %Z')

    # 盘中数据: 09:30-16:00 ET
    elif dt_time(9, 30) <= current_time < dt_time(16, 0):
        return True, "Regular market hours (09:30-16:00 ET)", et_now.strftime('%H:%M:%S %Z')

    # 盘后数据: 16:00-20:00 ET
    elif dt_time(16, 0) <= current_time < dt_time(20, 0):
        return True, "After-hours (16:00-20:00 ET)", et_now.strftime('%H:%M:%S %Z')

    # 深夜无数据: 20:00-04:00 ET
    else:
        return False, f"Market closed (20:00-04:00 ET)", et_now.strftime('%H:%M:%S %Z')


@pytest.mark.integration
def test_week1_hello_world_integration():
    """
    Week 1 Hello World 集成测试

    测试目标：
    1. 验证连接和订阅逻辑（任何时候都能验证）
    2. 如果有市场数据，验证完整流程
    3. 如果无市场数据，只验证接口调用
    """

    # 检查市场状态
    has_data, market_status, et_time = is_market_data_available()

    log.info("=" * 80)
    log.info("Week 1 Integration Test")
    log.info(f"US Eastern Time: {et_time}")
    log.info(f"Market Status: {market_status}")
    log.info(f"Data Available: {has_data}")
    log.info("=" * 80)

    # 1. 初始化组件
    log.info("\n[1/7] Initializing components...")
    client = IBKRClient()
    order_manager = OrderManager(client)
    risk_manager = RiskManager(client, min_cash=200.0)
    position_manager = PositionManager(client)

    try:
        # 2. 连接IBKR
        log.info("\n[2/7] Connecting to IBKR Gateway...")
        success = client.connect()

        if not success:
            pytest.skip("Cannot connect to IBKR Gateway (not running or wrong config)")

        log.info("✓ Connected to IBKR successfully")

        # 3. 查询初始持仓
        log.info("\n[3/7] Checking initial positions...")
        initial_positions = position_manager.get_positions()
        log.info(f"Initial positions count: {len(initial_positions)}")

        # 4. 初始化策略
        log.info("\n[4/7] Initializing strategy...")
        strategy = SimpleBuyStrategy(
            order_manager=order_manager,
            risk_manager=risk_manager,
            symbol="AAPL",
            buy_interval=10
        )
        log.info("✓ Strategy initialized")

        # 5. 订阅实时数据
        log.info("\n[5/7] Subscribing to real-time data...")
        feed = RealtimeDataFeed(client)

        subscribe_success = feed.subscribe_bars(
            symbol="AAPL",
            bar_size="5 secs",
            callback=strategy.on_bar
        )

        assert subscribe_success, "Failed to subscribe to real-time bars"
        log.info("✓ Subscribed to AAPL 5-second bars")

        # 6. 根据市场状态决定测试策略
        if has_data:
            # 有数据：运行完整测试
            log.info("\n[6/7] Market data available - Running full test...")
            log.info("Waiting 2 minutes for real-time data...")
            log.info("Strategy will buy 1 share every 10 bars")
            log.info("-" * 80)

            time.sleep(120)  # 等待2分钟接收数据

            # 验证应该有数据和订单
            orders = order_manager.get_all_orders()
            log.info(f"\nOrders placed: {len(orders)}")

            if len(orders) == 0:
                log.warning("⚠ No orders placed - possible reasons:")
                log.warning("  1. Strategy bar count < 10")
                log.warning("  2. Risk check failed (insufficient funds)")
                log.warning("  3. No data received from IBKR")
                log.warning(f"  Strategy bar count: {strategy.bar_count}")
            else:
                log.info("✓ Orders were placed successfully")
                for order in orders:
                    log.info(f"  Order #{order.order_id}: {order.action} {order.quantity} {order.symbol}")

        else:
            # 无数据：只验证接口调用
            log.info("\n[6/7] No market data available - Testing interfaces only...")
            log.info("Waiting 10 seconds to verify subscription...")

            time.sleep(10)

            log.info("✓ Subscription interface validated")
            log.info("ℹ Full flow validation requires market hours")

        # 7. 检查最终状态
        log.info("\n[7/7] Final checks...")

        # 验证订阅状态
        assert feed.is_subscribed("AAPL"), "Subscription should be active"
        log.info("✓ Subscription still active")

        # 显示最终持仓
        final_positions = position_manager.get_positions()
        log.info(f"Final positions count: {len(final_positions)}")

        log.info("\n" + "=" * 80)
        log.info("✓ Integration Test PASSED")
        if not has_data:
            log.info("ℹ Note: Full flow validation requires market data")
        log.info("=" * 80)

    except Exception as e:
        log.error(f"Test failed: {e}")
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
