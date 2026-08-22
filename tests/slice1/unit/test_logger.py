
"""测试日志系统"""

from common.logger import log

def test_logger_basic():
    """测试基本日志输出"""
    log.debug("This is a debug message")
    log.info("This is an info message")
    log.warning("This is a warning message")
    log.error("This is an error message")

    print("Logger basic test completed")

def test_logger_file_creation():
    """测试日志文件是否创建"""
    log.info("Testing log file creation")

    # 检查日志目录是否存在
    log_dir = Path("logs")
    assert log_dir.exists(), "Log directory should exist"

    # 检查是否有日志文件
    log_files = list(log_dir.glob("*.log"))
    assert len(log_files) > 0, "At least one log file should exist"

    print(f"Found {len(log_files)} log files")
    print("Log file creation test passed")

def test_logger_error_file():
    """测试错误日志单独文件"""
    log.error("This is a test error message")

    # 检查是否有错误日志文件
    log_dir = Path("logs")
    error_files = list(log_dir.glob("error_*.log"))

    # 错误日志文件可能存在
    print(f"Found {len(error_files)} error log files")
    print("Error log file test completed")

if __name__ == '__main__':
    test_logger_basic()
    test_logger_file_creation()
    test_logger_error_file()
    print("All logger tests passed")
