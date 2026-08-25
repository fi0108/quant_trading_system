# 任务2：风控增强 - 设计文档

**时间**: 2026-08-25  
**预估**: 6小时

---

## 📋 一、需求分析

### 1.1 核心需求
实现多层风控机制，在订单下单前进行全面检查，防止策略异常导致资金损失。

### 1.2 使用场景

```python
# 场景1：下单前风控检查
risk_manager = RiskManager()
result = risk_manager.check_order(order)

if result.passed:
    # 执行下单
    place_order(order)
else:
    # 拒绝订单
    log.warning(f"Order rejected: {result.reason}")

# 场景2：持仓检查
if risk_manager.check_position_limit("AAPL", 100):
    # 可以买入
    buy("AAPL", 100)
else:
    # 超过持仓限制
    log.warning("Position limit exceeded")

# 场景3：热更新配置
risk_manager.reload_config()
log.info("Risk config reloaded")
```

### 1.3 关键问题清单

#### Q1: 风控在哪个环节执行？
- **下单前检查**：在 `MarketOrder()` / `LimitOrder()` 前执行
- **持仓检查**：在买入前检查是否超限
- **交易频率检查**：统计单日交易次数

#### Q2: 风控如何配置？
- **配置文件**：`config/risk_config.yaml`
- **热更新**：监听文件变化，自动重新加载
- **优先级**：全局配置 < 策略配置 < 运行时覆盖

#### Q3: 风控触发后如何处理？
- **拒绝订单**：返回失败结果，不执行下单
- **记录日志**：详细记录触发原因
- **发送告警**：严重风控触发时告警

#### Q4: 如何统计交易次数？
- **内存计数器**：按日期和标的统计
- **定时重置**：每日0点重置
- **持久化**：可选存储到数据库

---

## 🏗️ 二、架构设计

### 2.1 风控体系架构

```
┌─────────────────────────────────────────┐
│         Trading Strategy                 │
│  MarketOrder() / LimitOrder()            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Risk Manager                     │
│  - check_order()                         │
│  - check_position()                      │
│  - check_trading_frequency()             │
└──────────────┬──────────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ Position     │  │ Order        │
│ Rules        │  │ Rules        │
│ - Max single │  │ - Max value  │
│ - Max total  │  │ - Daily limit│
│ - Concentr.  │  │ - Frequency  │
└──────────────┘  └──────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Risk Config                      │
│  (YAML file, hot reload)                 │
└─────────────────────────────────────────┘
```

### 2.2 风控规则分类

```
RiskRule (抽象基类)
    ├── check(order) -> RiskCheckResult
    │
    ├── PositionRule (持仓风控)
    │   ├── MaxSinglePositionRule (单只上限)
    │   ├── MaxTotalPositionRule (总持仓上限)
    │   └── PositionConcentrationRule (集中度)
    │
    ├── OrderRule (订单风控)
    │   ├── MaxOrderValueRule (单笔金额上限)
    │   ├── DailyTradesLimitRule (单日交易次数)
    │   └── TradingFrequencyRule (频繁交易检测)
    │
    └── CustomRule (自定义规则)
        └── 用户可扩展
```

### 2.3 关键类设计

#### RiskCheckResult (风控检查结果)
```python
@dataclass
class RiskCheckResult:
    """风控检查结果"""
    passed: bool              # 是否通过
    reason: str = ""          # 失败原因
    rule_name: str = ""       # 触发的规则名称
    severity: str = "warning" # 严重程度: info/warning/error
    context: dict = None      # 上下文信息
```

#### RiskRule (风控规则基类)
```python
class RiskRule(ABC):
    """风控规则抽象基类"""
    
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    def check(self, order: Order, context: dict) -> RiskCheckResult:
        """检查订单是否符合风控规则"""
        pass
    
    def is_enabled(self) -> bool:
        """规则是否启用"""
        return self.enabled
```

#### RiskManager (风控管理器)
```python
class RiskManager:
    """风控管理器"""
    
    def __init__(self, config_path: str = 'config/risk_config.yaml'):
        self.config_path = config_path
        self.rules: List[RiskRule] = []
        self.stats = RiskStats()
        self._load_config()
        self._init_rules()
    
    def check_order(self, order: Order) -> RiskCheckResult:
        """检查订单"""
        for rule in self.rules:
            if not rule.is_enabled():
                continue
            
            result = rule.check(order, self._get_context())
            
            if not result.passed:
                self._record_rejection(order, result)
                return result
        
        self._record_approval(order)
        return RiskCheckResult(passed=True)
    
    def reload_config(self):
        """热更新配置"""
        self._load_config()
        self._init_rules()
```

