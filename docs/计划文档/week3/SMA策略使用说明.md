# SMA双均线交叉策略 - 使用说明

## 策略简介

SMA双均线交叉策略是一个经典的趋势跟踪策略，基于快速和慢速简单移动平均线的交叉信号进行交易。

### 核心逻辑

- **金叉买入**：当快速均线从下方穿过慢速均线时，买入开仓
- **死叉卖出**：当快速均线从上方穿过慢速均线时，卖出平仓

### 适用场景

- 趋势明显的市场
- 中长期交易
- 适合股票、期货等有明显趋势的品种

---

## 快速开始

### 1. 环境准备

确保已安装依赖并配置好数据库：

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库（如果还没有）
python scripts/init_database.py
```

### 2. 下载历史数据

策略需要历史数据来预热指标：

```bash
# 下载AAPL的历史数据（最近1年）
python scripts/download_history.py AAPL 2025-08-24 2026-08-24 --resolution daily
```

### 3. 配置策略参数

编辑 `config/strategy_config.yaml`：

```yaml
strategy:
  sma:
    fast_period: 10      # 快速均线周期
    slow_period: 20      # 慢速均线周期
  
  trading:
    symbol: "AAPL"       # 交易标的
    default_quantity: 100 # 每次交易股数
  
  risk:
    max_order_value: 10000  # 单笔最大金额（美元）
```

### 4. 启动IBKR

- 打开TWS或IB Gateway
- 在 **配置 > API > 设置** 中：
  - 勾选"启用ActiveX和Socket客户端"
  - 端口设置为 `7497`（模拟盘）或 `7496`（实盘）
  - 添加信任的IP：`127.0.0.1`

### 5. 运行策略

```bash
# 使用默认配置运行
python scripts/run_strategy.py --strategy sma_crossover_live

# 或者覆盖部分参数
python scripts/run_strategy.py \
    --strategy sma_crossover_live \
    --symbol TSLA \
    --fast 5 \
    --slow 10 \
    --quantity 50
```

---

## 配置说明

### 策略参数

| 参数 | 说明 | 默认值 | 建议范围 |
|------|------|--------|----------|
| `fast_period` | 快速均线周期 | 10 | 5-20天 |
| `slow_period` | 慢速均线周期 | 20 | 20-50天 |
| `default_quantity` | 每次交易数量 | 100 | 根据资金调整 |
| `max_order_value` | 单笔最大金额 | 10000 | 根据风险承受度 |

### 参数调优建议

#### 保守型参数
```yaml
sma:
  fast_period: 10
  slow_period: 30
trading:
  default_quantity: 50
risk:
  max_order_value: 5000
```

- 慢速均线周期更长，信号更稳定但响应慢
- 交易数量和单笔金额较小，风险较低

#### 激进型参数
```yaml
sma:
  fast_period: 5
  slow_period: 15
trading:
  default_quantity: 200
risk:
  max_order_value: 20000
```

- 快速均线周期更短，信号更灵敏但可能频繁
- 交易数量和单笔金额较大，收益和风险都更高

---

## 运行示例

### 示例1：AAPL，10/20日均线

```bash
python scripts/run_strategy.py \
    --strategy sma_crossover_live \
    --symbol AAPL \
    --fast 10 \
    --slow 20 \
    --quantity 100
```

**预期输出**：

```
============================================================
Strategy Runner
============================================================

Loading config from: config/strategy_config.yaml
✓ Config loaded
Initializing database connection...
✓ Database initialized
✓ Logger initialized: logs/strategy.log
Connecting to IBKR...
✓ Connected to IBKR
Creating strategy: sma_crossover_live
✓ Strategy created
============================================================
Starting strategy execution...
============================================================
[LOG] ============================================================
[LOG] Initializing SMA Crossover Strategy
[LOG] Symbol: AAPL
[LOG] Fast SMA Period: 10
[LOG] Slow SMA Period: 20
[LOG] Trade Quantity: 100
[LOG] Max Order Value: $10000.00
[LOG] ============================================================
[LOG] [INDICATOR] Fast SMA created: period=10
[LOG] [INDICATOR] Slow SMA created: period=20
[LOG] [POSITION] No current position

Subscribing to market data: AAPL

✓ Strategy is running. Press Ctrl+C to stop.

[LOG] [WARMUP] Indicators warming up... Fast: 5/10, Slow: 5/20
[LOG] [WARMUP] Indicators warming up... Fast: 10/10, Slow: 10/20
[LOG] [WARMUP] Indicators warming up... Fast: 15/10, Slow: 15/20
[LOG] [WARMUP] Indicators warming up... Fast: 20/10, Slow: 20/20
[LOG] [INDICATOR] SMA_Fast=152.30, SMA_Slow=151.80
[LOG] [SIGNAL] Golden Cross detected! Fast: 151.50→152.30, Slow: 152.00→151.80
[LOG] [ORDER] Placing BUY order: AAPL x 100 @ $152.50
[LOG] [FILL] Order 1 filled: AAPL x 100 @ $152.50
[LOG] [POSITION] Current position: 100 shares, Avg cost: $152.50, P&L: $0.00
```

### 示例2：TSLA，5/15日均线（更激进）

```bash
python scripts/run_strategy.py \
    --strategy sma_crossover_live \
    --symbol TSLA \
    --fast 5 \
    --slow 15 \
    --quantity 50
