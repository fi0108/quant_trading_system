# 任务3：技术指标库 - 开发与测试思路

**时间**: 2026-08-24  
**预估**: 6小时

---

## 📋 一、需求分析

### 1.1 核心需求
实现常用技术指标（SMA、EMA），支持自动预热，集成到 QCAlgorithm

### 1.2 使用场景
```python
class MyStrategy(QCAlgorithm):
    def Initialize(self):
        # 创建指标
        self.sma_fast = self.SMA("AAPL", 10)
        self.sma_slow = self.SMA("AAPL", 20)
    
    def OnData(self, data):
        # 检查指标是否就绪
        if not self.sma_fast.IsReady:
            return
        
        # 使用指标值
        if self.sma_fast.Current.Value > self.sma_slow.Current.Value:
            self.MarketOrder("AAPL", 100)
```

### 1.3 关键问题清单

#### Q1: 指标预热的数据从哪来？
- **历史数据下载器**：从数据库读取历史数据
- **需要确保**：数据库中有足够的历史数据（Task 2 已完成）

#### Q2: 指标如何实时更新？
- **初始化时**：加载历史数据预热
- **运行时**：每次 OnData 时传入新数据更新

#### Q3: 指标的数据结构？
- **内部**：使用滑动窗口（deque 或 list）
- **对外**：提供 `.Current.Value` 访问当前值

#### Q4: 多个指标如何管理？
- QCAlgorithm 维护指标字典
- 每次 OnData 自动更新所有指标

---

## 🏗️ 二、架构设计

### 2.1 类层次结构

```
IndicatorBase (抽象基类)
    ├── properties: IsReady, Current, Period
    ├── methods: Update(value), Reset()
    │
    ├── SMA (简单移动平均)
    │   └── 实现：滑动窗口求平均
    │
    └── EMA (指数移动平均)
        └── 实现：指数加权计算
```

### 2.2 数据流

```
                    ┌─────────────┐
                    │ 历史数据    │
                    │ (预热)      │
                    └──────┬──────┘
                           │
                           ▼
┌──────────┐      ┌────────────────┐      ┌──────────┐
│ OnData   │─────▶│  Indicator     │─────▶│ IsReady  │
│ (实时)   │      │  Update()      │      │ Current  │
└──────────┘      └────────────────┘      └──────────┘
```

### 2.3 关键类设计

#### IndicatorDataPoint (数据点)
```python
class IndicatorDataPoint:
    """指标数据点"""
    def __init__(self, time: datetime, value: float):
        self.Time = time
        self.Value = value
```

#### IndicatorBase (基类)
```python
class IndicatorBase(ABC):
    """指标基类"""
    
    def __init__(self, name: str, period: int):
        self.Name = name
        self.Period = period
        self.Current = IndicatorDataPoint(datetime.min, 0.0)
        self._samples = 0
    
    @property
    def IsReady(self) -> bool:
        """是否已就绪（预热完成）"""
        return self._samples >= self.Period
    
    @abstractmethod
    def Update(self, time: datetime, value: float):
        """更新指标（子类实现）"""
        pass
    
    def Reset(self):
        """重置指标"""
        self._samples = 0
        self.Current = IndicatorDataPoint(datetime.min, 0.0)
```

#### SMA (简单移动平均)
```python
class SimpleMovingAverage(IndicatorBase):
    """简单移动平均"""
    
    def __init__(self, name: str, period: int):
        super().__init__(name, period)
        self._window = deque(maxlen=period)
    
    def Update(self, time: datetime, value: float):
        """更新指标"""
        self._window.append(value)
        self._samples += 1
        
        if self.IsReady:
            avg = sum(self._window) / len(self._window)
            self.Current = IndicatorDataPoint(time, avg)
```

