"""
指标集成测试

测试指标与 QCAlgorithm 的集成
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from data.ibkr_client import IBKRClient
from strategy.qc_algorithm import QCAlgorithm
from strategy.resolution import Resolution
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


class TestIndicatorStrategy(QCAlgorithm):
    """测试策略（使用指标）"""

    def Initialize(self):
        self.AddEquity("AAPL", Resolution.Daily)
        self.sma = self.SMA("AAPL", 3, Resolution.Daily)
        self.ema = self.EMA("AAPL", 3, Resolution.Daily)


@pytest.fixture
def mocked_components():
    """Mock 依赖组件"""
    ibkr = Mock(spec=IBKRClient)
    order_mgr = Mock(spec=OrderManager)
    order_mgr.register_filled_callback = Mock()

    position_mgr = Mock(spec=PositionManager)
    position_mgr.get_position = Mock(return_value=None)
    position_mgr.get_positions = Mock(return_value=[])
    position_mgr.get_total_market_value = Mock(return_value=0.0)
    position_mgr.get_total_unrealized_pnl = Mock(return_value=0.0)
    position_mgr.get_total_realized_pnl = Mock(return_value=0.0)

    return ibkr, order_mgr, position_mgr


def test_create_sma_indicator(mocked_components):
    """测试创建 SMA 指标"""
    ibkr, order_mgr, position_mgr = mocked_components

    strategy = TestIndicatorStrategy(ibkr, order_mgr, position_mgr)
    strategy._run_initialize()

    # 验证指标已创建
    assert strategy.sma is not None
    assert strategy.sma.Period == 3
    assert "AAPL" in strategy._indicators


def test_create_ema_indicator(mocked_components):
    """测试创建 EMA 指标"""
    ibkr, order_mgr, position_mgr = mocked_components

    strategy = TestIndicatorStrategy(ibkr, order_mgr, position_mgr)
    strategy._run_initialize()

    # 验证指标已创建
    assert strategy.ema is not None
    assert strategy.ema.Period == 3


def test_indicator_auto_update(mocked_components):
    """测试指标自动更新"""
    ibkr, order_mgr, position_mgr = mocked_components

    strategy = TestIndicatorStrategy(ibkr, order_mgr, position_mgr)
    strategy._run_initialize()

    # 手动给指标一些初始值
    strategy.sma.Update(datetime(2024, 1, 1), 10.0)
    strategy.sma.Update(datetime(2024, 1, 2), 20.0)
    strategy.sma.Update(datetime(2024, 1, 3), 30.0)

    old_value = strategy.sma.Current.Value

    # 模拟新数据到达
    data = {"AAPL": {"timestamp": datetime(2024, 1, 4), "close": 40.0}}

    strategy._process_data(data)

    # 验证指标已更新
    new_value = strategy.sma.Current.Value
    assert new_value != old_value
    assert new_value == pytest.approx(30.0)  # (20 + 30 + 40) / 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
