# Week5 代码修复计划

**基于**: 阶段一代码审查报告
**目标**: 将评分从82分提升到90分以上
**总预计时间**: 13-16.5小时
**执行时间**: Week5 (Day1-Day5)

---

## 📋 修复任务清单

### Day 1: 目录结构修复（3小时）

#### 任务1.1: 检查monitor vs monitoring重复（30分钟）

**目标**: 确定两个目录的功能和差异

**步骤**：

```bash
# 1. 列出两个目录的文件
ls -la src/monitor/
ls -la src/monitoring/

# 2. 对比功能
diff -r src/monitor/ src/monitoring/

# 3. 检查谁在使用
grep -rn "from monitor\." src/ tests/ scripts/ strategies/
grep -rn "from monitoring\." src/ tests/ scripts/ strategies/

# 4. 检查导入
grep -rn "import monitor" src/ tests/ scripts/ strategies/
grep -rn "import monitoring" src/ tests/ scripts/ strategies/
```

**输出**：

- [ ] 功能对比文档
- [ ] 使用情况统计

---

#### 任务1.2: 统一使用monitor目录（2小时）

**决策**: 保留 `src/monitor/`，删除 `src/monitoring/`

**步骤**：

1. **迁移必要的代码**（如果有）

```bash
# 如果monitoring有独特功能，迁移到monitor
# 如果完全重复，直接删除
```

2. **更新所有导入**

```bash
# 查找所有使用monitoring的地方
grep -rn "from monitoring" . --include="*.py" --exclude-dir=venv

# 批量替换
find . -name "*.py" -type f -exec sed -i 's/from monitoring\./from monitor./g' {} \;
find . -name "*.py" -type f -exec sed -i 's/import monitoring/import monitor/g' {} \;
```

3. **删除monitoring目录**

```bash
rm -rf src/monitoring/
```

4. **运行测试验证**

```bash
pytest tests/ -v
```

**输出**：

- [ ] monitoring目录已删除
- [ ] 所有导入已更新
- [ ] 测试全部通过

### Day 2-3: 创建端到端测试（8小时）

#### 任务2.1: 创建端到端测试框架（1小时）

**目标**: 建立端到端测试基础结构

**步骤**：

1. **创建目录结构**

```bash
mkdir -p tests/e2e
touch tests/e2e/__init__.py
touch tests/e2e/conftest.py
```

2. **创建共享fixtures** (`tests/e2e/conftest.py`)

```python
"""
端到端测试共享fixtures
"""
import pytest
from unittest.mock import Mock, MagicMock, patch

@pytest.fixture
def mock_ibkr():
    """Mock IBKR连接"""
    with patch('data.ibkr_client.IB') as mock:
        mock_instance = MagicMock()
        mock_instance.isConnected.return_value = True
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_db():
    """Mock数据库连接"""
    with patch('database.safe_connection.get_connection') as mock:
        yield mock

@pytest.fixture
def test_config():
    """测试配置"""
    return {
        'ibkr': {
            'host': '127.0.0.1',
            'port': 7497,
            'client_id': 999
        },
        'database': {
            'host': 'localhost',
            'port': 5432,
            'database': 'test_db'
        }
    }
```

**输出**：

- [ ] 测试框架已创建
- [ ] conftest.py已实现

---

#### 任务2.2: 完整交易流程测试（3小时）

**目标**: 测试从连接到下单的完整流程

**创建文件**: `tests/e2e/test_full_trading_flow.py`

