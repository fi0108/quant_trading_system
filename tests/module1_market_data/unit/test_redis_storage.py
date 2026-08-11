"""
Redis存储器单元测试

测试目的：验证Redis操作逻辑（使用fakeredis）
依据文档：docs/测试/模块一_市场数据接入_测试文档.md 第3.4节
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from datetime import datetime
from src.connection.storage.redis_writer import RedisWriter

# 尝试导入fakeredis
try:
    import fakeredis
    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False


def create_valid_bar(**kwargs):
    """创建有效的Mock Bar数据"""
    bar = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 150.0,
        'high': 151.0,
        'low': 149.5,
        'close': 150.5,
        'volume': 100000
    }
    bar.update(kwargs)
    return bar


class TestRedisWriter:
    """Redis存储器单元测试类"""

    def test_key_generation(self):
        """
        测试用例1：键生成逻辑

        测试目的：验证Redis键格式
        输入：标的代码AAPL
        预期：生成键"AAPL:latest_bars"
        """
        writer = RedisWriter()

        key = writer._make_key('AAPL')

        assert key == 'AAPL:latest_bars', "键格式应该是 symbol:latest_bars"

    def test_key_generation_with_prefix(self):
        """
        测试用例1：键生成逻辑（带前缀）

        输入：标的代码TSLA，带前缀"test:"
        预期：生成键"test:TSLA:latest_bars"
        """
        writer = RedisWriter(key_prefix='test:')

        key = writer._make_key('TSLA')

        assert key == 'test:TSLA:latest_bars', "应该包含前缀"

    def test_serialization(self):
        """
        测试用例2：数据序列化

        测试目的：验证JSON序列化和反序列化
        输入：包含datetime对象的Bar数据
        验证点1：datetime转换为ISO格式字符串
        验证点2：反序列化后datetime恢复
        验证点3：数据完整性保持
        """
        writer = RedisWriter()

        bar = create_valid_bar()

        # 序列化
        json_str = writer._serialize_bar(bar)

        assert isinstance(json_str, str), "应该返回字符串"
        assert 'AAPL' in json_str, "应该包含标的代码"
        assert '2026-08-09' in json_str, "datetime应该转为ISO格式"

        # 反序列化
        restored = writer._deserialize_bar(json_str)

        assert restored['symbol'] == 'AAPL', "标的代码应该保持"
        assert isinstance(restored['timestamp'], datetime), "timestamp应该恢复为datetime对象"
        assert restored['close'] == 150.5, "价格数据应该保持"
        assert restored['volume'] == 100000, "成交量应该保持"

    @pytest.mark.skipif(not HAS_FAKEREDIS, reason="需要fakeredis库")
    def test_ltrim_logic(self):
        """
        测试用例3：LTRIM保留最新数据

        测试目的：验证只保留最新N根Bar
        前置条件：设置max_bars=5
        输入：连续写入10根Bar
        预期：Redis中只保留最新5根
        使用：fakeredis内存模拟
        """
        import fakeredis

        # 使用fakeredis
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        writer = RedisWriter(max_bars=5)
        writer._client = fake_redis
        writer._is_connected = True

        # 写入10根Bar
        for i in range(10):
            bar = create_valid_bar(close=100.0 + i, timestamp=datetime(2026, 8, 9, 9, 30 + i, 0))
            writer.write_bar('AAPL', bar)

        # 验证只保留5根
        count = writer.get_bar_count('AAPL')
        assert count == 5, f"应该只保留5根Bar，实际{count}根"

        # 验证是最新的5根
        bars = writer.get_latest_bars('AAPL', count=5)
        assert len(bars) == 5, "应该返回5根Bar"
        assert bars[0]['close'] == 109.0, "第一根应该是最新的（close=109）"
        assert bars[4]['close'] == 105.0, "第五根应该是第五新的（close=105）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
