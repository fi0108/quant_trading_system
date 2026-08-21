# Week 1 Hello World - 快速开始指南

## 环境准备

### 1. Python 依赖安装

```bash
pip install ib_insync loguru pyyaml pytest
```

### 2. IBKR 准备

启动 IBKR Gateway 或 TWS：
- **纸盘模拟账户**：端口 `4002`
- **真实账户**：Gateway `4001`，TWS `7497`

确保 API 连接已启用：
- TWS: Configure → Global Configuration → API → Settings
- 勾选 "Enable ActiveX and Socket Clients"
- 勾选 "Allow connections from localhost only"

## 配置文件

### config/ibkr.yaml

```yaml
ibkr:
  host: "127.0.0.1"
  port: 4002          # 纸盘端口
  client_id: 1
  account: "DU123456" # 你的账户ID
  timeout: 15
```

**端口说明**：
- `4002` - 纸盘 Gateway
- `4001` - 真实账户 Gateway  
- `7497` - TWS (真实账户)
- `7496` - TWS (纸盘)

## 运行方式

### 1. 运行主程序

```bash
python week1_hello_world.py
```

**程序行为**：
1. 连接到 IBKR
2. 显示当前持仓
3. 订阅 AAPL 5秒K线
4. 每收到 10 个 Bar 买入 1 股 AAPL
5. 每次买入前检查现金余额 > $200
6. 按 Ctrl+C 停止

**示例输出**：
```
================================================================================
Week 1 Hello World - Trading System Starting
================================================================================
Connecting to IBKR...
Connected to IBKR successfully

Initial positions:
============================================================
No positions
============================================================

Subscribing to AAPL 5-second bars...
System is running. Press Ctrl+C to stop.
--------------------------------------------------------------------------------
[Bar 1] AAPL | Time: 2026-08-21 09:30:05 | Close: $150.25 | Volume: 1234
[Bar 2] AAPL | Time: 2026-08-21 09:30:10 | Close: $150.30 | Volume: 2341
...
[Bar 10] AAPL | Time: 2026-08-21 09:30:50 | Close: $150.35 | Volume: 1567
Attempting to buy 1 share of AAPL...
Available cash: $10000.00, Required: $200.00
Order created: BUY 1 AAPL, ID: 123
Order placed successfully: ID=123
```

### 2. 运行功能测试

测试单个功能模块：

```bash
# 测试所有功能
pytest tests/slice1/utils/ -v

# 测试订单管理
pytest tests/slice1/utils/test_order_manager.py -v

# 测试风控
pytest tests/slice1/utils/test_risk_manager.py -v

# 测试策略
pytest tests/slice1/utils/test_simple_buy_strategy.py -v
```

### 3. 运行集成测试

端到端集成测试（需要 IBKR 连接）：

```bash
pytest tests/slice1/integration/test_week1_hello_world.py -v
```

**集成测试流程**：
1. 连接 IBKR
2. 查询初始持仓
3. 订阅 AAPL 实时数据
4. 运行 2 分钟（约 24 个 Bar）
5. 验证下单逻辑（应触发 2 次买入）
6. 显示订单和持仓
7. 清理资源

## 验收标准检查

### ✅ 1. IBKR 连接

```bash
# 测试连接
pytest tests/slice1/utils/test_ibkr_connection.py -v
```

验证：
- 能连接到 IBKR Gateway
- 连接状态正确
- 断线能自动重连

### ✅ 2. 实时数据订阅

主程序运行后应看到：
```
Subscribed to AAPL
[Bar 1] AAPL | Time: ... | Close: $...
```

### ✅ 3. 固定买入策略

每 10 个 Bar 应看到：
```
Attempting to buy 1 share of AAPL...
Order created: BUY 1 AAPL, ID: xxx
```

### ✅ 4. 基础风控

如果现金不足：
```
Available cash: $150.00, Required: $200.00
Risk check failed, order rejected
```

### ✅ 5. 持仓查询

程序启动和停止时会打印持仓：
```
============================================================
Current Positions:
------------------------------------------------------------
AAPL     | Qty:      5 | Avg: $  150.25 | Value: $   751.25 | P&L: $    1.25
============================================================
```

### ✅ 6. 日志记录

日志文件位置：`logs/trading_YYYYMMDD.log`

关键日志：
- 连接事件
- 数据接收
- 订单创建
- 风控检查
- 错误异常

## 常见问题

### 1. 连接失败

**问题**：`Failed to connect to IBKR`

**解决**：
- 检查 Gateway/TWS 是否启动
- 检查端口是否正确（纸盘=4002）
- 检查 API 设置是否启用
- 检查防火墙设置

### 2. 订单被拒绝

**问题**：`Order rejected`

**可能原因**：
- 现金余额不足
- 股票代码错误
- 市场未开盘
- API 权限问题

**检查**：
```python
# 在 IBKR TWS 中查看
# Account → Account Window
# 查看可用资金和持仓
```

### 3. 没有数据推送

**问题**：没有看到 Bar 数据

**可能原因**：
- 市场未开盘（周末或节假日）
- 订阅失败
- 数据权限问题

**解决**：
- 确认市场交易时间
- 检查数据订阅权限
- 使用纸盘可以 7×24 测试

### 4. 测试失败

**问题**：功能测试失败

**解决**：
```bash
# 查看详细错误
pytest tests/slice1/utils/ -v --tb=long

# 清理缓存重试
rm -rf .pytest_cache __pycache__
pytest tests/slice1/utils/ -v
```

## 项目结构

```
quant_trading_system/
├── config/                      # 配置文件
│   ├── ibkr.yaml               # IBKR 连接配置
│   └── system.yaml             # 系统配置
├── src/
│   ├── broker/                 # 券商接口
│   │   ├── ibkr_client.py     # IBKR 客户端
│   │   ├── order_manager.py   # 订单管理
│   │   ├── risk_manager.py    # 风控管理
│   │   └── position_manager.py # 持仓管理
│   ├── data/
│   │   └── realtime_feed.py   # 实时数据订阅
│   ├── strategy/
│   │   └── simple_buy_strategy.py # 固定买入策略
│   └── common/
│       ├── config.py           # 配置加载
│       ├── logger.py           # 日志
│       └── models.py           # 数据模型
├── tests/slice1/
│   ├── utils/                  # 功能测试
│   └── integration/            # 集成测试
├── logs/                        # 日志目录
├── week1_hello_world.py        # 主程序
└── docs/
    ├── Week1_Summary.md        # Week 1 总结
    └── Week1_QuickStart.md     # 本文档
```

## 下一步

Week 1 完成后，继续 Week 2 开发：
1. 订单状态跟踪
2. 持仓管理增强  
3. PostgreSQL 存储
4. 基础监控告警

参考：`docs/计划文档/统一开发计划.md`

## 技术支持

遇到问题：
1. 查看日志文件 `logs/trading_*.log`
2. 运行测试定位问题 `pytest -v`
3. 检查 IBKR 连接状态
4. 查看配置文件是否正确
