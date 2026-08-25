"""
指标基础类和数据点

提供所有技术指标的通用接口
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class IndicatorDataPoint:
    """
    指标数据点

    封装指标在某个时间点的值
    """

    def __init__(self, time: datetime, value: float):
        """
        初始化数据点

        Args:
            time: 时间戳
            value: 指标值
        """
        self.Time = time
        self.Value = value

    def __repr__(self):
        return f"DataPoint({self.Time}, {self.Value:.4f})"


class IndicatorBase(ABC):
    """
    技术指标基类

    所有技术指标都继承此类
    提供统一的接口：
    - IsReady: 指标是否已就绪（预热完成）
    - Current: 当前指标值
    - Update(): 更新指标
    - Reset(): 重置指标
    """

    def __init__(self, name: str, period: int):
        """
        初始化指标

        Args:
            name: 指标名称（如 "SMA(20)"）
            period: 周期（需要多少个数据点才能计算）
        """
        self.Name = name
        self.Period = period
        self.Current = IndicatorDataPoint(datetime.min, 0.0)
        self._samples = 0  # 已收到的样本数

    @property
    def IsReady(self) -> bool:
        """
        指标是否已就绪

        Returns:
            True 如果已收到足够的数据点（>= Period）
        """
        return self._samples >= self.Period

    @property
    def Samples(self) -> int:
        """
        已收到的样本数

        Returns:
            样本数量
        """
        return self._samples

    @abstractmethod
    def Update(self, time: datetime, value: float):
        """
        更新指标（子类必须实现）

        Args:
            time: 时间戳
            value: 价格值（通常是收盘价）
        """
        pass

    def Reset(self):
        """
        重置指标

        清空所有状态，回到初始化状态
        """
        self._samples = 0
        self.Current = IndicatorDataPoint(datetime.min, 0.0)

    def __repr__(self):
        status = "Ready" if self.IsReady else f"Warming {self._samples}/{self.Period}"
        return f"{self.Name} [{status}] Current={self.Current.Value:.4f}"