#### EMA (指数移动平均)
```python
class ExponentialMovingAverage(IndicatorBase):
    """指数移动平均"""
    
    def __init__(self, name: str, period: int):
        super().__init__(name, period)
        self._k = 2.0 / (period + 1)  # 平滑系数
        self._ema_value = 0.0
    
    def Update(self, time: datetime, value: float):
        """更新指标"""
        self._samples += 1
        
        if self._samples == 1:
            # 第一个值直接使用
            self._ema_value = value
        else:
            # EMA = value * k + EMA_prev * (1 - k)
            self._ema_value = value * self._k + self._ema_value * (1 - self._k)
        
        self.Current = IndicatorDataPoint(time, self._ema_value)
```

---

## 🔧 三、集成到 QCAlgorithm

### 3.1 QCAlgorithm 增强

```python
class QCAlgorithm:
    def __init__(self, ...):
        # 指标管理
        self._indicators: Dict[str, List[IndicatorBase]] = {}  # {symbol: [indicators]}
    
    def SMA(self, symbol: str, period: int) -> SimpleMovingAverage:
        """创建 SMA 指标"""
        indicator = SimpleMovingAverage(f"SMA({period})", period)
        
        # 预热指标
        self._warmup_indicator(symbol, indicator)
        
        # 注册到自动更新列表
        if symbol not in self._indicators:
            self._indicators[symbol] = []
        self._indicators[symbol].append(indicator)
        
        return indicator
    
    def _warmup_indicator(self, symbol: str, indicator: IndicatorBase):
        """预热指标"""
        from data.historical.provider import HistoricalDataProvider
        
        provider = HistoricalDataProvider()
        
        # 获取足够的历史数据（指标周期 + buffer）
        history = provider.get_latest_bars(symbol, indicator.Period + 10, Resolution.Daily)
        
        if history.empty:
            log.warning(f"No history data for warming up {indicator.Name}")
            return
        
        # 用历史数据预热
        for timestamp, row in history.iterrows():
            indicator.Update(timestamp, row['close'])
        
        log.info(f"Warmed up {indicator.Name} with {len(history)} bars")
    
    def _process_data(self, data: Dict):
        """处理数据（自动更新指标）"""
        # 更新所有指标
        for symbol, bar in data.items():
            if symbol in self._indicators:
                for indicator in self._indicators[symbol]:
                    indicator.Update(bar.timestamp, bar.close)
        
        # 调用用户的 OnData
        self.OnData(data)
```

---

## ✅ 四、测试思路

### 4.1 单元测试（不依赖外部）

#### Test 1: SMA 计算正确性
```python
def test_sma_calculation():
    """测试 SMA 计算"""
    sma = SimpleMovingAverage("SMA(3)", 3)
    
    # 输入数据
    sma.Update(datetime(2024, 1, 1), 10.0)
    sma.Update(datetime(2024, 1, 2), 20.0)
    assert not sma.IsReady  # 还不够3个
    
    sma.Update(datetime(2024, 1, 3), 30.0)
    assert sma.IsReady  # 现在就绪了
    assert sma.Current.Value == 20.0  # (10+20+30)/3 = 20
    
    sma.Update(datetime(2024, 1, 4), 40.0)
    assert sma.Current.Value == 30.0  # (20+30+40)/3 = 30
```

#### Test 2: EMA 计算正确性
```python
def test_ema_calculation():
    """测试 EMA 计算"""
    ema = ExponentialMovingAverage("EMA(3)", 3)
    
    # 输入数据
    ema.Update(datetime(2024, 1, 1), 10.0)
    assert ema.Current.Value == 10.0  # 第一个值
    
    ema.Update(datetime(2024, 1, 2), 20.0)
    # EMA = 20 * 0.5 + 10 * 0.5 = 15
    assert ema.Current.Value == 15.0
```

#### Test 3: 指标重置
```python
def test_indicator_reset():
    """测试指标重置"""
    sma = SimpleMovingAverage("SMA(3)", 3)
    
    sma.Update(datetime(2024, 1, 1), 10.0)
    sma.Update(datetime(2024, 1, 2), 20.0)
    
    sma.Reset()
    
    assert sma._samples == 0
    assert not sma.IsReady
```