```

---

## 监控与日志

### 日志文件

日志默认输出到 `logs/strategy.log`，包含：

- 策略初始化信息
- 指标预热进度
- 交易信号（金叉/死叉）
- 订单提交/成交/拒绝
- 持仓变化
- 错误异常

### 关键日志格式

```
[SIGNAL] Golden Cross detected! ...  # 金叉信号
[SIGNAL] Death Cross detected! ...   # 死叉信号
[ORDER] Placing BUY order: ...       # 下单
[FILL] Order X filled: ...           # 成交
[POSITION] Current position: ...     # 持仓更新
[RISK] Order value exceeds max ...   # 风险控制
[ERROR] Exception in OnData: ...     # 异常错误
```

### 实时监控

运行时终端会显示关键日志，建议：

1. 使用 `tail -f logs/strategy.log` 实时查看日志
2. 在IBKR TWS中查看实时持仓和订单
3. 定期检查账户余额和盈亏

---

## 常见问题

### Q1: 策略启动后长时间没有交易

**可能原因**：
- 指标正在预热（需要等待慢速均线周期的数据）
- 当前市场没有交叉信号
- 历史数据不足

**解决方法**：
- 检查日志中的 `[WARMUP]` 信息，确认指标是否就绪
- 确保已下载足够的历史数据（至少慢速均线周期的2倍）
- 查看当前均线值是否接近交叉

### Q2: 订单被拒绝

**可能原因**：
- 账户资金不足
- 交易权限不足（如做空权限）
- 市场状态（如盘前/盘后）

**解决方法**：
- 检查IBKR账户余额
- 检查日志中的拒绝原因
- 调整 `default_quantity` 降低每次交易数量
- 确保在正常交易时段运行

### Q3: 连接IBKR失败

**可能原因**：
- TWS/Gateway未启动
- API设置未启用
- 端口号错误

**解决方法**：
1. 确认TWS或IB Gateway正在运行
2. 检查 **配置 > API > 设置**：
   - ✓ 启用ActiveX和Socket客户端
   - 端口：7497（模拟）或 7496（实盘）
   - 信任的IP：127.0.0.1
3. 检查配置文件中的端口号是否匹配

### Q4: 信号频繁，交易成本高

**解决方法**：
- 增加慢速均线周期，减少交叉频率
- 添加信号过滤条件（如最小价格变化）
- 考虑使用更长的时间周期（如日线改为周线）

### Q5: 策略崩溃或异常退出

**解决方法**：
- 查看 `logs/strategy.log` 中的错误堆栈
- 检查网络连接是否稳定
- 确认数据库连接正常
- 重启策略，观察是否重复

---

## 风险提示

⚠️ **重要警告**

1. **策略仅供学习和研究使用**，不构成投资建议
2. **先在模拟账户测试**，确认稳定后再考虑实盘
3. **严格控制仓位**，建议单笔不超过总资金的5-10%
4. **设置止损**，防止单次亏损过大
5. **双均线策略在震荡市场表现不佳**，注意市场环境
6. **历史表现不代表未来收益**

---

## 进阶使用

### 自定义策略

基于 `SMAStrategyLive` 可以轻松扩展：

```python
class MySMAStrategy(SMAStrategyLive):
    def Initialize(self):
        super().Initialize()
        # 添加止损参数
        self.stop_loss_pct = 0.05  # 5%止损
        
    def OnData(self, data):
        super().OnData(data)
        
        # 添加止损逻辑
        holdings = self.Portfolio.get_holdings(self.symbol)
        if holdings and holdings.quantity > 0:
            unrealized_pnl_pct = holdings.unrealized_pnl / (holdings.average_price * holdings.quantity)
            if unrealized_pnl_pct < -self.stop_loss_pct:
                self.Log(f"[STOP LOSS] Triggered at {unrealized_pnl_pct*100:.2f}%")
                self.MarketOrder(self.symbol, -holdings.quantity)
```

### 多标的同时运行

修改 `run_strategy.py`，支持多个标的：

```python
symbols = ["AAPL", "TSLA", "MSFT"]
strategies = []

for symbol in symbols:
    strategy = SMAStrategyLive(...)
    strategy.symbol = symbol
    strategy.Initialize()
    strategies.append(strategy)
```

---

## 支持与反馈

如有问题或建议，请查看：
- 项目文档：`docs/`
- 测试用例：`tests/slice3/`
- 设计文档：`docs/Task4_策略示例_设计文档.md`
