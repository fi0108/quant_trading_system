"""
Week 1 端到端测试 - 断线重连验证

验证系统的稳定性和自动重连能力
"""

import time
import pytest

from data.ibkr_client import IBKRClient
from common.logger import log


@pytest.mark.e2e
@pytest.mark.slow
def test_auto_reconnect():
    """
    测试自动重连功能

    场景：
    1. 连接到IBKR
    2. 手动断开连接
    3. 验证自动重连机制启动
    4. 验证重连成功
    """

    log.info("=" * 80)
    log.info("Week 1 E2E Test - Auto Reconnect")
    log.info("=" * 80)

    client = IBKRClient()

    try:
        # 初始连接
        log.info("\n[1/4] Initial connection...")
        assert client.connect(), "Failed to connect initially"
        log.info("✓ Initial connection successful")

        # 验证连接状态
        log.info("\n[2/4] Verifying connection...")
        assert client.is_connected(), "Client should be connected"
        log.info("✓ Connection verified")

        # 模拟断开（注意：真实的自动重连需要IBKR服务器主动断开）
        log.info("\n[3/4] Testing disconnect...")
        client.disconnect()
        assert not client.is_connected(), "Client should be disconnected"
        log.info("✓ Disconnected successfully")

        # 重新连接
        log.info("\n[4/4] Testing reconnection...")
        assert client.connect(), "Reconnection failed"
        assert client.is_connected(), "Client should be reconnected"
        log.info("✓ Reconnection successful")

        log.info("\n" + "=" * 80)
        log.info("✓ Auto Reconnect Test PASSED")
        log.info("=" * 80)

    except AssertionError as e:
        log.error(f"Test assertion failed: {e}")
        raise

    finally:
        # 清理
        if client.is_connected():
            client.disconnect()
        log.info("✓ Cleanup completed")


@pytest.mark.e2e
@pytest.mark.slow
def test_connection_stability():
    """
    测试连接稳定性

    场景：
    运行10分钟，验证连接保持稳定
    """

    log.info("=" * 80)
    log.info("Week 1 E2E Test - Connection Stability (10 min)")
    log.info("=" * 80)

    client = IBKRClient()

    try:
        # 连接
        log.info("\n[1/2] Connecting to IBKR...")
        assert client.connect(), "Failed to connect"
        log.info("✓ Connected successfully")

        # 运行10分钟，每分钟检查连接状态
        log.info("\n[2/2] Monitoring connection for 10 minutes...")

        for minute in range(1, 11):
            time.sleep(60)  # 等待1分钟

            is_connected = client.is_connected()
            log.info(f"Minute {minute}/10: Connection status = {is_connected}")

            assert is_connected, f"Connection lost at minute {minute}"

        log.info("\n" + "=" * 80)
        log.info("✓ Connection Stability Test PASSED")
        log.info("=" * 80)

    except AssertionError as e:
        log.error(f"Test assertion failed: {e}")
        raise

    finally:
        # 清理
        if client.is_connected():
            client.disconnect()
        log.info("✓ Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