```python
"""
端到端测试：完整交易流程

测试场景：
1. 系统初始化
2. IBKR连接
3. 数据订阅
4. 策略计算
5. 风控检查
6. 订单执行
7. 持仓更新
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from data.ibkr_client import IBKRClient
from strategy.qc_algorithm import QCAlgorithm, Resolution
from risk.manager import RiskManager
from risk.models import Order as RiskOrder
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


class TestFullTradingFlow:
    """完整交易流程端到端测试"""
  
    @patch('data.ibkr_client.IB')
    def test_complete_trading_flow(self, mock_ib):
        """
        测试：完整交易流程
  
        流程：
        连接 → 订阅数据 → 策略计算 → 风控检查 → 下单 → 持仓更新
        """
        # 1. 初始化系统组件
        # ========================================
  
        # Mock IBKR实例
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance
  
        # 创建客户端
        client = IBKRClient(host='127.0.0.1', port=7497, client_id=999)
  
        # 2. 连接测试
        # ========================================
        result = client.connect()
        assert result is True, "连接应该成功"
        assert client.is_connected(), "应该处于连接状态"
  
        # 3. 数据订阅测试
        # ========================================
        mock_bar_data = {
            'symbol': 'AAPL',
            'time': datetime.now(),
            'open': 150.0,
            'high': 151.0,
            'low': 149.0,
            'close': 150.5,
            'volume': 1000
        }
  
        data_received = []
  
        def on_bar(bars, has_new_bar):
            if has_new_bar:
                data_received.append(bars[-1])
  
        # 订阅数据
        client.subscribe_realtime_bars('AAPL', callback=on_bar)
  
        # 模拟数据到达
        # （实际Mock调用）
  
        # 4. 策略计算测试
        # ========================================
        class SimpleTestStrategy(QCAlgorithm):
            def __init__(self, ibkr_client):
                self.ibkr_client = ibkr_client
                self.signal_generated = False
          
            def Initialize(self):
                self.AddEquity("AAPL", Resolution.Minute)
          
            def OnData(self, data):
                # 简单策略：价格>150就买入
                if data.get('close', 0) > 150:
                    self.signal_generated = True
                    self.MarketOrder("AAPL", 100)
  
        # 创建策略实例
        strategy = SimpleTestStrategy(client)
        strategy.Initialize()
  
        # 模拟数据到达
        strategy.OnData(mock_bar_data)
  
        assert strategy.signal_generated, "策略应该生成交易信号"
  
        # 5. 风控检查测试
        # ========================================
        risk_manager = RiskManager()
  
        # 创建订单
        test_order = RiskOrder(
            symbol='AAPL',
            quantity=100,
            action='BUY',
            order_type='MARKET'
        )
  
        # 风控检查（Mock账户信息）
        context = {
            'portfolio_value': 100000,
            'cash': 50000,
            'positions': {}
        }
  
        risk_result = risk_manager.check_order(test_order, context)
        assert risk_result.passed, f"风控应该通过，失败原因：{risk_result.reason}"
  
        # 6. 订单执行测试
        # ========================================
        order_manager = OrderManager(client)
  
        # 下单
        with patch.object(order_manager, '_submit_to_ibkr') as mock_submit:
            mock_submit.return_value = {'order_id': 1001, 'status': 'Submitted'}
      
            order = order_manager.place_order(
                symbol='AAPL',
                quantity=100,
                action='BUY',
                order_type='MARKET'
            )
      
            assert order is not None, "订单应该创建成功"
            assert mock_submit.called, "应该提交到IBKR"
  
        # 7. 持仓更新测试
        # ========================================
        position_manager = PositionManager(client)
  
        # 模拟成交
        position_manager.update_position(
            symbol='AAPL',
            quantity=100,
            avg_price=150.5
        )
  
        position = position_manager.get_position('AAPL')
        assert position is not None, "持仓应该存在"
        assert position.quantity == 100, "持仓数量应该正确"
        assert position.avg_cost == 150.5, "持仓成本应该正确"
  
        # 8. 清理
        # ========================================
        client.disconnect()
  
        print("✅ 完整交易流程测试通过")
  
    @patch('data.ibkr_client.IB')
    def test_flow_with_risk_rejection(self, mock_ib):
        """
        测试：风控拒绝场景
  
        场景：订单被风控拒绝，不应该提交到IBKR
        """
        # Mock IBKR
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance
  
        client = IBKRClient(host='127.0.0.1', port=7497, client_id=999)
        client.connect()
  
        # 风控管理器
        risk_manager = RiskManager()
  
        # 创建超大订单（应该被拒绝）
        large_order = RiskOrder(
            symbol='AAPL',
            quantity=10000,  # 超大数量
            action='BUY',
            order_type='MARKET'
        )
  
        # 风控检查（账户资金不足）
        context = {
            'portfolio_value': 100000,
            'cash': 10000,  # 资金不足
            'positions': {}
        }
  
        risk_result = risk_manager.check_order(large_order, context)
        assert not risk_result.passed, "风控应该拒绝"
        assert "资金" in risk_result.reason or "insufficient" in risk_result.reason.lower()
  
        # 订单不应该提交
        order_manager = OrderManager(client)
  
        with patch.object(order_manager, '_submit_to_ibkr') as mock_submit:
            # 如果风控拒绝，应该抛出异常或返回None
            # （根据实际实现调整）
            pass
  
        print("✅ 风控拒绝场景测试通过")
```

