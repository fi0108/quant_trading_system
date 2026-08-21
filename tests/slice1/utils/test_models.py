import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

"""测试数据模型"""

from datetime import datetime
from src.common.models import Bar, ConnectionStatus


def test_bar_model():
    """测试Bar数据模型"""
    bar = Bar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 1, 9, 30, 0),
        open=150.0,
        high=151.0,
        low=149.5,
        close=150.5,
        volume=1000
    )

    # 测试属性
    assert bar.symbol == "AAPL"
    assert bar.open == 150.0
    assert bar.high == 151.0
    assert bar.low == 149.5
    assert bar.close == 150.5
    assert bar.volume == 1000

    # 测试字符串表示
    str_repr = str(bar)
    assert "AAPL" in str_repr
    assert "150.00" in str_repr or "150.0" in str_repr

    print(f"Bar model test passed: {bar}")


def test_connection_status():
    """测试ConnectionStatus模型"""
    # 测试已连接状态
    status = ConnectionStatus(
        connected=True,
        last_connect_time=datetime.now(),
        reconnect_attempts=0
    )

    assert status.connected is True
    assert status.reconnect_attempts == 0

    # 测试断开状态
    status2 = ConnectionStatus(
        connected=False,
        last_disconnect_time=datetime.now(),
        reconnect_attempts=3
    )

    assert status2.connected is False
    assert status2.reconnect_attempts == 3

    print(f"ConnectionStatus test passed: {status}")
    print(f"ConnectionStatus test passed: {status2}")


def test_bar_ohlc_logic():
    """测试Bar的OHLC逻辑"""
    bar = Bar(
        symbol="TEST",
        timestamp=datetime.now(),
        open=100.0,
        high=105.0,
        low=98.0,
        close=102.0,
        volume=5000
    )

    # OHLC逻辑检查
    assert bar.low <= bar.open <= bar.high
    assert bar.low <= bar.close <= bar.high
    assert bar.low <= bar.high

    print("Bar OHLC logic test passed")


if __name__ == '__main__':
    test_bar_model()
    test_connection_status()
    test_bar_ohlc_logic()
    print("All model tests passed")
