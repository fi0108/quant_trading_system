# Week 2 开发计划

**目标**: 基础设施完善 - 持续运行3天不崩溃  
**工期**: 25-30小时  
**切片**: Slice 2

---

## 📋 任务分解

### 1. 订单状态跟踪（6小时）

**目标**: 监听订单状态变化，成交后更新持仓

**文件位置**:
- `src/trading/order/tracker.py` - 订单状态跟踪器
- `src/trading/order/manager.py` - 增强订单管理器

**功能需求**:
- [ ] 监听 IBKR 订单状态事件
- [ ] 订单状态变化回调（Submitted → Filled → Cancelled）
- [ ] 成交后自动更新本地持仓
- [ ] 订单历史记录（内存 + 日志）

**测试**:
- `tests/slice2/unit/test_order_tracker.py`
- `tests/slice2/integration/test_order_lifecycle.py`

---

### 2. 持仓管理（6小时）

**目标**: 本地持仓跟踪，与IBKR定期同步，盈亏计算

**文件位置**:
- `src/trading/position/manager.py` - 增强持仓管理器
- `src/trading/position/sync.py` - 持仓同步器

**功能需求**:
- [ ] 本地持仓缓存
- [ ] 每分钟与 IBKR 同步一次
- [ ] 盈亏计算（未实现盈亏、已实现盈亏）
- [ ] 持仓变化事件通知

**测试**:
- `tests/slice2/unit/test_position_sync.py`
- `tests/slice2/integration/test_position_tracking.py`

---

### 3. 断线重连（6小时）

**目标**: 检测连接断开，自动重连（指数退避），重连后重新订阅

**文件位置**:
- `src/trading/connection/manager.py` - 增强连接管理器
- `src/trading/connection/reconnect.py` - 已有，需增强
- `src/trading/connection/state_machine.py` - 已有，需完善

**功能需求**:
- [ ] 连接断开检测（心跳机制）
- [ ] 自动重连（指数退避：5s, 15s, 30s, 60s）
- [ ] 重连后恢复订阅
- [ ] 连接状态事件通知

**测试**:
- `tests/slice2/unit/test_reconnect_strategy.py`
- `tests/slice2/integration/test_auto_reconnect.py`
- `tests/slice2/e2e/test_connection_stability.py`

---

### 4. PostgreSQL 存储（6小时）

**目标**: 订单表、持仓表、基础ORM封装、数据持久化

**文件位置**:
- `src/data/storage/database.py` - 数据库连接管理
- `src/data/storage/models.py` - ORM 模型（使用 peewee）
- `src/data/storage/order_repository.py` - 订单数据访问层
- `src/data/storage/position_repository.py` - 持仓数据访问层

**功能需求**:
- [ ] 数据库表设计（orders, positions, bars）
- [ ] 使用 peewee ORM
- [ ] 订单持久化（创建、更新、查询）
- [ ] 持仓快照持久化
- [ ] 数据库迁移脚本

**测试**:
- `tests/slice2/unit/test_database_models.py`
- `tests/slice2/integration/test_order_persistence.py`

---

### 5. 基础监控（4小时）

**目标**: 系统状态检查（连接、内存、CPU），邮件告警

**文件位置**:
- `src/monitoring/health_check.py` - 健康检查
- `src/monitoring/metrics.py` - 指标收集
- `src/monitoring/alerts.py` - 告警系统

**功能需求**:
- [ ] 健康检查：连接状态、内存使用、CPU使用
- [ ] 指标收集：订单数、持仓数、运行时长
- [ ] 邮件告警（连接断开、订单拒绝）
- [ ] 日志级别：ERROR 自动发送告警

**测试**:
- `tests/slice2/unit/test_health_check.py`
- `tests/slice2/integration/test_email_alerts.py`

---

## 🗄️ 数据库表设计

### orders 表
```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id INTEGER UNIQUE NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    action VARCHAR(4) NOT NULL,  -- BUY/SELL
    order_type VARCHAR(10) NOT NULL,  -- MARKET/LIMIT
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(10, 2),
    status VARCHAR(20) NOT NULL,  -- SUBMITTED/FILLED/CANCELLED
    filled_quantity INTEGER DEFAULT 0,
    avg_fill_price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
```

### positions 表
```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    quantity INTEGER NOT NULL,
    avg_cost DECIMAL(10, 2) NOT NULL,
    current_price DECIMAL(10, 2),
    market_value DECIMAL(12, 2),
    unrealized_pnl DECIMAL(12, 2),
    realized_pnl DECIMAL(12, 2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_positions_symbol ON positions(symbol);
```

### bars 表（Week 2 先创建表结构，暂不使用）
```sql
CREATE TABLE bars (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(10, 2) NOT NULL,
    high DECIMAL(10, 2) NOT NULL,
    low DECIMAL(10, 2) NOT NULL,
    close DECIMAL(10, 2) NOT NULL,
    volume INTEGER NOT NULL,
    bar_size VARCHAR(10) NOT NULL,  -- 5secs/1min/1hour/1day
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp, bar_size)
);

CREATE INDEX idx_bars_symbol_timestamp ON bars(symbol, timestamp DESC);
```

---

## 📊 验收标准

### 必须完成
- [ ] 订单状态跟踪正常工作
- [ ] 持仓与IBKR保持同步（误差<1%）
- [ ] 断线后30秒内自动重连
- [ ] 订单和持仓数据持久化到数据库
- [ ] 连接断开时发送邮件告警
- [ ] 模拟盘连续运行72小时不崩溃

### 可选优化
- [ ] Redis 缓存（提升查询性能）
- [ ] 复杂告警规则（阈值、频率限制）
- [ ] 性能监控（延迟、吞吐量）

---

## 🧪 测试结构

```
tests/slice2/
├── unit/                           # 单元测试
│   ├── test_order_tracker.py      # 订单跟踪器
│   ├── test_position_sync.py      # 持仓同步
│   ├── test_reconnect_strategy.py # 重连策略
│   ├── test_database_models.py    # 数据库模型
│   └── test_health_check.py       # 健康检查
│
├── integration/                    # 集成测试
│   ├── test_order_lifecycle.py    # 订单生命周期
│   ├── test_position_tracking.py  # 持仓跟踪
│   ├── test_auto_reconnect.py     # 自动重连
│   ├── test_order_persistence.py  # 订单持久化
│   └── test_email_alerts.py       # 邮件告警
│
└── e2e/                           # 端到端测试
    ├── test_72hour_stability.py   # 72小时稳定性测试
    └── test_connection_recovery.py # 连接恢复测试
```

---

## 🚀 开发顺序

### Day 1-2: 数据持久化（8小时）
1. 设计数据库表
2. 创建 ORM 模型
3. 实现订单和持仓持久化
4. 编写单元测试

### Day 3: 订单状态跟踪（6小时）
1. 实现订单状态监听
2. 订单状态变化回调
3. 编写单元和集成测试

### Day 4: 持仓管理（6小时）
1. 本地持仓缓存
2. 定时同步机制
3. 盈亏计算
4. 编写测试

### Day 5: 断线重连（6小时）
1. 增强连接管理器
2. 自动重连逻辑
3. 重连后恢复订阅
4. 编写测试

### Day 6: 监控告警（4小时）
1. 健康检查
2. 邮件告警
3. 编写测试
4. 集成测试

---

## 📝 下一步

开始开发任务1：PostgreSQL存储

准备好开始了吗？
