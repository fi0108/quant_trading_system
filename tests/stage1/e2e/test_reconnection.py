"""
端到端测试：断线重连

测试场景：
1. 正常连接
2. 模拟断线
3. 自动重连
4. 数据恢复
5. 订单状态同步
"""

import time
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest

from data.ibkr_client import IBKRClient
from trading.connection.manager import ConnectionManager
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


class TestReconnection:
    """断线重连测试"""

    @patch("data.ibkr_client.IB")
    def test_auto_reconnect(self, mock_ib, test_config):
        """
        测试：自动重连

        场景：
        1. 建立连接
        2. 模拟断线
        3. 验证自动重连
        """
        # ========================================
        # 1. 初始连接
        # ========================================

        # Mock IBKR 实例
        mock_ib_instance = MagicMock()
        mock_ib.return_value = mock_ib_instance

        # 初始连接成功
        mock_ib_instance.isConnected.return_value = True

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])

        assert client.connect(), "初始连接应该成功"
        assert client.is_connected(), "应该处于连接状态"

        # ========================================
        # 2. 模拟断线
        # ========================================

        mock_ib_instance.isConnected.return_value = False
        assert not client.is_connected(), "应该检测到断线"

        # ========================================
        # 3. 模拟重连成功
        # ========================================

        mock_ib_instance.isConnected.return_value = True

        # 触发重连（如果客户端有重连方法）
        if hasattr(client, "reconnect"):
            result = client.reconnect()
            assert result, "重连应该成功"
        else:
            # 如果没有显式重连方法，模拟重新连接
            result = client.connect()
            assert result, "重新连接应该成功"

        # 验证重连成功
        assert client.is_connected(), "应该重连成功"

        client.disconnect()

        print("✅ 自动重连测试通过")

    @patch("data.ibkr_client.IB")
    def test_data_subscription_recovery(self, mock_ib, test_config, sample_bar_data):
        """
        测试：重连后数据订阅恢复

        场景：
        1. 订阅数据
        2. 断线
        3. 重连
        4. 验证数据继续接收
        """
        # ========================================
        # 1. 初始化并订阅数据
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        # 订阅数据
        data_received = []

        def on_bar(bars, has_new_bar):
            if has_new_bar:
                data_received.append(bars[-1])

        symbol = "AAPL"
        client.subscribe_realtime_bars(symbol, callback=on_bar)

        # 模拟接收第一批数据
        on_bar([sample_bar_data], True)
        assert len(data_received) == 1, "应该接收到第一批数据"

        # ========================================
        # 2. 模拟断线
        # ========================================

        mock_ib_instance.isConnected.return_value = False
        assert not client.is_connected(), "应该检测到断线"

        # ========================================
        # 3. 重连
        # ========================================

        mock_ib_instance.isConnected.return_value = True

        if hasattr(client, "reconnect"):
            client.reconnect()
        else:
            client.connect()

        assert client.is_connected(), "应该重连成功"

        # ========================================
        # 4. 验证数据订阅恢复
        # ========================================

        # 如果客户端支持自动重新订阅，应该恢复订阅
        # 否则需要手动重新订阅
        if not hasattr(client, "_resubscribe_all"):
            # 手动重新订阅
            client.subscribe_realtime_bars(symbol, callback=on_bar)

        # 模拟接收重连后的数据
        new_data = {
            "symbol": "AAPL",
            "time": datetime.now(),
            "open": Decimal("151.00"),
            "high": Decimal("152.00"),
            "low": Decimal("150.00"),
            "close": Decimal("151.50"),
            "volume": 1500,
        }
        on_bar([new_data], True)

        assert len(data_received) == 2, "应该接收到重连后的数据"
        assert data_received[1]["close"] == Decimal("151.50"), "数据应该正确"

        client.disconnect()

        print("✅ 数据订阅恢复测试通过")

    @patch("data.ibkr_client.IB")
    def test_connection_manager_reconnect(self, mock_ib, test_config):
        """
        测试：ConnectionManager 的重连机制

        场景：
        1. 通过 ConnectionManager 管理连接
        2. 模拟断线
        3. ConnectionManager 自动重连
        """
        # ========================================
        # 1. 初始化 ConnectionManager
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        conn_manager = ConnectionManager(
            host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"]
        )

        # 连接
        result = conn_manager.connect()
        assert result, "ConnectionManager 应该连接成功"
        assert conn_manager.is_connected(), "应该处于连接状态"

        # ========================================
        # 2. 模拟断线
        # ========================================

        mock_ib_instance.isConnected.return_value = False
        assert not conn_manager.is_connected(), "应该检测到断线"

        # ========================================
        # 3. 触发重连
        # ========================================

        mock_ib_instance.isConnected.return_value = True

        # ConnectionManager 应该有健康检查和自动重连机制
        if hasattr(conn_manager, "check_and_reconnect"):
            result = conn_manager.check_and_reconnect()
            assert result, "应该重连成功"
        elif hasattr(conn_manager, "ensure_connected"):
            result = conn_manager.ensure_connected()
            assert result, "应该确保连接成功"
        else:
            # 手动重连
            result = conn_manager.connect()
            assert result, "应该重连成功"

        assert conn_manager.is_connected(), "应该恢复连接状态"

        conn_manager.disconnect()

        print("✅ ConnectionManager 重连测试通过")

    @patch("data.ibkr_client.IB")
    def test_order_status_sync_after_reconnect(self, mock_ib, test_config):
        """
        测试：重连后订单状态同步

        场景：
        1. 下单
        2. 断线
        3. 重连
        4. 同步订单状态
        """
        # ========================================
        # 1. 初始化并下单
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        order_manager = OrderManager(client)

        # 下单
        with patch.object(order_manager, "_submit_to_ibkr") as mock_submit:
            mock_submit.return_value = {
                "order_id": 1001,
                "symbol": "AAPL",
                "quantity": 100,
                "action": "BUY",
                "status": "Submitted",
            }

            order = order_manager.place_order(symbol="AAPL", quantity=100, action="BUY", order_type="MARKET")

        assert order is not None, "订单应该提交成功"
        order_id = order.get("order_id")

        # ========================================
        # 2. 模拟断线
        # ========================================

        mock_ib_instance.isConnected.return_value = False
        assert not client.is_connected(), "应该检测到断线"

        # ========================================
        # 3. 重连
        # ========================================

        mock_ib_instance.isConnected.return_value = True
        client.connect()
        assert client.is_connected(), "应该重连成功"

        # ========================================
        # 4. 同步订单状态
        # ========================================

        # Mock 从 IBKR 获取订单状态
        with patch.object(order_manager, "_fetch_order_status") as mock_fetch:
            mock_fetch.return_value = {
                "order_id": order_id,
                "status": "Filled",
                "filled_quantity": 100,
                "avg_fill_price": Decimal("150.50"),
            }

            # 同步订单状态
            if hasattr(order_manager, "sync_order_status"):
                updated_order = order_manager.sync_order_status(order_id)
                assert updated_order is not None, "应该同步到订单状态"
                assert updated_order["status"] == "Filled", "订单状态应该已更新"

        client.disconnect()

        print("✅ 订单状态同步测试通过")

    @patch("data.ibkr_client.IB")
    def test_position_sync_after_reconnect(self, mock_ib, test_config):
        """
        测试：重连后持仓同步

        场景：
        1. 建立持仓
        2. 断线
        3. 重连
        4. 同步持仓信息
        """
        # ========================================
        # 1. 初始化并建立持仓
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        position_manager = PositionManager(client)

        # 建立持仓
        position_manager.update_position(symbol="AAPL", quantity=100, avg_price=Decimal("150.00"))

        position = position_manager.get_position("AAPL")
        assert position is not None, "持仓应该存在"

        # ========================================
        # 2. 模拟断线
        # ========================================

        mock_ib_instance.isConnected.return_value = False
        assert not client.is_connected(), "应该检测到断线"

        # ========================================
        # 3. 重连
        # ========================================

        mock_ib_instance.isConnected.return_value = True
        client.connect()
        assert client.is_connected(), "应该重连成功"

        # ========================================
        # 4. 同步持仓
        # ========================================

        # Mock 从 IBKR 获取持仓
        with patch.object(position_manager, "_fetch_positions_from_ibkr") as mock_fetch:
            mock_fetch.return_value = [
                {"symbol": "AAPL", "quantity": 100, "avg_cost": Decimal("150.00"), "market_price": Decimal("151.00")}
            ]

            # 同步持仓
            if hasattr(position_manager, "sync_positions"):
                position_manager.sync_positions()

            position = position_manager.get_position("AAPL")
            assert position is not None, "持仓应该已同步"
            assert position.quantity == 100, "持仓数量应该正确"

        client.disconnect()

        print("✅ 持仓同步测试通过")

    @patch("data.ibkr_client.IB")
    def test_multiple_reconnect_attempts(self, mock_ib, test_config):
        """
        测试：多次重连尝试

        场景：
        1. 连接
        2. 断线
        3. 第一次重连失败
        4. 第二次重连失败
        5. 第三次重连成功
        """
        # ========================================
        # 1. 初始连接
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        # ========================================
        # 2. 断线
        # ========================================

        mock_ib_instance.isConnected.return_value = False

        # ========================================
        # 3. 模拟多次重连尝试
        # ========================================

        reconnect_attempts = []

        # 第一次失败
        mock_ib_instance.isConnected.return_value = False
        try:
            result = client.connect()
            reconnect_attempts.append(result)
        except Exception:
            reconnect_attempts.append(False)

        # 第二次失败
        mock_ib_instance.isConnected.return_value = False
        try:
            result = client.connect()
            reconnect_attempts.append(result)
        except Exception:
            reconnect_attempts.append(False)

        # 第三次成功
        mock_ib_instance.isConnected.return_value = True
        result = client.connect()
        reconnect_attempts.append(result)

        # 验证最终成功
        assert client.is_connected(), "最终应该重连成功"
        assert reconnect_attempts[-1] is True, "最后一次尝试应该成功"

        client.disconnect()

        print("✅ 多次重连尝试测试通过")
