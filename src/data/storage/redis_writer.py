"""
Redis存储器

职责：
1. 实时数据热存储
2. 保留最新100根K线
3. 供策略快速查询
4. 支持多标的独立存储
"""

from typing import List, Optional, Dict
import json
import redis
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RedisWriter:
    """
    Redis热存储写入器

    数据结构：
    - Key格式: {symbol}:latest_bars
    - Value: JSON数组，存储最新100根K线
    - 数据结构: List (LPUSH + LTRIM)
    - TTL: 1小时
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        max_bars: int = 100,
        ttl_seconds: int = 3600,
        key_prefix: str = ""
    ):
        """
        初始化Redis写入器

        Args:
            redis_url: Redis连接URL
            max_bars: 最多保留的Bar数量
            ttl_seconds: 键过期时间（秒）
            key_prefix: 键前缀（可选，用于隔离环境）
        """
        self.redis_url = redis_url
        self.max_bars = max_bars
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

        self._client: Optional[redis.Redis] = None
        self._is_connected = False

        # 统计
        self._writes_success = 0
        self._writes_failed = 0
        self._last_error: Optional[str] = None

    def connect(self) -> bool:
        """
        连接Redis

        Returns:
            是否连接成功
        """
        try:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True,  # 自动解码为字符串
                socket_connect_timeout=5,
                socket_timeout=5
            )

            # 测试连接
            self._client.ping()
            self._is_connected = True
            logger.info(f"Redis连接成功: {self.redis_url}")
            return True

        except Exception as e:
            self._is_connected = False
            self._last_error = str(e)
            logger.error(f"Redis连接失败: {e}")
            return False

    def disconnect(self):
        """断开Redis连接"""
        if self._client:
            try:
                self._client.close()
                self._is_connected = False
                logger.info("Redis连接已断开")
            except Exception as e:
                logger.error(f"断开Redis连接失败: {e}")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        if not self._is_connected or not self._client:
            return False

        try:
            self._client.ping()
            return True
        except:
            self._is_connected = False
            return False

    def write_bar(self, symbol: str, bar_data: dict) -> bool:
        """
        写入单根Bar到Redis

        Args:
            symbol: 标的代码
            bar_data: Bar数据字典

        Returns:
            是否写入成功
        """
        if not self.is_connected():
            logger.warning("Redis未连接，写入失败")
            self._writes_failed += 1
            return False

        try:
            key = self._make_key(symbol)

            # 序列化Bar数据
            bar_json = self._serialize_bar(bar_data)

            # LPUSH: 添加到列表头部（最新数据在前）
            self._client.lpush(key, bar_json)

            # LTRIM: 只保留最新max_bars条
            self._client.ltrim(key, 0, self.max_bars - 1)

            # 设置过期时间
            self._client.expire(key, self.ttl_seconds)

            self._writes_success += 1
            logger.debug(f"[{symbol}] Bar已写入Redis")
            return True

        except Exception as e:
            self._writes_failed += 1
            self._last_error = str(e)
            logger.error(f"[{symbol}] Redis写入失败: {e}")
            return False

    def write_bars(self, symbol: str, bars: List[dict]) -> int:
        """
        批量写入Bar到Redis

        Args:
            symbol: 标的代码
            bars: Bar数据列表

        Returns:
            成功写入的数量
        """
        if not self.is_connected():
            logger.warning("Redis未连接，批量写入失败")
            return 0

        success_count = 0
        for bar in bars:
            if self.write_bar(symbol, bar):
                success_count += 1

        logger.info(f"[{symbol}] 批量写入完成: {success_count}/{len(bars)}")
        return success_count

    def get_latest_bars(self, symbol: str, count: int = 100) -> List[dict]:
        """
        获取最新N根Bar

        Args:
            symbol: 标的代码
            count: 获取数量

        Returns:
            Bar数据列表（从新到旧）
        """
        if not self.is_connected():
            logger.warning("Redis未连接，读取失败")
            return []

        try:
            key = self._make_key(symbol)

            # LRANGE: 获取列表范围 [0, count-1]
            bars_json = self._client.lrange(key, 0, count - 1)

            # 反序列化
            bars = [self._deserialize_bar(bar_json) for bar_json in bars_json]

            logger.debug(f"[{symbol}] 读取{len(bars)}根Bar")
            return bars

        except Exception as e:
            logger.error(f"[{symbol}] Redis读取失败: {e}")
            return []

    def get_bar_count(self, symbol: str) -> int:
        """
        获取标的的Bar数量

        Args:
            symbol: 标的代码

        Returns:
            Bar数量
        """
        if not self.is_connected():
            return 0

        try:
            key = self._make_key(symbol)
            return self._client.llen(key)
        except Exception as e:
            logger.error(f"[{symbol}] 获取Bar数量失败: {e}")
            return 0

    def delete_bars(self, symbol: str) -> bool:
        """
        删除标的的所有Bar

        Args:
            symbol: 标的代码

        Returns:
            是否删除成功
        """
        if not self.is_connected():
            return False

        try:
            key = self._make_key(symbol)
            self._client.delete(key)
            logger.info(f"[{symbol}] Bar数据已删除")
            return True
        except Exception as e:
            logger.error(f"[{symbol}] 删除失败: {e}")
            return False

    def clear_all(self, pattern: str = "*:latest_bars") -> int:
        """
        清空所有匹配的键

        Args:
            pattern: 键模式（默认所有latest_bars）

        Returns:
            删除的键数量
        """
        if not self.is_connected():
            return 0

        try:
            full_pattern = f"{self.key_prefix}{pattern}"
            keys = self._client.keys(full_pattern)

            if keys:
                deleted = self._client.delete(*keys)
                logger.info(f"清空完成: 删除{deleted}个键")
                return deleted
            else:
                logger.info("没有匹配的键需要删除")
                return 0

        except Exception as e:
            logger.error(f"清空失败: {e}")
            return 0

    def _make_key(self, symbol: str) -> str:
        """
        生成Redis键

        Args:
            symbol: 标的代码

        Returns:
            Redis键
        """
        return f"{self.key_prefix}{symbol}:latest_bars"

    def _serialize_bar(self, bar_data: dict) -> str:
        """
        序列化Bar数据

        Args:
            bar_data: Bar数据字典

        Returns:
            JSON字符串
        """
        # 处理datetime对象
        bar_copy = bar_data.copy()

        # 转换timestamp为ISO格式字符串
        if 'timestamp' in bar_copy and isinstance(bar_copy['timestamp'], datetime):
            bar_copy['timestamp'] = bar_copy['timestamp'].isoformat()

        if 'received_at' in bar_copy and isinstance(bar_copy['received_at'], datetime):
            bar_copy['received_at'] = bar_copy['received_at'].isoformat()

        return json.dumps(bar_copy, ensure_ascii=False)

    def _deserialize_bar(self, bar_json: str) -> dict:
        """
        反序列化Bar数据

        Args:
            bar_json: JSON字符串

        Returns:
            Bar数据字典
        """
        bar_data = json.loads(bar_json)

        # 转换时间字符串回datetime对象
        if 'timestamp' in bar_data and isinstance(bar_data['timestamp'], str):
            bar_data['timestamp'] = datetime.fromisoformat(bar_data['timestamp'])

        if 'received_at' in bar_data and isinstance(bar_data['received_at'], str):
            bar_data['received_at'] = datetime.fromisoformat(bar_data['received_at'])

        return bar_data

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            'redis_url': self.redis_url,
            'is_connected': self.is_connected(),
            'max_bars': self.max_bars,
            'ttl_seconds': self.ttl_seconds,
            'key_prefix': self.key_prefix,
            'writes_success': self._writes_success,
            'writes_failed': self._writes_failed,
            'success_rate': (
                f"{self._writes_success / (self._writes_success + self._writes_failed) * 100:.2f}%"
                if (self._writes_success + self._writes_failed) > 0
                else "N/A"
            ),
            'last_error': self._last_error
        }

    def reset_stats(self):
        """重置统计信息"""
        self._writes_success = 0
        self._writes_failed = 0
        self._last_error = None
        logger.debug("Redis统计信息已重置")

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
