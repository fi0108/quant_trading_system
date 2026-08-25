"""
指数移动平均 (Exponential Moving Average, EMA)

对近期数据赋予更高的权重
"""

from datetime import datetime

from strategy.indicators.indicator_base import IndicatorBase, IndicatorDataPoint


class ExponentialMovingAverage(IndicatorBase):
    """
    指数移动平均

    公式：EMA_today = Price_today * k + EMA_yesterday * (1 - k)
    其中：k = 2 / (period + 1)

    示例：
        ema = ExponentialMovingAverage("EMA(20)", 20)
        ema.Update(datetime.now(), 100.0)
        if ema.IsReady:
            print(ema.Current.Value)
    """

    def __init__(self, name: str, period: int):
        """
        初始化 EMA

        Args:
            name: 指标名称
            period: 周期
        """
        super().__init__(name, period)
        # 平滑系数
        self._k = 2.0 / (period + 1)
        # EMA 值
        self._ema_value = 0.0

    def Update(self, time: datetime, value: float):
        """
        更新 EMA

        Args:
            time: 时间戳
            value: 价格值
        """
        self._samples += 1

        if self._samples == 1:
            # 第一个值直接使用
            self._ema_value = value
        else:
            # EMA = value * k + EMA_prev * (1 - k)
            self._ema_value = value * self._k + self._ema_value * (1 - self._k)

        self.Current = IndicatorDataPoint(time, self._ema_value)

    def Reset(self):
        """重置 EMA"""
        super().Reset()
        self._ema_value = 0.0
