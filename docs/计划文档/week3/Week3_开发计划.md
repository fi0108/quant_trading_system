# Week 3 开发计划

**目标**: 策略框架 - 能运行 SMA 双均线策略
**工期**: 25-30小时
**切片**: Slice 3

---

## 📋 开发顺序说明

### 为什么这个顺序？

1. **QCAlgorithm 基类优先** - 是策略开发的基础接口
2. **历史数据下载** - 为指标计算和策略测试提供数据
3. **技术指标库** - 策略逻辑依赖指标
4. **策略示例** - 验证整个框架可用性

**开发顺序**: QCAlgorithm 基类 → 历史数据下载 → 技术指标库 → 策略示例

---

## 任务列表（按开发顺序）

| 顺序 | 任务             | 预估时间 | 状态        | 依赖        |
| ---- | ---------------- | -------- | ----------- | ----------- |
| 1    | QCAlgorithm 基类 | 8h       | ⏸️ 待开始 | Week 2 完成 |
| 2    | 历史数据下载     | 6h       | ⏸️ 待开始 | QCAlgorithm |
| 3    | 技术指标库       | 6h       | ⏸️ 待开始 | 历史数据    |
| 4    | 策略示例         | 4h       | ⏸️ 待开始 | 基类 + 指标 |

**总计**: 24小时

---

## ⏸️ 任务1：QCAlgorithm 基类（待开始）

**优先级**: P0（最高）
**依赖**: Week 2 基础设施
**预估时间**: 8小时

### 目标

实现 QuantConnect 风格的策略基类，提供统一的 API

### 功能需求

#### 1. 策略生命周期

```python
class QCAlgorithm:
    def Initialize(self):
        """策略初始化"""
        pass
  
    def OnData(self, data):
        """行情数据事件"""
        pass
  
    def OnOrderEvent(self, order_event):
        """订单事件"""
        pass
```

#### 2. 股票管理 API

```python
# 添加股票
self.AddEquity("AAPL", Resolution.Minute)

# 获取历史数据
history = self.History("AAPL", 20, Resolution.Daily)
```

#### 3. 交易 API

```python
# 市价单
self.MarketOrder("AAPL", 100)

# 限价单
self.LimitOrder("AAPL", 100, 150.5)

# 平仓
self.Liquidate("AAPL")
```

#### 4. 持仓和账户 API

```python
# 持仓
position = self.Portfolio["AAPL"]
print(position.Quantity)
print(position.UnrealizedProfit)

# 账户
print(self.Portfolio.Cash)
print(self.Portfolio.TotalPortfolioValue)
```

### 文件位置

```
src/strategy/
├── qc_algorithm.py              # QCAlgorithm 基类（新建）
├── resolution.py                # 时间周期枚举（新建）
└── portfolio.py                 # 持仓和账户封装（新建）

tests/slice3/
├── unit/test_qc_algorithm.py
└── integration/test_strategy_lifecycle.py
```

### 实现步骤

#### Step 1: 创建基础类结构（2h）

- [ ] 创建 `QCAlgorithm` 基类
- [ ] 实现生命周期方法（空实现）
- [ ] 创建 `Resolution` 枚举
- [ ] 创建 `Portfolio` 和 `SecurityHolding` 类

#### Step 2: 实现交易 API（2h）

- [ ] `MarketOrder()` - 调用 OrderManager
- [ ] `LimitOrder()` - 调用 OrderManager
- [ ] `Liquidate()` - 平仓逻辑
- [ ] 订单事件转发到 `OnOrderEvent()`

#### Step 3: 实现持仓 API（2h）

- [ ] `Portfolio` 属性封装 PositionManager
- [ ] `Portfolio["symbol"]` 返回持仓
- [ ] `Portfolio.Cash` 和 `TotalPortfolioValue`

#### Step 4: 实现数据订阅（1h）

- [ ] `AddEquity()` - 添加实时数据订阅
- [ ] 行情数据转发到 `OnData()`
- [ ] 数据缓存机制

#### Step 5: 单元测试（1h）

- [ ] Mock 依赖
- [ ] 测试生命周期
- [ ] 测试交易 API
- [ ] 测试持仓 API

### 验收标准

- [ ] 能够继承 QCAlgorithm 创建策略
- [ ] Initialize、OnData、OnOrderEvent 被正确调用
- [ ] MarketOrder、LimitOrder 能下单
- [ ] Portfolio 能查询持仓和账户
- [ ] 单元测试覆盖率 > 80%

---

## ⏸️ 任务2：历史数据下载（待开始）

**优先级**: P1
**依赖**: QCAlgorithm 基类
**预估时间**: 6小时

### 目标

从 IBKR 下载历史数据并存储到 PostgreSQL

### 功能需求

#### 1. 历史数据下载

