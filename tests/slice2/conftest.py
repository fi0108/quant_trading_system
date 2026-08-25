"""
数据库测试配置

提供数据库测试的 fixture 和跳过条件
"""

import psycopg2
import pytest

from common.config import config
from data.storage.models import database


def is_database_available():
    """检查数据库是否可用"""
    try:
        # 从配置读取数据库信息
        db_host = config.get("database.postgres.host", "localhost")
        db_port = config.get("database.postgres.port", 5432)
        db_user = config.get("database.postgres.user", "postgres")
        db_password = config.get("database.postgres.password", "000000")

        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database="postgres",  # 连接默认数据库
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception as e:
        print(f"Database not available: {e}")
        return False


# 数据库可用性标记
requires_database = pytest.mark.skipif(
    not is_database_available(), reason="PostgreSQL not available (not running or connection failed)"
)


@pytest.fixture(scope="module")
def setup_test_database():
    """设置测试数据库"""
    if not is_database_available():
        pytest.skip("PostgreSQL not available")

    # 从配置读取数据库信息
    db_host = config.get("database.postgres.host", "localhost")
    db_port = config.get("database.postgres.port", 5432)
    db_user = config.get("database.postgres.user", "postgres")
    db_password = config.get("database.postgres.password", "000000")
    db_name = config.get("database.postgres.database", "quant_trading")

    # 使用测试数据库（在配置数据库名前加 test_ 前缀）
    test_db_name = f"test_{db_name}"

    # 初始化测试数据库连接
    database.init(test_db_name, host=db_host, port=db_port, user=db_user, password=db_password)

    # 尝试创建测试数据库（如果不存在）
    try:
        conn = psycopg2.connect(host=db_host, port=db_port, user=db_user, password=db_password, database="postgres")
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname='{test_db_name}'")
        if not cursor.fetchone():
            cursor.execute(f"CREATE DATABASE {test_db_name}")
            print(f"Created test database: {test_db_name}")
        cursor.close()
        conn.close()
    except Exception as e:
        pytest.skip(f"Cannot create test database: {e}")

    yield database

    # 测试完成后关闭连接
    if database.is_closed() is False:
        database.close()