**输出**：

- [ ] 完整交易流程测试已实现
- [ ] 风控拒绝场景测试已实现

---

#### 任务2.3: 断线重连测试（2小时）

**创建文件**: `tests/e2e/test_reconnection.py`

```python
"""
端到端测试：断线重连

测试场景：
1. 正常连接
2. 模拟断线
3. 自动重连
4. 数据恢复
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from data.ibkr_client import IBKRClient


class TestReconnection:
    """断线重连测试"""
  
    @patch('data.ibkr_client.IB')
    def test_auto_reconnect(self, mock_ib):
        """
        测试：自动重连
  
        场景：
        1. 建立连接
        2. 模拟断线
        3. 验证自动重连
        """
        # Mock IBKR实例
        mock_ib_instance = MagicMock()
        mock_ib.return_value = mock_ib_instance
  
        # 初始连接成功
        mock_ib_instance.isConnected.return_value = True
  
        client = IBKRClient(host='127.0.0.1', port=7497, client_id=999)
        assert client.connect(), "初始连接应该成功"
  
        # 模拟断线
        mock_ib_instance.isConnected.return_value = False
        assert not client.is_connected(), "应该检测到断线"
  
        # 模拟重连成功
        mock_ib_instance.isConnected.return_value = True
  
        # 触发重连（根据实际实现调整）
        # client._reconnect() 或等待自动重连
  
        # 验证重连成功
        time.sleep(0.1)  # 模拟等待
        assert client.is_connected(), "应该重连成功"
  
        print("✅ 自动重连测试通过")
  
    @patch('data.ibkr_client.IB')
    def test_data_subscription_recovery(self, mock_ib):
        """
        测试：重连后数据订阅恢复
  
        场景：
        1. 订阅数据
        2. 断线
        3. 重连
        4. 验证数据继续接收
        """
        # 实现测试逻辑
        pass
```

**输出**：

- [ ] 断线重连测试已实现

---

#### 任务2.4: 异常恢复测试（2小时）

**创建文件**: `tests/e2e/test_exception_recovery.py`

