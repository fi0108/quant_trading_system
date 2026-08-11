#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
快速集成测试 - 简化版

测试内容：
1. 连接IBKR模拟盘
2. 初始化数据库
3. 订阅实时数据（如果在交易时段）
4. 测试历史回填
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import asyncio
import pytest
from datetime import datetime, date
import logging

from ib_insync import IB
from src.core.timezone_manager import TimezoneManager
from src.calendar.trading_calendar import TradingCalendar
from src.connection.storage.redis_writer import RedisWriter
from src.connection.storage.postgres_writer import PostgresWriter
from src.connection.market_data.subscriber import MarketDataSubscriber
from src.connection.market_data.validator import DataValidator
from src.connection.market_data.historical_sync import HistoricalDataSync

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# 配置（直接在代码中修改）
# ============================================
IBKR_HOST = '127.0.0.1'
IBKR_PORT = 4002  # 模拟盘端口
IBKR_CLIENT_ID = 1

POSTGRES_URL = 'postgresql://postgres:postgres@localhost:5432/quant_trading'
REDIS_URL = 'redis://localhost:6379/0'

SYMBOLS = ['AAPL', 'TSLA']
# ============================================


@pytest.mark.asyncio
async def test_basic_connection():
    """测试1: 基础连接"""
    logger.info("=" * 60)
    logger.info("Test 1: Basic Connection")
    logger.info("=" * 60)

    # 时区管理器
    tz_manager = TimezoneManager()
    logger.info(f"Current time: {tz_manager.format_dual_timezone(tz_manager.now_utc())}")

    # 交易日历
    calendar = TradingCalendar()
    today = date.today()
    is_trading = calendar.is_trading_day(today)
    logger.info(f"Is trading day: {is_trading}")

    # 连接IBKR
    ib = IB()
    try:
        logger.info(f"Connecting to IBKR {IBKR_HOST}:{IBKR_PORT}...")
        await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID, timeout=15)
        logger.info("[OK] IBKR connected")

        # 断开
        ib.disconnect()
        logger.info("[OK] IBKR disconnected")
        return True

    except Exception as e:
        logger.error(f"[FAIL] IBKR connection failed: {e}")
        return False


@pytest.mark.asyncio
async def test_database_connection():
    """测试2: 数据库连接"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 2: Database Connection")
    logger.info("=" * 60)

    # PostgreSQL
    try:
        logger.info("Connecting to PostgreSQL...")
        postgres = PostgresWriter(POSTGRES_URL)
        if await postgres.init_pool():
            logger.info("[OK] PostgreSQL connected")
            await postgres.close_pool()
        else:
            logger.error("[FAIL] PostgreSQL connection failed")
            return False
    except Exception as e:
        logger.error(f"[FAIL] PostgreSQL error: {e}")
        return False

    # Redis
    try:
        logger.info("Connecting to Redis...")
        redis = RedisWriter(REDIS_URL)
        if redis.connect():
            logger.info("[OK] Redis connected")
            redis.disconnect()
        else:
            logger.warning("[WARN] Redis connection failed (optional)")
    except Exception as e:
        logger.warning(f"[WARN] Redis error: {e} (optional)")

    return True


@pytest.mark.asyncio
async def test_subscription():
    """测试3: 实时订阅（交易时段）"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 3: Real-time Subscription")
    logger.info("=" * 60)

    # 检查是否交易时段
    tz_manager = TimezoneManager()
    calendar = TradingCalendar()

    now_utc = tz_manager.now_utc()
    now_market = tz_manager.utc_to_market(now_utc)
    today = now_market.date()

    is_trading_day = calendar.is_trading_day(today)
    is_trading_time = tz_manager.is_trading_time(now_utc)

    if not is_trading_day or not is_trading_time:
        logger.info(f"[SKIP] Not in trading hours (trading_day={is_trading_day}, trading_time={is_trading_time})")
        return None

    # 连接IBKR
    ib = IB()
    try:
        await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID, timeout=15)
        logger.info("[OK] IBKR connected")

        # 创建订阅器
        subscriber = MarketDataSubscriber(ib, data_type=3)
        validator = DataValidator()

        bars_received = [0]

        def on_bar(bar):
            bars_received[0] += 1
            is_valid, msg, _ = validator.validate(bar)
            logger.info(f"  Received: {bar['symbol']} {bar['close']:.2f} (valid={is_valid}, total={bars_received[0]})")

        subscriber.register_callback(on_bar)

        # 订阅
        logger.info(f"Subscribing to {SYMBOLS}...")
        results = subscriber.subscribe(SYMBOLS)
        logger.info(f"Subscription results: {results}")

        # 等待30秒接收数据
        logger.info("Waiting 30 seconds for data...")
        await asyncio.sleep(30)

        # 清理
        subscriber.unsubscribe_all()
        ib.disconnect()

        if bars_received[0] > 0:
            logger.info(f"[OK] Received {bars_received[0]} bars")
            return True
        else:
            logger.warning("[WARN] No bars received (maybe delayed data)")
            return False

    except Exception as e:
        logger.error(f"[FAIL] Subscription error: {e}")
        if ib.isConnected():
            ib.disconnect()
        return False


@pytest.mark.asyncio
async def test_historical_backfill():
    """测试4: 历史回填"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 4: Historical Backfill")
    logger.info("=" * 60)

    # 连接IBKR
    ib = IB()
    try:
        await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID, timeout=15)
        logger.info("[OK] IBKR connected")

        # 初始化数据库
        postgres = PostgresWriter(POSTGRES_URL)
        await postgres.init_pool()
        await postgres.start()

        # 创建回填器
        tz_manager = TimezoneManager()
        calendar = TradingCalendar()
        syncer = HistoricalDataSync(ib, postgres, calendar, tz_manager)

        # 回填最近3个交易日（减少测试时间）
        logger.info("Backfilling recent 3 trading days for AAPL...")
        results = await syncer.backfill_recent_days(['AAPL'], days=3)

        logger.info(f"Backfill results: {results}")

        # 清理
        await postgres.stop()
        await postgres.close_pool()
        ib.disconnect()

        if results.get('AAPL', -1) >= 0:
            logger.info("[OK] Backfill completed")
            return True
        else:
            logger.error("[FAIL] Backfill failed")
            return False

    except Exception as e:
        logger.error(f"[FAIL] Backfill error: {e}")
        if ib.isConnected():
            ib.disconnect()
        return False


async def main():
    """主测试流程"""
    logger.info("\n" + "=" * 60)
    logger.info("Quick Integration Test")
    logger.info("=" * 60)

    results = []

    # 测试1: 基础连接
    result = await test_basic_connection()
    results.append(("Basic Connection", result))

    # 测试2: 数据库连接
    result = await test_database_connection()
    results.append(("Database Connection", result))

    # 测试3: 实时订阅
    result = await test_subscription()
    results.append(("Real-time Subscription", result))

    # 测试4: 历史回填
    result = await test_historical_backfill()
    results.append(("Historical Backfill", result))

    # 打印总结
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    for test_name, result in results:
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
        else:
            status = "[SKIP]"
        logger.info(f"  {status} {test_name}")

    logger.info("=" * 60)


if __name__ == "__main__":
    print("\n")
    print("QUICK INTEGRATION TEST")
    print("=" * 60)
    print("Make sure before running:")
    print("1. IBKR Gateway/TWS is running on port 4002")
    print("2. PostgreSQL is running with database 'quant_trading'")
    print("3. Redis is running (optional)")
    print("\nEdit config in the script if needed:")
    print(f"  POSTGRES_URL = '{POSTGRES_URL}'")
    print("=" * 60)
    print("\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
