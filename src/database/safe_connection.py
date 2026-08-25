"""
数据库安全连接

提供自动重连、超时处理、事务回滚等功能
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, List, Optional

import peewee

from common.exceptions import DatabaseConnectionError
from common.retry import retry

logger = logging.getLogger(__name__)


class SafeDatabaseConnection:
    """
    安全的数据库连接包装器

    功能：
    - 自动重连
    - 查询超时处理
    - 连接健康检查
    """

    def __init__(self, database: peewee.Database):
        """
        初始化连接包装器

        Args:
            database: Peewee数据库实例
        """
        self.database = database
        self.reconnect_count = 0
        self.last_error: Optional[Exception] = None

    def is_connected(self) -> bool:
        """
        检查连接是否正常

        Returns:
            True: 连接正常
            False: 连接断开
        """
        try:
            if self.database.is_closed():
                return False

            # 执行简单查询测试连接
            self.database.execute_sql("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")
            return False

    @retry(max_attempts=3, backoff=2.0, exceptions=(peewee.OperationalError,))
    def connect(self):
        """
        建立连接（带重试）

        Raises:
            DatabaseConnectionError: 连接失败
        """
        try:
            if not self.database.is_closed():
                self.database.close()

            self.database.connect()
            logger.info("Database connected")

        except peewee.OperationalError as e:
            self.last_error = e
            logger.error(f"Failed to connect to database: {e}")
            raise DatabaseConnectionError(f"Failed to connect to database: {e}", context={"error": str(e)})

    def reconnect(self):
        """重新连接"""
        self.reconnect_count += 1
        logger.info(f"Reconnecting to database (attempt #{self.reconnect_count})...")

        try:
            self.connect()
            logger.info("Database reconnected successfully")
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            raise

    @retry(max_attempts=3, backoff=2.0, exceptions=(peewee.OperationalError,))
    def execute(self, query):
        """
        执行查询（带重试和自动重连）

        Args:
            query: Peewee查询对象

        Returns:
            查询结果

        Raises:
            DatabaseConnectionError: 执行失败
        """
        try:
            # 检查连接
            if not self.is_connected():
                logger.warning("Database not connected, reconnecting...")
                self.reconnect()

            return query.execute()

        except peewee.OperationalError as e:
            logger.warning(f"Database error: {e}, attempting reconnect...")
            self.reconnect()
            raise

    @contextmanager
    def transaction(self):
        """
        事务上下文，失败自动回滚

        Example:
            with safe_db.transaction():
                # 数据库操作
                order.save()
        """
        try:
            with self.database.atomic():
                yield
        except Exception as e:
            logger.error(f"Transaction failed: {e}, rolling back")
            raise

    def close(self):
        """关闭连接"""
        try:
            if not self.database.is_closed():
                self.database.close()
                logger.info("Database connection closed")
        except Exception as e:
            logger.warning(f"Error closing database: {e}")

    def get_stats(self) -> dict:
        """
        获取连接统计信息

        Returns:
            统计信息字典
        """
        return {
            "is_connected": self.is_connected(),
            "is_closed": self.database.is_closed(),
            "reconnect_count": self.reconnect_count,
            "last_error": str(self.last_error) if self.last_error else None,
        }


class SafeRepository:
    """
    安全的数据库Repository封装

    提供常用CRUD操作的安全包装
    """

    def __init__(self, safe_connection: SafeDatabaseConnection):
        """
        初始化Repository

        Args:
            safe_connection: 安全连接实例
        """
        self.safe_connection = safe_connection

    def get_by_id(self, model: peewee.Model, record_id: Any) -> Optional[Any]:
        """
        根据ID获取记录

        Args:
            model: Peewee模型类
            record_id: 记录ID

        Returns:
            记录实例或None
        """
        try:
            query = model.select().where(model.id == record_id)
            result = self.safe_connection.execute(query)
            return result[0] if result else None
        except peewee.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting record by id: {e}")
            return None

    def get_all(self, model: peewee.Model, filters: Optional[List] = None, limit: Optional[int] = None) -> List[Any]:
        """
        获取所有记录

        Args:
            model: Peewee模型类
            filters: 过滤条件列表
            limit: 限制数量

        Returns:
            记录列表
        """
        try:
            query = model.select()

            if filters:
                query = query.where(*filters)

            if limit:
                query = query.limit(limit)

            result = self.safe_connection.execute(query)
            return list(result)

        except Exception as e:
            logger.error(f"Error getting records: {e}")
            return []

    def save(self, instance: peewee.Model) -> Optional[Any]:
        """
        保存记录

        Args:
            instance: 模型实例

        Returns:
            保存后的实例或None
        """
        try:
            with self.safe_connection.transaction():
                instance.save()
            return instance
        except peewee.IntegrityError as e:
            logger.warning(f"Integrity error: {e}")
            return None
        except Exception as e:
            logger.error(f"Save failed: {e}")
            return None

    def save_many(self, instances: List[peewee.Model]) -> int:
        """
        批量保存记录

        Args:
            instances: 模型实例列表

        Returns:
            成功保存的数量
        """
        if not instances:
            return 0

        success_count = 0
        try:
            with self.safe_connection.transaction():
                for instance in instances:
                    try:
                        instance.save()
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Error saving instance: {e}")
        except Exception as e:
            logger.error(f"Batch save failed: {e}")

        return success_count

    def delete(self, instance: peewee.Model) -> bool:
        """
        删除记录

        Args:
            instance: 模型实例

        Returns:
            True: 删除成功
            False: 删除失败
        """
        try:
            with self.safe_connection.transaction():
                instance.delete_instance()
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def count(self, model: peewee.Model, filters: Optional[List] = None) -> int:
        """
        统计记录数

        Args:
            model: Peewee模型类
            filters: 过滤条件列表

        Returns:
            记录数量
        """
        try:
            query = model.select()

            if filters:
                query = query.where(*filters)

            result = self.safe_connection.execute(query.count())
            return result if isinstance(result, int) else 0

        except Exception as e:
            logger.error(f"Count failed: {e}")
            return 0

    def exists(self, model: peewee.Model, filters: List) -> bool:
        """
        检查记录是否存在

        Args:
            model: Peewee模型类
            filters: 过滤条件列表

        Returns:
            True: 存在
            False: 不存在
        """
        try:
            query = model.select().where(*filters)
            result = self.safe_connection.execute(query.exists())
            return bool(result)
        except Exception as e:
            logger.error(f"Exists check failed: {e}")
            return False


def query_with_timeout(query, timeout: float = 10.0):
    """
    带超时的查询（装饰器使用）

    Args:
        query: 查询对象
        timeout: 超时时间（秒）

    Returns:
        查询结果

    Raises:
        TimeoutError: 查询超时
    """
    # 注意：Peewee本身不直接支持查询超时
    # 这里提供一个框架，实际实现需要依赖数据库驱动的超时机制

    start_time = time.time()

    try:
        result = query.execute()

        elapsed = time.time() - start_time
        if elapsed > timeout:
            logger.warning(f"Query completed but took {elapsed:.1f}s (timeout: {timeout}s)")

        return result

    except Exception as e:
        elapsed = time.time() - start_time

        if "timeout" in str(e).lower() or elapsed > timeout:
            logger.error(f"Query timeout after {elapsed:.1f}s")
            raise TimeoutError(f"Database query timeout after {elapsed:.1f}s") from e

        raise


@contextmanager
def safe_db_operation(default_return=None):
    """
    安全的数据库操作上下文管理器

    Args:
        default_return: 出错时的默认返回值

    Example:
        with safe_db_operation(default_return=[]):
            return Order.select().where(Order.status == 'active')
    """
    try:
        yield
    except peewee.DoesNotExist:
        logger.debug("Record does not exist")
        return default_return
    except peewee.IntegrityError as e:
        logger.warning(f"Integrity error: {e}")
        return default_return
    except peewee.OperationalError as e:
        logger.error(f"Database operational error: {e}")
        return default_return
    except Exception as e:
        logger.error(f"Unexpected database error: {e}", exc_info=True)
        return default_return
