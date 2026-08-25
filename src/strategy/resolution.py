"""
时间周期枚举

定义数据的时间粒度
"""

from enum import Enum


class Resolution(Enum):
    """数据时间周期"""

    Tick = "tick"  # Tick 数据
    Second = "1 sec"  # 1秒
    Minute = "1 min"  # 1分钟
    Hour = "1 hour"  # 1小时
    Daily = "1 day"  # 1日

    def __str__(self):
        return self.value

    @property
    def bar_size(self) -> str:
        """IBKR bar size 格式"""
        return self.value

    @property
    def seconds(self) -> int:
        """转换为秒数"""
        mapping = {
            Resolution.Tick: 0,
            Resolution.Second: 1,
            Resolution.Minute: 60,
            Resolution.Hour: 3600,
            Resolution.Daily: 86400,
        }
        return mapping.get(self, 0)
