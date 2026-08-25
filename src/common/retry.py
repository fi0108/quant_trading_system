"""
重试装饰器

提供自动重试功能，支持指数退避策略
"""

import logging
import time
from functools import wraps
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable = None,
):
    """
    重试装饰器，支持指数退避

    Args:
        max_attempts: 最大尝试次数
        backoff: 退避倍数（指数增长）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数

    Example:
        @retry(max_attempts=3, backoff=2.0, exceptions=(TimeoutError,))
        def risky_operation():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            delay = 1.0

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1

                    if attempt >= max_attempts:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                        raise

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay}s..."
                    )

                    # 调用重试回调
                    if on_retry:
                        try:
                            on_retry(attempt, e)
                        except Exception as callback_error:
                            logger.error(f"Retry callback failed: {callback_error}")

                    time.sleep(delay)
                    delay *= backoff

        return wrapper

    return decorator


def retry_with_timeout(
    max_attempts: int = 3,
    backoff: float = 2.0,
    total_timeout: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    带总超时时间的重试装饰器

    Args:
        max_attempts: 最大尝试次数
        backoff: 退避倍数
        total_timeout: 总超时时间（秒）
        exceptions: 需要重试的异常类型

    Example:
        @retry_with_timeout(max_attempts=5, total_timeout=30.0)
        def slow_operation():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            attempt = 0
            delay = 1.0

            while attempt < max_attempts:
                # 检查是否超过总超时时间
                elapsed = time.time() - start_time
                if elapsed > total_timeout:
                    logger.error(f"Function {func.__name__} timeout after {elapsed:.1f}s " f"(limit: {total_timeout}s)")
                    raise TimeoutError(f"Operation timeout after {elapsed:.1f}s " f"({attempt} attempts)")

                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1

                    if attempt >= max_attempts:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                        raise

                    # 计算剩余时间
                    remaining = total_timeout - (time.time() - start_time)
                    if remaining <= 0:
                        logger.error(f"Function {func.__name__} timeout")
                        raise TimeoutError(f"Operation timeout after {attempt} attempts")

                    # 调整延迟时间，不超过剩余时间
                    actual_delay = min(delay, remaining)

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {actual_delay:.1f}s (remaining: {remaining:.1f}s)..."
                    )

                    time.sleep(actual_delay)
                    delay *= backoff

        return wrapper

    return decorator


class RetryContext:
    """
    重试上下文，用于在重试过程中共享状态

    Example:
        retry_ctx = RetryContext(max_attempts=3)

        while retry_ctx.should_retry():
            try:
                result = operation()
                break
            except Exception as e:
                retry_ctx.record_failure(e)
    """

    def __init__(self, max_attempts: int = 3, backoff: float = 2.0):
        self.max_attempts = max_attempts
        self.backoff = backoff
        self.attempt = 0
        self.delay = 1.0
        self.failures = []

    def should_retry(self) -> bool:
        """是否应该继续重试"""
        return self.attempt < self.max_attempts

    def record_failure(self, exception: Exception):
        """记录失败"""
        self.attempt += 1
        self.failures.append(exception)

        if self.should_retry():
            logger.warning(
                f"Attempt {self.attempt}/{self.max_attempts} failed: {exception}. " f"Retrying in {self.delay}s..."
            )
            time.sleep(self.delay)
            self.delay *= self.backoff
        else:
            logger.error(f"All {self.max_attempts} attempts failed. " f"Failures: {[str(e) for e in self.failures]}")

    def reset(self):
        """重置状态"""
        self.attempt = 0
        self.delay = 1.0
        self.failures.clear()
