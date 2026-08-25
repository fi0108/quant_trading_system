# Task 4：策略示例 - 设计文档

## 1. 需求分析

### 1.1 任务目标
创建一个完整的SMA双均线策略示例，在实盘环境中验证整个策略框架的可用性。

### 1.2 核心需求
- **策略逻辑**：实现经典的SMA双均线交叉策略（金叉买入、死叉卖出）
- **实盘运行**：连接IBKR实盘账户，真实下单交易
- **风险控制**：限制每笔交易金额，避免过度风险
- **日志记录**：记录所有交易信号、订单状态、持仓变化
- **监控指标**：展示实时的均线数值、持仓、盈亏等信息

### 1.3 非功能需求
- **稳定性**：策略运行中不应崩溃，能处理异常情况
- **可配置**：交易标的、均线周期、交易数量等参数可配置
- **可观测**：通过日志能清晰了解策略运行状态
- **易部署**：提供启动脚本，一键运行策略

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────┐
│                  Strategy Runner                     │
│  (scripts/run_strategy.py)                          │
│  - 解析命令行参数                                      │
│  - 加载配置文件                                        │
│  - 实例化策略                                          │
│  - 启动QCAlgorithm引擎                                │
└─────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────┐
│              SMA Crossover Strategy                  │
│  (strategies/sma_crossover_live.py)                 │
│  - Initialize(): 设置参数、创建指标                    │
│  - OnData(): 处理实时数据、生成交易信号                │
│  - OnOrderEvent(): 处理订单反馈                       │
└─────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Indicators  │  │ QCAlgorithm  │  │ Portfolio    │
    │  - SMA Fast │  │  - MarketOrder│ │  - Holdings  │
    │  - SMA Slow │  │  - Log       │  │  - Cash      │
    └─────────────┘  └──────────────┘  └──────────────┘
                            │
                            ▼
            ┌───────────────────────────────┐
            │   Trading Connection Manager   │
            │   - IBKR Connection           │
            │   - Order Placement           │
            │   - Market Data Feed          │
            └───────────────────────────────┘
```

### 2.2 策略类设计

#### SMAStrategyLive
继承自 `QCAlgorithm`，实现实盘交易策略。

**核心属性**：
```python
class SMAStrategyLive(QCAlgorithm):
    # 配置参数
    symbol: str           # 交易标的
    fast_period: int      # 快速均线周期
    slow_period: int      # 慢速均线周期
    trade_quantity: int   # 每次交易数量
    
    # 指标
    sma_fast: SimpleMovingAverage
    sma_slow: SimpleMovingAverage
    
    # 状态跟踪
    previous_signal: str  # 上次信号 ("buy"/"sell"/"none")
```

**核心方法**：
- `Initialize()`: 初始化策略参数和指标
- `OnData(data)`: 处理实时行情数据
  - 检查指标是否就绪
  - 计算交叉信号
  - 生成交易指令
  - 记录日志
- `OnOrderEvent(order_event)`: 处理订单状态变化
  - 记录订单成交
  - 更新持仓信息

### 2.3 策略运行器设计

#### scripts/run_strategy.py
命令行工具，启动策略运行。

**功能**：
- 解析命令行参数（策略名称、配置文件路径）
- 加载配置文件（YAML格式）
- 初始化数据库连接
- 初始化交易连接
- 实例化策略类
- 启动策略引擎

**命令行接口**：
```bash
python scripts/run_strategy.py \
    --strategy sma_crossover_live \
    --config config/strategy_config.yaml \
    --symbol AAPL
```

### 2.4 配置文件设计

#### config/strategy_config.yaml
策略配置文件，包含所有可配置参数。

```yaml
# 策略参数
strategy:
  name: "SMA Crossover Live"
  
  # SMA参数
  sma:
    fast_period: 10
    slow_period: 20
    resolution: "daily"
  
  # 交易参数
  trading:
    default_quantity: 100
    max_position_size: 1000
    
  # 风险控制
  risk:
    max_order_value: 10000  # 单笔最大金额（美元）
    allow_short: false       # 是否允许做空

# 交易连接
ibkr:
  host: "127.0.0.1"
  port: 7497
  client_id: 1

# 数据库
database:
  host: "localhost"
  port: 5432
  database: "trading_system"
  user: "postgres"
  password: "password"