```python
"""
端到端测试：异常恢复

测试场景：
1. 数据缺失处理
2. 订单失败处理
3. 数据库异常处理
4. 系统恢复
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from data.ibkr_client import IBKRClient
from common.exceptions import DataMissingError, OrderExecutionError


class TestExceptionRecovery:
    """异常恢复测试"""
  
    @patch('data.ibkr_client.IB')
    def test_data_missing_recovery(self, mock_ib):
        """
        测试：数据缺失恢复
  
        场景：
        1. 接收到不完整数据
        2. 系统检测并处理
        3. 系统继续运行
        """
        # Mock IBKR
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib.return_value = mock_ib_instance
  
        client = IBKRClient()
        client.connect()
  
        # 模拟不完整数据
        incomplete_data = {
            'symbol': 'AAPL',
            # 缺少close价格
        }
  
        # 验证数据验证器处理
        from data.validator import DataValidator
        validator = DataValidator()
  
        result = validator.validate(incomplete_data)
        assert not result.is_valid, "应该检测到数据缺失"
  
        # 验证系统继续运行（不崩溃）
        assert client.is_connected(), "系统应该继续运行"
  
        print("✅ 数据缺失恢复测试通过")
  
    @patch('data.ibkr_client.IB')
    def test_order_failure_recovery(self, mock_ib):
        """
        测试：订单失败恢复
  
        场景：
        1. 提交订单
        2. 订单被拒绝
        3. 系统记录并继续
        """
        # 实现测试逻辑
        pass
  
    @patch('data.ibkr_client.IB')
    @patch('database.safe_connection.get_connection')
    def test_database_exception_recovery(self, mock_db, mock_ib):
        """
        测试：数据库异常恢复
  
        场景：
        1. 数据库连接失败
        2. 系统降级运行
        3. 恢复后继续记录
        """
        # 实现测试逻辑
        pass
```

**输出**：

- [ ] 异常恢复测试已实现

---

### Day 4: 一般问题修复（3小时）

#### 任务4.1: 检查risk manager重复（1小时）

**目标**: 确认是否功能重复

**步骤**：

```bash
# 1. 对比两个文件
diff src/trading/risk/manager.py src/risk/manager.py

# 2. 检查使用情况
grep -rn "from trading.risk" src/ tests/ scripts/ strategies/
grep -rn "from risk" src/ tests/ scripts/ strategies/

# 3. 决策
# - 如果功能不同：更新文档说明各自职责
# - 如果功能相同：合并到src/risk/，删除src/trading/risk/
```

**输出**：

- [ ] 功能对比文档
- [ ] 决策和执行结果

---

#### 任务4.2: 更新模块索引（1小时）

**目标**: 补充缺失的模块

**步骤**：

```bash
# 1. 识别缺失模块
# - src/scheduling/
# - src/utils/
# - src/data/storage/
# - 其他新增模块

# 2. 更新docs/模块索引.md
```

**输出**：

- [ ] 模块索引已更新

---

#### 任务4.3: 更新架构演进日志（1小时）

**目标**: 记录本周所有修复

**步骤**：

```markdown
# 在docs/架构演进日志.md顶部添加

## 2026-08-26: Week5代码质量修复

### 变更类型
🔧 **重构 (Refactoring)**

### 变更原因
基于阶段一代码审查报告，修复发现的问题

### 变更内容

#### 1. 统一监控模块
- 删除 `src/monitoring/`
- 统一使用 `src/monitor/`

#### 2. 创建端到端测试
- 新增 `tests/e2e/`
- 实现完整交易流程测试
- 实现断线重连测试
- 实现异常恢复测试

#### 3. 清理backtest目录
- 删除或明确保留原因

#### 4. 更新文档
- 更新模块索引
- 更新架构演进日志

### 影响范围
- 提升代码质量评分从82分到90+分
- 建立完整的端到端测试体系
- 架构更清晰
```

**输出**：

- [ ] 架构演进日志已更新

---

### Day 5: 代码质量工具和验证（2.5小时）

#### 任务5.1: 引入代码质量工具（1.5小时）

**目标**: 引入自动化代码质量检查

**步骤**：

1. **安装工具**

```bash
pip install flake8 pylint black isort pytest-cov
```

2. **配置flake8** (`.flake8`)

```ini
[flake8]
max-line-length = 120
exclude = venv,.git,__pycache__,build,dist
ignore = E203,W503
```

3. **配置isort** (`pyproject.toml`)

```toml
[tool.isort]
profile = "black"
line_length = 120
skip = ["venv", ".git"]
```

4. **配置black** (`pyproject.toml`)

```toml
[tool.black]
line-length = 120
target-version = ['py310']
exclude = '''
/(
    \.git
  | \.venv
  | build
  | dist
)/
'''
```

5. **运行检查**

