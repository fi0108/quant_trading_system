"""
断线重连集成测试

测试自动重连功能
"""

import time

import pytest

from common.logger import log
from data.ibkr_client import IBKRClient
from trading.connection.manager import ConnectionManager


@pytest.fixture(scope="module")
def connection_manager():
    """连接管理器"""
    mgr = ConnectionManager.from_config()
    mgr.auto_reconnect = True

    yield mgr

    mgr.disconnect()


@pytest.mark.integration
@pytest.mark.slow
def test_initial_connection(connection_manager):
    """测试初始连接

    验证：
    1. 能够成功连接到 IBKR
    2. 连接状态正确
    """
    log.info("=" * 80)
    log.info("Integration Test: Initial Connection")
    log.info("=" * 80)

    log.info("\n[1/2] Connecting to IBKR...")
    success = connection_manager.connect()

    if not success:
        pytest.skip("IBKR not available")

    assert connection_manager.is_connected()
    log.info("✓ Connected successfully")

    log.info("\n[2/2] Checking status...")
    status = connection_manager.get_status()
    assert status["is_connected"] is True
    log.info(f"✓ Status: {status}")

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.manual
def test_manual_reconnect():
    """手动测试断线重连

    需要手动操作：
    1. 启动测试
    2. 等待连接成功
    3. 手动关闭 IBKR Gateway
    4. 等待自动重连
    5. 重新启动 IBKR Gateway
    6. 验证重连成功

    注意：这个测试需要手动执行，用 pytest -m manual 运行
    """
    log.info("=" * 80)
    log.info("Manual Test: Auto Reconnect")
    log.info("=" * 80)

    # 使用一个空闲的 client_id（从 10 开始）
    mgr = ConnectionManager(host="127.0.0.1", port=4002, client_id=10, auto_reconnect=True)  # 使用 10，避免冲突

    # 记录事件
    events = []

    def on_connected():
        events.append(("connected", time.time()))
        log.info("✓ Connected event")

    def on_disconnected():
        events.append(("disconnected", time.time()))
        log.warning("⚠ Disconnected event")

    def on_reconnecting():
        events.append(("reconnecting", time.time()))
        log.info("🔄 Reconnecting event")

    mgr.register_connected_callback(on_connected)
    mgr.register_disconnected_callback(on_disconnected)
    mgr.register_reconnecting_callback(on_reconnecting)

    # 1. 初始连接
    log.info("\n[1/4] Initial connection...")
    success = mgr.connect()
    assert success
    log.info("✓ Connected")

    # 2. 等待稳定
    log.info("\n[2/4] Waiting for stable connection (10s)...")
    time.sleep(10)
    assert mgr.is_connected()
    log.info("✓ Connection stable")

    # 3. 提示用户操作
    log.info("\n[3/4] Manual step: Close IBKR Gateway NOW")
    log.info("      Waiting 60s for disconnection and reconnect attempts...")

    # 等待断开和重连
    timeout = 60
    start_time = time.time()
    disconnected = False
    reconnected = False

    while time.time() - start_time < timeout:
        if not mgr.is_connected() and not disconnected:
            log.warning("⚠ Disconnection detected")
            disconnected = True

        if disconnected and mgr.is_connected() and not reconnected:
            log.info("✓ Reconnection detected")
            reconnected = True
            break

        time.sleep(1)

    # 4. 验证事件
    log.info("\n[4/4] Event history:")
    for event_type, timestamp in events:
        log.info(f"  - {event_type} at {timestamp:.0f}")

    # 断言至少发生了断开
    assert disconnected, "Expected disconnection event"

    if reconnected:
        log.info("\n✓ Auto-reconnect successful")
    else:
        log.warning("\n⚠ Auto-reconnect not completed (Gateway may not have been restarted)")

    log.info("\n" + "=" * 80)
    log.info("Manual Test COMPLETED")
    log.info("=" * 80)

    mgr.disconnect()


@pytest.mark.integration
def test_connection_status_monitoring(connection_manager):
    """测试连接状态监控

    验证：
    1. 能够获取连接状态
    2. 状态信息完整
    """
    log.info("=" * 80)
    log.info("Integration Test: Connection Status Monitoring")
    log.info("=" * 80)

    log.info("\n[1/2] Connecting...")
    if not connection_manager.is_connected():
        success = connection_manager.connect()
        if not success:
            pytest.skip("IBKR not available")

    log.info("\n[2/2] Getting status...")
    status = connection_manager.get_status()

    # 验证状态字段
    required_fields = ["is_connected", "host", "port", "client_id", "reconnect_attempts", "auto_reconnect"]

    for field in required_fields:
        assert field in status, f"Missing field: {field}"
        log.info(f"  {field}: {status[field]}")

    log.info("\n" + "=" * 80)
    log.info("Integration Test PASSED")
    log.info("=" * 80)


if __name__ == "__main__":
    # 默认跳过手动测试
    pytest.main([__file__, "-v", "-s", "-m", "not manual"])