```python
# 下载日线数据
downloader.download(
    symbol="AAPL",
    start_date="2020-01-01",
    end_date="2024-12-31",
    bar_size="1 day"
)

# 下载分钟线数据
downloader.download(
    symbol="AAPL",
    start_date="2024-01-01",
    end_date="2024-12-31",
    bar_size="1 min"
)
```

#### 2. 数据存储

- 存储到 PostgreSQL 的 `bars` 表
- 自动去重（symbol + timestamp + bar_size 唯一）
- 支持增量更新

#### 3. 断点续传

- 检查已下载的日期范围
- 只下载缺失的数据

#### 4. 数据查询

```python
# 查询历史数据
history = data_provider.get_history(
    symbol="AAPL",
    start_date="2024-01-01",
    end_date="2024-01-31",
    resolution=Resolution.Daily
)
```

### 文件位置

```
src/data/
├── historical/
│   ├── downloader.py           # 历史数据下载器（新建）
│   └── provider.py             # 历史数据查询（新建）

scripts/
└── download_history.py         # 下载脚本（新建）

tests/slice3/
└── unit/test_historical_data.py
```

### 实现步骤

#### Step 1: 创建下载器（2h）

- [ ] `HistoricalDataDownloader` 类
- [ ] 调用 IBKR `reqHistoricalData()`
- [ ] 处理分页（IBKR 限制）
- [ ] 错误重试机制

#### Step 2: 数据存储（1h）

- [ ] 批量插入到 `bars` 表
- [ ] 去重逻辑（`INSERT ... ON CONFLICT`）
- [ ] 数据验证（OHLC 合法性）

#### Step 3: 断点续传（1h）

- [ ] 检查已有数据的日期范围
- [ ] 计算缺失的日期段
- [ ] 只下载缺失部分

#### Step 4: 数据查询（1h）

- [ ] `HistoricalDataProvider` 类
- [ ] 从数据库查询历史数据
- [ ] 转换为 DataFrame 格式
- [ ] 缓存机制

#### Step 5: 下载脚本和测试（1h）

- [ ] 命令行脚本
- [ ] 单元测试
- [ ] 集成测试（真实下载）

### 验收标准

- [ ] 能从 IBKR 下载日线和分钟线数据
- [ ] 数据正确存储到数据库
- [ ] 支持断点续传
- [ ] 能查询历史数据
- [ ] 单元测试通过
- [ ] 

# 日线

python scripts/download_history.py AAPL 2026-01-01 2026-08-24 --resolution daily

# 小时线

python scripts/download_history.py AAPL 2026-08-20 2026-08-24 --resolution hour

# 分钟线

python scripts/download_history.py AAPL 2026-08-23 2026-08-24 --resolution minute

---

## ⏸️ 任务3：技术指标库（待开始）

**优先级**: P1
**依赖**: 历史数据
**预估时间**: 6小时

### 目标

实现常用技术指标（SMA、EMA），支持自动预热

### 功能需求

#### 1. 简单移动平均（SMA）

```python
# 创建指标
self.sma_fast = self.SMA("AAPL", 10)
self.sma_slow = self.SMA("AAPL", 20)

# 获取值
if self.sma_fast.IsReady:
    print(self.sma_fast.Current.Value)
```

#### 2. 指数移动平均（EMA）

```python
self.ema = self.EMA("AAPL", 20)
```

#### 3. 自动预热

- 指标创建时自动加载历史数据
- 达到窗口期后 `IsReady = True`

#### 4. 实时更新

- 新数据到达时自动更新指标

### 文件位置

```
src/strategy/indicators/
├── indicator_base.py           # 指标基类（新建）
├── sma.py                      # 简单移动平均（新建）
├── ema.py                      # 指数移动平均（新建）
└── __init__.py

tests/slice3/
└── unit/test_indicators.py
```

### 实现步骤

#### Step 1: 指标基类（1.5h）

- [ ] `IndicatorBase` 抽象类
- [ ] `IsReady` 属性
- [ ] `Current` 属性（当前值）
- [ ] `Update(value)` 方法

#### Step 2: SMA 实现（1.5h）

- [ ] 滑动窗口实现
- [ ] 自动预热逻辑
- [ ] 实时更新

#### Step 3: EMA 实现（1.5h）

- [ ] 指数加权计算
- [ ] 自动预热
- [ ] 实时更新

#### Step 4: 集成到 QCAlgorithm（1h）

- [ ] `self.SMA()` 方法
- [ ] `self.EMA()` 方法
- [ ] 自动订阅数据更新

#### Step 5: 单元测试（0.5h）

- [ ] 测试 SMA 计算正确性
- [ ] 测试 EMA 计算正确性
- [ ] 测试预热机制

### 验收标准