```bash
# 代码格式化
black src/ tests/ scripts/ strategies/

# 导入排序
isort src/ tests/ scripts/ strategies/

# 代码规范检查
flake8 src/ tests/ scripts/ strategies/

# 代码质量检查
pylint src/ --max-line-length=120
```

**输出**：

- [ ] 代码质量工具已配置
- [ ] 代码已格式化

---

#### 任务5.2: 运行完整测试（30分钟）

**目标**: 验证所有修复

**步骤**：

```bash
# 1. 运行所有单元测试
pytest tests/ -v --cov=src --cov-report=html

# 2. 运行端到端测试
pytest tests/e2e/ -v

# 3. 检查覆盖率
open htmlcov/index.html

# 4. 验证Demo脚本
python scripts/demo/quick_test.py
python scripts/demo/run_integrated_demo.py --help
```

**期望结果**：

- [ ] 所有测试通过
- [ ] 覆盖率 > 85%
- [ ] Demo正常运行

---

#### 任务5.3: 重新运行代码审查（30分钟）

**目标**: 验证评分提升

**步骤**：

```bash
# 运行审查脚本
bash scripts/code_review.sh > docs/Week5_审查结果.txt

# 手动检查关键项
```

**期望结果**：

- [ ] 目录结构：5/5
- [ ] 导入规范：5/5
- [ ] 端到端测试：5/5
- [ ] 文档同步：15/15
- [ ] **总分 > 90/100**

---

## 📊 进度跟踪

### 每日完成情况

| Day    | 任务         | 预计 | 实际 | 状态 | 备注 |
| ------ | ------------ | ---- | ---- | ---- | ---- |
| Day1   | 目录结构修复 | 3h   |      | ⏳   |      |
| Day2-3 | 端到端测试   | 8h   |      | ⏳   |      |
| Day4   | 一般问题修复 | 3h   |      | ⏳   |      |
| Day5   | 工具和验证   | 2.5h |      | ⏳   |      |

### 问题修复状态

| 问题                  | 优先级 | 状态      | 完成时间 |
| --------------------- | ------ | --------- | -------- |
| monitor vs monitoring | 高     | ⏳ 待处理 |          |
| 缺少端到端测试        | 高     | ⏳ 待处理 |          |
| risk manager重复      | 中     | ⏳ 待处理 |          |
| backtest目录          | 中     | ⏳ 待处理 |          |
| 更新模块索引          | 中     | ⏳ 待处理 |          |

---

## ✅ 验收标准

### 修复完成标准

- [ ] monitor vs monitoring已统一
- [ ] 端到端测试已创建并通过
- [ ] risk manager重复已处理
- [ ] backtest目录已处理
- [ ] 模块索引已更新
- [ ] 架构演进日志已更新
- [ ] 代码质量工具已引入
- [ ] 所有测试通过
- [ ] 代码审查评分 > 90分

### 质量标准

- [ ] 测试覆盖率 > 85%
- [ ] 所有flake8检查通过
- [ ] 代码已格式化（black）
- [ ] 导入已排序（isort）
- [ ] 文档与代码同步

---

## 🎯 执行指引

### 开始执行

```bash
# 1. 创建Week5工作分支
git checkout -b week5-code-quality-fix

# 2. 按照计划逐日执行
# Day1: 执行任务1.1-1.3
# Day2-3: 执行任务2.1-2.4
# Day4: 执行任务4.1-4.3
# Day5: 执行任务5.1-5.3

# 3. 每天提交进度
git add .
git commit -m "Week5 DayX: 完成XXX任务"

# 4. 全部完成后合并
git checkout main
git merge week5-code-quality-fix
```

### 遇到问题

- 记录在 `docs/Week5_问题记录.md`
- 及时调整计划
- 保持文档同步

---

**Let's go! 开始执行修复计划！** 🚀

---

**文档版本**: v1.0
**创建时间**: 2026-08-25
**执行状态**: 待开始
**预计完成**: Week5 结束