---

## 🔧 三、子任务设计

### 3.1 持仓风控（2小时）

#### 核心功能
1. **单只股票持仓上限**（数量、市值）
2. **总持仓上限**
3. **持仓集中度检查**

#### 实现方案

**MaxSinglePositionRule（单只持仓上限）**：
```python
class MaxSinglePositionRule(RiskRule):
    """单只股票持仓上限"""
    
    def check(self, order: Order, context: dict) -> RiskCheckResult:
        """检查单只持仓是否超限"""
        symbol = order.symbol
        quantity = order.quantity
        
        # 获取当前持仓
        current_position = context['portfolio'].get_position(symbol)
        current_qty = current_position.quantity if current_position else 0
        
        # 计算下单后持仓
        if order.action == 'BUY':
            new_position = current_qty + quantity
        else:
            return RiskCheckResult(passed=True)  # 卖出不检查
        
        # 检查数量上限
        max_quantity = self.config.get('max_quantity', 10000)
        if new_position > max_quantity:
            return RiskCheckResult(
                passed=False,
                reason=f"Single position limit exceeded: {new_position} > {max_quantity}",
                rule_name=self.name,
                severity='error',
                context={'symbol': symbol, 'new_position': new_position, 'limit': max_quantity}
            )
        
        # 检查市值上限
        current_price = context.get('current_price', {}).get(symbol, 0)
        new_value = new_position * current_price
        max_value = self.config.get('max_value', 100000)
        
        if new_value > max_value:
            return RiskCheckResult(
                passed=False,
                reason=f"Single position value limit exceeded: ${new_value:.0f} > ${max_value:.0f}",
                rule_name=self.name,
                severity='error',
                context={'symbol': symbol, 'new_value': new_value, 'limit': max_value}
            )
        
        return RiskCheckResult(passed=True)
```

**MaxTotalPositionRule（总持仓上限）**：
```python
class MaxTotalPositionRule(RiskRule):
    """总持仓上限"""
    
    def check(self, order: Order, context: dict) -> RiskCheckResult:
        """检查总持仓是否超限"""
        portfolio = context['portfolio']
        current_prices = context.get('current_price', {})
        
        # 计算当前总市值
        total_value = 0
        for symbol, position in portfolio.get_all_positions().items():
            price = current_prices.get(symbol, 0)
            total_value += position.quantity * price
        
        # 计算订单市值
        order_price = current_prices.get(order.symbol, 0)
        order_value = order.quantity * order_price
        
        if order.action == 'BUY':
            new_total_value = total_value + order_value
        else:
            return RiskCheckResult(passed=True)
        
        # 检查总市值上限
        max_total_value = self.config.get('max_total_value', 500000)
        
        if new_total_value > max_total_value:
            return RiskCheckResult(
                passed=False,
                reason=f"Total position value limit exceeded: ${new_total_value:.0f} > ${max_total_value:.0f}",
                rule_name=self.name,
                severity='error',
                context={'new_total_value': new_total_value, 'limit': max_total_value}
            )
        
        return RiskCheckResult(passed=True)
```

**PositionConcentrationRule（持仓集中度）**：
```python
class PositionConcentrationRule(RiskRule):
    """持仓集中度检查"""
    
    def check(self, order: Order, context: dict) -> RiskCheckResult:
        """检查单只股票占总持仓的比例"""
        if order.action != 'BUY':
            return RiskCheckResult(passed=True)
        
        portfolio = context['portfolio']
        current_prices = context.get('current_price', {})
        
        # 计算总市值
        total_value = sum(
            pos.quantity * current_prices.get(sym, 0)
            for sym, pos in portfolio.get_all_positions().items()
        )
        
        # 计算订单后该股票的市值
        symbol = order.symbol
        current_position = portfolio.get_position(symbol)
        current_qty = current_position.quantity if current_position else 0
        new_qty = current_qty + order.quantity
        price = current_prices.get(symbol, 0)
        symbol_value = new_qty * price
        
        # 计算集中度
        if total_value + symbol_value > 0:
            concentration = symbol_value / (total_value + symbol_value)
        else:
            concentration = 0
        
        max_concentration = self.config.get('max_concentration', 0.3)  # 默认30%
        
        if concentration > max_concentration:
            return RiskCheckResult(
                passed=False,
                reason=f"Position concentration too high: {concentration*100:.1f}% > {max_concentration*100:.1f}%",
                rule_name=self.name,
                severity='warning',
                context={'symbol': symbol, 'concentration': concentration, 'limit': max_concentration}
            )
        
        return RiskCheckResult(passed=True)
```

