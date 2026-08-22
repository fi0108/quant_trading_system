
"""测试配置管理模块"""

import pytest
from common.config import config, Config

def test_load_system_config():
    """测试加载system配置"""
    cfg = config.load('system')
    assert cfg is not None
    assert 'system' in cfg
    assert cfg['system']['local_timezone'] == 'Asia/Shanghai'

def test_load_ibkr_config():
    """测试加载ibkr配置"""
    cfg = config.load('ibkr')
    assert cfg is not None
    assert 'ibkr' in cfg

def test_get_config_value():
    """测试获取配置值"""
    host = config.get('ibkr', 'ibkr.host')
    assert host == '127.0.0.1'

    port = config.get('ibkr', 'ibkr.port')
    assert port == 4002  # 纸盘端口

def test_get_nested_config():
    """测试获取嵌套配置"""
    timezone = config.get('system', 'system.local_timezone')
    assert timezone == 'Asia/Shanghai'

    market_tz = config.get('system', 'system.market_timezone')
    assert market_tz == 'America/New_York'

def test_get_with_default():
    """测试默认值"""
    # 不存在的配置项应该返回默认值
    value = config.get('system', 'not.exist.key', 'default_value')
    assert value == 'default_value'

    # 存在的配置项不应该返回默认值
    host = config.get('ibkr', 'ibkr.host', 'default')
    assert host == '127.0.0.1'

def test_config_cache():
    """测试配置缓存"""
    # 第一次加载
    cfg1 = config.load('system')
    # 第二次应该返回缓存
    cfg2 = config.load('system')
    assert cfg1 is cfg2  # 应该是同一个对象

def test_reload_config():
    """测试重新加载配置"""
    cfg1 = config.load('system')
    cfg2 = config.reload('system')
    # 虽然内容相同，但应该是重新加载的对象
    assert cfg1 == cfg2

def test_clear_cache():
    """测试清除缓存"""
    config.load('system')
    config.load('ibkr')

    config.clear_cache()

    # 缓存应该被清空，重新加载
    cfg = config.load('system')
    assert cfg is not None

def test_file_not_found():
    """测试文件不存在的情况"""
    test_config = Config()
    with pytest.raises(FileNotFoundError):
        test_config.load('not_exist_file')

if __name__ == '__main__':
    # 运行所有测试
    test_load_system_config()
    test_load_ibkr_config()
    test_get_config_value()
    test_get_nested_config()
    test_get_with_default()
    test_config_cache()
    test_reload_config()
    test_clear_cache()
    print("All config tests passed")
