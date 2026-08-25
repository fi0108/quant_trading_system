"""测试统一配置管理模块"""

import pytest

from common.config import config


def test_get_ibkr_config():
    """测试获取IBKR配置"""
    host = config.get("ibkr.host")
    assert host == "127.0.0.1"

    port = config.get("ibkr.port")
    assert port == 4002  # 开发环境端口

    client_id = config.get("ibkr.client_id")
    assert client_id == 1


def test_get_database_config():
    """测试获取数据库配置"""
    db_host = config.get("database.postgres.host")
    assert db_host == "localhost"

    db_name = config.get("database.postgres.database")
    assert db_name == "quant_trading"

    db_port = config.get("database.postgres.port")
    assert db_port == 5432


def test_get_nested_config():
    """测试获取嵌套配置"""
    local_tz = config.get("system.timezone.local")
    assert local_tz == "Asia/Shanghai"

    market_tz = config.get("system.timezone.market")
    assert market_tz == "America/New_York"


def test_get_with_default():
    """测试默认值"""
    # 不存在的配置项应该返回默认值
    value = config.get("not.exist.key", "default_value")
    assert value == "default_value"

    # 存在的配置项不应该返回默认值
    host = config.get("ibkr.host", "default")
    assert host == "127.0.0.1"


def test_get_section():
    """测试获取配置节"""
    ibkr_section = config.get_section("ibkr")
    assert ibkr_section is not None
    assert "host" in ibkr_section
    assert "port" in ibkr_section

    db_section = config.get_section("database")
    assert db_section is not None
    assert "postgres" in db_section


def test_load_compatibility():
    """测试向后兼容的load方法"""
    # 兼容旧的 config.load() 方式
    ibkr_config = config.load("ibkr")
    assert ibkr_config is not None
    assert ibkr_config["host"] == "127.0.0.1"

    system_config = config.load("system")
    assert system_config is not None
    assert "timezone" in system_config


def test_environment_variable_override():
    """测试环境变量覆盖（如果设置了.env.dev）"""
    # 密码应该从环境变量读取（.env.dev）
    db_password = config.get("database.postgres.password")
    # 开发环境应该是 "000000"（来自.env.dev）
    assert db_password in ["000000", ""]  # 空字符串表示未设置环境变量


def test_calendar_config():
    """测试交易日历配置"""
    market = config.get("calendar.market")
    assert market == "NYSE"

    cache_enabled = config.get("calendar.cache.enabled")
    assert cache_enabled is True


def test_trading_hours_config():
    """测试交易时段配置"""
    regular_start = config.get("trading_hours.regular_start")
    assert regular_start == "09:30"

    regular_end = config.get("trading_hours.regular_end")
    assert regular_end == "16:00"


def test_strategy_config():
    """测试策略配置"""
    default_symbol = config.get("strategy.default.symbol")
    assert default_symbol == "AAPL"

    buy_interval = config.get("strategy.simple_buy.buy_interval")
    assert buy_interval == 10


def test_reload_config():
    """测试重新加载配置"""
    host_before = config.get("ibkr.host")

    config.reload()

    host_after = config.get("ibkr.host")
    assert host_before == host_after


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