#### 测试用例
1. **test_single_position_quantity_limit** - 单只数量超限
2. **test_single_position_value_limit** - 单只市值超限
3. **test_total_position_limit** - 总持仓超限
4. **test_position_concentration_limit** - 集中度超限
5. **test_sell_order_bypass** - 卖出订单不受限制

---

### 3.2 订单风控（2小时）

#### 核心功能
1. **单笔订单金额上限**
2. **单日交易次数限制**
3. **频繁交易检测**

#### 实现方案

**MaxOrderValueRule（订单金额上限）**：
```python
class MaxOrderValueRule(RiskRule):
    """单笔订单金额上限"""
    
    def check(self, order: Order, context: dict) -> RiskCheckResult:
        """检查订单金额是否超限"""
        price = context.get('current_price', {}).get(order.symbol, 0)
        order_value = order.quantity * price
        
        max_value = self.config.get('max_order_value', 50000)
        
        if order_value > max_value:
            return RiskCheckResult(
                passed=False,
                reason=f"Order value exceeds limit: ${order_value:.0f} > ${max_value:.0f}",
                rule_name=self.name,
                severity='error',
                context={'order_value': order_value, 'limit': max_value}
            )
        
        return RiskCheckResult(passed=True)
```

**DailyTradesLimitRule（单日交易次数）**：
```python
class DailyTradesLimitRule(RiskRule):
    """单日交易次数限制"""
    
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.daily_trades: Dict[str, int] = {}  # {date: count}
        self.symbol_daily_trades: Dict[str, Dict[str, int]] = {}  # {date: {symbol: count}}
    
    def check(self, order: Order, context: dict) -> RiskCheckResult:
        """检查今日交易次数"""
        today = datetime.now().date().isoformat()
        
        # 初始化今日计数
        if today not in self.daily_trades:
            self._reset_daily_counters(today)
        
        # 检查总交易次数
        max_daily_trades = self.config.get('max_daily_trades', 100)
        if self.daily_trades[today] >= max_daily_trades:
            return RiskCheckResult(
                passed=False,
                reason=f"Daily trades limit exceeded: {self.daily_trades[today]} >= {max_daily_trades}",
                rule_name=self.name,
                severity='warning',
                context={'daily_trades': self.daily_trades[today], 'limit': max_daily_trades}
            )
        
        # 检查单只股票交易次数
        max_symbol_daily_trades = self.config.get('max_symbol_daily_trades', 20)
        symbol_count = self.symbol_daily_trades[today].get(order.symbol, 0)
        
        if symbol_count >= max_symbol_daily_trades:
            return RiskCheckResult(
                passed=False,
                reason=f"Daily trades limit for {order.symbol} exceeded: {symbol_count} >= {max_symbol_daily_trades}",
                rule_name=self.name,
                severity='warning',
                context={'symbol': order.symbol, 'symbol_trades': symbol_count, 'limit': max_symbol_daily_trades}
            )
        
        return RiskCheckResult(passed=True)
    
    def record_trade(self, order: Order):
        """记录交易（通过后调用）"""
        today = datetime.now().date().isoformat()
        self.daily_trades[today] = self.daily_trades.get(today, 0) + 1
        
        if today not in self.symbol_daily_trades:
            self.symbol_daily_trades[today] = {}
        self.symbol_daily_trades[today][order.symbol] = \
            self.symbol_daily_trades[today].get(order.symbol, 0) + 1
    
    def _reset_daily_counters(self, today: str):
        """重置每日计数器"""
        # 清理旧日期
        old_dates = [d for d in self.daily_trades.keys() if d != today]
        for d in old_dates:
            del self.daily_trades[d]
            if d in self.symbol_daily_trades:
                del self.symbol_daily_trades[d]
        
        self.daily_trades[today] = 0
        self.symbol_daily_trades[today] = {}
```

