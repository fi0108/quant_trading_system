"""
数据库初始化脚本

创建数据库表和索引
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.storage.models import init_database, create_tables, drop_tables
from common.logger import log


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Database initialization script')
    parser.add_argument('--drop', action='store_true', help='Drop tables before creating')
    parser.add_argument('--recreate', action='store_true', help='Drop and recreate tables')
    args = parser.parse_args()

    try:
        # 初始化数据库连接
        log.info("Initializing database connection...")
        init_database()

        # 删除表（如果需要）
        if args.drop or args.recreate:
            log.warning("Dropping tables...")
            drop_tables()
            log.info("Tables dropped successfully")

        # 创建表
        log.info("Creating tables...")
        create_tables()
        log.info("Tables created successfully")

        log.info("=" * 80)
        log.info("Database initialization completed!")
        log.info("=" * 80)

    except Exception as e:
        log.error(f"Database initialization failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
