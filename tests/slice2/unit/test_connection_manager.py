"""
连接管理器单元测试
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from ib_insync import IB

from trading.connection.manager import ConnectionManager
from trading.connection.reconnect import ReconnectStrategy


@pytest.fixture
def mock_ib():
    """Mock IBKR 连接"""
    ib = Mock(spec=IB)
    ib.isConnected = Mock(return_value=False)
    ib.connect = Mock()
    ib.disconnect = Mock()
    ib.connectedEvent = MagicMock()
    ib.disconnectedEvent = MagicMock()
    ib.errorEvent = MagicMock()
    return ib


@pytest.fixture
def manager(mock_ib):
    """创建连接管理器"""
    with patch("trading.connection.manager.IB", return_value=mock_ib):
        mgr = ConnectionManager(host="127.0.0.1", port=4002, client_id=1, auto_reconnect=False)  # 测试时禁用自动重连
        mgr.ib = mock_ib
        return mgr


def test_manager_initialization(manager):
    """测试管理器初始化"""
    assert manager.host == "127.0.0.1"
    assert manager.port == 4002
    assert manager.client_id == 1
    assert not manager.is_connected()


def test_connect_success(manager, mock_ib):
    """测试连接成功"""
    mock_ib.isConnected.return_value = True

    result = manager.connect()

    assert result is True
    assert mock_ib.connect.called


def test_connect_already_connected(manager):
    """测试已连接时再次连接"""
    manager._is_connected = True
    manager.ib.isConnected.return_value = True

    result = manager.connect()

    assert result is True
    # 不应该再次调用connect
    assert not manager.ib.connect.called


def test_connect_failure(manager, mock_ib):
    """测试连接失败"""
    mock_ib.connect.side_effect = Exception("Connection failed")

    result = manager.connect()

    assert result is False
    assert not manager.is_connected()


def test_disconnect(manager):
    """测试断开连接"""
    manager._is_connected = True
    manager.ib.isConnected.return_value = True

    manager.disconnect()

    assert manager.ib.disconnect.called
    assert not manager.is_connected()


def test_register_connected_callback(manager):
    """测试注册连接回调"""
    callback = Mock()
    manager.register_connected_callback(callback)

    # 模拟连接事件
    manager._on_ib_connected()

    assert callback.called


def test_register_disconnected_callback(manager):
    """测试注册断开回调"""
    callback = Mock()
    manager.register_disconnected_callback(callback)

    # 模拟断开事件
    manager._is_connected = True
    manager._on_ib_disconnected()

    assert callback.called


def test_heartbeat_update_on_connect(manager):
    """测试连接后心跳更新"""
    before = datetime.now()
    manager._on_ib_connected()
    after = datetime.now()

    assert manager._last_heartbeat is not None
    assert before <= manager._last_heartbeat <= after


def test_reconnect_strategy_reset_on_success(manager):
    """测试连接成功后重置重连策略"""
    manager.reconnect_strategy.record_attempt()
    assert manager.reconnect_strategy.attempt_count == 1

    manager._on_ib_connected()

    assert manager.reconnect_strategy.attempt_count == 0


def test_auto_reconnect_disabled(manager):
    """测试禁用自动重连"""
    manager.auto_reconnect = False
    manager._is_connected = True

    manager._on_ib_disconnected()

    # 不应该启动重连线程
    assert manager._reconnect_thread is None


def test_auto_reconnect_enabled():
    """测试启用自动重连"""
    with patch("trading.connection.manager.IB") as mock_ib_class:
        mock_ib = Mock()
        mock_ib_class.return_value = mock_ib
        mock_ib.isConnected.return_value = False
        mock_ib.connectedEvent = MagicMock()
        mock_ib.disconnectedEvent = MagicMock()
        mock_ib.errorEvent = MagicMock()

        mgr = ConnectionManager(auto_reconnect=True)
        mgr._is_connected = True

        mgr._on_ib_disconnected()

        # 应该启动重连线程
        time.sleep(0.1)
        assert mgr._reconnect_thread is not None


def test_get_status(manager):
    """测试获取连接状态"""
    status = manager.get_status()

    assert "is_connected" in status
    assert "host" in status
    assert "port" in status
    assert "reconnect_attempts" in status
    assert status["host"] == "127.0.0.1"
    assert status["port"] == 4002


def test_error_handling(manager):
    """测试错误处理"""
    # 测试信息性错误（应该被过滤）
    manager._on_ib_error(None, 2104, "Market data farm connection", None)
    # 不应该有影响

    # 测试连接丢失错误
    manager._is_connected = True
    manager._on_ib_error(None, 1100, "Connectivity lost", None)
    assert not manager._is_connected


def test_from_config():
    """测试从配置创建"""
    with patch("trading.connection.manager.config") as mock_config:
        mock_config.get = Mock(
            side_effect=lambda key, default: {
                "ibkr.host": "192.168.1.1",
                "ibkr.port": 7497,
                "ibkr.client_id": 2,
                "ibkr.timeout": 20,
                "ibkr.read_only": True,
                "ibkr.auto_reconnect": False,
            }.get(key, default)
        )

        with patch("trading.connection.manager.IB"):
            mgr = ConnectionManager.from_config()

            assert mgr.host == "192.168.1.1"
            assert mgr.port == 7497
            assert mgr.client_id == 2
            assert mgr.timeout == 20
            assert mgr.readonly is True
            assert mgr.auto_reconnect is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