```

---

## 3. 交易信号逻辑

### 3.1 金叉买入（Golden Cross）
**条件**：
- 快速均线从下方穿过慢速均线
- 即：`sma_fast[t-1] <= sma_slow[t-1]` 且 `sma_fast[t] > sma_slow[t]`

**动作**：
- 如果当前无持仓 → 买入开仓
- 如果当前有空仓 → 平仓 + 买入开仓

### 3.2 死叉卖出（Death Cross）
**条件**：
- 快速均线从上方穿过慢速均线
- 即：`sma_fast[t-1] >= sma_slow[t-1]` 且 `sma_fast[t] < sma_slow[t]`

**动作**：
- 如果当前有持仓 → 卖出平仓

### 3.3 状态机设计

```
             [无持仓]
                │
    金叉        │        死叉
    ┌───────────┴───────────┐
    ▼                       │
 [多头持仓] ─────────────────┘
```

**状态转换**：
- 无持仓 + 金叉 → 买入 → 多头持仓
- 多头持仓 + 死叉 → 卖出 → 无持仓

---

## 4. 测试策略

### 4.1 单元测试

#### 测试类：`TestSMAStrategyLive`

**测试用例**：

1. **test_strategy_initialization**
   - 验证策略初始化成功
   - 验证指标创建成功
   - 验证参数设置正确

2. **test_golden_cross_signal**
   - 模拟金叉场景
   - 验证生成买入信号
   - 验证交易数量正确

3. **test_death_cross_signal**
   - 模拟死叉场景
   - 验证生成卖出信号

4. **test_no_signal_when_not_ready**
   - 指标未就绪时
   - 验证不生成交易信号

5. **test_no_duplicate_signals**
   - 连续金叉/死叉
   - 验证不重复下单

6. **test_order_event_handling**
   - 模拟订单成交
   - 验证持仓更新
   - 验证日志记录

### 4.2 集成测试

#### 测试类：`TestSMAStrategyIntegration`

**测试用例**：

1. **test_strategy_with_historical_data**
   - 使用真实历史数据
   - 回放数据流
   - 验证策略逻辑正确

2. **test_strategy_with_mock_ibkr**
   - Mock IBKR连接
   - 验证订单发送
   - 验证错误处理

3. **test_strategy_runner_script**
   - 测试启动脚本
   - 验证配置加载
   - 验证策略运行

### 4.3 手工测试

#### 模拟盘测试（Paper Trading）
在IBKR模拟账户中运行策略，验证：
- ✅ 连接稳定性
- ✅ 订单执行正确
- ✅ 日志输出清晰
- ✅ 异常处理健壮

#### 小资金实盘测试
使用小额资金（如1股）在实盘测试：
- ✅ 真实下单流程
- ✅ 成交反馈处理
- ✅ 持仓同步
- ✅ 盈亏计算

---

## 5. 实现步骤

### 阶段1：策略类开发（1.5小时）
1. 创建 `strategies/sma_crossover_live.py`
2. 实现 `Initialize()` 方法
3. 实现 `OnData()` 方法（核心交易逻辑）
4. 实现 `OnOrderEvent()` 方法
5. 添加日志记录

### 阶段2：配置文件（0.5小时）
1. 创建 `config/strategy_config.yaml`
2. 定义所有可配置参数
3. 添加注释说明

### 阶段3：运行脚本（1小时）
1. 创建 `scripts/run_strategy.py`
2. 实现参数解析
3. 实现配置加载
4. 实现策略实例化
5. 实现运行循环

### 阶段4：单元测试（1小时）
1. 创建 `tests/slice3/unit/test_sma_strategy_live.py`
2. 实现6个单元测试用例
3. Mock外部依赖（IBKR连接、数据库）
4. 验证所有测试通过

### 阶段5：集成测试与调试（1小时）
1. 创建集成测试
2. 在模拟盘运行测试
3. 修复发现的问题
4. 完善文档

---

## 6. 关键技术点

### 6.1 交叉信号检测
需要比较当前值和前一个值：
```python
# 保存前一次的均线值
self.prev_fast = self.sma_fast.Current.Value
self.prev_slow = self.sma_slow.Current.Value

# 检测金叉
if self.prev_fast <= self.prev_slow and current_fast > current_slow:
    # 金叉发生
```

### 6.2 避免重复信号
使用状态变量记录上次信号：
```python
if signal == "buy" and self.previous_signal != "buy":
    self.MarketOrder(self.symbol, self.trade_quantity)
    self.previous_signal = "buy"
```

### 6.3 持仓查询
通过 `Portfolio` 获取当前持仓：
```python
holdings = self.Portfolio.get_holdings(self.symbol)
if holdings:
    current_position = holdings.quantity
else:
    current_position = 0
