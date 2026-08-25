# 任务4：数据质量检查 - 设计文档

**时间**: 2026-08-25  
**预估**: 4小时

---

## 📋 一、需求分析

### 1.1 核心需求
检测和处理行情数据异常，确保策略基于准确、完整的数据运行，避免因数据问题导致错误决策。

### 1.2 使用场景

```python
# 场景1：数据质量检查
checker = DataQualityChecker()
result = checker.check(bar_data)

if result.passed:
    # 数据正常，继续处理
    strategy.OnData(bar_data)
else:
    # 数据异常，记录并处理
    logger.warning(f"Data quality issue: {result.issues}")

# 场景2：缺失数据补全
handler = MissingDataHandler()
complete_data = handler.fill_missing(incomplete_data)

# 场景3：异常检测
if checker.detect_price_jump(current_price, last_price):
    # 价格跳变过大，可能是数据错误
    alert_manager.send_alert("Price jump detected")
```

### 1.3 关键问题清单

#### Q1: 检查哪些数据质量问题？
- **价格异常**：负价格、零价格、异常跳变
- **高低价关系**：high < low、close不在[low, high]范围
- **成交量异常**：负成交量、零成交量（非盘前盘后）
- **时间戳异常**：未来时间、倒序、重复

#### Q2: 如何判断价格跳变异常？
- **标准差方法**：计算最近N个价格的标准差，超过3σ视为异常
- **百分比方法**：涨跌幅超过阈值（如20%）
- **综合判断**：结合成交量、时间等多维度

#### Q3: 缺失数据如何处理？
- **前值填充**：使用上一个有效值（适合缓慢变化的数据）
- **线性插值**：根据前后值线性计算（适合连续数据）
- **跳过**：标记为缺失，不参与计算
- **告警**：严重缺失时发送告警

#### Q4: 数据质量问题如何记录？
- **日志级别**：WARNING（可自动修复）、ERROR（需要人工介入）
- **统计信息**：记录各类问题出现次数
- **上下文信息**：记录标的、时间、具体数值

---

## 🏗️ 二、架构设计

### 2.1 数据质量检查流程

```
原始数据
    ↓
时间戳检查
    ↓
价格合理性检查
    ↓
高低价关系检查
    ↓
成交量检查
    ↓
价格跳变检测
    ↓
    ├─ 通过 → 返回干净数据
    │
    └─ 失败 → 记录问题 → 尝试修复 → 返回结果
```

### 2.2 数据质量体系

```
DataQualityChecker (质量检查器)
    ├── check_timestamp()      # 时间戳检查
    ├── check_price_validity() # 价格有效性
    ├── check_price_range()    # 价格范围
    ├── check_volume()         # 成交量
    └── detect_price_jump()    # 价格跳变

MissingDataHandler (缺失处理器)
    ├── detect_missing()       # 检测缺失
    ├── fill_forward()         # 前值填充
    ├── interpolate()          # 线性插值
    └── get_fill_stats()       # 填充统计
```

### 2.3 关键类设计

#### DataQualityResult (检查结果)
```python
@dataclass
class DataQualityResult:
    """数据质量检查结果"""
    passed: bool                    # 是否通过
    issues: List[str]               # 问题列表
    severity: str                   # 严重程度: info/warning/error
    fixed: bool                     # 是否已修复
    original_data: Dict[str, Any]   # 原始数据
    fixed_data: Dict[str, Any]      # 修复后数据
```

