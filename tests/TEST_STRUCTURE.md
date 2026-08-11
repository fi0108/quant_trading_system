# 测试目录结构规范

## 目录结构

```
tests/
├── README.md                           # 测试总体说明
├── conftest.py                         # pytest配置和共享fixtures
├── requirements-test.txt               # 测试依赖
│
├── module1_market_data/                # 模块一：市场数据接入
│   ├── README.md                       # 模块测试说明
│   ├── unit/                           # 单元测试
│   │   ├── __init__.py
│   │   ├── test_timezone_manager.py
│   │   ├── test_trading_calendar.py
│   │   ├── test_connection_manager.py
│   │   ├── test_subscriber.py
│   │   ├── test_validator.py
│   │   ├── test_redis_writer.py
│   │   ├── test_postgres_writer.py
│   │   ├── test_historical_sync.py
│   │   └── test_quality_checker.py
│   ├── integration/                    # 集成测试
│   │   ├── __init__.py
│   │   ├── test_scheduler.py          # 调度器集成测试
│   │   ├── test_data_flow.py          # 完整数据流测试
│   │   └── test_storage_integration.py # 存储层集成测试
│   └── system/                         # 系统测试
│       ├── __init__.py
│       └── test_complete_flow.py       # 端到端测试
│
├── module2_strategy/                   # 模块二：策略框架（预留）
│   ├── unit/
│   ├── integration/
│   └── system/
│
├── utils/                              # 测试工具
│   ├── __init__.py
│   ├── mock_helpers.py                 # Mock辅助函数
│   └── fixtures.py                     # 通用fixtures
│
└── performance/                        # 性能测试
    └── test_data_throughput.py
```

## 测试分层说明

### 1. 单元测试 (unit/)
- **目的**: 测试单个组件/类的功能
- **特点**: 
  - 快速执行（< 1秒）
  - 无外部依赖
  - 使用Mock模拟外部服务
- **运行**: `pytest tests/module1_market_data/unit/`

### 2. 集成测试 (integration/)
- **目的**: 测试多个组件协作
- **特点**:
  - 中等执行时间（几秒到几分钟）
  - 可能依赖数据库、Redis（可用Docker或内存版本）
  - 测试组件间接口
- **运行**: `pytest tests/module1_market_data/integration/`

### 3. 系统测试 (system/)
- **目的**: 端到端完整流程测试
- **特点**:
  - 较长执行时间（可能几分钟到小时）
  - 需要真实IBKR连接、数据库
  - 测试完整业务场景
- **运行**: `pytest tests/module1_market_data/system/ -v`

## 运行测试

### 运行所有测试
```bash
pytest tests/
```

### 运行特定模块
```bash
# 模块一所有测试
pytest tests/module1_market_data/

# 只运行单元测试
pytest tests/module1_market_data/unit/

# 只运行集成测试
pytest tests/module1_market_data/integration/
```

### 运行特定测试文件
```bash
pytest tests/module1_market_data/unit/test_validator.py -v
```

### 带覆盖率报告
```bash
pytest tests/ --cov=src --cov-report=html
```

## 测试命名规范

- 测试文件: `test_<component_name>.py`
- 测试类: `Test<ComponentName>`
- 测试方法: `test_<功能描述>`

## 标记 (Markers)

```python
import pytest

@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.slow
def test_long_running():
    pass

@pytest.mark.requires_ibkr
def test_with_ibkr():
    pass
```

运行特定标记的测试：
```bash
pytest -m unit              # 只运行单元测试
pytest -m "not slow"        # 跳过慢速测试
pytest -m requires_ibkr     # 只运行需要IBKR的测试
```

# 单元测试（快速）
pytest tests/module1_market_data/unit/ -v

# 所有测试
pytest tests/module1_market_data/ -v

# 系统测试（需要IBKR）
pytest tests/module1_market_data/system/ -v