- [ ] SMA、EMA 计算正确
- [ ] 自动预热机制工作
- [ ] 实时更新正常
- [ ] 单元测试通过

---

## ⏸️ 任务4：策略示例（待开始）

**优先级**: P1
**依赖**: QCAlgorithm + 指标库
**预估时间**: 4小时

### 目标

实现 SMA 双均线策略，在实盘验证框架可用性

### 策略逻辑

```python
class SMAStrategy(QCAlgorithm):
    def Initialize(self):
        # 添加股票
        self.AddEquity("AAPL", Resolution.Minute)
      
        # 创建指标
        self.sma_fast = self.SMA("AAPL", 10)
        self.sma_slow = self.SMA("AAPL", 20)
  
    def OnData(self, data):
        # 等待指标预热
        if not self.sma_fast.IsReady or not self.sma_slow.IsReady:
            return
      
        # 交易信号
        if self.sma_fast.Current.Value > self.sma_slow.Current.Value:
            # 金叉 - 买入
            if not self.Portfolio["AAPL"].Invested:
                self.MarketOrder("AAPL", 100)
        else:
            # 死叉 - 卖出
            if self.Portfolio["AAPL"].Invested:
                self.Liquidate("AAPL")
```

### 文件位置

```
strategies/
└── sma_crossover.py            # SMA 双均线策略（新建）

scripts/
└── run_strategy.py             # 策略运行脚本（新建）

tests/slice3/
└── integration/test_sma_strategy.py
```

### 实现步骤

#### Step 1: 实现策略（1.5h）

- [ ] 继承 QCAlgorithm
- [ ] 实现 Initialize
- [ ] 实现 OnData
- [ ] 实现交易逻辑

#### Step 2: 运行脚本（1h）

- [ ] 命令行脚本
- [ ] 加载配置
- [ ] 启动策略
- [ ] 日志输出

#### Step 3: 实盘测试（1h）

- [ ] 连接 Paper Trading
- [ ] 运行策略
- [ ] 验证订单执行
- [ ] 验证持仓更新

#### Step 4: 集成测试（0.5h）

- [ ] Mock 数据测试策略逻辑
- [ ] 验证信号生成

### 验收标准

- [ ] 策略能够运行
- [ ] 金叉买入、死叉卖出逻辑正确
- [ ] 订单正确提交到 IBKR
- [ ] 持仓正确更新
- [ ] 日志记录完整

---

## 📊 任务依赖关系图

```
任务1: QCAlgorithm 基类 (P0)
    ↓
    ├──→ 任务2: 历史数据下载
    │       ↓
    │       └──→ 任务3: 技术指标库
    │               ↓
    └───────────────→ 任务4: 策略示例
```

---

## 🎯 开发建议

### 当前状态

- Week 2 已完成（基础设施）
- 可以开始 Week 3

### 下一步

**立即开始任务1：QCAlgorithm 基类**

理由：

1. 是整个策略框架的核心
2. 其他任务都依赖它
3. 定义了策略开发的 API 风格

### 开发节奏

```
Day 1-2: 任务1（QCAlgorithm 基类）- 8小时
Day 3:   任务2（历史数据下载）- 6小时
Day 4:   任务3（技术指标库）- 6小时
Day 5:   任务4（策略示例）- 4小时
Day 6:   测试和文档
```

---

## 💡 设计要点

### 1. API 风格

参考 QuantConnect 的 API 设计：

- 简洁易用
- 符合直觉
- 减少样板代码

### 2. 数据管理

- 历史数据和实时数据统一接口
- 自动缓存，减少数据库查询

### 3. 指标预热

- 自动加载历史数据
- 对策略开发者透明

### 4. 错误处理

- 策略错误不应该让系统崩溃
- 记录详细日志

---

## 📝 测试策略

### 单元测试

- 每个任务都有单元测试
- Mock 外部依赖
- 快速验证

### 集成测试

- 任务4 需要集成测试
- 真实 IBKR 连接
- 验证完整流程

### 端到端测试

- Week 3 结束时
- 运行真实策略
- 验证所有功能

---

## ✅ 验收标准

Week 3 完成标准：

- [ ] QCAlgorithm 基类实现完整
- [ ] 能下载和查询历史数据
- [ ] SMA、EMA 指标正常工作
- [ ] SMA 双均线策略能运行
- [ ] 策略能在实盘（Paper Trading）运行
- [ ] 单元测试覆盖率 > 80%
- [ ] 文档完善

---

## 🚫 不做的事情（Week 3）

- ❌ 复杂指标（MACD、RSI、布林带等）
- ❌ 多标的同时运行
- ❌ 回测引擎
- ❌ 参数优化
- ❌ 高级风控

这些留到 Week 4+ 再做。

---

**当前状态**: Week 2 完成，准备开始 Week 3
**最后更新**: 2026-08-24
