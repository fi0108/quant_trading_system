"""
Module 1 Dependencies Checker and Installer

检查并安装模块一所需的所有依赖包。

使用方法：
    python scripts/check_module1_dependencies.py

    # 自动安装缺失的包
    python scripts/check_module1_dependencies.py --install
"""

import sys
import subprocess
from pathlib import Path

# 模块一必需的依赖包
REQUIRED_PACKAGES = {
    'asyncpg': '0.29.0',
    'ib_insync': '0.9.86',
    'pandas_market_calendars': '4.3.3',
    'redis': '5.0.1',
    'psycopg2-binary': '2.9.9',
    'pytz': '2024.1',
    'pyyaml': '6.0.1',
}


def check_package(package_name: str, min_version: str = None) -> tuple[bool, str]:
    """
    检查包是否已安装。

    Returns:
        (is_installed, version_or_error)
    """
    # 包名映射（pip 安装名 vs import 名）
    import_name_map = {
        'ib_insync': 'ib_insync',
        'pandas_market_calendars': 'pandas_market_calendars',
        'psycopg2-binary': 'psycopg2',
        'pyyaml': 'yaml',
    }

    import_name = import_name_map.get(package_name, package_name)

    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        return True, version
    except ImportError as e:
        return False, str(e)


def install_package(package_name: str, version: str = None):
    """安装指定的包。"""
    if version:
        package_spec = f"{package_name}=={version}"
    else:
        package_spec = package_name

    print(f"Installing {package_spec}...")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package_spec],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"✓ {package_spec} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install {package_spec}: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Check and install Module 1 dependencies')
    parser.add_argument('--install', action='store_true', help='Automatically install missing packages')
    args = parser.parse_args()

    print("=" * 70)
    print("Module 1 Dependencies Checker")
    print("=" * 70)
    print(f"Python Executable: {sys.executable}")
    print(f"Python Version: {sys.version}")
    print("=" * 70)

    missing_packages = []
    installed_packages = []

    for package, version in REQUIRED_PACKAGES.items():
        is_installed, info = check_package(package, version)

        if is_installed:
            status = f"✓ {package:30s} {info}"
            print(status)
            installed_packages.append(package)
        else:
            status = f"✗ {package:30s} NOT INSTALLED"
            print(status)
            missing_packages.append((package, version))

    print("=" * 70)

    if missing_packages:
        print(f"\n⚠️  Missing {len(missing_packages)} package(s):")
        for pkg, ver in missing_packages:
            print(f"   - {pkg}=={ver}")

        if args.install:
            print("\n📦 Installing missing packages...")
            success_count = 0
            for pkg, ver in missing_packages:
                if install_package(pkg, ver):
                    success_count += 1

            print("=" * 70)
            if success_count == len(missing_packages):
                print("✅ All packages installed successfully!")
            else:
                print(f"⚠️  {len(missing_packages) - success_count} package(s) failed to install")
        else:
            print("\n💡 Run with --install flag to automatically install missing packages:")
            print(f"   python {__file__} --install")
            print("\nOr install manually:")
            print(f"   pip install {' '.join([f'{p}=={v}' for p, v in missing_packages])}")
            sys.exit(1)
    else:
        print("✅ All required packages are installed!")

    # 额外的导入测试
    print("\n" + "=" * 70)
    print("Testing imports...")
    print("=" * 70)

    test_imports = [
        ('asyncpg', 'asyncpg'),
        ('ib_insync', 'ib_insync.IB'),
        ('redis', 'redis.Redis'),
        ('psycopg2', 'psycopg2'),
        ('pandas_market_calendars', 'pandas_market_calendars.get_calendar'),
        ('pytz', 'pytz.timezone'),
        ('yaml', 'yaml.safe_load'),
    ]

    import_success = True
    for display_name, import_path in test_imports:
        try:
            parts = import_path.split('.')
            module = __import__(parts[0])
            for part in parts[1:]:
                module = getattr(module, part)
            print(f"✓ {display_name:30s} import successful")
        except Exception as e:
            print(f"✗ {display_name:30s} import failed: {e}")
            import_success = False

    print("=" * 70)

    if import_success:
        print("\n✅ All imports successful! Module 1 dependencies are ready.")
        return 0
    else:
        print("\n❌ Some imports failed. Please check the errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
