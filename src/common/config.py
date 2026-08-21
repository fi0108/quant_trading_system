"""配置管理模块

统一的配置加载和访问接口，支持多个YAML配置文件。
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class Config:
    """配置管理类

    提供统一的配置文件加载和访问接口。
    支持嵌套配置访问，使用点分隔路径（如 "ibkr.host"）。
    """

    def __init__(self, config_dir: str = "config"):
        """初始化配置管理器

        Args:
            config_dir: 配置文件目录路径
        """
        self.config_dir = Path(config_dir)
        self._configs: Dict[str, Any] = {}

    def load(self, name: str) -> Dict[str, Any]:
        """加载配置文件

        Args:
            name: 配置文件名（不含.yaml后缀）

        Returns:
            配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
        """
        # 如果已缓存，直接返回
        if name in self._configs:
            return self._configs[name]

        # 构建配置文件路径
        config_file = self.config_dir / f"{name}.yaml"
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        # 加载YAML文件
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 缓存配置
        self._configs[name] = config
        return config

    def get(self, name: str, key_path: str, default: Any = None) -> Any:
        """获取配置项

        支持点分隔的嵌套路径访问。

        Args:
            name: 配置文件名（不含.yaml后缀）
            key_path: 配置路径，用.分隔，如 "ibkr.host"
            default: 默认值，如果配置项不存在则返回此值

        Returns:
            配置值，如果不存在则返回default

        Examples:
            >>> config.get('ibkr', 'ibkr.host')
            '127.0.0.1'
            >>> config.get('ibkr', 'ibkr.port', 7497)
            4001
        """
        # 加载配置
        config = self.load(name)

        # 按点分隔路径遍历
        keys = key_path.split('.')
        value = config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def reload(self, name: str) -> Dict[str, Any]:
        """重新加载配置文件

        清除缓存并重新从文件加载。

        Args:
            name: 配置文件名（不含.yaml后缀）

        Returns:
            新加载的配置字典
        """
        if name in self._configs:
            del self._configs[name]
        return self.load(name)

    def clear_cache(self):
        """清除所有配置缓存"""
        self._configs.clear()


# 全局配置实例
config = Config()
