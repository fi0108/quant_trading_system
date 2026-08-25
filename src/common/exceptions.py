"""
异常类定义

定义系统中所有自定义异常类型，支持异常分类和统一处理
"""


class BaseException(Exception):
    """基础异常类"""

    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self):
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


# ============================================================================
# 系统级异常（需要立即告警）
# ============================================================================


class SystemException(BaseException):
    """系统级异常基类 - 需要人工介入"""

    pass


class ConnectionException(SystemException):
    """连接异常基类"""

    pass


class IBKRConnectionError(ConnectionException):
    """IBKR连接错误"""

    pass


class DatabaseConnectionError(ConnectionException):
    """数据库连接错误"""

    pass


class ConfigException(SystemException):
    """配置异常基类"""

    pass


class MissingConfigError(ConfigException):
    """配置缺失错误"""

    pass


class InvalidConfigError(ConfigException):
    """配置无效错误"""

    pass


# ============================================================================
# 业务级异常（记录日志，可自动恢复）
# ============================================================================


class BusinessException(BaseException):
    """业务级异常基类 - 可自动恢复"""

    pass


class DataException(BusinessException):
    """数据异常基类"""

    pass


class DataMissingError(DataException):
    """数据缺失错误"""

    pass


class DataFormatError(DataException):
    """数据格式错误"""

    pass


class DataQualityError(DataException):
    """数据质量错误"""

    pass


class OrderException(BusinessException):
    """订单异常基类"""

    pass


class OrderRejectError(OrderException):
    """订单拒绝错误"""

    pass


class OrderTimeoutError(OrderException):
    """订单超时错误"""

    pass


# ============================================================================
# 异常信息模板
# ============================================================================


class ExceptionMessages:
    """异常信息模板"""

    # 连接异常
    IBKR_CONNECTION_FAILED = "Failed to connect to IBKR: {host}:{port}"
    IBKR_CONNECTION_LOST = "IBKR connection lost"
    DATABASE_CONNECTION_FAILED = "Failed to connect to database: {host}:{database}"
    DATABASE_CONNECTION_LOST = "Database connection lost"

    # 配置异常
    CONFIG_MISSING = "Required configuration missing: {key}"
    CONFIG_INVALID = "Invalid configuration value: {key}={value}"

    # 数据异常
    DATA_MISSING_FIELDS = "Data missing required fields: {fields}"
    DATA_INVALID_TYPE = "Invalid data type for field '{field}': expected {expected}, got {actual}"
    DATA_PRICE_JUMP = "Price jump too large: {change_pct:.1f}% (threshold: {threshold:.1f}%)"
    DATA_INVALID_PRICE = "Invalid price value: {price}"

    # 订单异常
    ORDER_REJECTED = "Order rejected: {reason}"
    ORDER_TIMEOUT = "Order timeout after {timeout}s"
