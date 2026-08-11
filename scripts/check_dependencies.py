#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
依赖检查和自动安装脚本
"""

import subprocess
import sys

# 模块一必需的依赖
REQUIRED_PACKAGES = {
    'ib_insync': 'ib-insync',
    'pandas_market_calendars': 'pandas-market-calendars',
    'asyncpg': 'asyncpg',
    'redis': 'redis',
    'pytz': 'pytz',
    'pandas': 'pandas',
    'numpy': 'numpy',
}


def check_package(package_name):
    """检查包是否已安装"""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def install_package(pip_name):
    """安装包"""
    print(f"Installing {pip_name}...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pip_name, "-q"]
        )
        print(f"  [OK] {pip_name} installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [FAIL] {pip_name} failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Checking Module 1 Dependencies")
    print("=" * 60)

    missing = []

    # 检查必需依赖
    print("\nRequired packages:")
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        if check_package(import_name):
            print(f"  [OK] {pip_name}")
        else:
            print(f"  [MISSING] {pip_name}")
            missing.append(pip_name)

    # 安装缺失的依赖
    if missing:
        print("\n" + "=" * 60)
        print("Installing missing dependencies")
        print("=" * 60)

        failed = []
        for pip_name in missing:
            if not install_package(pip_name):
                failed.append(pip_name)

        if failed:
            print("\n" + "=" * 60)
            print("Failed to install:")
            for pkg in failed:
                print(f"  [FAIL] {pkg}")
            print("\nManual install: pip install " + " ".join(failed))
            return 1
    else:
        print("\n[OK] All required packages are installed!")

    # 验证导入
    print("\n" + "=" * 60)
    print("Verifying imports")
    print("=" * 60)

    try:
        from src.core.timezone_manager import TimezoneManager
        print("  [OK] TimezoneManager")
    except Exception as e:
        print(f"  [FAIL] TimezoneManager: {e}")

    try:
        from src.calendar.trading_calendar import TradingCalendar
        print("  [OK] TradingCalendar")
    except Exception as e:
        print(f"  [FAIL] TradingCalendar: {e}")

    try:
        from src.connection.manager import ConnectionManager
        print("  [OK] ConnectionManager")
    except Exception as e:
        print(f"  [FAIL] ConnectionManager: {e}")

    try:
        from src.connection.storage.redis_writer import RedisWriter
        print("  [OK] RedisWriter")
    except Exception as e:
        print(f"  [FAIL] RedisWriter: {e}")

    try:
        from src.connection.storage.postgres_writer import PostgresWriter
        print("  [OK] PostgresWriter")
    except Exception as e:
        print(f"  [FAIL] PostgresWriter: {e}")

    print("\n" + "=" * 60)
    print("Dependency check complete!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