### 4.2 集成测试（需要数据库）

#### Test 4: 指标预热
```python
@requires_database
def test_indicator_warmup():
    """测试指标预热"""
    # 准备：数据库中有 AAPL 的历史数据
    
    strategy = TestStrategy(...)
    strategy._run_initialize()
    
    # 验证：指标已预热
    assert strategy.sma.IsReady
    assert strategy.sma.Current.Value > 0
```

#### Test 5: 指标实时更新
```python
def test_indicator_auto_update():
    """测试指标自动更新"""
    strategy = TestStrategy(...)
    strategy._run_initialize()
    
    # 模拟新数据
    data = {"AAPL": Mock(timestamp=datetime.now(), close=150.0)}
    
    old_value = strategy.sma.Current.Value
    strategy._process_data(data)
    new_value = strategy.sma.Current.Value
    
    # 验证：指标已更新
    assert new_value != old_value
```

---

## 🚀 五、实现步骤（按顺序）

### Step 1: 基础类 (1.5h)
- [ ] 创建 `IndicatorDataPoint`
- [ ] 创建 `IndicatorBase` 抽象类
- [ ] 编写基类单元测试

### Step 2: SMA 实现 (1.5h)
- [ ] 实现 `SimpleMovingAverage`
- [ ] 编写 SMA 单元测试（计算正确性）
- [ ] 验证滑动窗口逻辑

### Step 3: EMA 实现 (1.5h)
- [ ] 实现 `ExponentialMovingAverage`
- [ ] 编写 EMA 单元测试
- [ ] 验证指数加权计算

### Step 4: 集成到 QCAlgorithm (1h)
- [ ] 添加 `SMA()` 方法
- [ ] 添加 `EMA()` 方法
- [ ] 实现 `_warmup_indicator()`
- [ ] 实现自动更新逻辑

### Step 5: 测试 (0.5h)
- [ ] 集成测试（需要数据库）
- [ ] 端到端测试（完整策略）

---

## 🎯 六、验收标准

### 功能性
- [ ] SMA 计算正确（手工验证几个值）
- [ ] EMA 计算正确
- [ ] 指标能自动预热
- [ ] 指标能实时更新
- [ ] IsReady 状态正确

### 性能
- [ ] 指标更新快速（< 1ms）
- [ ] 内存占用合理（滑动窗口有上限）

### 代码质量
- [ ] 单元测试覆盖率 > 80%
- [ ] 代码注释清晰
- [ ] 符合 QuantConnect API 风格

---

## ⚠️ 七、潜在问题与解决

### 问题1: 历史数据不足
**现象**: 指标预热时数据库没有足够数据  
**解决**: 
- 先检查数据库，没有就提示用户下载
- 或者降级：不预热，等实时数据慢慢填满

### 问题2: 数据类型不一致
**现象**: bar.close 是 Decimal，指标需要 float  
**解决**: 在 Update 时统一转换为 float

### 问题3: 时间戳格式
**现象**: 数据库的 timestamp 和实时数据的 timestamp 格式不同  
**解决**: 使用 _normalize_timestamp 统一处理

---

## 📝 八、文件结构

```
src/strategy/indicators/
├── __init__.py
├── indicator_base.py       # 基类和数据点
├── sma.py                  # 简单移动平均
└── ema.py                  # 指数移动平均

tests/slice3/unit/
├── test_indicator_base.py
├── test_sma.py
└── test_ema.py
```

---

## ✅ 九、检查清单（开发前）

在开始编码前，确认以下问题都有答案：

- [x] 指标的数据来源明确（历史数据 + 实时数据）
- [x] 指标的计算公式明确（SMA、EMA）
- [x] 指标的生命周期明确（创建 → 预热 → 更新）
- [x] 指标与 QCAlgorithm 的集成方式明确
- [x] 测试用例设计完成
- [x] 潜在问题有预案

---

**准备开始编码！**  
**预计时间**: 6小时  
**当前状态**: 思路已清晰 ✅
