"""
端到端测试共享 fixtures

提供测试所需的 Mock 对象和测试配置
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_ibkr():
    """Mock IBKR 连接"""
    with patch("data.ibkr_client.IB") as mock:
        mock_instance = MagicMock()
        mock_instance.isConnected.return_value = True

        # Mock 常用方法
        mock_instance.connect = Mock(return_value=None)
        mock_instance.disconnect = Mock(return_value=None)
        mock_instance.reqMarketDataType = Mock()
        mock_instance.reqAccountUpdates = Mock()

        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_db():
    """Mock 数据库连接"""
    with patch("database.safe_connection.get_connection") as mock:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock cursor 行为
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_cursor.execute.return_value = None

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock.return_value = mock_conn

        yield mock_conn


@pytest.fixture
def test_config():
    """测试配置"""
    return {
        "ibkr": {"host": "127.0.0.1", "port": 7497, "client_id": 999, "timeout": 10},
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "test_trading_db",
            "user": "test_user",
            "password": "test_password",
        },
        "risk": {"max_position_size": 10000, "max_order_value": 50000, "max_daily_loss": 5000},
        "strategy": {"name": "test_strategy", "symbols": ["AAPL", "MSFT"], "resolution": "1min"},
    }


@pytest.fixture
def sample_bar_data():
    """示例 Bar 数据"""
    return {
        "symbol": "AAPL",
        "time": datetime.now(),
        "open": Decimal("150.00"),
        "high": Decimal("151.00"),
        "low": Decimal("149.00"),
        "close": Decimal("150.50"),
        "volume": 1000,
    }


@pytest.fixture
def sample_account_info():
    """示例账户信息"""
    return {
        "account_id": "DU123456",
        "total_cash_value": Decimal("100000.00"),
        "net_liquidation": Decimal("100000.00"),
        "available_funds": Decimal("50000.00"),
        "buying_power": Decimal("50000.00"),
        "gross_position_value": Decimal("0.00"),
    }


@pytest.fixture
def sample_position():
    """示例持仓"""
    return {
        "symbol": "AAPL",
        "quantity": 100,
        "avg_cost": Decimal("150.00"),
        "market_price": Decimal("150.50"),
        "market_value": Decimal("15050.00"),
        "unrealized_pnl": Decimal("50.00"),
    }


@pytest.fixture
def sample_order():
    """示例订单"""
    return {
        "order_id": 1001,
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100,
        "order_type": "MARKET",
        "status": "Submitted",
        "filled_quantity": 0,
        "avg_fill_price": None,
    }
