"""
配置监听器

监听配置文件变化，触发热更新
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """
    配置文件监听器

    功能：
    - 监听配置文件修改时间
    - 检测到变化后触发回调
    - 支持启动/停止监听
    """

    def __init__(self, config_path: str, callback: Callable, check_interval: int = 5):
        """
        初始化配置监听器

        Args:
            config_path: 配置文件路径
            callback: 文件变化时的回调函数
            check_interval: 检查间隔（秒）
        """
        self.config_path = config_path
        self.callback = callback
        self.check_interval = check_interval
        self.last_modified = 0
        self.watching = False
        self.watch_thread: threading.Thread = None

    def start(self):
        """启动监听"""
        if self.watching:
            logger.warning("ConfigWatcher is already running")
            return

        # 获取初始修改时间
        if os.path.exists(self.config_path):
            self.last_modified = os.path.getmtime(self.config_path)
        else:
            logger.warning(f"Config file not found: {self.config_path}")

        self.watching = True
        self.watch_thread = threading.Thread(target=self._watch_loop, name="ConfigWatcher", daemon=True)
        self.watch_thread.start()

        logger.info(f"ConfigWatcher started, monitoring: {self.config_path}")

    def stop(self):
        """停止监听"""
        if not self.watching:
            return

        self.watching = False

        if self.watch_thread:
            self.watch_thread.join(timeout=10)

        logger.info("ConfigWatcher stopped")

    def _watch_loop(self):
        """监听循环"""
        logger.info("ConfigWatcher loop started")

        while self.watching:
            try:
                # 检查文件是否存在
                if not os.path.exists(self.config_path):
                    logger.warning(f"Config file not found: {self.config_path}")
                    time.sleep(self.check_interval)
                    continue

                # 获取当前修改时间
                current_modified = os.path.getmtime(self.config_path)

                # 检查是否有变化
                if current_modified > self.last_modified:
                    logger.info(f"Config file changed: {self.config_path}")
                    self.last_modified = current_modified

                    # 稍微等待，确保文件写入完成
                    time.sleep(0.5)

                    # 触发回调
                    try:
                        self.callback()
                        logger.info("Config reload callback executed successfully")
                    except Exception as e:
                        logger.error(f"Error in config reload callback: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Error in config watch loop: {e}", exc_info=True)

            time.sleep(self.check_interval)

        logger.info("ConfigWatcher loop stopped")

    def force_reload(self):
        """强制触发重新加载"""
        logger.info("Forcing config reload...")
        try:
            self.callback()
            logger.info("Forced reload completed")
        except Exception as e:
            logger.error(f"Error in forced reload: {e}", exc_info=True)

    def get_status(self) -> dict:
        """
        获取监听状态

        Returns:
            状态字典
        """
        return {
            "watching": self.watching,
            "config_path": self.config_path,
            "check_interval": self.check_interval,
            "last_modified": self.last_modified,
            "file_exists": os.path.exists(self.config_path),
        }