```

### 6.4 日志格式
统一的日志格式，便于监控：
```python
self.Log(f"[SIGNAL] Golden Cross: SMA_Fast={fast:.2f} > SMA_Slow={slow:.2f}")
self.Log(f"[ORDER] BUY {self.symbol} x {quantity}")
self.Log(f"[FILL] Order {order_id} filled at {price:.2f}")
```

---

## 7. 潜在问题与解决方案

### 问题1：指标预热时间过长
**现象**：策略启动后长时间不交易
**原因**：慢速均线周期长（如50日），需要等待50天数据
**解决**：
- 使用历史数据自动预热（已实现）
- 配置文件中选择合适的均线周期

### 问题2：实时数据延迟
**现象**：收到的行情数据不是最新的
**原因**：IBKR数据推送延迟或网络延迟
**解决**：
- 检查时间戳，过滤过期数据
- 设置合理的超时时间

### 问题3：订单拒绝
**现象**：下单后被IBKR拒绝
**原因**：资金不足、交易权限、市场状态等
**解决**：
- 捕获 `OnOrderEvent` 中的错误信息
- 记录详细日志
- 实现风险控制（检查账户余额）

### 问题4：持仓不同步
**现象**：策略记录的持仓与实际不符
**原因**：手工交易、其他策略交易、重启策略
**解决**：
- 启动时查询当前持仓
- 定期同步持仓状态
- 订单成交后立即更新

### 问题5：日志过多
**现象**：每条数据都记录日志，文件过大
**原因**：OnData每秒/每分钟触发一次
**解决**：
- 只记录关键事件（信号、订单、成交）
- 使用不同日志级别（INFO/DEBUG）
- 定期轮转日志文件

### 问题6：策略崩溃
**现象**：运行中抛出异常，程序退出
**原因**：网络断开、数据异常、代码bug
**解决**：
- 在 `OnData` 中捕获所有异常
- 记录异常堆栈
- 实现自动重连机制

---

## 8. 监控与运维

### 8.1 日志监控
关键日志内容：
- ✅ 策略启动/停止
- ✅ 指标就绪状态
- ✅ 交易信号生成
- ✅ 订单提交/成交/拒绝
- ✅ 持仓变化
- ✅ 异常错误

### 8.2 性能指标
需要记录的指标：
- 总交易次数
- 盈利交易 / 亏损交易
- 最大回撤
- 当前持仓
- 账户余额

### 8.3 告警机制
需要告警的情况：
- 🚨 策略崩溃
- 🚨 连接断开超过5分钟
- 🚨 订单连续拒绝
- 🚨 持仓超过最大限制
- 🚨 亏损超过阈值

---

## 9. 文档与示例

### 9.1 README.md
策略使用说明文档：
- 策略原理介绍
- 参数配置说明
- 启动步骤
- 常见问题

### 9.2 配置示例
提供多个配置模板：
- `config/strategy_config.example.yaml` - 示例配置
- `config/strategy_config.conservative.yaml` - 保守参数
- `config/strategy_config.aggressive.yaml` - 激进参数

---

## 10. 验收标准

### 功能完整性
- ✅ 策略可以成功启动
- ✅ 能接收实时数据
- ✅ 指标计算正确
- ✅ 信号生成准确
- ✅ 订单提交成功
- ✅ 订单状态回调正常
- ✅ 持仓记录正确

### 代码质量
- ✅ 所有单元测试通过
- ✅ 代码符合PEP8规范
- ✅ 关键逻辑有注释
- ✅ 异常处理完善

### 文档完整
- ✅ 设计文档完整
- ✅ 使用说明清晰
- ✅ 配置示例齐全

### 实盘验证
- ✅ 模拟盘运行稳定（至少1小时）
- ✅ 小资金实盘测试通过

---

## 11. 时间估算

| 阶段 | 任务 | 预估时间 |
|------|------|----------|
| 1 | 策略类开发 | 1.5h |
| 2 | 配置文件 | 0.5h |
| 3 | 运行脚本 | 1.0h |
| 4 | 单元测试 | 1.0h |
| 5 | 集成测试与调试 | 1.0h |
| **总计** | | **5.0h** |

*注：包含1小时缓冲时间*

---

## 12. 总结

本设计文档详细规划了SMA双均线策略示例的开发：

1. **清晰的需求**：明确策略逻辑、配置、监控要求
2. **完整的架构**：策略类、运行器、配置文件三层结构
3. **详细的交易逻辑**：金叉/死叉信号检测和状态转换
4. **全面的测试**：单元测试、集成测试、手工测试
5. **分步实施**：5个阶段，每阶段目标明确
6. **风险防控**：列出7个潜在问题及解决方案
7. **运维支持**：日志、监控、告警机制

按照此文档开发，可以有效减少返工，确保代码质量。
