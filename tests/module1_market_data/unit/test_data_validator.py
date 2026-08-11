"""
数据验证器单元测试

测试目的：验证Bar数据验证逻辑
依据文档：docs/测试/模块一_市场数据接入_测试文档.md 第3.3节
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from datetime import datetime
from src.connection.market_data.validator import DataValidator


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


class TestDataValidator:
    """数据验证器单元测试类"""

    def test_completeness_missing_field(self):
        """
        测试用例1：数据完整性检查（缺失字段）

        测试目的：检测缺失字段
        输入：缺少high字段的Bar数据
        预期：验证失败，错误信息包含"缺少字段"
        使用：Mock数据
        """
        validator = DataValidator()

        # 缺少high字段
        incomplete_bar = create_valid_bar()
        del incomplete_bar['high']

        is_valid, msg, _ = validator.validate(incomplete_bar)

        assert is_valid == False, "缺少字段应该验证失败"
        assert "缺少" in msg or "high" in msg.lower(), "错误信息应包含缺失字段"

    def test_completeness_zero_price(self):
        """
        测试用例1：数据完整性检查（零价格）

        输入：价格为0的Bar数据
        预期：验证失败
        """
        validator = DataValidator()

        # 价格为0
        zero_price_bar = create_valid_bar(open=0.0)

        is_valid, msg, _ = validator.validate(zero_price_bar)

        assert is_valid == False, "价格为0应该验证失败"

    def test_completeness_negative_volume(self):
        """
        测试用例1：数据完整性检查（负成交量）

        输入：负成交量的Bar数据
        预期：验证失败
        """
        validator = DataValidator()

        # 负成交量
        negative_volume_bar = create_valid_bar(volume=-100)

        is_valid, msg, _ = validator.validate(negative_volume_bar)

        assert is_valid == False, "负成交量应该验证失败"

    def test_consistency_high_less_than_low(self):
        """
        测试用例2：逻辑一致性检查（high < low）

        测试目的：检测价格逻辑错误
        输入：high小于low的Bar
        预期：验证失败
        """
        validator = DataValidator()

        # high < low
        bad_bar = create_valid_bar(high=149.0, low=151.0)

        is_valid, msg, _ = validator.validate(bad_bar)

        assert is_valid == False, "high<low应该验证失败"
        assert "high" in msg.lower() or "low" in msg.lower(), "错误信息应包含high/low"

    def test_consistency_high_less_than_close(self):
        """
        测试用例2：逻辑一致性检查（high < close）

        输入：high小于close的Bar
        预期：验证失败
        """
        validator = DataValidator()

        # high < close
        bad_bar = create_valid_bar(high=149.0, close=150.0)

        is_valid, msg, _ = validator.validate(bad_bar)

        assert is_valid == False, "high<close应该验证失败"

    def test_price_change_excessive_strict_mode(self):
        """
        测试用例3：价格变动检查（超过阈值，严格模式）

        测试目的：检测异常价格波动
        前置条件：第一根Bar收盘价100，严格模式
        输入：第二根Bar开盘价150（涨幅50%）
        预期：验证失败（超过20%阈值）
        """
        # 使用严格模式
        validator = DataValidator(max_price_change_percent=0.20, strict_mode=True)

        # 第一根Bar
        bar1 = create_valid_bar(close=100.0, open=99.0, high=101.0, low=98.0)
        validator.validate(bar1)

        # 第二根Bar暴涨50%
        bar2 = create_valid_bar(
            timestamp=datetime(2026, 8, 9, 9, 31, 0),
            open=150.0,
            close=150.5,
            high=151.0,
            low=149.5
        )
        is_valid, msg, fixed = validator.validate(bar2)

        assert is_valid == False, "严格模式下50%涨幅应该验证失败"
        assert fixed is None, "严格模式下不应该返回修正数据"
        assert "价格" in msg or "变动" in msg, "错误信息应包含价格变动"

    def test_price_change_excessive_non_strict_mode(self):
        """
        测试用例3：价格变动检查（超过阈值，非严格模式）

        测试目的：验证非严格模式的自动修正
        前置条件：第一根Bar收盘价100，非严格模式
        输入：第二根Bar开盘价150（涨幅50%）
        预期：验证失败但返回修正数据
        """
        # 非严格模式（默认）
        validator = DataValidator(max_price_change_percent=0.20, strict_mode=False)

        # 第一根Bar
        bar1 = create_valid_bar(close=100.0, open=99.0, high=101.0, low=98.0)
        validator.validate(bar1)

        # 第二根Bar暴涨50%
        bar2 = create_valid_bar(
            timestamp=datetime(2026, 8, 9, 9, 31, 0),
            open=150.0,
            close=150.5,
            high=151.0,
            low=149.5
        )
        is_valid, msg, fixed = validator.validate(bar2)

        # 非严格模式：会返回修正数据
        assert is_valid == True, "非严格模式应该返回True（但有修正数据）"
        assert fixed is not None, "应该返回修正后的数据"
        assert fixed['close'] == 100.0, "修正后价格应该使用前收盘价"
        assert '_fixed' in fixed, "修正数据应该有_fixed标记"

    def test_price_change_normal(self):
        """
        测试用例3：价格变动检查（正常范围）

        输入：第二根Bar开盘价105（涨幅5%）
        预期：验证通过
        """
        validator = DataValidator(max_price_change_percent=0.20)

        # 第一根Bar
        bar1 = create_valid_bar(close=100.0, open=99.0, high=101.0, low=98.0)
        validator.validate(bar1)

        # 第二根Bar涨5%
        bar2 = create_valid_bar(
            timestamp=datetime(2026, 8, 9, 9, 31, 0),
            open=105.0,
            close=105.5,
            high=106.0,
            low=104.5
        )
        is_valid, msg, _ = validator.validate(bar2)

        assert is_valid == True, "5%涨幅应该在20%阈值内"

    def test_time_gap_excessive(self):
        """
        测试用例4：时间连续性检查（超过阈值）

        测试目的：检测时间间隔异常
        输入：两根Bar相隔10分钟
        预期：验证失败（超过5分钟阈值）
        """
        validator = DataValidator(max_bar_gap_minutes=5)

        # 第一根Bar：09:30
        bar1 = create_valid_bar(timestamp=datetime(2026, 8, 9, 9, 30, 0))
        validator.validate(bar1)

        # 第二根Bar：09:40（相隔10分钟）
        bar2 = create_valid_bar(timestamp=datetime(2026, 8, 9, 9, 40, 0))
        is_valid, msg, _ = validator.validate(bar2)

        assert is_valid == False, "10分钟间隔应该超过5分钟阈值"
        assert "时间" in msg or "间隔" in msg, "错误信息应包含时间间隔"

    def test_time_gap_normal(self):
        """
        测试用例4：时间连续性检查（正常范围）

        输入：两根Bar相隔1分钟
        预期：验证通过
        """
        validator = DataValidator(max_bar_gap_minutes=5)

        # 第一根Bar：09:30
        bar1 = create_valid_bar(timestamp=datetime(2026, 8, 9, 9, 30, 0))
        validator.validate(bar1)

        # 第二根Bar：09:31（相隔1分钟）
        bar2 = create_valid_bar(timestamp=datetime(2026, 8, 9, 9, 31, 0))
        is_valid, msg, _ = validator.validate(bar2)

        assert is_valid == True, "1分钟间隔应该在5分钟阈值内"

    def test_time_backward(self):
        """
        测试用例4：时间连续性检查（时间倒退）

        输入：时间倒退的Bar
        预期：验证失败
        """
        validator = DataValidator()

        # 第一根Bar：09:30
        bar1 = create_valid_bar(timestamp=datetime(2026, 8, 9, 9, 30, 0))
        validator.validate(bar1)

        # 第二根Bar：09:29（时间倒退）
        bar2 = create_valid_bar(timestamp=datetime(2026, 8, 9, 9, 29, 0))
        is_valid, msg, _ = validator.validate(bar2)

        assert is_valid == False, "时间倒退应该验证失败"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
