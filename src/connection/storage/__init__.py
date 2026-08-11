"""
数据存储模块
"""

from .redis_writer import RedisWriter
from .postgres_writer import PostgresWriter

__all__ = ['RedisWriter', 'PostgresWriter']
