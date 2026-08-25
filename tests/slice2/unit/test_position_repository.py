"""
持仓仓库单元测试
"""

import pytest

from common.models import Position
from data.storage.models import create_tables, database, drop_tables, init_database
from data.storage.position_repository import PositionRepository


@pytest.fixture(scope="module")
def setup_database():
    """设置测试数据库"""
    database.init("test_quant_trading", host="localhost", user="postgres", password="")
    with database:
        create_tables()
    yield
    with database:
        drop_tables()
    database.close()


@pytest.fixture
def clean_positions(setup_database):
    """每个测试前清空持仓表"""
    from data.storage.models import PositionModel

    with database.atomic():
        PositionModel.delete().execute()
    yield


def test_save_or_update_new_position(clean_positions):
    """测试保存新持仓"""
    position = Position(
        symbol="AAPL", quantity=100, avg_cost=150.00, current_price=155.00, market_value=15500.00, unrealized_pnl=500.00
    )

    result = PositionRepository.save_or_update(position)

    assert result is True

    # 验证保存成功
    retrieved = PositionRepository.get_by_symbol("AAPL")
    assert retrieved is not None
    assert retrieved.quantity == 100
    assert retrieved.avg_cost == 150.00


def test_save_or_update_existing_position(clean_positions):
    """测试更新已存在的持仓"""
    # 先保存一个持仓
    position = Position(symbol="AAPL", quantity=100, avg_cost=150.00, market_value=15000.00, unrealized_pnl=0.0)
    PositionRepository.save_or_update(position)

    # 更新持仓
    updated_position = Position(
        symbol="AAPL", quantity=150, avg_cost=152.00, market_value=23250.00, unrealized_pnl=450.00, current_price=155.00
    )

    result = PositionRepository.save_or_update(updated_position)

    assert result is True

    # 验证更新成功
    retrieved = PositionRepository.get_by_symbol("AAPL")
    assert retrieved.quantity == 150
    assert retrieved.avg_cost == 152.00


def test_get_by_symbol(clean_positions):
    """测试根据标的查询持仓"""
    position = Position(symbol="AAPL", quantity=100, avg_cost=150.00, market_value=15000.00, unrealized_pnl=0.0)
    PositionRepository.save_or_update(position)

    # 查询存在的持仓
    retrieved = PositionRepository.get_by_symbol("AAPL")
    assert retrieved is not None
    assert retrieved.symbol == "AAPL"

    # 查询不存在的持仓
    not_found = PositionRepository.get_by_symbol("TSLA")
    assert not_found is None


def test_get_all_positions(clean_positions):
    """测试获取所有持仓"""
    # 创建多个持仓
    symbols = ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"]
    for symbol in symbols:
        position = Position(symbol=symbol, quantity=100, avg_cost=150.00, market_value=15000.00, unrealized_pnl=0.0)
        PositionRepository.save_or_update(position)

    # 获取所有持仓
    positions = PositionRepository.get_all()

    assert len(positions) == 5
    assert set(p.symbol for p in positions) == set(symbols)


def test_delete_position(clean_positions):
    """测试删除持仓"""
    # 先保存持仓
    position = Position(symbol="AAPL", quantity=100, avg_cost=150.00, market_value=15000.00, unrealized_pnl=0.0)
    PositionRepository.save_or_update(position)

    # 删除持仓
    result = PositionRepository.delete("AAPL")
    assert result is True

    # 验证删除成功
    retrieved = PositionRepository.get_by_symbol("AAPL")
    assert retrieved is None

    # 删除不存在的持仓
    result = PositionRepository.delete("TSLA")
    assert result is False


def test_position_pnl_calculation(clean_positions):
    """测试持仓盈亏数据"""
    position = Position(
        symbol="AAPL",
        quantity=100,
        avg_cost=150.00,
        current_price=155.00,
        market_value=15500.00,
        unrealized_pnl=500.00,
        realized_pnl=100.00,
    )

    PositionRepository.save_or_update(position)

    # 验证盈亏数据
    retrieved = PositionRepository.get_by_symbol("AAPL")
    assert retrieved.unrealized_pnl == 500.00
    assert retrieved.realized_pnl == 100.00
    assert retrieved.market_value == 15500.00


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
