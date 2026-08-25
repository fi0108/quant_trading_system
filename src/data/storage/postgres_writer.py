"""
PostgreSQL存储器

职责：
1. 历史数据冷存储
2. 批量异步写入（每10秒或100条触发）
3. 数据持久化
4. 支持查询和回测
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import asyncpg
import logging

logger = logging.getLogger(__name__)


class PostgresWriter:
    """
    PostgreSQL批量写入器

    特性：
    - 批量写入优化性能
    - 异步写入不阻塞实时数据接收
    - 幂等性保证（ON CONFLICT DO NOTHING）
    - 连接池管理
    """

    def __init__(
        self,
        db_url: str,
        batch_size: int = 100,
        batch_interval: int = 10,
        max_pool_size: int = 10,
        table_name: str = 'market_data_1min'
    ):
        """
        初始化PostgreSQL写入器

        Args:
            db_url: 数据库连接URL
            batch_size: 批量写入大小（条数）
            batch_interval: 批量写入间隔（秒）
            max_pool_size: 连接池最大连接数
            table_name: 目标表名
        """
        self.db_url = db_url
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.max_pool_size = max_pool_size
        self.table_name = table_name

        # 连接池
        self.pool: Optional[asyncpg.Pool] = None

        # 缓冲区
        self._buffer: List[Dict] = []
        self._buffer_lock = asyncio.Lock()

        # 故障队列（数据库不可用时缓存）
        self._failure_queue: List[Dict] = []
        self._max_queue_size = 1000

        # 批量写入任务
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

        # 统计
        self._writes_success = 0
        self._writes_failed = 0
        self._last_flush_time: Optional[datetime] = None
        self._last_error: Optional[str] = None

    async def init_pool(self) -> bool:
        """
        初始化连接池

        Returns:
            是否初始化成功
        """
        try:
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=self.max_pool_size,
                command_timeout=60
            )
            logger.info(f"PostgreSQL连接池已创建: max_size={self.max_pool_size}")
            return True

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"PostgreSQL连接池创建失败: {e}")
            return False

    async def close_pool(self):
        """关闭连接池"""
        if self.pool:
            try:
                await self.pool.close()
                logger.info("PostgreSQL连接池已关闭")
            except Exception as e:
                logger.error(f"关闭连接池失败: {e}")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.pool is not None

    async def start(self):
        """启动批量写入任务"""
        if self._running:
            logger.warning("批量写入任务已在运行")
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(f"批量写入任务已启动: 间隔{self.batch_interval}秒")

    async def stop(self):
        """停止批量写入任务"""
        if not self._running:
            return

        self._running = False

        # 取消任务
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # 刷新剩余缓冲区
        await self.flush()

        logger.info("批量写入任务已停止")

    def add_bar(self, bar_data: Dict):
        """
        添加Bar到缓冲区（同步接口）

        Args:
            bar_data: Bar数据字典
        """
        # 创建任务在事件循环中执行
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._add_bar_async(bar_data))
        except RuntimeError:
            # 如果没有运行的事件循环，直接添加到缓冲区
            self._buffer.append(bar_data)

    async def _add_bar_async(self, bar_data: Dict):
        """
        异步添加Bar到缓冲区

        Args:
            bar_data: Bar数据字典
        """
        async with self._buffer_lock:
            self._buffer.append(bar_data)

            # 达到批量大小，立即刷新
            if len(self._buffer) >= self.batch_size:
                await self._flush_internal()

    async def _flush_loop(self):
        """批量写入循环"""
        while self._running:
            try:
                await asyncio.sleep(self.batch_interval)
                await self._flush_internal()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"批量写入循环错误: {e}", exc_info=True)

    async def flush(self):
        """手动刷新缓冲区"""
        async with self._buffer_lock:
            await self._flush_internal()

    async def _flush_internal(self):
        """
        内部刷新方法（不加锁，由调用方保证）
        """
        if not self._buffer:
            return

        # 获取当前缓冲区数据
        bars = self._buffer.copy()
        self._buffer.clear()

        # 如果有故障队列，优先处理
        if self._failure_queue:
            bars = self._failure_queue + bars
            self._failure_queue.clear()

        # 批量写入
        success = await self._batch_insert(bars)

        if not success:
            # 写入失败，加入故障队列
            self._failure_queue.extend(bars)

            # 队列溢出，丢弃最旧数据
            if len(self._failure_queue) > self._max_queue_size:
                overflow = len(self._failure_queue) - self._max_queue_size
                self._failure_queue = self._failure_queue[overflow:]
                logger.warning(f"故障队列溢出，丢弃{overflow}条最旧数据")

        self._last_flush_time = datetime.utcnow()

    async def _batch_insert(self, bars: List[Dict]) -> bool:
        """
        批量插入Bar数据

        Args:
            bars: Bar数据列表

        Returns:
            是否插入成功
        """
        if not bars:
            return True

        if not self.pool:
            logger.error("数据库连接池未初始化")
            self._writes_failed += len(bars)
            return False

        try:
            # 准备数据
            records = [
                (
                    bar['symbol'],
                    bar['timestamp'],
                    float(bar['open']),
                    float(bar['high']),
                    float(bar['low']),
                    float(bar['close']),
                    int(bar['volume']),
                    bar.get('source', 'unknown')
                )
                for bar in bars
            ]

            # 批量插入
            async with self.pool.acquire() as conn:
                await conn.executemany(
                    f"""
                    INSERT INTO {self.table_name}
                    (symbol, timestamp, open, high, low, close, volume, source)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (symbol, timestamp) DO NOTHING
                    """,
                    records
                )

            self._writes_success += len(bars)
            logger.debug(f"批量写入成功: {len(bars)}条")
            return True

        except Exception as e:
            self._writes_failed += len(bars)
            self._last_error = str(e)
            logger.error(f"批量写入失败: {e}", exc_info=True)
            return False

    async def query_bars(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        查询Bar数据

        Args:
            symbol: 标的代码
            start_time: 开始时间（UTC）
            end_time: 结束时间（UTC）
            limit: 最大返回数量

        Returns:
            Bar数据列表
        """
        if not self.pool:
            logger.error("数据库连接池未初始化")
            return []

        try:
            async with self.pool.acquire() as conn:
                # 构造查询条件
                conditions = ["symbol = $1"]
                params = [symbol]
                param_idx = 2

                if start_time:
                    conditions.append(f"timestamp >= ${param_idx}")
                    params.append(start_time)
                    param_idx += 1

                if end_time:
                    conditions.append(f"timestamp <= ${param_idx}")
                    params.append(end_time)
                    param_idx += 1

                where_clause = " AND ".join(conditions)
                params.append(limit)

                query = f"""
                    SELECT symbol, timestamp, open, high, low, close, volume, source, created_at
                    FROM market_data_1min
                    WHERE {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ${param_idx}
                """

                rows = await conn.fetch(query, *params)

                # 转换为字典列表
                bars = [
                    {
                        'symbol': row['symbol'],
                        'timestamp': row['timestamp'],
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': int(row['volume']),
                        'source': row['source'],
                        'created_at': row['created_at']
                    }
                    for row in rows
                ]

                logger.debug(f"[{symbol}] 查询到{len(bars)}条记录")
                return bars

        except Exception as e:
            logger.error(f"查询失败: {e}")
            return []

    async def count_bars(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """
        统计Bar数量

        Args:
            symbol: 标的代码
            start_time: 开始时间（UTC）
            end_time: 结束时间（UTC）

        Returns:
            Bar数量
        """
        if not self.pool:
            return 0

        try:
            async with self.pool.acquire() as conn:
                conditions = ["symbol = $1"]
                params = [symbol]
                param_idx = 2

                if start_time:
                    conditions.append(f"timestamp >= ${param_idx}")
                    params.append(start_time)
                    param_idx += 1

                if end_time:
                    conditions.append(f"timestamp <= ${param_idx}")
                    params.append(end_time)
                    param_idx += 1

                where_clause = " AND ".join(conditions)

                query = f"""
                    SELECT COUNT(*) as count
                    FROM market_data_1min
                    WHERE {where_clause}
                """

                row = await conn.fetchrow(query, *params)
                return row['count']

        except Exception as e:
            logger.error(f"统计失败: {e}")
            return 0

    async def delete_bars(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """
        删除Bar数据

        Args:
            symbol: 标的代码
            start_time: 开始时间（UTC）
            end_time: 结束时间（UTC）

        Returns:
            删除的数量
        """
        if not self.pool:
            return 0

        try:
            async with self.pool.acquire() as conn:
                conditions = ["symbol = $1"]
                params = [symbol]
                param_idx = 2

                if start_time:
                    conditions.append(f"timestamp >= ${param_idx}")
                    params.append(start_time)
                    param_idx += 1

                if end_time:
                    conditions.append(f"timestamp <= ${param_idx}")
                    params.append(end_time)
                    param_idx += 1

                where_clause = " AND ".join(conditions)

                query = f"""
                    DELETE FROM market_data_1min
                    WHERE {where_clause}
                """

                result = await conn.execute(query, *params)
                # 从结果中提取删除数量
                deleted = int(result.split()[-1])
                logger.info(f"[{symbol}] 删除{deleted}条记录")
                return deleted

        except Exception as e:
            logger.error(f"删除失败: {e}")
            return 0

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        buffer_size = len(self._buffer)
        queue_size = len(self._failure_queue)

        return {
            'db_url': self.db_url.split('@')[-1] if '@' in self.db_url else self.db_url,  # 隐藏密码
            'is_connected': self.is_connected(),
            'is_running': self._running,
            'batch_size': self.batch_size,
            'batch_interval': self.batch_interval,
            'buffer_size': buffer_size,
            'failure_queue_size': queue_size,
            'writes_success': self._writes_success,
            'writes_failed': self._writes_failed,
            'success_rate': (
                f"{self._writes_success / (self._writes_success + self._writes_failed) * 100:.2f}%"
                if (self._writes_success + self._writes_failed) > 0
                else "N/A"
            ),
            'last_flush_time': self._last_flush_time.isoformat() if self._last_flush_time else None,
            'last_error': self._last_error
        }

    def reset_stats(self):
        """重置统计信息"""
        self._writes_success = 0
        self._writes_failed = 0
        self._last_error = None
        logger.debug("PostgreSQL统计信息已重置")
