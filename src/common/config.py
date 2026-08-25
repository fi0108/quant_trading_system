"""
统一配置管理器

支持：
- 统一的 config.yaml 配置文件
- 环境变量覆盖（.env / .env.dev）
- 多环境配置（development/production）
- 配置缓存
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml

# 自动加载环境变量
try:
    from dotenv import load_dotenv

    # 根据ENV环境变量决定加载哪个.env文件
    env = os.getenv("ENV", "development")

    if env == "production":
        # 生产环境：加载 .env
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)
        else:
            # 如果.env不存在，尝试从环境变量读取
            pass
    else:
        # 开发/测试环境：加载 .env.dev
        env_file = Path(".env.dev")
        if env_file.exists():
            load_dotenv(env_file)
        else:
            # 兼容：如果.env.dev不存在，尝试.env
            load_dotenv()

except ImportError:
    # python-dotenv 未安装，跳过
    pass


class Config:
    """统一配置管理器"""

    def __init__(self):
        self._config = {}
        self._config_dir = Path(__file__).parent.parent.parent / "config"
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        # 1. 加载主配置文件 config.yaml
        config_file = self._config_dir / "config.yaml"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            raise FileNotFoundError(f"Config file not found: {config_file}")

        # 2. 根据环境加载环境特定配置
        env = os.getenv("ENV", "development")
        env_config_file = self._config_dir / f"config.{env}.yaml"

        if env_config_file.exists():
            with open(env_config_file, "r", encoding="utf-8") as f:
                env_config = yaml.safe_load(f) or {}
                self._deep_merge(self._config, env_config)

        # 3. 应用环境变量覆盖
        self._apply_env_overrides()

    def _deep_merge(self, base: dict, override: dict):
        """深度合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # 数据库密码
        if os.getenv("DB_PASSWORD"):
            self._set_nested("database.postgres.password", os.getenv("DB_PASSWORD"))

        # Redis 密码
        if os.getenv("REDIS_PASSWORD"):
            self._set_nested("database.redis.password", os.getenv("REDIS_PASSWORD"))

        # IBKR 密码（如果需要）
        if os.getenv("IBKR_PASSWORD"):
            self._set_nested("ibkr.password", os.getenv("IBKR_PASSWORD"))

        # 邮件密码
        if os.getenv("EMAIL_PASSWORD"):
            self._set_nested("monitoring.email.smtp.password", os.getenv("EMAIL_PASSWORD"))

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号路径）

        Args:
            key: 配置键，支持点号路径如 "database.postgres.host"
            default: 默认值

        Returns:
            配置值

        Examples:
            >>> config.get('ibkr.host')
            '127.0.0.1'
            >>> config.get('database.postgres.port')
            5432
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def _set_nested(self, key: str, value: Any):
        """设置嵌套配置值"""
        keys = key.split(".")
        current = self._config

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def get_section(self, section: str) -> dict:
        """
        获取配置节

        Args:
            section: 配置节名称

        Returns:
            配置节字典
        """
        return self._config.get(section, {})

    def load(self, name: str) -> dict:
        """
        兼容旧的 config.load() 方法

        Args:
            name: 配置节名称

        Returns:
            配置节字典
        """
        return self.get_section(name)

    def reload(self):
        """重新加载配置"""
        self._load_config()


# 全局配置实例
config = Config()
