"""
重试装饰器 - 单元测试
"""

import time
from unittest.mock import Mock

import pytest

from common.retry import RetryContext, retry, retry_with_timeout


class TestRetryDecorator:
    """重试装饰器测试"""

    def test_retry_success_on_first_attempt(self):
        """测试1：第一次尝试就成功"""
        mock_func = Mock(return_value="success")

        @retry(max_attempts=3)
        def operation():
            return mock_func()

        result = operation()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_success_on_second_attempt(self):
        """测试2：第二次尝试成功"""
        mock_func = Mock(side_effect=[ValueError("error"), "success"])

        @retry(max_attempts=3, backoff=1.0, exceptions=(ValueError,))
        def operation():
            return mock_func()

        result = operation()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_fail_after_max_attempts(self):
        """测试3：达到最大重试次数后失败"""
        mock_func = Mock(side_effect=ValueError("error"))

        @retry(max_attempts=3, backoff=1.0, exceptions=(ValueError,))
        def operation():
            return mock_func()

        with pytest.raises(ValueError):
            operation()

        assert mock_func.call_count == 3

    def test_retry_backoff(self):
        """测试4：指数退避延迟"""
        call_times = []

        @retry(max_attempts=3, backoff=2.0, exceptions=(ValueError,))
        def operation():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("error")
            return "success"

        result = operation()

        assert result == "success"
        assert len(call_times) == 3

        # 验证延迟时间
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # 第一次延迟约1秒，第二次延迟约2秒
        assert 0.9 < delay1 < 1.5
        assert 1.8 < delay2 < 2.5

    def test_retry_specific_exception_only(self):
        """测试5：只重试指定类型的异常"""
        mock_func = Mock(side_effect=RuntimeError("error"))

        @retry(max_attempts=3, backoff=1.0, exceptions=(ValueError,))
        def operation():
            return mock_func()

        # RuntimeError不在重试列表中，应该立即抛出
        with pytest.raises(RuntimeError):
            operation()

        assert mock_func.call_count == 1

    def test_retry_with_callback(self):
        """测试6：重试时的回调函数"""
        callback_calls = []

        def on_retry_callback(attempt, exception):
            callback_calls.append((attempt, str(exception)))

        mock_func = Mock(side_effect=[ValueError("error1"), ValueError("error2"), "success"])

        @retry(max_attempts=3, backoff=1.0, exceptions=(ValueError,), on_retry=on_retry_callback)
        def operation():
            return mock_func()

        result = operation()

        assert result == "success"
        assert len(callback_calls) == 2
        assert callback_calls[0] == (1, "error1")
        assert callback_calls[1] == (2, "error2")


class TestRetryWithTimeout:
    """带超时的重试装饰器测试"""

    def test_timeout_success_within_limit(self):
        """测试1：在超时时间内成功"""
        mock_func = Mock(return_value="success")

        @retry_with_timeout(max_attempts=3, total_timeout=10.0)
        def operation():
            return mock_func()

        result = operation()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_timeout_exceeded(self):
        """测试2：超过总超时时间"""

        def slow_operation():
            time.sleep(2)
            raise ValueError("error")

        @retry_with_timeout(max_attempts=10, backoff=2.0, total_timeout=3.0, exceptions=(ValueError,))
        def operation():
            return slow_operation()

        with pytest.raises(TimeoutError):
            operation()

    def test_timeout_adjust_delay(self):
        """测试3：超时时调整延迟时间"""
        call_times = []

        @retry_with_timeout(max_attempts=5, backoff=2.0, total_timeout=5.0, exceptions=(ValueError,))
        def operation():
            call_times.append(time.time())
            if len(call_times) < 10:  # 确保会超时
                raise ValueError("error")
            return "success"

        with pytest.raises(TimeoutError):
            operation()

        # 验证总时间不超过超时限制太多
        total_time = call_times[-1] - call_times[0]
        assert total_time < 6.0  # 允许一些误差


class TestRetryContext:
    """重试上下文测试"""

    def test_context_should_retry(self):
        """测试1：判断是否应该继续重试"""
        ctx = RetryContext(max_attempts=3)

        assert ctx.should_retry() is True
        ctx.attempt = 2
        assert ctx.should_retry() is True
        ctx.attempt = 3
        assert ctx.should_retry() is False

    def test_context_record_failure(self):
        """测试2：记录失败"""
        ctx = RetryContext(max_attempts=3, backoff=1.0)

        ctx.record_failure(ValueError("error1"))
        assert len(ctx.failures) == 1
        assert ctx.attempt == 1

        ctx.record_failure(ValueError("error2"))
        assert len(ctx.failures) == 2
        assert ctx.attempt == 2

    def test_context_usage(self):
        """测试3：完整使用流程"""
        ctx = RetryContext(max_attempts=3, backoff=1.0)
        call_count = 0

        while ctx.should_retry():
            try:
                call_count += 1
                if call_count < 3:
                    raise ValueError(f"error {call_count}")
                result = "success"
                break
            except ValueError as e:
                ctx.record_failure(e)

        assert result == "success"
        assert call_count == 3
        assert len(ctx.failures) == 2

    def test_context_reset(self):
        """测试4：重置状态"""
        ctx = RetryContext(max_attempts=3)

        ctx.record_failure(ValueError("error"))
        assert ctx.attempt == 1
        assert len(ctx.failures) == 1

        ctx.reset()
        assert ctx.attempt == 0
        assert len(ctx.failures) == 0
        assert ctx.delay == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