**TradingFrequencyRule（频繁交易检测）**：
```python
class TradingFrequencyRule(RiskRule):
    """频繁交易检测（防止短时间内大量下单）"""
    
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.recent_orders: List[Tuple[str, float]] = []  # [(symbol, timestamp)]
    
    def check(self, order: Order, context: dict) -> RiskCheckResult:
        """检查交易频率"""
        now = time.time()
        symbol = order.symbol
        
        # 清理过期记录
        time_window = self.config.get('time_window', 60)  # 默认60秒
        self.recent_orders = [
            (s, t) for s, t in self.recent_orders 
            if now - t < time_window
        ]
        
        # 统计时间窗口内的交易次数
        symbol_count = sum(1 for s, t in self.recent_orders if s == symbol)
        total_count = len(self.recent_orders)
        
        # 检查单只股票频率
        max_symbol_frequency = self.config.get('max_symbol_frequency', 5)
        if symbol_count >= max_symbol_frequency:
            return RiskCheckResult(
                passed=False,
                reason=f"Trading frequency too high for {symbol}: {symbol_count} orders in {time_window}s",
                rule_name=self.name,
                severity='warning',
                context={'symbol': symbol, 'count': symbol_count, 'time_window': time_window}
            )
        
        # 检查总体频率
        max_total_frequency = self.config.get('max_total_frequency', 10)
        if total_count >= max_total_frequency:
            return RiskCheckResult(
                passed=False,
                reason=f"Trading frequency too high: {total_count} orders in {time_window}s",
                rule_name=self.name,
                severity='warning',
                context={'count': total_count, 'time_window': time_window}
            )
        
        return RiskCheckResult(passed=True)
    
    def record_order(self, order: Order):
        """记录订单（通过后调用）"""
        self.recent_orders.append((order.symbol, time.time()))
```

#### 测试用例
1. **test_order_value_limit** - 订单金额超限
2. **test_daily_trades_limit** - 单日交易次数超限
3. **test_symbol_daily_limit** - 单只股票日交易超限
4. **test_trading_frequency** - 频繁交易检测
5. **test_frequency_time_window** - 时间窗口过期清理

---

### 3.3 风控配置化（2小时）

#### 核心功能
1. **配置文件定义**
2. **热更新机制**
3. **配置验证**

#### 配置文件设计

**config/risk_config.yaml**：
```yaml
# 风控配置文件

# 持仓风控
position:
  # 单只股票持仓上限
  max_single_position:
    enabled: true
    max_quantity: 10000        # 最大持仓数量
    max_value: 100000          # 最大持仓市值（美元）
  
  # 总持仓上限
  max_total_position:
    enabled: true
    max_total_value: 500000    # 总持仓市值上限（美元）
  
  # 持仓集中度
  position_concentration:
    enabled: true
    max_concentration: 0.3     # 单只最大占比30%

# 订单风控
order:
  # 单笔订单金额上限
  max_order_value:
    enabled: true
    max_order_value: 50000     # 单笔最大金额（美元）
  
  # 单日交易次数限制
  daily_trades_limit:
    enabled: true
    max_daily_trades: 100      # 全部标的每日最大交易次数
    max_symbol_daily_trades: 20 # 单只标的每日最大交易次数
  
  # 频繁交易检测
  trading_frequency:
    enabled: true
    time_window: 60            # 时间窗口（秒）
    max_symbol_frequency: 5    # 窗口内单只最大交易次数
    max_total_frequency: 10    # 窗口内全部最大交易次数

# 全局设置
global:
  strict_mode: false           # 严格模式：任何风控失败都拒绝
  log_all_checks: false        # 记录所有检查（包括通过的）
  alert_on_rejection: true     # 风控拒绝时发送告警
```

#### 热更新实现

```python
class ConfigWatcher:
    """配置文件监听器"""
    
    def __init__(self, config_path: str, callback: Callable):
        self.config_path = config_path
        self.callback = callback
        self.last_modified = 0
        self.watching = False
    
    def start(self):
        """启动监听"""
        self.watching = True
        threading.Thread(target=self._watch_loop, daemon=True).start()
    
    def stop(self):
        """停止监听"""
        self.watching = False
    
    def _watch_loop(self):
        """监听循环"""
        while self.watching:
            try:
                current_modified = os.path.getmtime(self.config_path)
                
                if current_modified > self.last_modified:
                    logger.info(f"Config file changed, reloading...")
                    self.last_modified = current_modified
                    self.callback()
            
            except Exception as e:
                logger.error(f"Error watching config: {e}")
            
            time.sleep(5)  # 每5秒检查一次
```

#### 测试用例
1. **test_load_config** - 加载配置文件
2. **test_config_validation** - 配置验证
3. **test_hot_reload** - 热更新配置
4. **test_config_override** - 配置覆盖优先级
5. **test_invalid_config** - 无效配置处理

---

## 🧪 四、测试策略

### 4.1 单元测试

**测试目标**：覆盖率 > 85%

**关键测试场景**：

| 测试类 | 测试用例数 | 覆盖内容 |
|--------|-----------|----------|
| TestPositionRules | 6 | 单只持仓、总持仓、集中度 |
| TestOrderRules | 6 | 订单金额、交易次数、频率 |
| TestRiskManager | 5 | 管理器流程、统计、热更新 |
| TestConfigWatcher | 3 | 配置监听、热更新 |

