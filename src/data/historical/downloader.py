"""
历史数据下载器

从 IBKR 下载历史数据并存储到数据库
"""

import time
from typing import Optional, List
from datetime import datetime, timedelta

from ib_insync import Stock, util
from common.logger import log
from data.ibkr_client import IBKRClient
from data.storage.models import BarModel, database
from strategy.resolution import Resolution


class HistoricalDataDownloader:
    """
    历史数据下载器

    功能：
    - 从 IBKR 下载历史数据
    - 存储到 PostgreSQL
    - 支持断点续传
    - 自动处理分页和限流
    """

    # IBKR 限制
    MAX_BARS_PER_REQUEST = 2000  # 单次请求最大 bar 数
    REQUEST_DELAY = 0.5  # 请求间隔（秒）

    def __init__(self, ibkr_client: IBKRClient):
        """
        初始化下载器

        Args:
            ibkr_client: IBKR 客户端
        """
        self.ibkr_client = ibkr_client

    @staticmethod
    def _normalize_timestamp(ts) -> datetime:
        """
        统一时间类型转换

        IBKR 返回的时间类型可能是：
        - datetime.date (日线)
        - datetime.datetime (naive, 无时区)
        - datetime.datetime (aware, 有时区)

        统一转换为：datetime.datetime (naive, 无时区)

        Args:
            ts: 任意时间类型

        Returns:
            标准化的 datetime (naive)
        """
        from datetime import date

        # 如果是 date，转换为 datetime
        if isinstance(ts, date) and not isinstance(ts, datetime):
            return datetime.combine(ts, datetime.min.time())

        # 如果是 datetime
        if isinstance(ts, datetime):
            # 如果有时区，转换为 naive (去掉时区信息)
            if ts.tzinfo is not None:
                return ts.replace(tzinfo=None)
            return ts

        # 其他情况，尝试直接返回
        return ts

    def download(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        resolution: Resolution = Resolution.Daily,
        what_to_show: str = "TRADES"
    ) -> int:
        """
        下载历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            resolution: 时间周期
            what_to_show: 数据类型 (TRADES, MIDPOINT, BID, ASK)

        Returns:
            下载的 bar 数量
        """
        if not self.ibkr_client.is_connected():
            log.error("IBKR not connected")
            return 0

        log.info(f"Downloading {symbol} {resolution} from {start_date} to {end_date}")

        # 解析日期
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # 检查已有数据
        existing_range = self._get_existing_range(symbol, resolution)
        if existing_range:
            log.info(f"Existing data: {existing_range[0]} to {existing_range[1]}")
            # TODO: 智能跳过已有数据

        # 创建合约
        contract = Stock(symbol, 'SMART', 'USD')

        # 分段下载
        total_bars = 0
        current_end = end_dt

        log.info(f"Download strategy: from {end_dt} backwards to {start_dt}")

        while current_end > start_dt:
            # 下载一段数据
            log.debug(f"Requesting data ending at {current_end}, duration: {self._get_duration_string(resolution)}")

            bars = self._download_chunk(
                contract=contract,
                end_datetime=current_end,
                duration=self._get_duration_string(resolution),
                bar_size=resolution.bar_size,
                what_to_show=what_to_show
            )

            if not bars:
                log.warning(f"No data returned for {symbol} ending at {current_end}")
                break

            # 打印下载的日期范围
            if bars:
                first_bar_date = bars[0].date
                last_bar_date = bars[-1].date
                log.info(f"Received {len(bars)} bars: {first_bar_date} to {last_bar_date}")

            # 存储到数据库（过滤掉早于 start_date 的数据）
            saved_count = self._save_bars(symbol, bars, resolution, start_dt)
            total_bars += saved_count

            log.info(f"Saved {saved_count} bars (total: {total_bars})")

            # 计算下一段的结束时间（统一时间类型）
            earliest_bar_time = self._normalize_timestamp(bars[0].date)

            # 如果最早的数据已经早于或等于 start_date，停止下载
            if earliest_bar_time <= start_dt:
                log.info(f"Reached start date {start_dt}, stopping download")
                break

            current_end = earliest_bar_time - timedelta(seconds=1)

            # 限流
            time.sleep(self.REQUEST_DELAY)

        log.info(f"Download completed: {total_bars} bars saved for {symbol}")
        return total_bars

    def _download_chunk(
        self,
        contract,
        end_datetime: datetime,
        duration: str,
        bar_size: str,
        what_to_show: str
    ) -> List:
        """
        下载一段数据

        Args:
            contract: IBKR 合约
            end_datetime: 结束时间
            duration: 持续时间（如 "1 Y", "6 M"）
            bar_size: Bar 大小
            what_to_show: 数据类型

        Returns:
            Bar 列表
        """
        try:
            bars = self.ibkr_client.ib.reqHistoricalData(
                contract=contract,
                endDateTime=end_datetime,
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=True,  # 只获取常规交易时间
                formatDate=1  # 返回 datetime 对象
            )

            return bars

        except Exception as e:
            log.error(f"Error downloading data: {e}")
            return []

    def _save_bars(
        self,
        symbol: str,
        bars: List,
        resolution: Resolution,
        start_dt: Optional[datetime] = None
    ) -> int:
        """
        保存 bars 到数据库

        Args:
            symbol: 股票代码
            bars: Bar 列表
            resolution: 时间周期
            start_dt: 起始日期（可选），早于此日期的数据会被过滤

        Returns:
            保存的数量
        """
        if not bars:
            return 0

        saved_count = 0

        with database.atomic():
            for bar in bars:
                try:
                    # 统一时间类型转换
                    bar_timestamp = self._normalize_timestamp(bar.date)

                    # 如果指定了 start_dt，过滤掉早于它的数据
                    if start_dt and bar_timestamp < start_dt:
                        log.debug(f"Skipping bar {bar_timestamp} (before {start_dt})")
                        continue

                    # 使用 INSERT ... ON CONFLICT DO NOTHING 去重
                    BarModel.create(
                        symbol=symbol,
                        timestamp=bar_timestamp,
                        bar_size=resolution.bar_size,
                        open=float(bar.open),
                        high=float(bar.high),
                        low=float(bar.low),
                        close=float(bar.close),
                        volume=int(bar.volume)
                    )
                    saved_count += 1

                except Exception as e:
                    # 重复数据会抛异常，跳过
                    if 'duplicate key' in str(e).lower():
                        continue
                    else:
                        log.error(f"Error saving bar: {e}")

        return saved_count

    def _get_existing_range(
        self,
        symbol: str,
        resolution: Resolution
    ) -> Optional[tuple]:
        """
        获取已有数据的日期范围

        Args:
            symbol: 股票代码
            resolution: 时间周期

        Returns:
            (最早日期, 最晚日期) 或 None
        """
        try:
            from peewee import fn

            query = (
                BarModel
                .select(
                    fn.MIN(BarModel.timestamp).alias('min_date'),
                    fn.MAX(BarModel.timestamp).alias('max_date')
                )
                .where(
                    (BarModel.symbol == symbol) &
                    (BarModel.bar_size == resolution.bar_size)
                )
            )

            result = query.get()

            if result.min_date and result.max_date:
                return (result.min_date, result.max_date)

            return None

        except Exception as e:
            log.error(f"Error getting existing range: {e}")
            return None

    def _get_duration_string(self, resolution: Resolution) -> str:
        """
        根据时间周期获取合适的下载时长

        Args:
            resolution: 时间周期

        Returns:
            IBKR duration 字符串
        """
        # 根据周期选择合适的下载时长
        if resolution == Resolution.Daily:
            return "1 Y"  # 日线：一次下载1年
        elif resolution == Resolution.Hour:
            return "1 M"  # 小时线：一次下载1个月
        elif resolution == Resolution.Minute:
            return "1 W"  # 分钟线：一次下载1周
        else:
            return "1 D"  # 其他：一次下载1天

    def get_missing_ranges(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        resolution: Resolution
    ) -> List[tuple]:
        """
        获取缺失的日期范围

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            resolution: 时间周期

        Returns:
            缺失的日期范围列表 [(start1, end1), (start2, end2), ...]
        """
        # TODO: 实现智能检测缺失范围
        # 目前简单返回整个范围
        return [(start_date, end_date)]
