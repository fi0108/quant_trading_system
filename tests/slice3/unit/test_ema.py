"""
EMA 单元测试
"""

from datetime import datetime

import pytest

from strategy.indicators.ema import ExponentialMovingAverage


def test_ema_initialization():
    """测试 EMA 初始化"""
    ema = ExponentialMovingAverage("EMA(3)", 3)

    assert ema.Name == "EMA(3)"
    assert ema.Period == 3
    assert not ema.IsReady
    assert ema.Samples == 0


def test_ema_first_value():
    """测试 EMA 第一个值"""
    ema = ExponentialMovingAverage("EMA(3)", 3)

    ema.Update(datetime(2024, 1, 1), 10.0)

    # 第一个值直接使用
    assert ema.Current.Value == 10.0
    assert ema.Samples == 1


def test_ema_calculation():
    """测试 EMA 计算正确性"""
    ema = ExponentialMovingAverage("EMA(3)", 3)

    # k = 2 / (3 + 1) = 0.5

    # 第1个值：10
    ema.Update(datetime(2024, 1, 1), 10.0)
    assert ema.Current.Value == pytest.approx(10.0)

    # 第2个值：20
    # EMA = 20 * 0.5 + 10 * 0.5 = 15.0
    ema.Update(datetime(2024, 1, 2), 20.0)
    assert ema.Current.Value == pytest.approx(15.0)

    # 第3个值：30
    # EMA = 30 * 0.5 + 15 * 0.5 = 22.5
    ema.Update(datetime(2024, 1, 3), 30.0)
    assert ema.Current.Value == pytest.approx(22.5)

    # 现在已就绪
    assert ema.IsReady


def test_ema_becomes_ready():
    """测试 EMA 就绪状态"""
    ema = ExponentialMovingAverage("EMA(5)", 5)

    for i in range(4):
        ema.Update(datetime(2024, 1, i + 1), float(i + 1))
        assert not ema.IsReady

    ema.Update(datetime(2024, 1, 5), 5.0)
    assert ema.IsReady


def test_ema_reset():
    """测试 EMA 重置"""
    ema = ExponentialMovingAverage("EMA(3)", 3)

    ema.Update(datetime(2024, 1, 1), 10.0)
    ema.Update(datetime(2024, 1, 2), 20.0)
    ema.Update(datetime(2024, 1, 3), 30.0)

    assert ema.IsReady

    # 重置
    ema.Reset()

    assert not ema.IsReady
    assert ema.Samples == 0
    assert ema.Current.Value == 0.0


def test_ema_vs_sma():
    """测试 EMA 对比 SMA（EMA 对新数据更敏感）"""
    from strategy.indicators.sma import SimpleMovingAverage

    sma = SimpleMovingAverage("SMA(3)", 3)
    ema = ExponentialMovingAverage("EMA(3)", 3)

    # 输入相同数据
    data = [10.0, 10.0, 10.0, 20.0]  # 前3个是10，第4个突然变20

    for i, value in enumerate(data):
        sma.Update(datetime(2024, 1, i + 1), value)
        ema.Update(datetime(2024, 1, i + 1), value)

    # 第4个数据后：
    # SMA = (10 + 10 + 20) / 3 = 13.33
    # EMA 应该更接近 20（对新数据敏感）

    assert sma.Current.Value == pytest.approx(13.33, 0.01)
    assert ema.Current.Value > sma.Current.Value  # EMA 更大


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
