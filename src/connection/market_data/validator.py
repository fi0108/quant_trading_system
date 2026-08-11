"""
数据验证器

职责：
1. 验证Bar数据的合理性
2. 检查价格完整性
3. 检查价格变动幅度
4. 检查时间连续性
5. 异常数据处理策略
"""

from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Bar数据验证器

    验证规则：
    1. 数据完整性：OHLCV字段非空且大于0
    2. 价格合理性：相邻两根Bar价格变动不超过阈值（默认20%）
    3. 时间连续性：相邻两根Bar时间间隔不超过阈值（默认5分钟）
    4. 逻辑一致性：high >= max(open, close), low <= min(open, close)
    """

    def __init__(
        self,
        max_price_change_percent: float = 0.20,  # 最大价格变动20%
        max_bar_gap_minutes: int = 5,  # 最大时间间隔5分钟
        min_volume: int = 0,  # 最小成交量
        strict_mode: bool = False  # 严格模式
    ):
        """
        初始化验证器

        Args:
            max_price_change_percent: 最大价格变动百分比（0.20 = 20%）
            max_bar_gap_minutes: 最大时间间隔（分钟）
            min_volume: 最小成交量
            strict_mode: 严格模式（True时拒绝所有异常，False时部分异常可填充）
        """
        self.max_price_change_percent = max_price_change_percent
        self.max_bar_gap_minutes = max_bar_gap_minutes
        self.min_volume = min_volume
        self.strict_mode = strict_mode

        # 缓存上一根Bar（按标的分别缓存）
        self._last_bars: Dict[str, dict] = {}

        # 统计
        self._total_validated = 0
        self._total_passed = 0
        self._total_failed = 0
        self._failed_reasons: Dict[str, int] = {}
        self._consecutive_failures: Dict[str, int] = {}  # 连续失败次数

    def validate(self, bar_data: dict) -> Tuple[bool, str, Optional[dict]]:
        """
        验证Bar数据

        Args:
            bar_data: Bar数据字典，必须包含：
                - symbol: 标的代码
                - timestamp: 时间戳
                - open, high, low, close: 价格
                - volume: 成交量

        Returns:
            (is_valid, error_msg, fixed_data)
            - is_valid: 是否通过验证
            - error_msg: 错误信息（通过时为空）
            - fixed_data: 修正后的数据（仅在非严格模式下有值）
        """
        self._total_validated += 1

        symbol = bar_data.get('symbol', 'UNKNOWN')

        # 1. 数据完整性检查
        is_complete, msg = self._check_completeness(bar_data)
        if not is_complete:
            return self._handle_failure(symbol, 'completeness', msg)

        # 2. 逻辑一致性检查
        is_consistent, msg = self._check_consistency(bar_data)
        if not is_consistent:
            return self._handle_failure(symbol, 'consistency', msg)

        # 3. 价格合理性检查（需要历史数据）
        if symbol in self._last_bars:
            is_reasonable, msg, fixed_bar = self._check_price_change(bar_data, self._last_bars[symbol])
            if not is_reasonable:
                if not self.strict_mode and fixed_bar:
                    # 非严格模式，返回修正后的数据
                    logger.warning(f"[{symbol}] 价格异常但已修正: {msg}")
                    self._update_last_bar(symbol, fixed_bar)
                    self._total_passed += 1
                    return True, "", fixed_bar
                else:
                    return self._handle_failure(symbol, 'price_change', msg)

        # 4. 时间连续性检查（需要历史数据）
        if symbol in self._last_bars:
            is_continuous, msg = self._check_time_gap(bar_data, self._last_bars[symbol])
            if not is_continuous:
                return self._handle_failure(symbol, 'time_gap', msg)

        # 验证通过
        self._update_last_bar(symbol, bar_data)
        self._total_passed += 1
        self._consecutive_failures[symbol] = 0  # 重置连续失败计数
        return True, "", None

    def _check_completeness(self, bar: dict) -> Tuple[bool, str]:
        """
        检查数据完整性

        Args:
            bar: Bar数据

        Returns:
            (is_complete, error_msg)
        """
        required_fields = ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume']

        # 检查字段存在
        for field in required_fields:
            if field not in bar:
                return False, f"缺少字段: {field}"

        # 检查价格字段非空且大于0
        price_fields = ['open', 'high', 'low', 'close']
        for field in price_fields:
            value = bar.get(field)
            if value is None or value <= 0:
                return False, f"价格字段 {field} 无效: {value}"

        # 检查成交量（允许为0，但不能为负）
        volume = bar.get('volume')
        if volume is None or volume < self.min_volume:
            return False, f"成交量无效: {volume} (最小: {self.min_volume})"

        return True, ""

    def _check_consistency(self, bar: dict) -> Tuple[bool, str]:
        """
        检查逻辑一致性

        Args:
            bar: Bar数据

        Returns:
            (is_consistent, error_msg)
        """
        open_price = bar['open']
        high = bar['high']
        low = bar['low']
        close = bar['close']

        # high应该是最高价
        max_price = max(open_price, close)
        if high < max_price:
            return False, f"high({high}) < max(open, close)({max_price})"

        # low应该是最低价
        min_price = min(open_price, close)
        if low > min_price:
            return False, f"low({low}) > min(open, close)({min_price})"

        # high应该 >= low
        if high < low:
            return False, f"high({high}) < low({low})"

        return True, ""

    def _check_price_change(
        self,
        current_bar: dict,
        previous_bar: dict
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        检查价格变动幅度

        Args:
            current_bar: 当前Bar
            previous_bar: 上一根Bar

        Returns:
            (is_reasonable, error_msg, fixed_bar)
        """
        prev_close = previous_bar['close']
        curr_open = current_bar['open']
        curr_close = current_bar['close']

        # 计算价格变动（对比上一根收盘价）
        change_from_open = abs(curr_open - prev_close) / prev_close
        change_from_close = abs(curr_close - prev_close) / prev_close

        max_change = max(change_from_open, change_from_close)

        if max_change > self.max_price_change_percent:
            msg = (
                f"价格变动过大: {max_change:.2%} > {self.max_price_change_percent:.2%}, "
                f"前收盘={prev_close:.2f}, 当前开盘={curr_open:.2f}, 当前收盘={curr_close:.2f}"
            )

            # 非严格模式：使用前值填充
            if not self.strict_mode:
                fixed_bar = current_bar.copy()
                fixed_bar['open'] = prev_close
                fixed_bar['high'] = prev_close
                fixed_bar['low'] = prev_close
                fixed_bar['close'] = prev_close
                fixed_bar['_fixed'] = True
                return False, msg, fixed_bar

            return False, msg, None

        return True, "", None

    def _check_time_gap(self, current_bar: dict, previous_bar: dict) -> Tuple[bool, str]:
        """
        检查时间连续性

        Args:
            current_bar: 当前Bar
            previous_bar: 上一根Bar

        Returns:
            (is_continuous, error_msg)
        """
        curr_time = current_bar['timestamp']
        prev_time = previous_bar['timestamp']

        # 确保是datetime对象
        if isinstance(curr_time, str):
            curr_time = datetime.fromisoformat(curr_time)
        if isinstance(prev_time, str):
            prev_time = datetime.fromisoformat(prev_time)

        # 计算时间间隔（分钟）
        time_diff = (curr_time - prev_time).total_seconds() / 60

        if time_diff > self.max_bar_gap_minutes:
            return False, f"时间间隔过大: {time_diff:.1f}分钟 > {self.max_bar_gap_minutes}分钟"

        if time_diff < 0:
            return False, f"时间倒退: 当前时间({curr_time}) < 前一时间({prev_time})"

        return True, ""

    def _handle_failure(self, symbol: str, reason: str, msg: str) -> Tuple[bool, str, None]:
        """
        处理验证失败

        Args:
            symbol: 标的代码
            reason: 失败原因类型
            msg: 错误消息

        Returns:
            (False, error_msg, None)
        """
        self._total_failed += 1

        # 记录失败原因统计
        self._failed_reasons[reason] = self._failed_reasons.get(reason, 0) + 1

        # 记录连续失败次数
        self._consecutive_failures[symbol] = self._consecutive_failures.get(symbol, 0) + 1

        # 连续失败告警
        if self._consecutive_failures[symbol] >= 3:
            logger.error(f"[{symbol}] 连续验证失败 {self._consecutive_failures[symbol]} 次，建议暂停订阅")

        logger.warning(f"[{symbol}] 数据验证失败 ({reason}): {msg}")

        return False, msg, None

    def _update_last_bar(self, symbol: str, bar_data: dict):
        """
        更新缓存的上一根Bar

        Args:
            symbol: 标的代码
            bar_data: Bar数据
        """
        self._last_bars[symbol] = bar_data.copy()

    def get_consecutive_failures(self, symbol: str) -> int:
        """
        获取标的的连续失败次数

        Args:
            symbol: 标的代码

        Returns:
            连续失败次数
        """
        return self._consecutive_failures.get(symbol, 0)

    def should_pause_subscription(self, symbol: str, threshold: int = 3) -> bool:
        """
        判断是否应该暂停标的订阅

        Args:
            symbol: 标的代码
            threshold: 连续失败阈值

        Returns:
            是否应该暂停
        """
        return self.get_consecutive_failures(symbol) >= threshold

    def reset_failures(self, symbol: str):
        """
        重置标的的失败计数

        Args:
            symbol: 标的代码
        """
        self._consecutive_failures[symbol] = 0
        logger.info(f"[{symbol}] 失败计数已重置")

    def get_stats(self) -> dict:
        """
        获取验证统计信息

        Returns:
            统计信息字典
        """
        pass_rate = (self._total_passed / self._total_validated * 100) if self._total_validated > 0 else 0

        return {
            'total_validated': self._total_validated,
            'total_passed': self._total_passed,
            'total_failed': self._total_failed,
            'pass_rate': f"{pass_rate:.2f}%",
            'failed_reasons': self._failed_reasons.copy(),
            'consecutive_failures': self._consecutive_failures.copy(),
            'config': {
                'max_price_change_percent': self.max_price_change_percent,
                'max_bar_gap_minutes': self.max_bar_gap_minutes,
                'min_volume': self.min_volume,
                'strict_mode': self.strict_mode
            }
        }

    def reset_stats(self):
        """重置统计信息"""
        self._total_validated = 0
        self._total_passed = 0
        self._total_failed = 0
        self._failed_reasons.clear()
        logger.debug("验证统计信息已重置")
