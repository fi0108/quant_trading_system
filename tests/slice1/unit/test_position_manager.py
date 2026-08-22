
"""持仓管理器功能测试"""

import pytest
from unittest.mock import Mock, MagicMock
from trading.position.manager import PositionManager
from data.ibkr_client import IBKRClient

def test_get_positions_success():
    """测试成功获取持仓"""
    # Mock客户端
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    # Mock持仓数据
    mock_pos1 = MagicMock()
    mock_pos1.contract.symbol = 'AAPL'
    mock_pos1.position = 100
    mock_pos1.avgCost = 150.0
    mock_pos1.marketValue = 15500.0
    mock_pos1.unrealizedPNL = 500.0

    mock_pos2 = MagicMock()
    mock_pos2.contract.symbol = 'GOOGL'
    mock_pos2.position = 50
    mock_pos2.avgCost = 2800.0
    mock_pos2.marketValue = 142000.0
    mock_pos2.unrealizedPNL = 2000.0

    mock_ib = MagicMock()
    mock_ib.positions.return_value = [mock_pos1, mock_pos2]
    client.ib = mock_ib

    # 创建持仓管理器
    manager = PositionManager(client)

    # 获取持仓
    positions = manager.get_positions()

    # 验证
    assert len(positions) == 2
    assert positions[0].symbol == 'AAPL'
    assert positions[0].quantity == 100
    assert positions[1].symbol == 'GOOGL'
    assert positions[1].quantity == 50

def test_get_positions_empty():
    """测试空持仓"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    mock_ib = MagicMock()
    mock_ib.positions.return_value = []
    client.ib = mock_ib

    manager = PositionManager(client)
    positions = manager.get_positions()

    assert len(positions) == 0

def test_get_positions_not_connected():
    """测试未连接时获取持仓"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = False

    manager = PositionManager(client)
    positions = manager.get_positions()

    assert len(positions) == 0

def test_print_positions():
    """测试打印持仓"""
    client = Mock(spec=IBKRClient)
    client.is_connected.return_value = True

    mock_pos = MagicMock()
    mock_pos.contract.symbol = 'AAPL'
    mock_pos.position = 100
    mock_pos.avgCost = 150.0
    mock_pos.marketValue = 15500.0
    mock_pos.unrealizedPNL = 500.0

    mock_ib = MagicMock()
    mock_ib.positions.return_value = [mock_pos]
    client.ib = mock_ib

    manager = PositionManager(client)

    # 不应该抛出异常
    manager.print_positions()