#### DataQualityChecker (质量检查器)
```python
class DataQualityChecker:
    """数据质量检查器"""
    
    def __init__(self, alert_manager=None):
        self.alert_manager = alert_manager
        self.stats = DataQualityStats()
        self.price_history: Dict[str, List[float]] = {}
        
    def check(self, symbol: str, data: Dict[str, Any]) -> DataQualityResult:
        """全面检查数据质量"""
        issues = []
        
        # 1. 时间戳检查
        if not self._check_timestamp(data):
            issues.append("Invalid timestamp")
        
        # 2. 价格有效性
        if not self._check_price_validity(data):
            issues.append("Invalid price")
        
        # 3. 高低价关系
        if not self._check_price_range(data):
            issues.append("Invalid price range")
        
        # 4. 成交量
        if not self._check_volume(data):
            issues.append("Invalid volume")
        
        # 5. 价格跳变
        if self._detect_price_jump(symbol, data):
            issues.append("Price jump detected")
        
        passed = len(issues) == 0
        return DataQualityResult(
            passed=passed,
            issues=issues,
            severity='error' if not passed else 'info'
        )
```

#### MissingDataHandler (缺失处理器)
```python
class MissingDataHandler:
    """缺失数据处理器"""
    
    def __init__(self):
        self.last_valid: Dict[str, Dict[str, Any]] = {}
        self.stats = MissingDataStats()
    
    def fill_missing(
        self,
        symbol: str,
        data: Dict[str, Any],
        method: str = 'forward'
    ) -> Dict[str, Any]:
        """填充缺失数据"""
        missing_fields = self._detect_missing(data)
        
        if not missing_fields:
            return data
        
        if method == 'forward':
            return self._fill_forward(symbol, data, missing_fields)
        elif method == 'interpolate':
            return self._interpolate(symbol, data, missing_fields)
        else:
            return data
```

---

## 🔧 三、子任务设计

### 3.1 数据异常检测（2小时）

#### 核心功能
1. **价格跳空检测**
2. **成交量异常检测**
3. **时间戳检查**

#### 实现方案

