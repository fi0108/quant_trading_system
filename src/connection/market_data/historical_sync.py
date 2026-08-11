"""
历史数据回填器

职责：
1. 检测数据缺口
2. 回填历史数据
3. 限速控制（60请求/10分钟）
4. 断点续传
"""

import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, timedelta
from ib_insync import IB, Stock
import logging

logger = logging.getLogger(__name__)


class HistoricalDataSync:
    """
    历史数据回填器

    功能：
    - 自动检测数据缺口
    - 批量下载历史数据
    - IBKR API限速控制（60请求/10分钟）
    - 断点续传支持
    """

    # IBKR限制：60请求/10分钟
    MAX_REQUESTS = 60
    TIME_WINDOW = 600  # 10分钟（秒）

    def __init__(
        self,
        ib_client: IB,
        postgres_writer,
        trading_calendar,
        timezone_manager
    ):
        """
        初始化历史数据回填器

        Args:
            ib_client: IB连接客户端
            postgres_writer: PostgreSQL写入器
            trading_calendar: 交易日历管理器
            timezone_manager: 时区管理器
        """
        self.ib = ib_client
        self.db = postgres_writer
        self.calendar = trading_calendar
        self.tz_manager = timezone_manager

        # 限流器（令牌桶）
        self._tokens = self.MAX_REQUESTS
        self._last_refill = datetime.utcnow()
        self._token_lock = asyncio.Lock()

        # 统计
        self._requests_made = 0
        self._bars_downloaded = 0
        self._tasks_completed = 0
        self._tasks_failed = 0

    async def backfill_recent_days(
        self,
        symbols: List[str],
        days: int = 7
    ) -> Dict[str, int]:
        """
        回填最近N个交易日

        Args:
            symbols: 标的列表
            days: 回填天数

        Returns:
            每个标的回填的数量 {symbol: count}
        """
        logger.info(f"开始回填最近{days}个交易日的数据，标的数：{len(symbols)}")

        # 获取最近N个交易日
        trading_days = self._get_recent_trading_days(days)
        logger.info(f"找到{len(trading_days)}个交易日: {trading_days}")

        results = {}

        for symbol in symbols:
            try:
                # 检查每个交易日的缺口
                gaps = await self._check_gaps_for_symbol(symbol, trading_days)

                if gaps:
                    logger.info(f"[{symbol}] 发现{len(gaps)}个缺口")
                    filled = await self._fill_gaps(symbol, gaps)
                    results[symbol] = filled
                else:
                    logger.info(f"[{symbol}] 数据完整，无需回填")
                    results[symbol] = 0

            except Exception as e:
                logger.error(f"[{symbol}] 回填失败: {e}")
                results[symbol] = -1

        logger.info(f"回填完成: {results}")
        return results

    async def backfill_date_range(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> int:
        """
        回填指定日期范围

        Args:
            symbol: 标的代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            回填的Bar数量
        """
        logger.info(f"[{symbol}] 回填日期范围: {start_date} 至 {end_date}")

        # 获取日期范围内的所有交易日
        trading_days = self.calendar.get_trading_days(start_date, end_date)

        if not trading_days:
            logger.warning(f"日期范围内没有交易日")
            return 0

        logger.info(f"找到{len(trading_days)}个交易日")

        total_filled = 0
        for trading_day in trading_days:
            try:
                # 下载该日数据
                bars = await self._download_day_data(symbol, trading_day)

                if bars:
                    # 写入数据库
                    for bar in bars:
                        bar['source'] = 'historical'
                        self.db.add_bar(bar)

                    total_filled += len(bars)
                    logger.info(f"[{symbol}] {trading_day}: 回填{len(bars)}根Bar")

            except Exception as e:
                logger.error(f"[{symbol}] {trading_day} 回填失败: {e}")
                self._tasks_failed += 1

        # 刷新缓冲区
        await self.db.flush()

        logger.info(f"[{symbol}] 回填完成，共{total_filled}根Bar")
        return total_filled

    def _get_recent_trading_days(self, days: int) -> List[date]:
        """
        获取最近N个交易日

        Args:
            days: 天数

        Returns:
            交易日列表（从旧到新）
        """
        trading_days = []
        current_date = date.today()

        while len(trading_days) < days and current_date >= date(2020, 1, 1):
            if self.calendar.is_trading_day(current_date):
                trading_days.append(current_date)
            current_date -= timedelta(days=1)

        trading_days.reverse()  # 从旧到新
        return trading_days

    async def _check_gaps_for_symbol(
        self,
        symbol: str,
        trading_days: List[date]
    ) -> List[date]:
        """
        检查标的在指定交易日的数据缺口

        Args:
            symbol: 标的代码
            trading_days: 交易日列表

        Returns:
            有缺口的日期列表
        """
        gaps = []

        for trading_day in trading_days:
            # 查询该日数据量
            start_time = datetime.combine(trading_day, datetime.min.time())
            end_time = start_time + timedelta(days=1)

            count = await self.db.count_bars(
                symbol,
                start_time=start_time,
                end_time=end_time
            )

            # 完整交易日应有390根Bar（09:30-16:00，390分钟）
            expected_bars = 390

            if count < expected_bars:
                logger.debug(f"[{symbol}] {trading_day}: 缺口 {expected_bars - count}根")
                gaps.append(trading_day)

        return gaps

    async def _fill_gaps(
        self,
        symbol: str,
        gap_dates: List[date]
    ) -> int:
        """
        填充缺口

        Args:
            symbol: 标的代码
            gap_dates: 缺口日期列表

        Returns:
            填充的Bar数量
        """
        total_filled = 0

        for gap_date in gap_dates:
            try:
                # 限流
                await self._acquire_token()

                # 下载数据
                bars = await self._download_day_data(symbol, gap_date)

                if bars:
                    # 写入数据库
                    for bar in bars:
                        bar['source'] = 'backfill'
                        self.db.add_bar(bar)

                    total_filled += len(bars)
                    logger.info(f"[{symbol}] {gap_date}: 回填{len(bars)}根Bar")
                    self._tasks_completed += 1

            except Exception as e:
                logger.error(f"[{symbol}] {gap_date} 回填失败: {e}")
                self._tasks_failed += 1

        # 刷新缓冲区
        await self.db.flush()

        return total_filled

    async def _download_day_data(
        self,
        symbol: str,
        trading_day: date
    ) -> List[Dict]:
        """
        下载指定日期的数据

        Args:
            symbol: 标的代码
            trading_day: 交易日

        Returns:
            Bar数据列表
        """
        if not self.ib.isConnected():
            logger.error("IB未连接，无法下载数据")
            return []

        try:
            # 创建合约
            contract = Stock(symbol, 'SMART', 'USD')

            # 构造结束时间（当日收盘后）
            end_datetime = datetime.combine(trading_day, datetime.max.time())
            end_datetime = self.tz_manager.market_tz.localize(end_datetime)

            # 请求历史数据
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',  # 1天
                barSizeSetting='1 min',  # 1分钟
                whatToShow='TRADES',
                useRTH=True,  # 只要常规交易时段
                formatDate=1  # 返回字符串格式
            )

            self._requests_made += 1

            # 转换为标准格式
            bar_data_list = []
            for bar in bars:
                bar_data = {
                    'symbol': symbol,
                    'timestamp': bar.date,  # 已经是datetime对象
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume),
                    'source': 'historical'
                }
                bar_data_list.append(bar_data)
                self._bars_downloaded += 1

            logger.debug(f"[{symbol}] {trading_day}: 下载{len(bar_data_list)}根Bar")
            return bar_data_list

        except Exception as e:
            logger.error(f"[{symbol}] {trading_day} 下载失败: {e}")
            return []

    async def _acquire_token(self):
        """
        获取令牌（限流）

        使用令牌桶算法：
        - 容量：60个令牌
        - 补充速率：60个/10分钟 = 6个/分钟
        """
        async with self._token_lock:
            while True:
                # 补充令牌
                self._refill_tokens()

                # 检查是否有可用令牌
                if self._tokens >= 1:
                    self._tokens -= 1
                    return

                # 没有令牌，等待1秒后重试
                await asyncio.sleep(1)

    def _refill_tokens(self):
        """补充令牌"""
        now = datetime.utcnow()
        elapsed = (now - self._last_refill).total_seconds()

        # 计算应补充的令牌数
        tokens_to_add = (elapsed / self.TIME_WINDOW) * self.MAX_REQUESTS

        if tokens_to_add >= 1:
            self._tokens = min(self.MAX_REQUESTS, self._tokens + tokens_to_add)
            self._last_refill = now

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            'requests_made': self._requests_made,
            'bars_downloaded': self._bars_downloaded,
            'tasks_completed': self._tasks_completed,
            'tasks_failed': self._tasks_failed,
            'current_tokens': int(self._tokens),
            'max_tokens': self.MAX_REQUESTS,
            'rate_limit': f"{self.MAX_REQUESTS} 请求 / {self.TIME_WINDOW / 60:.0f} 分钟"
        }

    def reset_stats(self):
        """重置统计信息"""
        self._requests_made = 0
        self._bars_downloaded = 0
        self._tasks_completed = 0
        self._tasks_failed = 0
        logger.debug("统计信息已重置")
