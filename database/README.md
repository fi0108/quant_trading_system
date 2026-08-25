# 数据库说明

## 📂 数据库管理

### 数据库名称
```
quant_trading
```

### 表结构来源
**唯一来源**: `src/data/storage/models.py`（使用 peewee ORM）

---

## 🚀 初始化数据库

### 1. 创建数据库（首次）
```bash
# PostgreSQL
createdb quant_trading

# 或使用 psql
psql -U postgres -c "CREATE DATABASE quant_trading;"
```

### 2. 初始化表结构
```bash
# 创建所有表
python scripts/init_database.py

# 重建所有表（删除后重新创建）
python scripts/init_database.py --recreate

# 仅删除表
python scripts/init_database.py --drop
```

---

## 📊 表结构

当前数据库包含以下表（由 ORM 自动创建）：

### 1. **orders** - 订单表
```python
- id: 自增主键
- order_id: IBKR订单ID（唯一索引）
- symbol: 股票代码
- action: BUY/SELL
- order_type: MARKET/LIMIT
- quantity: 数量
- status: 订单状态
- filled_quantity: 已成交数量
- avg_fill_price: 平均成交价
- created_at, filled_at, updated_at: 时间戳
```

### 2. **positions** - 持仓表
```python
- id: 自增主键
- symbol: 股票代码（唯一）
- quantity: 持仓数量
- avg_cost: 平均成本
- current_price: 当前价格
- market_value: 市值
- unrealized_pnl: 未实现盈亏
- realized_pnl: 已实现盈亏
- updated_at: 更新时间
```

### 3. **bars** - K线数据表
```python
- id: 自增主键
- symbol: 股票代码
- timestamp: 时间戳
- open, high, low, close: OHLC
- volume: 成交量
- bar_size: K线周期（5secs/1min/1hour/1day）
- created_at: 创建时间
- 唯一约束: (symbol, timestamp, bar_size)
```

---

## ⚠️ 重要规则

### ✅ 正确做法
- 所有表结构修改在 `src/data/storage/models.py` 中进行
- 使用 `scripts/init_database.py` 初始化数据库
- 通过 ORM（peewee）操作数据库

### ❌ 不要
- ❌ 不要手动编写 SQL 文件创建表
- ❌ 不要直接在数据库中手动建表
- ❌ 不要跳过 ORM 直接执行 SQL

### 📝 为什么？
- ORM 保证代码和数据库结构一致
- 自动处理类型转换
- 易于测试和迁移
- 单一真相来源

---

## 🔧 数据库配置

配置文件：`config/config.yaml`

```yaml
database:
  postgres:
    host: localhost
    port: 5432
    database: quant_trading
    user: postgres
    password: ""  # 从环境变量读取
```

环境变量：`.env.dev` 或 `.env`
```bash
DB_PASSWORD=your_password
```

---

## 📚 相关文件

| 文件 | 用途 |
|------|------|
| `src/data/storage/models.py` | ORM 模型定义（表结构） |
| `src/data/storage/order_repository.py` | 订单数据访问 |
| `src/data/storage/position_repository.py` | 持仓数据访问 |
| `scripts/init_database.py` | 数据库初始化脚本 |
| `tests/slice2/unit/test_database_models.py` | 数据库模型测试 |

---

## 🗂️ 归档说明

`database/archive/` 目录存放已废弃的文件：
- `init_schema.sql.old` - 旧的 SQL 初始化文件（已废弃，仅供参考）

---

## 🧪 验证数据库

```bash
# 1. 连接数据库
psql quant_trading

# 2. 查看所有表
\dt

# 预期输出：
#  orders
#  positions
#  bars

# 3. 查看表结构
\d orders
\d positions
\d bars

# 4. 退出
\q
```

---

## 📝 开发流程

### 添加新表
1. 在 `src/data/storage/models.py` 添加新模型
2. 运行 `python scripts/init_database.py --recreate`
3. 创建对应的 Repository
4. 编写单元测试

### 修改表结构
1. 修改 `models.py` 中的模型定义
2. （未来）使用迁移脚本
3. 当前：重建表 `--recreate`（开发阶段）

---

## 🎯 Week 2 进度

- ✅ Task 1: PostgreSQL 存储（已完成）
  - ✅ ORM 模型
  - ✅ Repository 层
  - ✅ 初始化脚本
  - ✅ 单元测试

---

**最后更新**: 2026-08-23  
**维护者**: 项目团队
