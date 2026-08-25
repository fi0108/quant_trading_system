"""
持仓数据访问层

提供持仓的增删改查操作
"""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from data.storage.models import PositionModel, database
from common.logger import log
from common.models import Position


class PositionRepository:
    """持仓数据仓库"""

    @staticmethod
    def save_or_update(position: Position) -> bool:
        """
        保存或更新持仓

        如果持仓已存在则更新，否则创建
        """
        try:
            with database.atomic():
                # 先检查是否存在
                existing = PositionModel.get_or_none(PositionModel.symbol == position.symbol)

                if existing:
                    # 更新
                    existing.quantity = position.quantity
                    existing.avg_cost = Decimal(str(position.avg_cost))
                    existing.current_price = Decimal(str(position.current_price)) if position.current_price else None
                    existing.market_value = Decimal(str(position.market_value))
                    existing.unrealized_pnl = Decimal(str(position.unrealized_pnl))
                    existing.realized_pnl = Decimal(str(position.realized_pnl))
                    existing.updated_at = datetime.now()
                    existing.save()
                else:
                    # 创建
                    PositionModel.create(
                        symbol=position.symbol,
                        quantity=position.quantity,
                        avg_cost=Decimal(str(position.avg_cost)),
                        current_price=Decimal(str(position.current_price)) if position.current_price else None,
                        market_value=Decimal(str(position.market_value)),
                        unrealized_pnl=Decimal(str(position.unrealized_pnl)),
                        realized_pnl=Decimal(str(position.realized_pnl)),
                        updated_at=datetime.now()
                    )

            log.info(f"Position saved: {position.symbol} ({position.quantity})")
            return True

        except Exception as e:
            log.error(f"Failed to save position {position.symbol}: {e}")
            return False

    @staticmethod
    def get_by_symbol(symbol: str) -> Optional[Position]:
        """
        根据标的查询持仓

        Args:
            symbol: 股票代码

        Returns:
            Position对象，不存在返回None
        """
        try:
            model = PositionModel.get(PositionModel.symbol == symbol)
            return PositionRepository._model_to_position(model)

        except PositionModel.DoesNotExist:
            return None

        except Exception as e:
            log.error(f"Failed to get position for {symbol}: {e}")
            return None

    @staticmethod
    def get_all() -> List[Position]:
        """
        获取所有持仓

        Returns:
            Position对象列表
        """
        try:
            models = PositionModel.select().order_by(PositionModel.symbol)
            return [PositionRepository._model_to_position(m) for m in models]

        except Exception as e:
            log.error(f"Failed to get positions: {e}")
            return []

    @staticmethod
    def delete(symbol: str) -> bool:
        """
        删除持仓记录

        Args:
            symbol: 股票代码

        Returns:
            True表示删除成功
        """
        try:
            query = PositionModel.delete().where(PositionModel.symbol == symbol)
            rows_deleted = query.execute()

            if rows_deleted > 0:
                log.info(f"Position deleted: {symbol}")
                return True
            else:
                log.warning(f"Position not found for deletion: {symbol}")
                return False

        except Exception as e:
            log.error(f"Failed to delete position {symbol}: {e}")
            return False

    @staticmethod
    def _model_to_position(model: PositionModel) -> Position:
        """
        将ORM模型转换为Position对象

        Args:
            model: PositionModel实例

        Returns:
            Position对象
        """
        return Position(
            symbol=model.symbol,
            quantity=model.quantity,
            avg_cost=float(model.avg_cost),
            current_price=float(model.current_price) if model.current_price else None,
            market_value=float(model.market_value) if model.market_value else None,
            unrealized_pnl=float(model.unrealized_pnl) if model.unrealized_pnl else None,
            realized_pnl=float(model.realized_pnl) if model.realized_pnl else 0
        )
