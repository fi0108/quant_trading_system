# 测试目录结构说明

## 目录组织原则

按照垂直切片开发计划组织测试，每个切片对应一个测试目录。

## 目录结构

```
tests/
├── slice1/              # 【切片1】数据接入验证
│   ├── unit/           # 单元测试
│   ├── integration/    # 集成测试
│   └── e2e/            # 端到端测试
│
├── slice2/              # 【切片2】基础设施完善
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── slice3/              # 【切片3】策略框架
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── slice4/              # 【切片4】稳定性强化
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── slice5/              # 【切片5-6】回测引擎
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── README.md            # 本文件
```

## 测试类型说明

### 1. unit/ - 单元测试
- 测试单个函数、类、方法
- 不依赖外部服务（IBKR、数据库）
- 使用 Mock/Stub
- 快速执行（< 1秒）

**示例**：
- `slice1/unit/test_data_validator.py` - 测试数据验证逻辑
- `slice2/unit/test_order_manager.py` - 测试订单管理器单个方法

### 2. integration/ - 集成测试
- 测试多个模块协作
- 可能需要外部服务（数据库、Redis）
- 真实环境或测试环境
- 中等执行时间（1-10秒）

**示例**：
- `slice1/integration/test_ibkr_connection.py` - 测试IBKR连接+数据订阅
- `slice2/integration/test_order_flow.py` - 测试订单创建→提交→状态更新全流程

### 3. e2e/ - 端到端测试
- 测试完整业务场景
- 所有真实依赖（IBKR模拟盘、数据库）
- 验证验收标准
- 较慢执行（10秒-几分钟）

**示例**：
- `slice1/e2e/test_realtime_data_feed.py` - 运行1小时验证数据接收稳定性
- `slice3/e2e/test_sma_strategy.py` - 完整运行SMA策略

## 切片对应关系

| 切片 | 周次 | 核心功能 | 测试重点 |
|------|------|---------|---------|
| slice1 | Week 1 | 数据接入验证 | IBKR连接、实时数据订阅、断线重连 |
| slice2 | Week 2 | 基础设施完善 | 数据持久化、订单/持仓管理、日志 |
| slice3 | Week 3 | 策略框架 | QCAlgorithm接口、技术指标、策略执行 |
| slice4 | Week 4 | 稳定性强化 | 异常处理、风控、监控告警、长时间运行 |
| slice5 | Week 5-7 | 回测引擎 | 回测核心、绩效分析、参数优化 |

## 命名规范

### 文件命名
- `test_<模块名>.py` - 例如：`test_ibkr_client.py`
- `test_<场景描述>.py` - 例如：`test_order_lifecycle.py`

### 测试函数命名
- `test_<功能>_<场景>_<预期结果>()`
- 例如：`test_connect_with_valid_credentials_success()`
- 例如：`test_place_order_insufficient_funds_rejected()`

## 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定切片的测试
pytest tests/slice1/

# 运行特定类型的测试
pytest tests/slice1/unit/
pytest tests/slice1/integration/
pytest tests/slice1/e2e/

# 运行特定测试文件
pytest tests/slice1/unit/test_ibkr_client.py

# 快速测试（只运行单元测试）
pytest tests/*/unit/

# 完整验证（包含e2e）
pytest tests/ --runslow
```

## 测试覆盖率

目标覆盖率：
- 单元测试：> 80%
- 集成测试：核心流程 100%
- e2e测试：每个切片验收标准 100%

## 注意事项

1. **单元测试优先**：新功能先写单元测试
2. **Mock外部依赖**：单元测试不连接IBKR/数据库
3. **集成测试使用测试环境**：不污染生产数据
4. **e2e测试标记为慢测试**：使用 `@pytest.mark.slow` 装饰器
5. **每个切片完成后补充测试**：边开发边测试

## 示例测试结构

```python
# tests/slice1/unit/test_ibkr_client.py
import pytest
from unittest.mock import Mock
from data.ibkr_client import IBKRClient

class TestIBKRClient:
    def test_connect_success(self):
        # 单元测试示例
        client = IBKRClient()
        # ... mock IB对象
        assert client.connect() == True
    
    def test_connect_timeout_retry(self):
        # 测试重试逻辑
        pass

# tests/slice1/integration/test_data_subscription.py
import pytest
from data.ibkr_client import IBKRClient
from data.realtime.subscriber import MarketDataSubscriber

class TestDataSubscription:
    def test_subscribe_and_receive_bars(self):
        # 集成测试示例（需要IBKR连接）
        client = IBKRClient()
        client.connect()
        # ... 真实订阅测试
        client.disconnect()

# tests/slice1/e2e/test_realtime_feed.py
import pytest

@pytest.mark.slow
@pytest.mark.e2e
def test_continuous_data_feed_1hour():
    # 端到端测试：运行1小时验证稳定性
    pass
```
