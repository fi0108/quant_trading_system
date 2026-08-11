"""
市场数据调度器 - 集成时区管理、交易日历和连接管理

职责：
1. 判断当前是否在交易时段
2. 交易时段内：启动连接管理器，订阅实时数据
3. 非交易时段：断开连接，进入休眠
4. 每分钟检查一次交易时段状态
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable
import logging

from ..core.timezone_manager import TimezoneManager
from ..calendar.trading_calendar import TradingCalendar
from .manager import ConnectionManager

logger = logging.getLogger(__name__)


class MarketDataScheduler:
    """
    市场数据调度器

    集成三个核心组件：
    - TimezoneManager: 时区管理和交易时段判断
    - TradingCalendar: 交易日历管理
    - ConnectionManager: IBKR连接管理

    自动根据交易时段控制连接状态。
    """

    CHECK_INTERVAL = 60  # 每60秒检查一次
    PRE_MARKET_BUFFER = 10 * 60  # 开盘前10分钟启动
    POST_MARKET_BUFFER = 20 * 60  # 收盘后20分钟断开（延迟数据+缓冲）

    def __init__(
        self,
        timezone_manager: Optional[TimezoneManager] = None,
        trading_calendar: Optional[TradingCalendar] = None,
        connection_manager: Optional[ConnectionManager] = None
    ):
        """
        初始化调度器

        Args:
            timezone_manager: 时区管理器（默认创建新实例）
            trading_calendar: 交易日历管理器（默认创建新实例）
            connection_manager: 连接管理器（默认创建新实例）
        """
        self.tz_manager = timezone_manager or TimezoneManager()
        self.calendar = trading_calendar or TradingCalendar()
        self.conn_manager = connection_manager or ConnectionManager()

        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        # 状态回调
        self._on_trading_start_callbacks: list[Callable] = []
        self._on_trading_end_callbacks: list[Callable] = []

    def should_connect_now(self) -> tuple[bool, str]:
        """
        判断当前是否应该连接IBKR

        Returns:
            (是否应该连接, 原因说明)
        """
        now_utc = self.tz_manager.now_utc()
        now_market = self.tz_manager.utc_to_market(now_utc)
        today = now_market.date()

        # 1. 检查是否交易日
        if not self.calendar.is_trading_day(today):
            next_trading_day = self.calendar.next_trading_day(today)
            return False, f"非交易日（{today.strftime('%A')}），下一交易日: {next_trading_day}"

        # 2. 检查是否在交易时段（含缓冲时间）
        market_open, market_close = self.tz_manager.get_trading_day_bounds(now_utc)

        # 开盘前10分钟启动
        connect_time = market_open - timedelta(seconds=self.PRE_MARKET_BUFFER)
        # 收盘后20分钟断开（延迟15分钟数据 + 5分钟缓冲）
        disconnect_time = market_close + timedelta(seconds=self.POST_MARKET_BUFFER)

        if now_utc < connect_time:
            return False, f"开盘前，等待时间: {self.tz_manager.format_dual_timezone(connect_time)}"

        if now_utc > disconnect_time:
            return False, f"收盘后已过缓冲期，下一交易日: {self.calendar.next_trading_day(today)}"

        # 3. 在交易时段内
        if connect_time <= now_utc <= disconnect_time:
            if now_utc < market_open:
                return True, f"开盘前准备期（提前{self.PRE_MARKET_BUFFER//60}分钟）"
            elif now_utc <= market_close:
                return True, "交易时段内"
            else:
                return True, f"收盘后缓冲期（延迟数据接收中）"

        return False, "未知状态"

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        logger.info("市场数据调度器启动")
        logger.info(f"当前时间: {self.tz_manager.format_dual_timezone(self.tz_manager.now_utc())}")

        # 立即检查一次
        await self._check_and_update_connection()

        # 启动调度循环
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        """停止调度器"""
        if not self._running:
            return

        self._running = False
        logger.info("市场数据调度器停止")

        # 取消调度任务
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        # 断开连接
        if self.conn_manager.is_connected():
            await self.conn_manager.disconnect()

    async def _scheduler_loop(self):
        """调度循环：每分钟检查一次"""
        while self._running:
            try:
                await asyncio.sleep(self.CHECK_INTERVAL)
                await self._check_and_update_connection()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度循环错误: {e}", exc_info=True)

    async def _check_and_update_connection(self):
        """检查并更新连接状态"""
        should_connect, reason = self.should_connect_now()
        is_connected = self.conn_manager.is_connected()

        logger.info(f"调度检查 - 应该连接: {should_connect}, 当前连接: {is_connected}, 原因: {reason}")

        # 应该连接但未连接
        if should_connect and not is_connected:
            logger.info("开始连接IBKR...")
            try:
                success = await self.conn_manager.connect()
                if success:
                    logger.info("连接成功")
                    self._trigger_trading_start_callbacks()
                else:
                    logger.warning("连接失败")
            except Exception as e:
                logger.error(f"连接错误: {e}", exc_info=True)

        # 不应该连接但已连接
        elif not should_connect and is_connected:
            logger.info("断开IBKR连接...")
            await self.conn_manager.disconnect()
            logger.info("连接已断开")
            self._trigger_trading_end_callbacks()

        # 状态符合预期
        else:
            if should_connect:
                logger.debug("连接状态正常（交易时段内）")
            else:
                logger.debug("连接状态正常（非交易时段）")

    def register_trading_start_callback(self, callback: Callable):
        """注册交易时段开始回调"""
        self._on_trading_start_callbacks.append(callback)

    def register_trading_end_callback(self, callback: Callable):
        """注册交易时段结束回调"""
        self._on_trading_end_callbacks.append(callback)

    def _trigger_trading_start_callbacks(self):
        """触发交易开始回调"""
        for callback in self._on_trading_start_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"交易开始回调错误: {e}")

    def _trigger_trading_end_callbacks(self):
        """触发交易结束回调"""
        for callback in self._on_trading_end_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"交易结束回调错误: {e}")

    def get_status(self) -> dict:
        """
        获取调度器状态

        Returns:
            状态字典
        """
        should_connect, reason = self.should_connect_now()
        now_utc = self.tz_manager.now_utc()
        now_market = self.tz_manager.utc_to_market(now_utc)
        today = now_market.date()

        return {
            'scheduler_running': self._running,
            'current_time': {
                'utc': now_utc.isoformat(),
                'market': now_market.isoformat(),
                'local': self.tz_manager.utc_to_local(now_utc).isoformat(),
                'formatted': self.tz_manager.format_dual_timezone(now_utc)
            },
            'trading_day': {
                'date': today.isoformat(),
                'is_trading_day': self.calendar.is_trading_day(today),
                'is_half_day': self.calendar.is_half_day(today),
                'next_trading_day': self.calendar.next_trading_day(today).isoformat()
            },
            'connection': {
                'should_connect': should_connect,
                'reason': reason,
                'is_connected': self.conn_manager.is_connected(),
                'is_ready': self.conn_manager.is_ready(),
                'connection_status': self.conn_manager.get_status()
            },
            'timezone': {
                'is_dst': self.tz_manager.is_dst(),
                'utc_offset': self.tz_manager.get_utc_offset(),
                'timezone_name': 'EDT' if self.tz_manager.is_dst() else 'EST'
            }
        }
