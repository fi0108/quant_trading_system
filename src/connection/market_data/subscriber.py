"""
实时数据订阅器

职责：
1. 订阅IBKR实时行情（延迟15分钟）
2. 接收Bar数据
3. 通过回调传递数据给下游处理
"""

from typing import List, Callable, Optional, Dict
from datetime import datetime
from ib_insync import IB, Stock, util
import logging

logger = logging.getLogger(__name__)


class MarketDataSubscriber:
    """
    实时行情订阅器

    功能：
    - 设置延迟数据模式（免费，延迟15分钟）
    - 订阅1分钟K线
    - 接收已完成的Bar数据
    - 通过回调传递数据
    """

    def __init__(
        self,
        ib_client: IB,
        data_type: int = 3,  # 1=实时, 2=冻结, 3=延迟15分钟
        bar_size: int = 60,  # 秒，默认60秒=1分钟
    ):
        """
        初始化订阅器

        Args:
            ib_client: IB连接客户端
            data_type: 数据类型 (1=实时, 2=冻结, 3=延迟15分钟)
            bar_size: Bar大小（秒），默认60秒
        """
        self.ib = ib_client
        self.data_type = data_type
        self.bar_size = bar_size

        # 订阅管理
        self._subscriptions: Dict[str, object] = {}  # symbol -> RealTimeBar对象
        self._callbacks: List[Callable] = []

        # 统计
        self._bars_received = 0
        self._subscription_errors: Dict[str, str] = {}

    def set_data_type(self, data_type: int):
        """
        设置数据类型

        Args:
            data_type: 1=实时(Live), 2=冻结(Frozen), 3=延迟15分钟(Delayed)
        """
        if not self.ib.isConnected():
            logger.warning("未连接IBKR，无法设置数据类型")
            return

        self.data_type = data_type
        self.ib.reqMarketDataType(data_type)

        data_type_names = {1: '实时数据(Live)', 2: '冻结数据(Frozen)', 3: '延迟15分钟(Delayed)'}
        logger.info(f"数据类型已设置为: {data_type_names.get(data_type, f'未知({data_type})')}")

    def subscribe(self, symbols: List[str]) -> Dict[str, bool]:
        """
        批量订阅标的

        Args:
            symbols: 标的代码列表，如 ['AAPL', 'TSLA', 'MSFT']

        Returns:
            订阅结果字典 {symbol: success}
        """
        if not self.ib.isConnected():
            logger.error("未连接IBKR，无法订阅")
            return {symbol: False for symbol in symbols}

        # 设置数据类型
        self.set_data_type(self.data_type)

        results = {}
        for symbol in symbols:
            try:
                success = self._subscribe_single(symbol)
                results[symbol] = success
            except Exception as e:
                logger.error(f"订阅 {symbol} 失败: {e}")
                self._subscription_errors[symbol] = str(e)
                results[symbol] = False

        logger.info(f"订阅完成: 成功 {sum(results.values())}/{len(symbols)}")
        return results

    def _subscribe_single(self, symbol: str) -> bool:
        """
        订阅单个标的

        Args:
            symbol: 标的代码

        Returns:
            是否订阅成功
        """
        if symbol in self._subscriptions:
            logger.warning(f"{symbol} 已订阅，跳过")
            return True

        # 创建合约
        contract = Stock(symbol, 'SMART', 'USD')

        try:
            # 请求实时Bar数据
            bars = self.ib.reqRealTimeBars(
                contract,
                barSize=self.bar_size,
                whatToShow='TRADES',  # 成交数据
                useRTH=True,  # 只要常规交易时段
            )

            # 注册回调
            bars.updateEvent += self._on_bar_update

            # 保存订阅
            self._subscriptions[symbol] = bars

            logger.info(f"订阅成功: {symbol} (Bar大小: {self.bar_size}秒)")
            return True

        except Exception as e:
            logger.error(f"订阅失败 {symbol}: {e}")
            self._subscription_errors[symbol] = str(e)
            return False

    def _on_bar_update(self, bars, hasNewBar):
        """
        Bar数据更新回调（由ib_insync触发）

        Args:
            bars: Bar数据列表
            hasNewBar: 是否有新的已完成Bar
        """
        if not hasNewBar:
            return

        # 获取最新的已完成Bar
        if len(bars) > 0:
            latest_bar = bars[-1]

            # 提取标的代码
            symbol = latest_bar.contract.symbol if hasattr(latest_bar, 'contract') else 'UNKNOWN'

            # 构造Bar数据字典
            bar_data = {
                'symbol': symbol,
                'timestamp': latest_bar.time,  # Bar的真实时间（不是接收时间）
                'open': float(latest_bar.open),
                'high': float(latest_bar.high),
                'low': float(latest_bar.low),
                'close': float(latest_bar.close),
                'volume': int(latest_bar.volume),
                'wap': float(latest_bar.wap) if hasattr(latest_bar, 'wap') else None,
                'count': int(latest_bar.count) if hasattr(latest_bar, 'count') else None,
                'source': 'realtime',
                'received_at': datetime.utcnow()  # 接收时间（用于监控延迟）
            }

            self._bars_received += 1

            # 触发回调
            self._trigger_callbacks(bar_data)

    def _trigger_callbacks(self, bar_data: dict):
        """
        触发所有回调

        Args:
            bar_data: Bar数据字典
        """
        for callback in self._callbacks:
            try:
                callback(bar_data)
            except Exception as e:
                logger.error(f"回调错误: {e}", exc_info=True)

    def register_callback(self, callback: Callable):
        """
        注册Bar数据回调

        Args:
            callback: 回调函数，接收bar_data字典
        """
        self._callbacks.append(callback)
        logger.debug(f"回调已注册，当前回调数量: {len(self._callbacks)}")

    def unsubscribe(self, symbol: str) -> bool:
        """
        取消订阅单个标的

        Args:
            symbol: 标的代码

        Returns:
            是否取消成功
        """
        if symbol not in self._subscriptions:
            logger.warning(f"{symbol} 未订阅")
            return False

        try:
            bars = self._subscriptions[symbol]
            self.ib.cancelRealTimeBars(bars)
            del self._subscriptions[symbol]
            logger.info(f"取消订阅: {symbol}")
            return True

        except Exception as e:
            logger.error(f"取消订阅失败 {symbol}: {e}")
            return False

    def unsubscribe_all(self):
        """取消所有订阅"""
        symbols = list(self._subscriptions.keys())
        for symbol in symbols:
            self.unsubscribe(symbol)

        logger.info("已取消所有订阅")

    def get_subscribed_symbols(self) -> List[str]:
        """获取已订阅的标的列表"""
        return list(self._subscriptions.keys())

    def is_subscribed(self, symbol: str) -> bool:
        """检查标的是否已订阅"""
        return symbol in self._subscriptions

    def get_stats(self) -> dict:
        """
        获取订阅统计信息

        Returns:
            统计信息字典
        """
        return {
            'data_type': self.data_type,
            'data_type_name': {1: 'Live', 2: 'Frozen', 3: 'Delayed'}[self.data_type],
            'bar_size_seconds': self.bar_size,
            'subscribed_count': len(self._subscriptions),
            'subscribed_symbols': self.get_subscribed_symbols(),
            'bars_received': self._bars_received,
            'callback_count': len(self._callbacks),
            'subscription_errors': self._subscription_errors.copy()
        }

    def reset_stats(self):
        """重置统计信息"""
        self._bars_received = 0
        self._subscription_errors.clear()
        logger.debug("统计信息已重置")
