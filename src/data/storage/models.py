"""
数据库 ORM 模型

使用 peewee ORM 定义订单、持仓、K线数据表
"""

from datetime import datetime
from peewee import (
    Model,
    PostgresqlDatabase,
    CharField,
    IntegerField,
    DecimalField,
    DateTimeField,
    AutoField,
    SQL
)

from common.config import config
from common.logger import log


# 数据库连接（延迟初始化）
database = PostgresqlDatabase(None)


def init_database():
    """
    初始化数据库连接

    从配置文件读取数据库连接信息
    """
    database.init(
        config.get("database.postgres.database", "quant_trading"),
        host=config.get("database.postgres.host", "localhost"),
        port=config.get("database.postgres.port", 5432),
        user=config.get("database.postgres.user", "postgres"),
        password=config.get("database.postgres.password", ""),
    )

    db_name = config.get("database.postgres.database", "quant_trading")
    db_host = config.get("database.postgres.host", "localhost")
    log.info(f"Database initialized: {db_name}@{db_host}")



class BaseModel(Model):
    """基础模型"""

    class Meta:
        database = database


class OrderModel(BaseModel):
    """
    订单表模型

    存储订单的完整生命周期信息
    """

    id = AutoField()
    order_id = IntegerField(unique=True, index=True)
    symbol = CharField(max_length=10, index=True)
    action = CharField(max_length=4)  # BUY/SELL
    order_type = CharField(max_length=10)  # MARKET/LIMIT
    quantity = IntegerField()
    limit_price = DecimalField(max_digits=10, decimal_places=2, null=True)
    status = CharField(max_length=20, index=True)  # SUBMITTED/FILLED/CANCELLED/REJECTED
    filled_quantity = IntegerField(default=0)
    avg_fill_price = DecimalField(max_digits=10, decimal_places=2, null=True)
    commission = DecimalField(max_digits=10, decimal_places=2, null=True)
    created_at = DateTimeField(default=datetime.now, index=True)
    filled_at = DateTimeField(null=True)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'orders'

    def __str__(self):
        return f"Order(id={self.order_id}, {self.symbol}, {self.action} {self.quantity}@{self.order_type}, {self.status})"


class PositionModel(BaseModel):
    """
    持仓表模型

    存储当前持仓快照
    """

    id = AutoField()
    symbol = CharField(max_length=10, unique=True, index=True)
    quantity = IntegerField()
    avg_cost = DecimalField(max_digits=10, decimal_places=2)
    current_price = DecimalField(max_digits=10, decimal_places=2, null=True)
    market_value = DecimalField(max_digits=12, decimal_places=2, null=True)
    unrealized_pnl = DecimalField(max_digits=12, decimal_places=2, null=True)
    realized_pnl = DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'positions'

    def __str__(self):
        return f"Position({self.symbol}, qty={self.quantity}, cost={self.avg_cost}, pnl={self.unrealized_pnl})"


class BarModel(BaseModel):
    """
    K线数据表模型

    存储历史和实时K线数据
    """

    id = AutoField()
    symbol = CharField(max_length=10, index=True)
    timestamp = DateTimeField(index=True)
    open = DecimalField(max_digits=10, decimal_places=2)
    high = DecimalField(max_digits=10, decimal_places=2)
    low = DecimalField(max_digits=10, decimal_places=2)
    close = DecimalField(max_digits=10, decimal_places=2)
    volume = IntegerField()
    bar_size = CharField(max_length=10)  # 5secs/1min/1hour/1day
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'bars'
        indexes = (
            (('symbol', 'timestamp', 'bar_size'), True),  # 唯一索引
        )

    def __str__(self):
        return f"Bar({self.symbol}, {self.timestamp}, O={self.open} H={self.high} L={self.low} C={self.close})"


def create_tables():
    """
    创建所有数据库表

    如果表已存在则跳过
    """
    with database:
        database.create_tables([OrderModel, PositionModel, BarModel], safe=True)
        log.info("Database tables created successfully")


def drop_tables():
    """
    删除所有数据库表

    谨慎使用！会删除所有数据
    """
    with database:
        database.drop_tables([OrderModel, PositionModel, BarModel], safe=True)
        log.info("Database tables dropped")