**DataQualityChecker（数据质量检查器）**：
```python
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import deque

class DataQualityChecker:
    """数据质量检查器"""
    
    def __init__(self, alert_manager=None):
        self.alert_manager = alert_manager
        self.stats = DataQualityStats()
        
        # 价格历史（用于跳变检测）
        self.price_history: Dict[str, deque] = {}
        self.history_size = 20  # 保留最近20个价格
        
        # 配置
        self.config = {
            'price_jump_std': 3.0,        # 标准差倍数
            'price_jump_pct': 0.2,        # 百分比阈值（20%）
            'volume_std': 5.0,            # 成交量异常倍数
            'future_tolerance': 60        # 未来时间容忍度（秒）
        }
    
    def check(self, symbol: str, data: Dict[str, Any]) -> DataQualityResult:
        """
        全面检查数据质量
        
        Args:
            symbol: 标的符号
            data: 行情数据
            
        Returns:
            检查结果
        """
        issues = []
        fixed_data = data.copy()
        
        # 1. 时间戳检查
        timestamp_issue = self._check_timestamp(data)
        if timestamp_issue:
            issues.append(timestamp_issue)
        
        # 2. 价格有效性
        price_issue = self._check_price_validity(data)
        if price_issue:
            issues.append(price_issue)
        
        # 3. 高低价关系
        range_issue = self._check_price_range(data)
        if range_issue:
            issues.append(range_issue)
        
        # 4. 成交量
        volume_issue = self._check_volume(data)
        if volume_issue:
            issues.append(volume_issue)
        
        # 5. 价格跳变
        jump_issue = self._detect_price_jump(symbol, data)
        if jump_issue:
            issues.append(jump_issue)
        
        # 记录统计
        passed = len(issues) == 0
        self.stats.record_check(passed)
        
        if not passed:
            self.stats.record_issues(issues)
            
            # 发送告警
            if self.alert_manager:
                self.alert_manager.send_alert(
                    alert_type='data',
                    severity='warning',
                    message=f"Data quality issues for {symbol}: {', '.join(issues)}",
                    context={'symbol': symbol, 'issues': issues}
                )
        
        return DataQualityResult(
            passed=passed,
            issues=issues,
            severity='error' if not passed else 'info',
            fixed=False,
            original_data=data,
            fixed_data=fixed_data
        )
    
    def _check_timestamp(self, data: Dict[str, Any]) -> Optional[str]:
        """检查时间戳"""
        if 'time' not in data:
            return "Missing timestamp"
        
        try:
            timestamp = data['time']
            
            # 转换为datetime
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            elif isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp)
            else:
                return f"Invalid timestamp type: {type(timestamp)}"
            
            # 检查是否未来时间
            now = datetime.now()
            if dt > now:
                diff = (dt - now).total_seconds()
                if diff > self.config['future_tolerance']:
                    return f"Future timestamp: {diff:.0f}s ahead"
            
            return None
            
        except Exception as e:
            return f"Timestamp error: {e}"
    
    def _check_price_validity(self, data: Dict[str, Any]) -> Optional[str]:
        """检查价格有效性"""
        price_fields = ['open', 'high', 'low', 'close']
        
        for field in price_fields:
            if field not in data:
                continue
            
            price = data[field]
            
            # 检查类型
            if not isinstance(price, (int, float)):
                return f"Invalid {field} type: {type(price)}"
            
            # 检查是否为正
            if price <= 0:
                return f"Invalid {field}: {price} (must be positive)"
        
        return None
    
    def _check_price_range(self, data: Dict[str, Any]) -> Optional[str]:
        """检查高低价关系"""
        required = ['high', 'low', 'close']
        if not all(f in data for f in required):
            return None
        
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 检查 high >= low
        if high < low:
            return f"High ({high}) < Low ({low})"
        
        # 检查 close 在 [low, high] 范围内
        if not (low <= close <= high):
            return f"Close ({close}) out of range [{low}, {high}]"
        
        return None
    
    def _check_volume(self, data: Dict[str, Any]) -> Optional[str]:
        """检查成交量"""
        if 'volume' not in data:
            return None
        
        volume = data['volume']
        
        # 检查类型
        if not isinstance(volume, (int, float)):
            return f"Invalid volume type: {type(volume)}"
        
        # 检查是否非负
        if volume < 0:
            return f"Negative volume: {volume}"
        
        return None
    
    def _detect_price_jump(self, symbol: str, data: Dict[str, Any]) -> Optional[str]:
        """检测价格跳变"""
        if 'close' not in data:
            return None
        
        current_price = data['close']
        
        # 初始化历史
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.history_size)
        
        history = self.price_history[symbol]
        
        # 历史数据不足
        if len(history) < 5:
            history.append(current_price)
            return None
        
        # 计算标准差
        prices = list(history)
        mean = np.mean(prices)
        std = np.std(prices)
        
        if std > 0:
            # 标准差方法
            z_score = abs(current_price - mean) / std
            
            if z_score > self.config['price_jump_std']:
                history.append(current_price)
                return f"Price jump: {z_score:.2f}σ from mean"
        
        # 百分比方法
        last_price = history[-1]
        if last_price > 0:
            change_pct = abs(current_price - last_price) / last_price
            
            if change_pct > self.config['price_jump_pct']:
                history.append(current_price)
                return f"Price jump: {change_pct*100:.1f}% change"
        
        history.append(current_price)
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.get_summary()


@dataclass
class DataQualityResult:
    """数据质量检查结果"""
    passed: bool
    issues: List[str]
    severity: str
    fixed: bool = False
    original_data: Dict[str, Any] = field(default_factory=dict)
    fixed_data: Dict[str, Any] = field(default_factory=dict)


class DataQualityStats:
    """数据质量统计"""
    
    def __init__(self):
        self.total_checks = 0
        self.passed_checks = 0
        self.failed_checks = 0
        self.issue_counts: Dict[str, int] = {}
    
    def record_check(self, passed: bool):
        """记录检查"""
        self.total_checks += 1
        if passed:
            self.passed_checks += 1
        else:
            self.failed_checks += 1
    
    def record_issues(self, issues: List[str]):
        """记录问题"""
        for issue in issues:
            self.issue_counts[issue] = self.issue_counts.get(issue, 0) + 1
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'failed_checks': self.failed_checks,
            'pass_rate': self.passed_checks / self.total_checks if self.total_checks > 0 else 0,
            'issue_counts': self.issue_counts.copy()
        }
```

