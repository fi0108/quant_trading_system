"""
数据验证器 - 单元测试
"""

from datetime import datetime

import pytest

from common.exceptions import DataFormatError, DataMissingError, DataQualityError
from data.validator import DataValidator, safe_float, safe_get, safe_int


class TestDataValidator:
    """数据验证器测试"""

    def setup_method(self):
        """每个测试前的设置"""
        self.validator = DataValidator(price_jump_threshold=0.2)

    def test_validate_valid_data(self):
        """测试1：验证有效数据"""
        data = {"time": datetime.now(), "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 1000}

        result = self.validator.validate("AAPL", data)

        assert result == data
        assert self.validator.validation_stats["passed"] == 1

    def test_missing_required_fields(self):
        """测试2：缺少必需字段"""
        data = {"time": datetime.now(), "close": 100.0}

        with pytest.raises(DataMissingError) as exc_info:
            self.validator.validate("AAPL", data)

        assert "open" in str(exc_info.value)
        assert self.validator.validation_stats["failed"] == 1

    def test_invalid_data_type(self):
        """测试3：数据类型错误"""
        data = {
            "time": datetime.now(),
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": "invalid",  # 应该是数字
            "volume": 1000,
        }

        with pytest.raises(DataFormatError) as exc_info:
            self.validator.validate("AAPL", data)

        assert "close" in str(exc_info.value)

    def test_negative_price(self):
        """测试4：负价格"""
        data = {
            "time": datetime.now(),
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": -10.0,  # 负价格
            "volume": 1000,
        }

        with pytest.raises(DataQualityError):
            self.validator.validate("AAPL", data)

    def test_high_lower_than_low(self):
        """测试5：最高价低于最低价"""
        data = {
            "time": datetime.now(),
            "open": 100.0,
            "high": 95.0,  # 高价低于低价
            "low": 99.0,
            "close": 97.0,
            "volume": 1000,
        }

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate("AAPL", data)

        assert "High" in str(exc_info.value) or "Low" in str(exc_info.value)

    def test_close_out_of_range(self):
        """测试6：收盘价超出高低价范围"""
        data = {
            "time": datetime.now(),
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 110.0,  # 超出范围
            "volume": 1000,
        }

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate("AAPL", data)

        assert "out of range" in str(exc_info.value).lower()

    def test_price_jump_detection(self):
        """测试7：价格跳变检测"""
        # 第一次数据
        data1 = {"time": datetime.now(), "open": 100.0, "high": 105.0, "low": 99.0, "close": 100.0, "volume": 1000}
        self.validator.validate("AAPL", data1)

        # 第二次数据，价格跳变超过20%
        data2 = {
            "time": datetime.now(),
            "open": 130.0,
            "high": 135.0,
            "low": 129.0,
            "close": 130.0,  # 从100跳到130，涨幅30%
            "volume": 1000,
        }

        # 价格跳变被检测到，应该返回降级数据（上次有效值）
        result = self.validator.validate("AAPL", data2)

        assert result == data1  # 返回上次有效数据
        assert self.validator.validation_stats["fallback_used"] == 1

    def test_fallback_data(self):
        """测试8：使用降级数据"""
        # 第一次有效数据
        valid_data = {"time": datetime.now(), "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 1000}
        self.validator.validate("AAPL", valid_data)

        # 第二次无效数据
        invalid_data = {"time": datetime.now(), "close": -10.0}  # 缺少字段且价格无效

        # 应该返回上次有效数据
        result = self.validator.validate("AAPL", invalid_data)

        assert result == valid_data
        assert self.validator.validation_stats["fallback_used"] == 1

    def test_no_fallback_data_available(self):
        """测试9：无降级数据可用"""
        invalid_data = {"time": datetime.now(), "close": -10.0}

        # 第一次验证，没有历史数据
        with pytest.raises(DataMissingError):
            self.validator.validate("AAPL", invalid_data)

    def test_get_stats(self):
        """测试10：获取统计信息"""
        # 验证几次数据
        valid_data = {"time": datetime.now(), "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 1000}

        self.validator.validate("AAPL", valid_data)
        self.validator.validate("TSLA", valid_data)

        stats = self.validator.get_stats()

        assert stats["total"] == 2
        assert stats["passed"] == 2
        assert stats["pass_rate"] == 1.0
        assert "AAPL" in stats["cached_symbols"]
        assert "TSLA" in stats["cached_symbols"]

    def test_clear_cache(self):
        """测试11：清除缓存"""
        data = {"time": datetime.now(), "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 1000}

        self.validator.validate("AAPL", data)
        self.validator.validate("TSLA", data)

        # 清除单个标的
        self.validator.clear_cache("AAPL")
        assert "AAPL" not in self.validator.last_valid_data
        assert "TSLA" in self.validator.last_valid_data

        # 清除所有
        self.validator.clear_cache()
        assert len(self.validator.last_valid_data) == 0


class TestSafeHelpers:
    """安全辅助函数测试"""

    def test_safe_get_existing_key(self):
        """测试1：获取存在的键"""
        data = {"price": 100.0}
        result = safe_get(data, "price", default=0.0)
        assert result == 100.0

    def test_safe_get_missing_key(self):
        """测试2：获取不存在的键"""
        data = {"price": 100.0}
        result = safe_get(data, "volume", default=0)
        assert result == 0

    def test_safe_float_valid(self):
        """测试3：转换有效float"""
        assert safe_float("100.5") == 100.5
        assert safe_float(100) == 100.0

    def test_safe_float_invalid(self):
        """测试4：转换无效float"""
        assert safe_float("invalid", default=0.0) == 0.0
        assert safe_float(None, default=-1.0) == -1.0

    def test_safe_int_valid(self):
        """测试5：转换有效int"""
        assert safe_int("100") == 100
        assert safe_int(100.5) == 100

    def test_safe_int_invalid(self):
        """测试6：转换无效int"""
        assert safe_int("invalid", default=0) == 0
        assert safe_int(None, default=-1) == -1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
