"""数据模型定义

定义系统中使用的核心数据结构。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


@dataclass
class Bar:
    """K线数据

    表示单根K线（Bar）的OHLCV数据。

    Attributes:
        symbol: 股票代码
        timestamp: 时间戳
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量
    """
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __str__(self) -> str:
        """格式化输出"""
        return (
            f"{self.symbol} {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"O={self.open:.2f} H={self.high:.2f} L={self.low:.2f} C={self.close:.2f} V={self.volume}"
        )


@dataclass
class ConnectionStatus:
    """连接状态

    记录IBKR连接的状态信息。

    Attributes:
        connected: 是否已连接
        last_connect_time: 最后连接时间
        last_disconnect_time: 最后断开时间
        reconnect_attempts: 重连尝试次数
    """
    connected: bool
    last_connect_time: Optional[datetime] = None
    last_disconnect_time: Optional[datetime] = None
    reconnect_attempts: int = 0

    def __str__(self) -> str:
        """格式化输出"""
        status = "Connected" if self.connected else "Disconnected"
        return f"ConnectionStatus({status}, attempts={self.reconnect_attempts})"


class OrderStatus(Enum):
    """订单状态枚举"""
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


@dataclass
class Order:
    """订单信息

    表示一个交易订单。

    Attributes:
        order_id: 订单ID
        symbol: 股票代码
        action: 操作类型 (BUY/SELL)
        quantity: 数量
        order_type: 订单类型 (MARKET/LIMIT)
        status: 订单状态
        filled_quantity: 已成交数量
        avg_fill_price: 平均成交价
        create_time: 创建时间
    """
    order_id: int
    symbol: str
    action: str
    quantity: int
    order_type: str
    status: OrderStatus
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    create_time: datetime = None

    def __post_init__(self):
        if self.create_time is None:
            self.create_time = datetime.now()


@dataclass
class Position:
    """持仓信息

    表示一个持仓。

    Attributes:
        symbol: 股票代码
        quantity: 持仓数量
        avg_cost: 平均成本
        market_value: 市值
        unrealized_pnl: 未实现盈亏
    """
    symbol: str
    quantity: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float