#### 测试用例
1. **test_valid_data** - 有效数据通过检查
2. **test_invalid_price** - 负价格检测
3. **test_price_range** - 高低价关系检测
4. **test_price_jump** - 价格跳变检测
5. **test_future_timestamp** - 未来时间戳检测

---

### 3.2 缺失数据处理（2小时）

#### 核心功能
1. **缺失检测**
2. **前值填充**
3. **线性插值**

#### 实现方案

**MissingDataHandler（缺失数据处理器）**：
```python
class MissingDataHandler:
    """缺失数据处理器"""
    
    def __init__(self, alert_manager=None):
        self.alert_manager = alert_manager
        self.last_valid: Dict[str, Dict[str, Any]] = {}
        self.stats = MissingDataStats()
    
    def fill_missing(
        self,
        symbol: str,
        data: Dict[str, Any],
        method: str = 'forward'
    ) -> Dict[str, Any]:
        """
        填充缺失数据
        
        Args:
            symbol: 标的符号
            data: 原始数据
            method: 填充方法（forward/interpolate/skip）
            
        Returns:
            填充后的数据
        """
        missing_fields = self._detect_missing(data)
        
        if not missing_fields:
            # 保存有效数据
            self.last_valid[symbol] = data.copy()
            return data
        
        # 记录缺失
        self.stats.record_missing(symbol, missing_fields)
        
        # 发送告警
        if self.alert_manager and len(missing_fields) > 2:
            self.alert_manager.send_alert(
                alert_type='data',
                severity='warning',
                message=f"Multiple missing fields for {symbol}: {', '.join(missing_fields)}",
                context={'symbol': symbol, 'missing_fields': missing_fields}
            )
        
        # 填充
        if method == 'forward':
            filled_data = self._fill_forward(symbol, data, missing_fields)
        elif method == 'interpolate':
            filled_data = self._interpolate(symbol, data, missing_fields)
        else:
            filled_data = data
        
        # 保存
        if filled_data:
            self.last_valid[symbol] = filled_data.copy()
        
        return filled_data
    
    def _detect_missing(self, data: Dict[str, Any]) -> List[str]:
        """检测缺失字段"""
        required_fields = ['time', 'open', 'high', 'low', 'close', 'volume']
        missing = []
        
        for field in required_fields:
            if field not in data or data[field] is None:
                missing.append(field)
        
        return missing
    
    def _fill_forward(
        self,
        symbol: str,
        data: Dict[str, Any],
        missing_fields: List[str]
    ) -> Dict[str, Any]:
        """前值填充"""
        if symbol not in self.last_valid:
            logger.warning(f"No previous data for {symbol}, cannot fill forward")
            return data
        
        filled_data = data.copy()
        last_data = self.last_valid[symbol]
        
        for field in missing_fields:
            if field in last_data:
                filled_data[field] = last_data[field]
                logger.debug(f"Filled {field} for {symbol} with forward fill")
                self.stats.record_fill(symbol, field, 'forward')
        
        return filled_data
    
    def _interpolate(
        self,
        symbol: str,
        data: Dict[str, Any],
        missing_fields: List[str]
    ) -> Dict[str, Any]:
        """线性插值（简化版，需要历史数据序列）"""
        # 简化实现：退化为前值填充
        # 完整实现需要维护时间序列数据
        return self._fill_forward(symbol, data, missing_fields)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.get_summary()


class MissingDataStats:
    """缺失数据统计"""
    
    def __init__(self):
        self.missing_by_symbol: Dict[str, int] = {}
        self.missing_by_field: Dict[str, int] = {}
        self.fills_by_method: Dict[str, int] = {}
    
    def record_missing(self, symbol: str, fields: List[str]):
        """记录缺失"""
        self.missing_by_symbol[symbol] = self.missing_by_symbol.get(symbol, 0) + 1
        
        for field in fields:
            self.missing_by_field[field] = self.missing_by_field.get(field, 0) + 1
    
    def record_fill(self, symbol: str, field: str, method: str):
        """记录填充"""
        self.fills_by_method[method] = self.fills_by_method.get(method, 0) + 1
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            'missing_by_symbol': self.missing_by_symbol.copy(),
            'missing_by_field': self.missing_by_field.copy(),
            'fills_by_method': self.fills_by_method.copy()
        }
```

