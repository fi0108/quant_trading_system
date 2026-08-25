"""
统一的IBKR客户端封装

整合了连接管理、实时数据订阅和历史数据请求功能。
"""

import time
import asyncio
import logging
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from ib_insync import IB, Stock, Contract, util

from common.config import config
from common.logger import log
from common.models import ConnectionStatus

logger = logging.getLogger(__name__)


class IBKRClient:
    """
    统一的IBKR客户端

    功能：
    - 连接管理（同步/异步）
    - 自动重连
    - 历史数据请求
    - 实时数据订阅
    """

    def __init__(self, host: str = None, port: int = None, client_id: int = None, timeout: int = None):
        """
        初始化IBKR客户端

        Args:
            host: IB Gateway/TWS host，默认从配置读取
            port: 端口（7497=TWS, 4001=Gateway），默认从配置读取
            client_id: 客户端ID，默认从配置读取
            timeout: 连接超时，默认从配置读取
        """
        self.ib = IB()
        self.status = ConnectionStatus(connected=False)

        # 从配置或参数获取连接信息
        self.host = host or config.get('ibkr.host', '127.0.0.1')
        self.port = port or config.get('ibkr.port', 4002)
        self.client_id = client_id or config.get('ibkr.client_id', 1)
        self.timeout = timeout or config.get('ibkr.timeout', 15)

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 5

        # 自动重连配置
        self.reconnect_enabled = True
        self.max_reconnect_attempts = 10
        self.backoff_factor = 2
        self.initial_delay = 5

        # 注册断线事件
        self.ib.disconnectedEvent += self._on_disconnected

    def connect(self) -> bool:
        """
        同步连接到IBKR

        Returns:
            True表示连接成功
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                log.info(f"Connecting to IBKR {self.host}:{self.port} (attempt {attempt}/{self.max_retries})")

                self.ib.connect(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=self.timeout
                )

                self.status.connected = True
                self.status.last_connect_time = datetime.now()
                self.status.reconnect_attempts = 0

                log.info("Connected to IBKR successfully")
                return True

            except Exception as e:
                log.error(f"Connection attempt {attempt} failed: {e}")
                if attempt < self.max_retries:
                    log.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)

        log.error(f"Failed to connect after {self.max_retries} attempts")
        return False

    async def connect_async(self) -> bool:
        """
        异步连接到IBKR

        Returns:
            True表示连接成功
        """
        try:
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.timeout
            )
            self.status.connected = True
            self.status.last_connect_time = datetime.now()
            self.status.reconnect_attempts = 0

            log.info(f"Connected to IBKR at {self.host}:{self.port}")
            return True

        except Exception as e:
            self.status.connected = False
            log.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.ib.isConnected():
            log.info("Disconnecting from IBKR...")
            self.ib.disconnect()
            self.status.connected = False
            self.status.last_disconnect_time = datetime.now()
            log.info("Disconnected")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.ib.isConnected()

    def _on_disconnected(self):
        """断线事件处理"""
        self.status.connected = False
        self.status.last_disconnect_time = datetime.now()
        log.warning("Disconnected from IBKR")

        if self.reconnect_enabled:
            self._auto_reconnect()

    def _auto_reconnect(self):
        """自动重连（指数退避）"""
        delay = self.initial_delay

        for attempt in range(1, self.max_reconnect_attempts + 1):
            self.status.reconnect_attempts = attempt
            log.info(f"Auto-reconnecting (attempt {attempt}/{self.max_reconnect_attempts})")

            time.sleep(delay)

            if self.connect():
                log.info("Auto-reconnect successful")
                return True

            delay = min(delay * self.backoff_factor, 60)

        log.error(f"Auto-reconnect failed after {self.max_reconnect_attempts} attempts")
        return False

    async def get_historical_bars(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        bar_size: str = '1 day'
    ) -> List[Dict]:
        """
        获取历史K线数据（异步）

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            bar_size: K线周期 ('1 min', '5 mins', '1 hour', '1 day', '1 week', '1 month')

        Returns:
            K线数据列表，每个字典包含: symbol, timestamp, open, high, low, close, volume
        """
        if not self.is_connected():
            log.error("Not connected to IBKR")
            return []

        try:
            # 创建合约
            contract = Stock(symbol, 'SMART', 'USD')

            # 计算请求时长
            duration_days = (end_date - start_date).days + 2

            if bar_size in ['1 min', '5 mins', '15 mins', '30 mins']:
                if duration_days <= 1:
                    duration_str = '1 D'
                elif duration_days <= 7:
                    duration_str = f'{duration_days} D'
                else:
                    duration_str = f'{min(duration_days, 30)} D'
            elif bar_size == '1 hour':
                if duration_days <= 30:
                    duration_str = f'{duration_days} D'
                else:
                    duration_str = f'{min(duration_days // 7 + 1, 52)} W'
            else:
                if duration_days <= 30:
                    duration_str = f'{duration_days} D'
                elif duration_days <= 365:
                    duration_str = f'{duration_days // 7 + 2} W'
                else:
                    duration_str = f'{duration_days // 365 + 1} Y'

            # 请求历史数据
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end_date,
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            # 转换并过滤数据
            result = []
            for bar in bars:
                bar_timestamp = bar.date

                # 根据K线周期判断是否包含此K线
                include = False
                if bar_size in ['1 day', '1 week', '1 month']:
                    bar_date = bar_timestamp.date() if hasattr(bar_timestamp, 'date') else bar_timestamp
                    include = bar_date >= start_date.date() and bar_date <= end_date.date()
                else:
                    if not hasattr(bar_timestamp, 'hour'):
                        bar_timestamp = datetime.combine(bar_timestamp, datetime.min.time())
                    if start_date.tzinfo and not (hasattr(bar_timestamp, 'tzinfo') and bar_timestamp.tzinfo):
                        bar_timestamp = start_date.tzinfo.localize(bar_timestamp)
                    include = bar_timestamp >= start_date and bar_timestamp <= end_date

                if include:
                    result.append({
                        'symbol': symbol,
                        'timestamp': bar.date,
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': int(bar.volume)
                    })

            log.info(f"Retrieved {len(result)} bars for {symbol}")
            return result

        except Exception as e:
            log.error(f"Failed to get historical bars for {symbol}: {e}")
            return []

    def subscribe_realtime_bars(
        self,
        symbol: str,
        bar_size: str = '5 secs',
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅实时K线数据

        Args:
            symbol: 股票代码
            bar_size: K线周期（IBKR仅支持 '5 secs'）
            callback: 回调函数 callback(symbol, bar_data)

        Returns:
            True表示订阅成功
        """
        if not self.is_connected():
            log.error("Not connected to IBKR")
            return False

        try:
            contract = Stock(symbol, 'SMART', 'USD')

            if bar_size == '5 secs':
                bars = self.ib.reqRealTimeBars(
                    contract,
                    barSize=5,
                    whatToShow='TRADES',
                    useRTH=False
                )

                if callback:
                    def on_bar_update(bars, hasNewBar):
                        if hasNewBar:
                            bar = bars[-1]
                            bar_data = {
                                'symbol': symbol,
                                'timestamp': bar.time,
                                'open': float(bar.open_),
                                'high': float(bar.high),
                                'low': float(bar.low),
                                'close': float(bar.close),
                                'volume': int(bar.volume)
                            }
                            callback(symbol, bar_data)

                    bars.updateEvent += on_bar_update

                log.info(f"Subscribed to real-time bars for {symbol}")
                return True
            else:
                log.warning(f"Bar size {bar_size} not supported, use '5 secs'")
                return False

        except Exception as e:
            log.error(f"Failed to subscribe to real-time bars for {symbol}: {e}")
            return False

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.disconnect()
