"""
健康检查单元测试
"""

from unittest.mock import MagicMock, Mock

import pytest

from data.ibkr_client import IBKRClient
from monitor.health_checker import HealthChecker
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


@pytest.fixture
def mock_ibkr_client():
    """Mock IBKR 客户端"""
    client = Mock(spec=IBKRClient)
    client.is_connected = Mock(return_value=True)
    return client


@pytest.fixture
def mock_order_manager():
    """Mock 订单管理器"""
    mgr = Mock(spec=OrderManager)
    mgr.get_all_orders = Mock(return_value=[])
    return mgr


@pytest.fixture
def mock_position_manager():
    """Mock 持仓管理器"""
    mgr = Mock(spec=PositionManager)
    mgr.get_positions = Mock(return_value=[])
    mgr.get_total_market_value = Mock(return_value=0.0)
    mgr.get_total_unrealized_pnl = Mock(return_value=0.0)
    mgr.get_total_realized_pnl = Mock(return_value=0.0)
    return mgr


@pytest.fixture
def health_checker(mock_ibkr_client, mock_order_manager, mock_position_manager):
    """创建健康检查器"""
    return HealthChecker(
        ibkr_client=mock_ibkr_client, order_manager=mock_order_manager, position_manager=mock_position_manager
    )


def test_check_connection_healthy(health_checker, mock_ibkr_client):
    """测试连接状态检查（健康）"""
    mock_ibkr_client.is_connected.return_value = True

    result = health_checker.check_connection()

    assert result["status"] == "healthy"
    assert result["connected"] is True


def test_check_connection_unhealthy(health_checker, mock_ibkr_client):
    """测试连接状态检查（不健康）"""
    mock_ibkr_client.is_connected.return_value = False

    result = health_checker.check_connection()

    assert result["status"] == "unhealthy"
    assert result["connected"] is False


def test_check_memory(health_checker):
    """测试内存检查"""
    result = health_checker.check_memory(threshold_percent=80.0)

    assert "status" in result
    assert "percent_used" in result
    assert "total_mb" in result
    assert "available_mb" in result
    assert result["percent_used"] >= 0
    assert result["percent_used"] <= 100


def test_check_cpu(health_checker):
    """测试 CPU 检查"""
    result = health_checker.check_cpu(threshold_percent=80.0, interval=0.1)

    assert "status" in result
    assert "percent_used" in result
    assert "cpu_count" in result
    assert result["percent_used"] >= 0
    assert result["percent_used"] <= 100


def test_check_orders(health_checker, mock_order_manager):
    """测试订单检查"""
    from common.models import Order, OrderStatus

    # Mock 一些订单
    orders = [Mock(status=OrderStatus.FILLED), Mock(status=OrderStatus.SUBMITTED), Mock(status=OrderStatus.FILLED)]
    mock_order_manager.get_all_orders.return_value = orders

    result = health_checker.check_orders()

    assert result["status"] == "healthy"
    assert result["total_orders"] == 3
    assert result["by_status"]["Filled"] == 2
    assert result["by_status"]["Submitted"] == 1


def test_check_positions(health_checker, mock_position_manager):
    """测试持仓检查"""
    from common.models import Position

    # Mock 一些持仓
    positions = [Mock(spec=Position), Mock(spec=Position)]
    mock_position_manager.get_positions.return_value = positions
    mock_position_manager.get_total_market_value.return_value = 50000.0
    mock_position_manager.get_total_unrealized_pnl.return_value = 1000.0

    result = health_checker.check_positions()

    assert result["status"] == "healthy"
    assert result["total_positions"] == 2
    assert result["total_market_value"] == 50000.0
    assert result["total_unrealized_pnl"] == 1000.0


def test_check_all(health_checker):
    """测试完整健康检查"""
    report = health_checker.check_all()

    # 验证报告结构
    assert "timestamp" in report
    assert "checks" in report
    assert "overall_status" in report

    # 验证所有检查项
    assert "connection" in report["checks"]
    assert "memory" in report["checks"]
    assert "cpu" in report["checks"]
    assert "orders" in report["checks"]
    assert "positions" in report["checks"]

    # 验证总体状态
    assert report["overall_status"] in ["healthy", "warning", "unhealthy"]


def test_check_all_unhealthy(health_checker, mock_ibkr_client):
    """测试不健康的系统"""
    # 模拟连接断开
    mock_ibkr_client.is_connected.return_value = False

    report = health_checker.check_all()

    assert report["overall_status"] == "unhealthy"
    assert report["checks"]["connection"]["status"] == "unhealthy"


def test_print_report(health_checker, capsys):
    """测试打印报告"""
    report = health_checker.check_all()

    health_checker.print_report(report)

    # 验证有输出
    # (实际输出到日志，这里只验证不抛异常)
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