**Mock策略**：
- Mock Portfolio：返回模拟持仓
- Mock Order：构造测试订单
- Mock 价格数据

### 4.2 集成测试

**测试场景**：

1. **完整下单流程测试**
   - 构造订单
   - 风控检查
   - 验证拒绝或通过

2. **多规则组合测试**
   - 同时触发多个风控规则
   - 验证优先级和逻辑

3. **配置热更新测试**
   - 修改配置文件
   - 验证自动重新加载
   - 验证新规则生效

---

## 📦 五、实现步骤

### 步骤1：基础类定义（30分钟）
1. 创建 `src/risk/models.py`
2. 定义 `RiskCheckResult`
3. 定义 `RiskRule` 基类
4. 定义 `RiskStats` 统计类

### 步骤2：持仓风控规则（2小时）
1. 创建 `src/risk/rules/position_rules.py`
2. 实现 `MaxSinglePositionRule`
3. 实现 `MaxTotalPositionRule`
4. 实现 `PositionConcentrationRule`
5. 编写单元测试

### 步骤3：订单风控规则（2小时）
1. 创建 `src/risk/rules/order_rules.py`
2. 实现 `MaxOrderValueRule`
3. 实现 `DailyTradesLimitRule`
4. 实现 `TradingFrequencyRule`
5. 编写单元测试

### 步骤4：风控管理器（1小时）
1. 创建 `src/risk/manager.py`
2. 实现 `RiskManager`
3. 实现配置加载
4. 实现规则注册
5. 编写单元测试

### 步骤5：配置热更新（30分钟）
1. 创建 `src/risk/config_watcher.py`
2. 实现 `ConfigWatcher`
3. 集成到 `RiskManager`
4. 编写单元测试

### 步骤6：集成和调试（30分钟）
1. 创建配置文件模板
2. 集成所有模块
3. 运行所有测试
4. 修复发现的问题

---

## 🚨 六、潜在问题与解决方案

### 问题1：持仓数据不准确
**现象**：风控检查时持仓与实际不符
**解决**：
- 使用实时持仓数据
- 定期与IBKR同步
- 增加持仓校验机制

### 问题2：价格数据延迟
**现象**：使用过期价格计算市值
**解决**：
- 使用最新行情数据
- 增加时间戳检查
- 价格过期时告警

### 问题3：配置热更新丢失状态
**现象**：重新加载配置后交易计数器清零
**解决**：
- 保留有状态的规则实例
- 只更新配置参数
- 或持久化状态到数据库

### 问题4：多策略并发下单
**现象**：多个策略同时下单，风控检查不准确
**解决**：
- 增加线程锁
- 使用原子操作
- 或使用分布式锁

---

## ✅ 七、验收标准

### 功能完整性
- ✅ 所有订单下单前经过风控检查
- ✅ 6类风控规则全部实现
- ✅ 风控触发时拒绝订单并记录
- ✅ 风控配置可在运行时修改

### 准确性
- ✅ 持仓计算准确
- ✅ 市值计算准确
- ✅ 交易次数统计准确
- ✅ 频率检测准确

### 测试覆盖
- ✅ 单元测试覆盖率 > 85%
- ✅ 所有规则有测试
- ✅ 集成测试通过

### 可维护性
- ✅ 规则易于扩展
- ✅ 配置清晰易懂
- ✅ 日志完整
- ✅ 代码符合规范

---

## 📊 八、时间分配

| 阶段 | 任务 | 预估时间 | 实际时间 |
|------|------|----------|----------|
| 1 | 基础类定义 | 0.5h | |
| 2 | 持仓风控规则 | 2.0h | |
| 3 | 订单风控规则 | 2.0h | |
| 4 | 风控管理器 | 1.0h | |
| 5 | 配置热更新 | 0.5h | |
| 6 | 集成和调试 | 0.5h | |
| **总计** | | **6.5h** | |

*注：预留0.5小时缓冲时间*

---

## 📝 九、总结

任务2的核心目标是**资金安全**，通过：

1. **持仓风控** - 防止过度集中
2. **订单风控** - 防止单笔过大
3. **频率控制** - 防止高频异常
4. **配置化** - 灵活调整参数

完成后，系统将具备：
- ✅ 多层风控保护
- ✅ 实时风控检查
- ✅ 灵活配置管理
- ✅ 完整的审计日志

这是保障**交易安全**的核心机制。
