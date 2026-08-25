# 任务2：订单状态跟踪 - 实现计划

**开始时间**: 2026-08-23  
**预估时间**: 6小时  
**依赖**: PostgreSQL 存储（✅ 已完成）

---

## 📋 需求分析

### 目标
监听 IBKR 订单状态变化，自动更新数据库和本地持仓

### 核心功能
1. 监听 IBKR 订单事件
2. 订单状态变化回调
3. 自动更新数据库
4. 成交后通知持仓管理器

---

## 🏗️ 架构设计

### 组件关系
```
IBKR Gateway
    ↓ (事件推送)
OrderTracker（新建）
    ↓ (状态变化)
OrderRepository（已有）
    ↓ (持久化)
Database
    
OrderTracker（成交事件）
    ↓ (通知)
PositionManager（已有）
```

### 类设计

#### 1. OrderTracker
```python
class OrderTracker:
    """订单状态跟踪器"""
    
    def __init__(self, ib_client, order_repository, position_manager):
        self.ib = ib_client
        self.repo = order_repository
        self.position_mgr = position_manager
        self._callbacks = []
    
    def start(self):
        """开始跟踪"""
        # 注册 IBKR 事件
        self.ib.ib.orderStatusEvent += self._on_order_status
        self.ib.ib.execDetailsEvent += self._on_execution
    
    def _on_order_status(self, trade):
        """订单状态变化"""
        # 更新数据库
        # 触发回调
    
    def _on_execution(self, trade, fill):
        """订单成交"""
        # 更新数据库
        # 通知持仓管理器
```

---

## 📝 实现步骤

### Step 1: 创建 OrderTracker 类（1.5h）
- [ ] 创建文件 `src/trading/order/tracker.py`
- [ ] 实现初始化
- [ ] 注册 IBKR 事件
- [ ] 实现状态变化回调

### Step 2: 实现状态更新逻辑（1.5h）
- [ ] 解析 IBKR 订单状态
- [ ] 映射到本地状态
- [ ] 更新数据库
- [ ] 日志记录

### Step 3: 实现成交通知（1h）
- [ ] 检测订单完全成交
- [ ] 通知持仓管理器
- [ ] 记录成交详情

### Step 4: 增强 OrderManager（1h）
- [ ] 集成 OrderTracker
- [ ] 提供统一接口
- [ ] 订单历史查询

### Step 5: 单元测试（0.5h）
- [ ] Mock IBKR 事件
- [ ] 测试状态变化
- [ ] 测试数据库更新

### Step 6: 集成测试（0.5h）
- [ ] 真实 IBKR 连接
- [ ] 完整订单生命周期
- [ ] 验证持久化

---

## 🎯 验收标准

- [ ] 订单状态变化自动更新数据库
- [ ] 订单成交后通知持仓管理器
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] 日志完善

---

**准备开始实现！**
