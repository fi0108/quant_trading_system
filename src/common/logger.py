"""日志系统配置

使用loguru提供统一的日志接口。
"""

import sys
from pathlib import Path
from loguru import logger
from .config import config


def setup_logger():
    """配置日志系统

    从配置文件读取日志参数并配置loguru。

    Returns:
        配置好的logger实例
    """
    # 移除默认处理器
    logger.remove()

    # 从配置读取参数（如果config/system.yaml没有相关配置，使用默认值）
    try:
        system_config = config.load('system')
        # 注意：当前system.yaml没有logging配置，我们使用合理的默认值
        log_level = "INFO"
        log_path = "logs/"
        rotation = "1 day"
        retention = "30 days"
    except Exception:
        # 如果配置文件不存在或格式错误，使用默认值
        log_level = "INFO"
        log_path = "logs/"
        rotation = "1 day"
        retention = "30 days"

    # 创建日志目录
    Path(log_path).mkdir(parents=True, exist_ok=True)

    # 控制台输出（彩色，简洁格式）
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
               "<level>{message}</level>",
        colorize=True
    )

    # 文件输出（所有日志）
    logger.add(
        f"{log_path}/{{time:YYYY-MM-DD}}.log",
        level="DEBUG",
        rotation=rotation,
        retention=retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding='utf-8'
    )

    # 错误日志单独文件
    logger.add(
        f"{log_path}/error_{{time:YYYY-MM-DD}}.log",
        level="ERROR",
        rotation=rotation,
        retention=retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding='utf-8'
    )

    return logger


# 初始化并导出全局logger实例
log = setup_logger()
