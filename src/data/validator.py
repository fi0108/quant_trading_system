"""
数据验证器

验证行情数据质量，检测异常数据并提供降级策略
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from common.exceptions import (
    DataMissingError,
    DataFormatError,
    DataQualityError,
    ExceptionMessages
)

logger = logging.getLogger(__name__)


class DataValidator:
    """
    数据验证器

    功能：
    - 检查必需字段
    - 验证数据类型
    - 检查数据合理性
    - 提供降级数据
    """

    def __init__(self, price_jump_threshold: float = 0.2):
        """
        初始化验证器

        Args:
            price_jump_threshold: 价格跳变阈值（百分比）
        """
        self.price_jump_threshold = price_jump_threshold
        self.last_valid_data: Dict[str, Dict[str, Any]] = {}
        self.validation_stats: Dict[str, int] = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'fallback_used': 0
        }

    def validate(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证数据并返回清洗后的数据

        Args:
            symbol: 标的符号
            data: 原始数据

        Returns:
            验证通过或降级后的数据

        Raises:
            DataException: 无法降级时抛出
        """
        self.validation_stats['total'] += 1

        try:
            # 1. 检查必需字段
            self._check_required_fields(data)

            # 2. 检查数据类型
            self._check_data_types(data)

            # 3. 检查数据合理性
            self._check_data_reasonableness(symbol, data)

            # 4. 更新最后有效数据
            self.last_valid_data[symbol] = data.copy()
            self.validation_stats['passed'] += 1

            return data

        except (DataMissingError, DataFormatError, DataQualityError) as e:
            logger.warning(f"Data validation failed for {symbol}: {e}")
            self.validation_stats['failed'] += 1

            # 尝试使用降级数据
            fallback_data = self._get_fallback_data(symbol)
            if fallback_data:
                self.validation_stats['fallback_used'] += 1
                logger.info(f"Using fallback data for {symbol}")
                return fallback_data
            else:
                logger.error(f"No fallback data available for {symbol}")
                raise

    def _check_required_fields(self, data: Dict[str, Any]):
        """
        检查必需字段

        Args:
            data: 数据字典

        Raises:
            DataMissingError: 缺少必需字段
        """
        required_fields = ['time', 'open', 'high', 'low', 'close', 'volume']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise DataMissingError(
                ExceptionMessages.DATA_MISSING_FIELDS.format(
                    fields=', '.join(missing_fields)
                ),
                context={'missing_fields': missing_fields}
            )

    def _check_data_types(self, data: Dict[str, Any]):
        """
        检查数据类型

        Args:
            data: 数据字典

        Raises:
            DataFormatError: 数据类型错误
        """
        # 检查价格字段
        price_fields = ['open', 'high', 'low', 'close']
        for field in price_fields:
            if field in data:
                value = data[field]
                if not isinstance(value, (int, float)):
                    raise DataFormatError(
                        ExceptionMessages.DATA_INVALID_TYPE.format(
                            field=field,
                            expected='float',
                            actual=type(value).__name__
                        ),
                        context={'field': field, 'value': value, 'type': type(value).__name__}
                    )

        # 检查成交量
        if 'volume' in data:
            volume = data['volume']
            if not isinstance(volume, (int, float)):
                raise DataFormatError(
                    ExceptionMessages.DATA_INVALID_TYPE.format(
                        field='volume',
                        expected='int/float',
                        actual=type(volume).__name__
                    ),
                    context={'field': 'volume', 'value': volume}
                )

        # 检查时间戳
        if 'time' in data:
            time_value = data['time']
            if not isinstance(time_value, (datetime, str, int, float)):
                raise DataFormatError(
                    ExceptionMessages.DATA_INVALID_TYPE.format(
                        field='time',
                        expected='datetime/str/timestamp',
                        actual=type(time_value).__name__
                    ),
                    context={'field': 'time', 'value': time_value}
                )

    def _check_data_reasonableness(self, symbol: str, data: Dict[str, Any]):
        """
        检查数据合理性

        Args:
            symbol: 标的符号
            data: 数据字典

        Raises:
            DataQualityError: 数据质量问题
        """
        # 检查价格是否为正
        price_fields = ['open', 'high', 'low', 'close']
        for field in price_fields:
            if field in data:
                price = data[field]
                if price <= 0:
                    raise DataQualityError(
                        ExceptionMessages.DATA_INVALID_PRICE.format(price=price),
                        context={'field': field, 'price': price}
                    )

        # 检查高低价关系
        if all(field in data for field in ['high', 'low']):
            if data['high'] < data['low']:
                raise DataQualityError(
                    f"High price ({data['high']}) < Low price ({data['low']})",
                    context={'high': data['high'], 'low': data['low']}
                )

        # 检查收盘价是否在高低价范围内
        if all(field in data for field in ['high', 'low', 'close']):
            if not (data['low'] <= data['close'] <= data['high']):
                raise DataQualityError(
                    f"Close price ({data['close']}) out of range [{data['low']}, {data['high']}]",
                    context={'close': data['close'], 'low': data['low'], 'high': data['high']}
                )

        # 检查价格跳变
        if symbol in self.last_valid_data and 'close' in data:
            self._check_price_jump(symbol, data['close'])

        # 检查成交量合理性
        if 'volume' in data and data['volume'] < 0:
            raise DataQualityError(
                f"Negative volume: {data['volume']}",
                context={'volume': data['volume']}
            )

    def _check_price_jump(self, symbol: str, current_price: float):
        """
        检查价格跳变

        Args:
            symbol: 标的符号
            current_price: 当前价格

        Raises:
            DataQualityError: 价格跳变过大
        """
        last_data = self.last_valid_data[symbol]
        last_price = last_data.get('close')

        if last_price and last_price > 0:
            change_pct = abs(current_price - last_price) / last_price

            if change_pct > self.price_jump_threshold:
                raise DataQualityError(
                    ExceptionMessages.DATA_PRICE_JUMP.format(
                        change_pct=change_pct * 100,
                        threshold=self.price_jump_threshold * 100
                    ),
                    context={
                        'symbol': symbol,
                        'last_price': last_price,
                        'current_price': current_price,
                        'change_pct': change_pct
                    }
                )

    def _get_fallback_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取降级数据（使用最后有效值）

        Args:
            symbol: 标的符号

        Returns:
            降级数据，如果没有则返回None
        """
        if symbol in self.last_valid_data:
            return self.last_valid_data[symbol].copy()
        return None

    def clear_cache(self, symbol: Optional[str] = None):
        """
        清除缓存数据

        Args:
            symbol: 标的符号，None表示清除所有
        """
        if symbol:
            if symbol in self.last_valid_data:
                del self.last_valid_data[symbol]
                logger.debug(f"Cleared cache for {symbol}")
        else:
            self.last_valid_data.clear()
            logger.debug("Cleared all cache")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取验证统计信息

        Returns:
            统计信息字典
        """
        total = self.validation_stats['total']
        passed = self.validation_stats['passed']
        failed = self.validation_stats['failed']
        fallback = self.validation_stats['fallback_used']

        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'fallback_used': fallback,
            'pass_rate': passed / total if total > 0 else 0,
            'fallback_rate': fallback / failed if failed > 0 else 0,
            'cached_symbols': list(self.last_valid_data.keys())
        }


def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    安全地从字典获取值

    Args:
        data: 数据字典
        key: 键名
        default: 默认值

    Returns:
        值或默认值
    """
    try:
        value = data.get(key, default)
        if value is None and default is not None:
            logger.debug(f"Key '{key}' not found, using default: {default}")
        return value
    except Exception as e:
        logger.error(f"Error accessing key '{key}': {e}")
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    安全地转换为float

    Args:
        value: 输入值
        default: 默认值

    Returns:
        float值或默认值
    """
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Cannot convert to float: {value}, using default: {default}")
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    安全地转换为int

    Args:
        value: 输入值
        default: 默认值

    Returns:
        int值或默认值
    """
    try:
        return int(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Cannot convert to int: {value}, using default: {default}")
        return default
