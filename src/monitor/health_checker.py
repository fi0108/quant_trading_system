"""
系统健康检查模块

监控系统关键指标
"""

from datetime import datetime
from typing import Dict, Optional

import psutil

from common.logger import log
from data.ibkr_client import IBKRClient
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


class HealthChecker:
    """
    系统健康检查器

    监控内容：
    - IBKR 连接状态
    - 系统资源使用（CPU、内存）
    - 订单和持仓统计
    - 数据库连接状态
    """

    def __init__(
        self,
        ibkr_client: Optional[IBKRClient] = None,
        order_manager: Optional[OrderManager] = None,
        position_manager: Optional[PositionManager] = None,
    ):
        """
        初始化健康检查器

        Args:
            ibkr_client: IBKR 客户端
            order_manager: 订单管理器
            position_manager: 持仓管理器
        """
        self.ibkr_client = ibkr_client
        self.order_manager = order_manager
        self.position_manager = position_manager

    def check_connection(self) -> Dict:
        """
        检查 IBKR 连接状态

        Returns:
            连接状态信息
        """
        if not self.ibkr_client:
            return {"status": "unknown", "message": "IBKR client not configured"}

        is_connected = self.ibkr_client.is_connected()

        return {
            "status": "healthy" if is_connected else "unhealthy",
            "connected": is_connected,
            "message": "Connected to IBKR Gateway" if is_connected else "Not connected to IBKR Gateway",
            "timestamp": datetime.now().isoformat(),
        }

    def check_memory(self, threshold_percent: float = 80.0) -> Dict:
        """
        检查内存使用

        Args:
            threshold_percent: 内存使用率阈值（百分比）

        Returns:
            内存使用信息
        """
        memory = psutil.virtual_memory()
        percent_used = memory.percent

        return {
            "status": "healthy" if percent_used < threshold_percent else "warning",
            "percent_used": percent_used,
            "total_mb": memory.total / (1024 * 1024),
            "available_mb": memory.available / (1024 * 1024),
            "used_mb": memory.used / (1024 * 1024),
            "threshold_percent": threshold_percent,
            "message": f"Memory usage: {percent_used:.1f}%",
            "timestamp": datetime.now().isoformat(),
        }

    def check_cpu(self, threshold_percent: float = 80.0, interval: float = 1.0) -> Dict:
        """
        检查 CPU 使用

        Args:
            threshold_percent: CPU 使用率阈值（百分比）
            interval: 采样间隔（秒）

        Returns:
            CPU 使用信息
        """
        percent_used = psutil.cpu_percent(interval=interval)

        return {
            "status": "healthy" if percent_used < threshold_percent else "warning",
            "percent_used": percent_used,
            "cpu_count": psutil.cpu_count(),
            "threshold_percent": threshold_percent,
            "message": f"CPU usage: {percent_used:.1f}%",
            "timestamp": datetime.now().isoformat(),
        }

    def check_orders(self) -> Dict:
        """
        检查订单统计

        Returns:
            订单统计信息
        """
        if not self.order_manager:
            return {"status": "unknown", "message": "Order manager not configured"}

        try:
            orders = self.order_manager.get_all_orders()
            order_count = len(orders)

            # 按状态统计
            from common.models import OrderStatus

            status_counts = {}
            for order in orders:
                status = order.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "status": "healthy",
                "total_orders": order_count,
                "by_status": status_counts,
                "message": f"Total orders: {order_count}",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            log.error(f"Error checking orders: {e}")
            return {"status": "error", "message": f"Error checking orders: {e}"}

    def check_positions(self) -> Dict:
        """
        检查持仓统计

        Returns:
            持仓统计信息
        """
        if not self.position_manager:
            return {"status": "unknown", "message": "Position manager not configured"}

        try:
            positions = self.position_manager.get_positions()
            position_count = len(positions)

            # 计算总市值和盈亏
            total_market_value = self.position_manager.get_total_market_value()
            total_unrealized_pnl = self.position_manager.get_total_unrealized_pnl()
            total_realized_pnl = self.position_manager.get_total_realized_pnl()

            return {
                "status": "healthy",
                "total_positions": position_count,
                "total_market_value": total_market_value,
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_realized_pnl": total_realized_pnl,
                "message": f"Total positions: {position_count}, Market value: ${total_market_value:.2f}",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            log.error(f"Error checking positions: {e}")
            return {"status": "error", "message": f"Error checking positions: {e}"}

    def check_database(self) -> Dict:
        """
        检查数据库连接

        Returns:
            数据库状态信息
        """
        try:
            from data.storage.models import database

            if database.is_closed():
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "message": "Database connection is closed",
                    "timestamp": datetime.now().isoformat(),
                }

            # 尝试简单查询
            database.execute_sql("SELECT 1")

            return {
                "status": "healthy",
                "connected": True,
                "message": "Database connection OK",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            log.error(f"Database health check failed: {e}")
            return {
                "status": "error",
                "connected": False,
                "message": f"Database error: {e}",
                "timestamp": datetime.now().isoformat(),
            }

    def check_all(self) -> Dict:
        """
        执行所有健康检查

        Returns:
            完整健康检查报告
        """
        log.info("Running health checks...")

        report = {
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "connection": self.check_connection(),
                "memory": self.check_memory(),
                "cpu": self.check_cpu(),
                "database": self.check_database(),
                "orders": self.check_orders(),
                "positions": self.check_positions(),
            },
        }

        # 计算总体状态
        statuses = [check["status"] for check in report["checks"].values()]

        if "error" in statuses or "unhealthy" in statuses:
            report["overall_status"] = "unhealthy"
        elif "warning" in statuses:
            report["overall_status"] = "warning"
        else:
            report["overall_status"] = "healthy"

        log.info(f"Health check completed: {report['overall_status']}")

        return report

    def print_report(self, report: Dict):
        """
        打印健康检查报告

        Args:
            report: 健康检查报告
        """
        log.info("=" * 80)
        log.info("System Health Report")
        log.info("=" * 80)

        log.info(f"Overall Status: {report['overall_status'].upper()}")
        log.info(f"Timestamp: {report['timestamp']}")
        log.info("-" * 80)

        for check_name, check_result in report["checks"].items():
            status = check_result["status"].upper()
            message = check_result.get("message", "N/A")

            status_symbol = {"HEALTHY": "✓", "WARNING": "⚠", "UNHEALTHY": "✗", "ERROR": "✗", "UNKNOWN": "?"}.get(
                status, "?"
            )

            log.info(f"{status_symbol} {check_name:15s}: {status:10s} - {message}")

        log.info("=" * 80)
