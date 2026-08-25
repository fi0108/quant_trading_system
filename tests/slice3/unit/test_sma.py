"""
SMA 单元测试
"""

from datetime import datetime

import pytest

from strategy.indicators.sma import SimpleMovingAverage


def test_sma_initialization():
    """测试 SMA 初始化"""
    sma = SimpleMovingAverage("SMA(3)", 3)

    assert sma.Name == "SMA(3)"
    assert sma.Period == 3
    assert not sma.IsReady
    assert sma.Samples == 0


def test_sma_not_ready():
    """测试 SMA 未就绪状态"""
    sma = SimpleMovingAverage("SMA(3)", 3)

    sma.Update(datetime(2024, 1, 1), 10.0)
    assert not sma.IsReady
    assert sma.Samples == 1

    sma.Update(datetime(2024, 1, 2), 20.0)
    assert not sma.IsReady
    assert sma.Samples == 2


def test_sma_becomes_ready():
    """测试 SMA 就绪"""
    sma = SimpleMovingAverage("SMA(3)", 3)

    sma.Update(datetime(2024, 1, 1), 10.0)
    sma.Update(datetime(2024, 1, 2), 20.0)
    sma.Update(datetime(2024, 1, 3), 30.0)

    assert sma.IsReady
    assert sma.Samples == 3


def test_sma_calculation():
    """测试 SMA 计算正确性"""
    sma = SimpleMovingAverage("SMA(3)", 3)

    # 输入：10, 20, 30
    sma.Update(datetime(2024, 1, 1), 10.0)
    sma.Update(datetime(2024, 1, 2), 20.0)
    sma.Update(datetime(2024, 1, 3), 30.0)

    # (10 + 20 + 30) / 3 = 20.0
    assert sma.Current.Value == pytest.approx(20.0)

    # 输入：40 (窗口：20, 30, 40)
    sma.Update(datetime(2024, 1, 4), 40.0)

    # (20 + 30 + 40) / 3 = 30.0
    assert sma.Current.Value == pytest.approx(30.0)

    # 输入：50 (窗口：30, 40, 50)
    sma.Update(datetime(2024, 1, 5), 50.0)

    # (30 + 40 + 50) / 3 = 40.0
    assert sma.Current.Value == pytest.approx(40.0)


def test_sma_sliding_window():
    """测试 SMA 滑动窗口"""
    sma = SimpleMovingAverage("SMA(3)", 3)

    # 输入一系列数据
    data = [10, 20, 30, 40, 50, 60]
    expected = [
        None,  # 未就绪
        None,  # 未就绪
        20.0,  # (10+20+30)/3
        30.0,  # (20+30+40)/3
        40.0,  # (30+40+50)/3
        50.0,  # (40+50+60)/3
    ]

    for i, value in enumerate(data):
        sma.Update(datetime(2024, 1, i + 1), value)

        if sma.IsReady:
            assert sma.Current.Value == pytest.approx(expected[i])


def test_sma_reset():
    """测试 SMA 重置"""
    sma = SimpleMovingAverage("SMA(3)", 3)

    sma.Update(datetime(2024, 1, 1), 10.0)
    sma.Update(datetime(2024, 1, 2), 20.0)
    sma.Update(datetime(2024, 1, 3), 30.0)

    assert sma.IsReady

    # 重置
    sma.Reset()

    assert not sma.IsReady
    assert sma.Samples == 0
    assert sma.Current.Value == 0.0


def test_sma_single_period():
    """测试周期为1的 SMA"""
    sma = SimpleMovingAverage("SMA(1)", 1)

    sma.Update(datetime(2024, 1, 1), 100.0)

    assert sma.IsReady
    assert sma.Current.Value == 100.0

    sma.Update(datetime(2024, 1, 2), 200.0)
    assert sma.Current.Value == 200.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
