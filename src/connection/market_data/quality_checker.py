"""
数据质量检查器

职责：
1. 收盘后对比实时数据与官方历史数据
2. 检测数据差异
3. 自动修正差异数据
4. 记录质量日志
"""

import asyncio
from typing import List, Dict, Tuple, Optional
from datetime import datetime, date, time, timedelta
from ib_insync import IB, Stock
import logging

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """
    数据质量检查器

    功能：
    - 每日收盘后自动检查
    - 对比实时数据与官方历史数据
    - 自动修正差异超过阈值的数据
    - 记录质量日志
    """

    def __init__(
        self,
        ib_client: IB,
        postgres_writer,
        timezone_manager,
        difference_threshold: float = 0.005  # 差异阈值0.5%
    ):
        """
        初始化数据质量检查器

        Args:
            ib_client: IB连接客户端
            postgres_writer: PostgreSQL写入器
            timezone_manager: 时区管理器
            difference_threshold: 差异阈值（0.005 = 0.5%）
        """
        self.ib = ib_client
        self.db = postgres_writer
        self.tz_manager = timezone_manager
        self.difference_threshold = difference_threshold

        # 统计
        self._checks_performed = 0
        self._differences_found = 0
        self._corrections_made = 0
        self._failed_checks = 0

    async def check_today_data(
        self,
        symbols: List[str]
    ) -> Dict[str, dict]:
        """
        检查今日数据质量

        Args:
            symbols: 标的列表

        Returns:
            检查结果 {symbol: result_dict}
        """
        today = date.today()
        logger.info(f"开始检查{today}的数据质量，标的数：{len(symbols)}")

        results = {}

        for symbol in symbols:
            try:
                result = await self._check_symbol_data(symbol, today)
                results[symbol] = result
                self._checks_performed += 1

            except Exception as e:
                logger.error(f"[{symbol}] 质量检查失败: {e}")
                results[symbol] = {
                    'success': False,
                    'error': str(e)
                }
                self._failed_checks += 1

        logger.info(f"质量检查完成: {results}")
        return results

    async def check_date_data(
        self,
        symbol: str,
        check_date: date
    ) -> dict:
        """
        检查指定日期的数据质量

        Args:
            symbol: 标的代码
            check_date: 检查日期

        Returns:
            检查结果字典
        """
        logger.info(f"[{symbol}] 检查{check_date}的数据质量")
        return await self._check_symbol_data(symbol, check_date)

    async def _check_symbol_data(
        self,
        symbol: str,
        check_date: date
    ) -> dict:
        """
        检查单个标的的数据质量

        Args:
            symbol: 标的代码
            check_date: 检查日期

        Returns:
            检查结果字典
        """
        # 1. 获取实时数据（数据库中的）
        realtime_bars = await self._get_realtime_bars(symbol, check_date)

        if not realtime_bars:
            logger.warning(f"[{symbol}] {check_date}: 无实时数据")
            return {
                'success': False,
                'reason': '无实时数据'
            }

        # 2. 获取官方历史数据（从IBKR下载）
        historical_bars = await self._get_historical_bars(symbol, check_date)

        if not historical_bars:
            logger.warning(f"[{symbol}] {check_date}: 无法获取历史数据")
            return {
                'success': False,
                'reason': '无法获取历史数据'
            }

        # 3. 对比数据
        comparison = self._compare_bars(realtime_bars, historical_bars)

        # 4. 处理差异
        if comparison['has_differences']:
            self._differences_found += 1
            logger.warning(f"[{symbol}] {check_date}: 发现{comparison['difference_count']}个差异")

            # 差异超过阈值，自动修正
            if comparison['max_difference'] > self.difference_threshold:
                await self._correct_differences(symbol, check_date, historical_bars)
                self._corrections_made += 1
                logger.info(f"[{symbol}] {check_date}: 数据已自动修正")

                return {
                    'success': True,
                    'has_differences': True,
                    'difference_count': comparison['difference_count'],
                    'max_difference': comparison['max_difference'],
                    'corrected': True
                }
            else:
                # 差异较小，仅记录日志
                logger.info(f"[{symbol}] {check_date}: 差异较小，不修正")
                return {
                    'success': True,
                    'has_differences': True,
                    'difference_count': comparison['difference_count'],
                    'max_difference': comparison['max_difference'],
                    'corrected': False
                }
        else:
            logger.info(f"[{symbol}] {check_date}: 数据质量良好")
            return {
                'success': True,
                'has_differences': False,
                'difference_count': 0,
                'max_difference': 0.0,
                'corrected': False
            }

    async def _get_realtime_bars(
        self,
        symbol: str,
        check_date: date
    ) -> List[Dict]:
        """
        获取实时数据（从数据库）

        Args:
            symbol: 标的代码
            check_date: 日期

        Returns:
            Bar数据列表
        """
        start_time = datetime.combine(check_date, time.min)
        end_time = datetime.combine(check_date, time.max)

        bars = await self.db.query_bars(
            symbol,
            start_time=start_time,
            end_time=end_time,
            limit=500
        )

        # 只取source='realtime'的数据
        realtime_bars = [bar for bar in bars if bar.get('source') == 'realtime']

        logger.debug(f"[{symbol}] {check_date}: 实时数据{len(realtime_bars)}根")
        return realtime_bars

    async def _get_historical_bars(
        self,
        symbol: str,
        check_date: date
    ) -> List[Dict]:
        """
        获取官方历史数据（从IBKR）

        Args:
            symbol: 标的代码
            check_date: 日期

        Returns:
            Bar数据列表
        """
        if not self.ib.isConnected():
            logger.error("IB未连接，无法获取历史数据")
            return []

        try:
            # 创建合约
            contract = Stock(symbol, 'SMART', 'USD')

            # 构造结束时间（当日收盘后）
            end_datetime = datetime.combine(check_date, time.max)
            end_datetime = self.tz_manager.market_tz.localize(end_datetime)

            # 请求历史数据
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            # 转换为标准格式
            bar_data_list = []
            for bar in bars:
                bar_data = {
                    'timestamp': bar.date,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume),
                }
                bar_data_list.append(bar_data)

            logger.debug(f"[{symbol}] {check_date}: 历史数据{len(bar_data_list)}根")
            return bar_data_list

        except Exception as e:
            logger.error(f"[{symbol}] {check_date} 获取历史数据失败: {e}")
            return []

    def _compare_bars(
        self,
        realtime_bars: List[Dict],
        historical_bars: List[Dict]
    ) -> dict:
        """
        对比实时数据和历史数据

        Args:
            realtime_bars: 实时数据
            historical_bars: 历史数据

        Returns:
            对比结果
        """
        # 将历史数据按时间戳索引
        historical_dict = {
            bar['timestamp']: bar
            for bar in historical_bars
        }

        differences = []
        max_difference = 0.0

        for rt_bar in realtime_bars:
            timestamp = rt_bar['timestamp']

            # 查找对应的历史数据
            if timestamp not in historical_dict:
                continue

            hist_bar = historical_dict[timestamp]

            # 对比价格
            price_diff = self._calculate_price_difference(rt_bar, hist_bar)

            if price_diff > 0.0:
                differences.append({
                    'timestamp': timestamp,
                    'realtime': rt_bar,
                    'historical': hist_bar,
                    'difference': price_diff
                })

                max_difference = max(max_difference, price_diff)

        return {
            'has_differences': len(differences) > 0,
            'difference_count': len(differences),
            'max_difference': max_difference,
            'differences': differences
        }

    def _calculate_price_difference(
        self,
        bar1: Dict,
        bar2: Dict
    ) -> float:
        """
        计算两根Bar的价格差异

        Args:
            bar1: Bar数据1
            bar2: Bar数据2

        Returns:
            最大差异百分比
        """
        fields = ['open', 'high', 'low', 'close']
        max_diff = 0.0

        for field in fields:
            val1 = bar1.get(field, 0)
            val2 = bar2.get(field, 0)

            if val2 > 0:
                diff = abs(val1 - val2) / val2
                max_diff = max(max_diff, diff)

        return max_diff

    async def _correct_differences(
        self,
        symbol: str,
        check_date: date,
        historical_bars: List[Dict]
    ):
        """
        修正差异数据

        Args:
            symbol: 标的代码
            check_date: 日期
            historical_bars: 历史数据（正确的）
        """
        logger.info(f"[{symbol}] {check_date}: 开始修正数据")

        # 删除旧数据
        start_time = datetime.combine(check_date, time.min)
        end_time = datetime.combine(check_date, time.max)

        deleted = await self.db.delete_bars(symbol, start_time, end_time)
        logger.debug(f"[{symbol}] {check_date}: 删除{deleted}根旧数据")

        # 写入正确的历史数据
        for bar in historical_bars:
            bar_data = {
                'symbol': symbol,
                'timestamp': bar['timestamp'],
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar['volume'],
                'source': 'historical_corrected'  # 标记为修正后的数据
            }
            self.db.add_bar(bar_data)

        # 刷新缓冲区
        await self.db.flush()

        logger.info(f"[{symbol}] {check_date}: 修正完成，写入{len(historical_bars)}根Bar")

    async def schedule_daily_check(
        self,
        symbols: List[str],
        check_time: time = time(16, 30)  # 美东16:30（收盘后30分钟）
    ):
        """
        调度每日检查

        Args:
            symbols: 标的列表
            check_time: 检查时间（美东时间）
        """
        logger.info(f"每日数据质量检查已调度: {check_time}")

        while True:
            try:
                # 计算下次检查时间
                now_utc = datetime.utcnow()
                now_market = self.tz_manager.utc_to_market(now_utc)

                today = now_market.date()
                target_datetime = datetime.combine(today, check_time)
                target_datetime = self.tz_manager.market_tz.localize(target_datetime)

                # 如果今天的检查时间已过，等待到明天
                if now_market >= target_datetime:
                    target_datetime += timedelta(days=1)

                # 计算等待时间
                target_utc = self.tz_manager.market_to_utc(target_datetime)
                wait_seconds = (target_utc - now_utc).total_seconds()

                logger.info(f"下次质量检查: {target_datetime} (等待{wait_seconds/3600:.1f}小时)")

                # 等待
                await asyncio.sleep(wait_seconds)

                # 执行检查
                await self.check_today_data(symbols)

            except asyncio.CancelledError:
                logger.info("每日质量检查已取消")
                break
            except Exception as e:
                logger.error(f"每日质量检查错误: {e}", exc_info=True)
                # 出错后等待1小时重试
                await asyncio.sleep(3600)

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            'checks_performed': self._checks_performed,
            'differences_found': self._differences_found,
            'corrections_made': self._corrections_made,
            'failed_checks': self._failed_checks,
            'difference_threshold': f"{self.difference_threshold * 100}%",
            'correction_rate': (
                f"{self._corrections_made / self._differences_found * 100:.1f}%"
                if self._differences_found > 0
                else "N/A"
            )
        }

    def reset_stats(self):
        """重置统计信息"""
        self._checks_performed = 0
        self._differences_found = 0
        self._corrections_made = 0
        self._failed_checks = 0
        logger.debug("质量检查统计信息已重置")
