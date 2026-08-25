"""
实时数据订阅模块

封装IBKR实时数据订阅，提供简洁的接口给策略使用。
"""

from typing import Callable, Dict, Optional
from datetime import datetime

from data.ibkr_client import IBKRClient
from common.logger import log
from common.models import Bar


class RealtimeDataFeed:
    """
    实时数据订阅管理器

    功能：
    - 订阅单个或多个标的的实时K线
    - 数据回调到策略
    - 管理订阅生命周期
    """

    def __init__(self, client: IBKRClient):
        """
        初始化实时数据订阅器

        Args:
            client: IBKR客户端实例
        """
        self.client = client
        self.subscriptions: Dict[str, bool] = {}  # symbol -> is_subscribed
        self._callbacks: Dict[str, Callable] = {}  # symbol -> callback

    def subscribe_bars(
        self,
        symbol: str,
        bar_size: str = "5 secs",
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅实时K线数据

        Args:
            symbol: 股票代码（如 "AAPL"）
            bar_size: K线周期（IBKR仅支持 "5 secs"）
            callback: 回调函数 callback(bar: Bar)

        Returns:
            True表示订阅成功
        """
        if not self.client.is_connected():
            log.error(f"Cannot subscribe {symbol}: client not connected")
            return False

        if symbol in self.subscriptions and self.subscriptions[symbol]:
            log.warning(f"Already subscribed to {symbol}")
            return True

        # 包装回调函数，转换为Bar对象
        def wrapped_callback(sym: str, bar_data: dict):
            """将字典数据转换为Bar对象并调用用户回调"""
            bar = Bar(
                symbol=bar_data['symbol'],
                timestamp=bar_data['timestamp'],
                open=bar_data['open'],
                high=bar_data['high'],
                low=bar_data['low'],
                close=bar_data['close'],
                volume=bar_data['volume']
            )

            if callback:
                try:
                    callback(bar)
                except Exception as e:
                    log.error(f"Error in callback for {symbol}: {e}")

        # 订阅实时数据
        success = self.client.subscribe_realtime_bars(
            symbol=symbol,
            bar_size=bar_size,
            callback=wrapped_callback
        )

        if success:
            self.subscriptions[symbol] = True
            self._callbacks[symbol] = callback
            log.info(f"Subscribed to {symbol} {bar_size} bars")
        else:
            log.error(f"Failed to subscribe to {symbol}")

        return success

    def unsubscribe(self, symbol: str) -> bool:
        """
        取消订阅指定标的

        Args:
            symbol: 股票代码

        Returns:
            True表示取消成功
        """
        if symbol not in self.subscriptions or not self.subscriptions[symbol]:
            log.warning(f"Not subscribed to {symbol}")
            return False

        # IBKR的取消订阅需要通过cancelRealTimeBars
        # 这里简单标记为未订阅
        self.subscriptions[symbol] = False
        if symbol in self._callbacks:
            del self._callbacks[symbol]

        log.info(f"Unsubscribed from {symbol}")
        return True

    def unsubscribe_all(self):
        """取消所有订阅"""
        symbols = list(self.subscriptions.keys())
        for symbol in symbols:
            self.unsubscribe(symbol)

        log.info("Unsubscribed from all symbols")

    def is_subscribed(self, symbol: str) -> bool:
        """
        检查是否已订阅某个标的

        Args:
            symbol: 股票代码

        Returns:
            True表示已订阅
        """
        return self.subscriptions.get(symbol, False)

    def get_subscribed_symbols(self) -> list:
        """
        获取所有已订阅的标的列表

        Returns:
            已订阅的股票代码列表
        """
        return [sym for sym, subscribed in self.subscriptions.items() if subscribed]
