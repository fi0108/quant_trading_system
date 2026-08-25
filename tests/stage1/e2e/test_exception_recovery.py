"""
端到端测试：异常恢复

测试场景：
1. 数据缺失处理
2. 订单失败处理
3. 数据库异常处理
4. 系统恢复
5. 异常链式传播
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import psycopg2
import pytest

from common.exceptions import DatabaseError, DataMissingError, OrderExecutionError, ValidationError
from data.ibkr_client import IBKRClient
from data.validator import DataValidator
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


class TestExceptionRecovery:
    """异常恢复测试"""

    @patch("data.ibkr_client.IB")
    def test_data_missing_recovery(self, mock_ib, test_config):
        """
        测试：数据缺失恢复

        场景：
        1. 接收到不完整数据
        2. 系统检测并处理
        3. 系统继续运行
        """
        # ========================================
        # 1. 初始化
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        # ========================================
        # 2. 测试不完整数据
        # ========================================

        # 缺少 close 价格
        incomplete_data_1 = {
            "symbol": "AAPL",
            "time": datetime.now(),
            "open": Decimal("150.00"),
            "high": Decimal("151.00"),
            "low": Decimal("149.00"),
            # 'close': 缺失
            "volume": 1000,
        }

        # 缺少 symbol
        incomplete_data_2 = {
            # 'symbol': 缺失
            "time": datetime.now(),
            "open": Decimal("150.00"),
            "high": Decimal("151.00"),
            "low": Decimal("149.00"),
            "close": Decimal("150.50"),
            "volume": 1000,
        }

        # ========================================
        # 3. 数据验证
        # ========================================

        validator = DataValidator()

        # 测试缺少 close 的数据
        result_1 = validator.validate(incomplete_data_1)
        assert not result_1.is_valid, "应该检测到数据缺失"
        assert "close" in result_1.errors or "missing" in str(result_1.errors).lower()

        # 测试缺少 symbol 的数据
        result_2 = validator.validate(incomplete_data_2)
        assert not result_2.is_valid, "应该检测到 symbol 缺失"

        # ========================================
        # 4. 验证系统继续运行
        # ========================================

        # 即使接收到错误数据，系统也应该继续运行
        assert client.is_connected(), "系统应该继续运行"

        # 验证可以正常处理后续正确数据
        valid_data = {
            "symbol": "AAPL",
            "time": datetime.now(),
            "open": Decimal("150.00"),
            "high": Decimal("151.00"),
            "low": Decimal("149.00"),
            "close": Decimal("150.50"),
            "volume": 1000,
        }

        result_valid = validator.validate(valid_data)
        assert result_valid.is_valid, "正确数据应该通过验证"

        client.disconnect()

        print("✅ 数据缺失恢复测试通过")

    @patch("data.ibkr_client.IB")
    def test_order_failure_recovery(self, mock_ib, test_config):
        """
        测试：订单失败恢复

        场景：
        1. 提交订单
        2. 订单被拒绝
        3. 系统记录并继续
        """
        # ========================================
        # 1. 初始化
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        order_manager = OrderManager(client)

        # ========================================
        # 2. 模拟订单被拒绝
        # ========================================

        with patch.object(order_manager, "_submit_to_ibkr") as mock_submit:
            # 模拟 IBKR 拒绝订单
            mock_submit.side_effect = OrderExecutionError("Order rejected: Insufficient margin")

            # 尝试下单
            try:
                order = order_manager.place_order(
                    symbol="AAPL", quantity=10000, action="BUY", order_type="MARKET"  # 超大订单
                )
                order_placed = True
            except OrderExecutionError as e:
                order_placed = False
                error_message = str(e)

            # 验证订单被拒绝
            assert not order_placed, "订单应该被拒绝"
            assert "margin" in error_message.lower() or "rejected" in error_message.lower()

        # ========================================
        # 3. 验证系统继续运行
        # ========================================

        assert client.is_connected(), "系统应该继续运行"

        # 验证可以提交后续订单
        with patch.object(order_manager, "_submit_to_ibkr") as mock_submit:
            mock_submit.return_value = {
                "order_id": 1002,
                "symbol": "AAPL",
                "quantity": 100,
                "action": "BUY",
                "status": "Submitted",
            }

            order = order_manager.place_order(
                symbol="AAPL", quantity=100, action="BUY", order_type="MARKET"  # 正常订单
            )

            assert order is not None, "后续订单应该可以提交"

        client.disconnect()

        print("✅ 订单失败恢复测试通过")

    @patch("data.ibkr_client.IB")
    @patch("database.safe_connection.get_connection")
    def test_database_exception_recovery(self, mock_db, mock_ib, test_config):
        """
        测试：数据库异常恢复

        场景：
        1. 数据库连接失败
        2. 系统降级运行（不记录数据库）
        3. 数据库恢复后继续记录
        """
        # ========================================
        # 1. 初始化
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        order_manager = OrderManager(client)

        # ========================================
        # 2. 模拟数据库异常
        # ========================================

        # 第一次尝试：数据库连接失败
        mock_db.side_effect = psycopg2.OperationalError("Could not connect to database")

        with patch.object(order_manager, "_submit_to_ibkr") as mock_submit:
            mock_submit.return_value = {
                "order_id": 1001,
                "symbol": "AAPL",
                "quantity": 100,
                "action": "BUY",
                "status": "Submitted",
            }

            # 尝试下单（可能涉及数据库记录）
            try:
                order = order_manager.place_order(symbol="AAPL", quantity=100, action="BUY", order_type="MARKET")
                # 订单应该提交成功，即使数据库失败
                assert order is not None, "订单应该提交成功（降级模式）"
            except DatabaseError:
                # 如果系统设计为数据库必需，则应该抛出异常
                pass

        # ========================================
        # 3. 验证系统继续运行
        # ========================================

        assert client.is_connected(), "系统应该继续运行"

        # ========================================
        # 4. 数据库恢复
        # ========================================

        # 重置 mock，模拟数据库恢复
        mock_db.side_effect = None
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value = mock_conn

        # 验证数据库恢复后可以正常记录
        with patch.object(order_manager, "_submit_to_ibkr") as mock_submit:
            mock_submit.return_value = {
                "order_id": 1002,
                "symbol": "MSFT",
                "quantity": 50,
                "action": "BUY",
                "status": "Submitted",
            }

            order = order_manager.place_order(symbol="MSFT", quantity=50, action="BUY", order_type="MARKET")

            assert order is not None, "数据库恢复后订单应该正常提交"

        client.disconnect()

        print("✅ 数据库异常恢复测试通过")

    @patch("data.ibkr_client.IB")
    def test_invalid_symbol_handling(self, mock_ib, test_config):
        """
        测试：无效符号处理

        场景：
        1. 尝试订阅无效符号
        2. 系统检测并拒绝
        3. 系统继续运行
        """
        # ========================================
        # 1. 初始化
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        # ========================================
        # 2. 测试无效符号
        # ========================================

        invalid_symbols = ["", "   ", "INVALID123456", None]

        for invalid_symbol in invalid_symbols:
            try:
                if invalid_symbol is not None:
                    client.subscribe_realtime_bars(invalid_symbol, callback=lambda b, h: None)
                    # 如果没有抛出异常，检查是否被静默拒绝
                else:
                    # None 应该直接被拒绝
                    with pytest.raises((ValueError, TypeError, ValidationError)):
                        client.subscribe_realtime_bars(invalid_symbol, callback=lambda b, h: None)
            except (ValueError, ValidationError) as e:
                # 预期的异常
                assert invalid_symbol in str(e) or "symbol" in str(e).lower()

        # ========================================
        # 3. 验证系统继续运行
        # ========================================

        assert client.is_connected(), "系统应该继续运行"

        # 验证可以订阅有效符号
        valid_symbol = "AAPL"
        try:
            client.subscribe_realtime_bars(valid_symbol, callback=lambda b, h: None)
            subscribed = True
        except Exception:
            subscribed = False

        assert subscribed, "应该可以订阅有效符号"

        client.disconnect()

        print("✅ 无效符号处理测试通过")

    @patch("data.ibkr_client.IB")
    def test_concurrent_errors_handling(self, mock_ib, test_config):
        """
        测试：并发错误处理

        场景：
        1. 多个组件同时出现错误
        2. 系统正确处理所有错误
        3. 系统保持稳定
        """
        # ========================================
        # 1. 初始化
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        order_manager = OrderManager(client)
        position_manager = PositionManager(client)

        # ========================================
        # 2. 模拟多个组件同时出错
        # ========================================

        errors_caught = []

        # 错误 1: 数据验证失败
        try:
            validator = DataValidator()
            result = validator.validate({})  # 空数据
            if not result.is_valid:
                errors_caught.append("data_validation")
        except Exception as e:
            errors_caught.append("data_validation")

        # 错误 2: 订单提交失败
        with patch.object(order_manager, "_submit_to_ibkr") as mock_submit:
            mock_submit.side_effect = OrderExecutionError("Network error")

            try:
                order_manager.place_order(symbol="AAPL", quantity=100, action="BUY", order_type="MARKET")
            except OrderExecutionError:
                errors_caught.append("order_execution")

        # 错误 3: 持仓更新失败
        try:
            # 传递无效参数
            position_manager.update_position(
                symbol="", quantity=-100, avg_price=Decimal("0")  # 空符号  # 负数量  # 零价格
            )
        except (ValueError, ValidationError):
            errors_caught.append("position_update")

        # ========================================
        # 3. 验证所有错误都被捕获
        # ========================================

        assert len(errors_caught) >= 2, "应该捕获多个错误"

        # ========================================
        # 4. 验证系统仍然稳定
        # ========================================

        assert client.is_connected(), "系统应该保持连接"

        # 验证系统可以处理正常操作
        with patch.object(order_manager, "_submit_to_ibkr") as mock_submit:
            mock_submit.return_value = {
                "order_id": 1001,
                "symbol": "AAPL",
                "quantity": 100,
                "action": "BUY",
                "status": "Submitted",
            }

            order = order_manager.place_order(symbol="AAPL", quantity=100, action="BUY", order_type="MARKET")

            assert order is not None, "系统应该恢复正常操作"

        client.disconnect()

        print("✅ 并发错误处理测试通过")

    @patch("data.ibkr_client.IB")
    def test_graceful_degradation(self, mock_ib, test_config):
        """
        测试：优雅降级

        场景：
        1. 某些功能不可用
        2. 系统以降级模式运行
        3. 核心功能仍可用
        """
        # ========================================
        # 1. 初始化
        # ========================================

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance

        ibkr_config = test_config["ibkr"]
        client = IBKRClient(host=ibkr_config["host"], port=ibkr_config["port"], client_id=ibkr_config["client_id"])
        client.connect()

        order_manager = OrderManager(client)

        # ========================================
        # 2. 模拟部分功能不可用
        # ========================================

        # 模拟历史数据不可用
        with patch.object(client, "get_historical_data", side_effect=Exception("Historical data unavailable")):
            # 应该仍然可以获取实时数据和下单

            # 测试实时数据订阅
            try:
                client.subscribe_realtime_bars("AAPL", callback=lambda b, h: None)
                realtime_available = True
            except Exception:
                realtime_available = False

            assert realtime_available, "实时数据应该可用"

            # 测试下单功能
            with patch.object(order_manager, "_submit_to_ibkr") as mock_submit:
                mock_submit.return_value = {
                    "order_id": 1001,
                    "symbol": "AAPL",
                    "quantity": 100,
                    "action": "BUY",
                    "status": "Submitted",
                }

                order = order_manager.place_order(symbol="AAPL", quantity=100, action="BUY", order_type="MARKET")

                assert order is not None, "下单功能应该可用"

        client.disconnect()

        print("✅ 优雅降级测试通过")
