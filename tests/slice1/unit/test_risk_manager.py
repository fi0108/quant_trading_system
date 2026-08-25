"""风控管理器功能测试"""

from unittest.mock import MagicMock, Mock

import pytest

from data.ibkr_client import IBKRClient
from trading.risk.manager import RiskManager


def test_check_cash_sufficient():
    """测试现金充足的情况"""
    # Mock客户端
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    # Mock账户信息
    mock_value = MagicMock()
    mock_value.tag = "AvailableFunds"
    mock_value.value = "1000.00"

    mock_ib = MagicMock()
    mock_ib.accountValues.return_value = [mock_value]
    client.ib = mock_ib

    # 创建风控管理器
    manager = RiskManager(client, min_cash=200.0)

    # 检查现金
    assert manager.check_cash() is True


def test_check_cash_insufficient():
    """测试现金不足的情况"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    # Mock账户信息 - 现金不足
    mock_value = MagicMock()
    mock_value.tag = "AvailableFunds"
    mock_value.value = "100.00"

    mock_ib = MagicMock()
    mock_ib.accountValues.return_value = [mock_value]
    client.ib = mock_ib

    manager = RiskManager(client, min_cash=200.0)

    assert manager.check_cash() is False


def test_check_cash_not_connected():
    """测试未连接时检查现金"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = False

    manager = RiskManager(client)

    assert manager.check_cash() is False


def test_can_place_buy_order():
    """测试买入订单检查"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    mock_value = MagicMock()
    mock_value.tag = "AvailableFunds"
    mock_value.value = "1000.00"

    mock_ib = MagicMock()
    mock_ib.accountValues.return_value = [mock_value]
    client.ib = mock_ib

    manager = RiskManager(client, min_cash=200.0)

    # BUY订单需要检查现金
    assert manager.can_place_order("AAPL", 10, "BUY") is True


def test_can_place_sell_order():
    """测试卖出订单检查"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    manager = RiskManager(client)

    # SELL订单暂时不检查
    assert manager.can_place_order("AAPL", 10, "SELL") is True