#### 测试用例
1. **test_detect_missing** - 检测缺失字段
2. **test_fill_forward** - 前值填充
3. **test_no_previous_data** - 无历史数据时的处理
4. **test_multiple_missing** - 多字段缺失
5. **test_stats** - 统计信息

---

## 🧪 四、测试策略

### 4.1 单元测试

**测试目标**：覆盖率 > 85%

**关键测试场景**：

| 测试类 | 测试用例数 | 覆盖内容 |
|--------|-----------|----------|
| TestDataQualityChecker | 8 | 各类异常检测 |
| TestMissingDataHandler | 5 | 缺失检测和填充 |

**Mock策略**：
- Mock AlertManager：验证告警发送
- Mock时间：测试时间戳检查
- Mock numpy：测试统计计算

### 4.2 集成测试

**测试场景**：
1. 完整数据处理流程
2. 质量检查+缺失填充组合
3. 告警触发验证

---

## 📦 五、实现步骤

### 步骤1：数据质量检查器（2小时）
1. 创建 `src/data/quality_checker.py`
2. 实现各类检查方法
3. 实现价格跳变检测
4. 编写单元测试

### 步骤2：缺失数据处理器（2小时）
1. 创建 `src/data/missing_handler.py`
2. 实现缺失检测
3. 实现填充策略
4. 编写单元测试

### 步骤3：集成和调试（30分钟）
1. 集成所有模块
2. 运行所有测试
3. 修复发现的问题

---

## 🚨 六、潜在问题与解决方案

### 问题1：正常波动被误判为跳变
**解决**：
- 结合多种检测方法
- 可配置的阈值
- 考虑成交量等辅助信息

### 问题2：填充数据不准确
**解决**：
- 明确标记填充数据
- 记录详细日志
- 提供多种填充策略

### 问题3：历史数据占用内存
**解决**：
- 限制历史数据大小
- 只保留必要字段
- 定期清理旧数据

---

## ✅ 七、验收标准

### 功能完整性
- ✅ 所有行情数据经过质量检查
- ✅ 异常数据被检测并记录
- ✅ 缺失数据被填充或标记
- ✅ 数据质量问题有告警

### 准确性
- ✅ 异常检测准确率>95%
- ✅ 填充数据合理
- ✅ 统计信息准确

### 测试覆盖
- ✅ 单元测试覆盖率 > 85%
- ✅ 所有检查场景有测试

### 可维护性
- ✅ 易于添加新的检查规则
- ✅ 配置灵活
- ✅ 日志完整

---

## 📊 八、时间分配

| 阶段 | 任务 | 预估时间 | 实际时间 |
|------|------|----------|----------|
| 1 | 数据质量检查器 | 2.0h | |
| 2 | 缺失数据处理器 | 2.0h | |
| 3 | 集成和调试 | 0.5h | |
| **总计** | | **4.5h** | |

---

## 📝 九、总结

任务4的核心目标是**数据可靠性**，通过：

1. **质量检查** - 多维度检测异常
2. **缺失处理** - 智能填充策略
3. **统计监控** - 掌握数据质量
4. **告警通知** - 及时发现问题

完成后，系统将具备：
- ✅ 完善的数据质量检查
- ✅ 智能的缺失数据处理
- ✅ 详细的统计信息
- ✅ 及时的问题告警

这是保障**策略正确决策**的基础。
