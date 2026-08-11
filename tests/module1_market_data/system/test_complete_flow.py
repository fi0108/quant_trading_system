#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
集成测试 - 完整数据流测试

测试流程：
1. 连接IBKR模拟盘
2. 初始化PostgreSQL和Redis
3. 订阅实时数据
4. 验证数据流
5. 测试历史回填
6. 运行质量检查

运行前确保：
- IBKR Gateway/TWS模拟盘已启动（端口4002）
- PostgreSQL已安装并创建数据库
- Redis已启动
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import asyncio
from datetime import datetime, date
import configparser
import logging

from ib_insync import IB
from src.core.timezone_manager import TimezoneManager
from src.calendar.trading_calendar import TradingCalendar
from src.connection.manager import ConnectionManager
from src.connection.scheduler import MarketDataScheduler
from src.connection.market_data.subscriber import MarketDataSubscriber
from src.connection.market_data.validator import DataValidator
from src.connection.storage.redis_writer import RedisWriter
from src.connection.storage.postgres_writer import PostgresWriter
from src.connection.market_data.historical_sync import HistoricalDataSync
from src.connection.market_data.quality_checker import DataQualityChecker

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegrationTest:
    """集成测试类"""

    def __init__(self, config_file='config/integration_test.ini'):
        """初始化测试"""
        self.config = self._load_config(config_file)

        # 核心组件
        self.ib = None
        self.tz_manager = None
        self.calendar = None
        self.conn_manager = None
        self.subscriber = None
        self.validator = None
        self.redis_writer = None
        self.postgres_writer = None
        self.historical_sync = None
        self.quality_checker = None
        self.scheduler = None

        # 统计
        self.bars_received = 0
        self.bars_validated = 0
        self.bars_stored = 0

    def _load_config(self, config_file):
        """加载配置文件"""
        config = configparser.ConfigParser()

        if os.path.exists(config_file):
            config.read(config_file)
            logger.info(f"配置文件已加载: {config_file}")
        else:
            logger.warning(f"配置文件不存在: {config_file}，使用默认配置")
            # 使用默认配置
            config['ibkr'] = {
                'host': '127.0.0.1',
                'port': '4002',
                'client_id': '1',
                'data_type': '3'
            }
            config['postgres'] = {
                'host': 'localhost',
                'port': '5432',
                'database': 'quant_trading',
                'user': 'postgres',
                'password': 'postgres'
            }
            config['redis'] = {
                'host': 'localhost',
                'port': '6379',
                'db': '0'
            }
            config['subscription'] = {
                'symbols': 'AAPL,TSLA'
            }

        return config

    async def setup(self):
        """初始化所有组件"""
        logger.info("=" * 60)
        logger.info("开始初始化组件")
        logger.info("=" * 60)

        # 1. 时区管理器和交易日历
        logger.info("1. 初始化时区管理器和交易日历")
        self.tz_manager = TimezoneManager()
        self.calendar = TradingCalendar()
        logger.info(f"   当前时间: {self.tz_manager.format_dual_timezone(self.tz_manager.now_utc())}")
        logger.info(f"   今天是交易日: {self.calendar.is_trading_day(date.today())}")

        # 2. 连接IBKR
        logger.info("2. 连接IBKR模拟盘")
        self.ib = IB()
        try:
            await self.ib.connectAsync(
                self.config['ibkr']['host'],
                int(self.config['ibkr']['port']),
                clientId=int(self.config['ibkr']['client_id']),
                timeout=15
            )
            logger.info(f"   IBKR已连接: {self.config['ibkr']['host']}:{self.config['ibkr']['port']}")
        except Exception as e:
            logger.error(f"   IBKR连接失败: {e}")
            raise

        # 3. 初始化PostgreSQL
        logger.info("3. 初始化PostgreSQL")
        db_url = (
            f"postgresql://{self.config['postgres']['user']}:{self.config['postgres']['password']}"
            f"@{self.config['postgres']['host']}:{self.config['postgres']['port']}"
            f"/{self.config['postgres']['database']}"
        )
        self.postgres_writer = PostgresWriter(db_url)
        if await self.postgres_writer.init_pool():
            logger.info("   PostgreSQL连接池已创建")
        else:
            logger.error("   PostgreSQL连接池创建失败")
            raise Exception("PostgreSQL initialization failed")

        await self.postgres_writer.start()
        logger.info("   PostgreSQL批量写入任务已启动")

        # 4. 初始化Redis
        logger.info("4. 初始化Redis")
        redis_url = f"redis://{self.config['redis']['host']}:{self.config['redis']['port']}/{self.config['redis']['db']}"
        self.redis_writer = RedisWriter(redis_url)
        if self.redis_writer.connect():
            logger.info("   Redis已连接")
        else:
            logger.warning("   Redis连接失败（非致命）")

        # 5. 创建订阅器和验证器
        logger.info("5. 创建订阅器和验证器")
        self.subscriber = MarketDataSubscriber(
            self.ib,
            data_type=int(self.config['ibkr']['data_type'])
        )
        self.validator = DataValidator()
        logger.info("   订阅器和验证器已创建")

        # 6. 创建历史回填器和质量检查器
        logger.info("6. 创建历史回填器和质量检查器")
        self.historical_sync = HistoricalDataSync(
            self.ib,
            self.postgres_writer,
            self.calendar,
            self.tz_manager
        )
        self.quality_checker = DataQualityChecker(
            self.ib,
            self.postgres_writer,
            self.tz_manager
        )
        logger.info("   历史回填器和质量检查器已创建")

        logger.info("=" * 60)
        logger.info("所有组件初始化完成")
        logger.info("=" * 60)

    async def test_subscription(self):
        """测试实时订阅"""
        logger.info("\n" + "=" * 60)
        logger.info("测试1: 实时数据订阅")
        logger.info("=" * 60)

        # 注册回调
        def on_bar_data(bar):
            self.bars_received += 1

            # 验证数据
            is_valid, msg, fixed_data = self.validator.validate(bar)

            if is_valid:
                self.bars_validated += 1
                final_data = fixed_data if fixed_data else bar

                # 写入Redis
                if self.redis_writer.is_connected():
                    self.redis_writer.write_bar(final_data['symbol'], final_data)

                # 写入PostgreSQL
                self.postgres_writer.add_bar(final_data)
                self.bars_stored += 1

                logger.info(f"   收到Bar: {final_data['symbol']} {final_data['close']:.2f} (总计:{self.bars_received})")
            else:
                logger.warning(f"   验证失败: {msg}")

        self.subscriber.register_callback(on_bar_data)

        # 订阅标的
        symbols = self.config['subscription']['symbols'].split(',')
        logger.info(f"订阅标的: {symbols}")

        results = self.subscriber.subscribe(symbols)
        logger.info(f"订阅结果: {results}")

        # 等待接收数据
        logger.info("等待接收数据（60秒）...")
        await asyncio.sleep(60)

        # 统计
        logger.info(f"\n接收统计:")
        logger.info(f"  接收: {self.bars_received}根")
        logger.info(f"  验证通过: {self.bars_validated}根")
        logger.info(f"  已存储: {self.bars_stored}根")

        if self.bars_received > 0:
            logger.info("✓ 实时订阅测试通过")
            return True
        else:
            logger.warning("✗ 未接收到数据（可能非交易时段）")
            return False

    async def test_historical_backfill(self):
        """测试历史回填"""
        logger.info("\n" + "=" * 60)
        logger.info("测试2: 历史数据回填")
        logger.info("=" * 60)

        symbols = ['AAPL']
        logger.info(f"回填标的: {symbols}")
        logger.info(f"回填范围: 最近7个交易日")

        results = await self.historical_sync.backfill_recent_days(symbols, days=7)

        logger.info(f"\n回填结果: {results}")

        for symbol, count in results.items():
            if count > 0:
                logger.info(f"  {symbol}: 回填{count}根Bar ✓")
            elif count == 0:
                logger.info(f"  {symbol}: 数据完整，无需回填 ✓")
            else:
                logger.warning(f"  {symbol}: 回填失败 ✗")

        return True

    async def test_quality_check(self):
        """测试质量检查"""
        logger.info("\n" + "=" * 60)
        logger.info("测试3: 数据质量检查")
        logger.info("=" * 60)

        symbols = ['AAPL']
        logger.info(f"检查标的: {symbols}")

        results = await self.quality_checker.check_today_data(symbols)

        logger.info(f"\n质量检查结果:")
        for symbol, result in results.items():
            if result.get('success'):
                if result.get('has_differences'):
                    logger.warning(f"  {symbol}: 发现差异 {result['difference_count']}个, "
                                 f"最大差异{result['max_difference']*100:.2f}%")
                    if result.get('corrected'):
                        logger.info(f"  {symbol}: 已自动修正 ✓")
                else:
                    logger.info(f"  {symbol}: 数据质量良好 ✓")
            else:
                logger.warning(f"  {symbol}: 检查失败 - {result.get('reason')} ✗")

        return True

    async def test_storage_query(self):
        """测试存储查询"""
        logger.info("\n" + "=" * 60)
        logger.info("测试4: 存储查询")
        logger.info("=" * 60)

        symbol = 'AAPL'

        # 查询PostgreSQL
        logger.info(f"1. PostgreSQL查询:")
        bars = await self.postgres_writer.query_bars(symbol, limit=10)
        logger.info(f"   查询到{len(bars)}根Bar")
        if bars:
            latest = bars[0]
            logger.info(f"   最新Bar: {latest['timestamp']} close={latest['close']}")

        # 查询Redis
        logger.info(f"2. Redis查询:")
        if self.redis_writer.is_connected():
            redis_bars = self.redis_writer.get_latest_bars(symbol, count=10)
            logger.info(f"   查询到{len(redis_bars)}根Bar")
            if redis_bars:
                logger.info(f"   最新Bar: {redis_bars[0]['timestamp']}")

        return True

    async def cleanup(self):
        """清理资源"""
        logger.info("\n" + "=" * 60)
        logger.info("清理资源")
        logger.info("=" * 60)

        # 停止PostgreSQL
        if self.postgres_writer:
            await self.postgres_writer.stop()
            await self.postgres_writer.close_pool()
            logger.info("PostgreSQL已关闭")

        # 断开Redis
        if self.redis_writer:
            self.redis_writer.disconnect()
            logger.info("Redis已断开")

        # 断开IBKR
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            logger.info("IBKR已断开")

    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("\n" + "=" * 60)
        logger.info("开始集成测试")
        logger.info("=" * 60)

        try:
            # 初始化
            await self.setup()

            # 运行测试
            results = []

            # 测试1: 实时订阅（如果在交易时段）
            should_connect, reason = self._check_trading_time()
            if should_connect:
                result = await self.test_subscription()
                results.append(("实时订阅", result))
            else:
                logger.info(f"\n跳过实时订阅测试: {reason}")
                results.append(("实时订阅", None))

            # 测试2: 历史回填
            result = await self.test_historical_backfill()
            results.append(("历史回填", result))

            # 测试3: 质量检查
            result = await self.test_quality_check()
            results.append(("质量检查", result))

            # 测试4: 存储查询
            result = await self.test_storage_query()
            results.append(("存储查询", result))

            # 打印总结
            logger.info("\n" + "=" * 60)
            logger.info("测试总结")
            logger.info("=" * 60)

            for test_name, result in results:
                if result is True:
                    logger.info(f"  {test_name}: 通过 ✓")
                elif result is False:
                    logger.info(f"  {test_name}: 失败 ✗")
                else:
                    logger.info(f"  {test_name}: 跳过 -")

            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"测试失败: {e}", exc_info=True)

        finally:
            await self.cleanup()

    def _check_trading_time(self):
        """检查是否在交易时段"""
        now_utc = self.tz_manager.now_utc()
        now_market = self.tz_manager.utc_to_market(now_utc)
        today = now_market.date()

        is_trading_day = self.calendar.is_trading_day(today)
        is_trading_time = self.tz_manager.is_trading_time(now_utc)

        if not is_trading_day:
            return False, f"非交易日（{today.strftime('%A')}）"

        if not is_trading_time:
            return False, "非交易时段"

        return True, "交易时段内"


async def main():
    """主函数"""
    test = IntegrationTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
