"""
简单移动平均 (Simple Moving Average, SMA)

计算指定周期内的平均值
"""

from collections import deque
from datetime import datetime

from strategy.indicators.indicator_base import IndicatorBase, IndicatorDataPoint


class SimpleMovingAverage(IndicatorBase):
    """
    简单移动平均

    公式：SMA = (P1 + P2 + ... + Pn) / n

    示例：
        sma = SimpleMovingAverage("SMA(20)", 20)
        sma.Update(datetime.now(), 100.0)
        if sma.IsReady:
            print(sma.Current.Value)
    """

    def __init__(self, name: str, period: int):
        """
        初始化 SMA

        Args:
            name: 指标名称
            period: 周期（窗口大小）
        """
        super().__init__(name, period)
        # 使用 deque 作为滑动窗口，自动维护大小
        self._window = deque(maxlen=period)
        self._sum = 0.0  # 窗口内的总和（优化性能）

    def Update(self, time: datetime, value: float):
        """
        更新 SMA

        Args:
            time: 时间戳
            value: 价格值
        """
        # 如果窗口已满，减去要被挤出的值
        if len(self._window) == self.Period:
            self._sum -= self._window[0]

        # 添加新值
        self._window.append(value)
        self._sum += value
        self._samples += 1

        # 计算平均值
        if self.IsReady:
            avg = self._sum / len(self._window)
            self.Current = IndicatorDataPoint(time, avg)

    def Reset(self):
        """重置 SMA"""
        super().Reset()
        self._window.clear()
        self._sum = 0.0
