# 任务1：异常处理完善 - 设计文档

**时间**: 2026-08-25  
**预估**: 6小时

---

## 📋 一、需求分析

### 1.1 核心需求
在所有关键路径添加异常捕获和降级处理，确保单点故障不导致系统崩溃。

### 1.2 使用场景

```python
# 场景1：网络异常自动重连
@retry(max_attempts=3, backoff=2.0)
def connect_to_ibkr():
    connection.connect()

# 场景2：数据异常使用默认值
try:
    price = parse_market_data(data)
except DataException as e:
    log.warning(f"Data error: {e}, using last valid price")
    price = last_valid_price

# 场景3：数据库异常自动重连
@auto_reconnect
def save_to_database(order):
    db.orders.insert(order)
```

### 1.3 关键问题清单

#### Q1: 哪些是关键路径？
- **IBKR连接**：connect(), disconnect(), 数据订阅
- **数据处理**：OnData(), 指标更新
- **订单执行**：MarketOrder(), OnOrderEvent()
- **数据库操作**：查询、插入、更新

#### Q2: 异常如何分类？
- **可恢复异常**：网络超时、连接断开 → 自动重试
- **可降级异常**：数据缺失、格式错误 → 使用默认值
- **致命异常**：配置错误、权限不足 → 记录日志并退出

#### Q3: 重试策略如何设计？
- **指数退避**：1s → 2s → 4s → 8s
- **最大重试次数**：3-5次
- **超时时间**：根据操作类型设定

#### Q4: 异常信息如何记录？
- **日志级别**：ERROR（需要人工介入）、WARNING（自动恢复）
- **日志内容**：异常类型、堆栈、上下文信息
- **告警触发**：致命异常立即告警

---

## 🏗️ 二、架构设计

### 2.1 异常处理层次结构

```
┌─────────────────────────────────────────┐
│         Application Layer                │
│  (strategies, scripts)                   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Exception Handler Layer             │
│  - @retry decorator                      │
│  - @exception_handler decorator          │
│  - Context manager                       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Core Services                    │
│  - IBKR Connection                       │
│  - Database                              │
│  - Data Processing                       │
└─────────────────────────────────────────┘
```

### 2.2 异常分类体系

```
BaseException
    │
    ├── SystemException (系统级异常)
    │   ├── ConnectionException (连接异常)
    │   │   ├── IBKRConnectionError
    │   │   └── DatabaseConnectionError
    │   │
    │   └── ConfigException (配置异常)
    │       ├── MissingConfigError
    │       └── InvalidConfigError
    │
    └── BusinessException (业务级异常)
        ├── DataException (数据异常)
        │   ├── DataMissingError
        │   ├── DataFormatError
        │   └── DataQualityError
        │
        └── OrderException (订单异常)
            ├── OrderRejectError
            └── OrderTimeoutError
```

### 2.3 关键类设计

#### ExceptionHandler (异常处理器)
```python
class ExceptionHandler:
    """统一异常处理器"""
    
    def __init__(self, logger, alert_manager):
        self.logger = logger
        self.alert_manager = alert_manager
    
    def handle(self, exception: Exception, context: dict):
        """处理异常"""
        # 1. 记录日志
        self.logger.error(f"Exception: {exception}", extra=context)
        
        # 2. 判断是否需要告警
        if self._should_alert(exception):
            self.alert_manager.send_alert(exception, context)
        
        # 3. 返回降级策略
        return self._get_fallback_strategy(exception)
    
    def _should_alert(self, exception: Exception) -> bool:
        """判断是否需要告警"""
        return isinstance(exception, SystemException)
    
    def _get_fallback_strategy(self, exception: Exception):
        """获取降级策略"""
        if isinstance(exception, DataException):
            return FallbackStrategy.USE_LAST_VALUE
        elif isinstance(exception, ConnectionException):
            return FallbackStrategy.RETRY
        else:
            return FallbackStrategy.FAIL_FAST
```

#### RetryDecorator (重试装饰器)
```python
def retry(max_attempts=3, backoff=2.0, exceptions=(Exception,)):
    """重试装饰器，支持指数退避"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            delay = 1.0
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    
                    log.warning(f"Attempt {attempt}/{max_attempts} failed: {e}")
                    time.sleep(delay)
                    delay *= backoff
            
        return wrapper
    return decorator
```

#### AutoReconnect (自动重连)
```python
class AutoReconnect:
    """自动重连上下文管理器"""
    
    def __init__(self, connection, max_retries=3):
        self.connection = connection
        self.max_retries = max_retries
    
    def __enter__(self):
        return self.connection
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, ConnectionException):
            log.warning("Connection lost, attempting to reconnect...")
            
            for i in range(self.max_retries):
                try:
                    self.connection.reconnect()
                    log.info("Reconnection successful")
                    return True  # 抑制异常
                except Exception as e:
                    log.error(f"Reconnect attempt {i+1} failed: {e}")
                    time.sleep(2 ** i)
            
            log.error("All reconnect attempts failed")
        
        return False  # 不抑制异常
```

---

## 🔧 三、子任务设计

### 3.1 网络异常处理（2小时）

#### 核心功能
1. **IBKR连接断开检测**
2. **自动重连机制**
3. **数据订阅恢复**

#### 实现方案

**连接状态监控**：
```python
class ConnectionMonitor:
    """连接状态监控器"""
    
    def __init__(self, connection, check_interval=5):
        self.connection = connection
        self.check_interval = check_interval
        self.last_heartbeat = time.time()
    
    def start(self):
        """启动监控"""
        threading.Thread(target=self._monitor_loop, daemon=True).start()
    
    def _monitor_loop(self):
        """监控循环"""
        while True:
            if not self.connection.is_connected():
                log.warning("Connection lost, initiating reconnect...")
                self._handle_disconnect()
            
            time.sleep(self.check_interval)
    
    def _handle_disconnect(self):
        """处理断线"""
        for i in range(3):
            try:
                self.connection.reconnect()
                self.connection.resubscribe_all()
                log.info("Reconnection successful")
                break
            except Exception as e:
                log.error(f"Reconnect attempt {i+1} failed: {e}")
                time.sleep(2 ** i)
```

**网络超时处理**：
```python
@retry(max_attempts=3, backoff=2.0, exceptions=(TimeoutError,))
def request_with_timeout(url, timeout=10):
    """带超时的网络请求"""
    try:
        response = requests.get(url, timeout=timeout)
        return response
    except requests.Timeout as e:
        log.warning(f"Request timeout: {url}")
        raise TimeoutError(f"Request to {url} timed out") from e
```

#### 测试用例
1. **test_connection_lost_reconnect** - 模拟连接断开，验证自动重连
2. **test_network_timeout_retry** - 模拟网络超时，验证重试机制
3. **test_resubscribe_after_reconnect** - 验证重连后数据订阅恢复

---

### 3.2 数据异常处理（2小时）

#### 核心功能
1. **数据缺失处理**
2. **数据格式异常处理**
3. **数据合理性检查**

#### 实现方案

**数据验证器**：
```python
class DataValidator:
    """数据验证器"""
    
    def __init__(self):
        self.last_valid_data = {}
    
    def validate(self, symbol: str, data: dict) -> dict:
        """验证数据并返回清洗后的数据"""
        try:
            # 1. 检查必需字段
            self._check_required_fields(data)
            
            # 2. 检查数据类型
            self._check_data_types(data)
            
            # 3. 检查数据合理性
            self._check_data_reasonableness(symbol, data)
            
            # 4. 更新最后有效数据
            self.last_valid_data[symbol] = data
            
            return data
        
        except DataException as e:
            log.warning(f"Data validation failed for {symbol}: {e}")
            return self._get_fallback_data(symbol)
    
    def _check_required_fields(self, data: dict):
        """检查必需字段"""
        required = ['time', 'open', 'high', 'low', 'close', 'volume']
        missing = [f for f in required if f not in data]
        if missing:
            raise DataMissingError(f"Missing fields: {missing}")
    
    def _check_data_types(self, data: dict):
        """检查数据类型"""
        if not isinstance(data['close'], (int, float)):
            raise DataFormatError(f"Invalid price type: {type(data['close'])}")
    
    def _check_data_reasonableness(self, symbol: str, data: dict):
        """检查数据合理性"""
        # 检查价格是否为正
        if data['close'] <= 0:
            raise DataQualityError(f"Invalid price: {data['close']}")
        
        # 检查价格跳变
        if symbol in self.last_valid_data:
            last_price = self.last_valid_data[symbol]['close']
            change_pct = abs(data['close'] - last_price) / last_price
            
            if change_pct > 0.2:  # 20%跳变
                raise DataQualityError(f"Price jump too large: {change_pct*100:.1f}%")
    
    def _get_fallback_data(self, symbol: str) -> dict:
        """获取降级数据"""
        if symbol in self.last_valid_data:
            log.info(f"Using last valid data for {symbol}")
            return self.last_valid_data[symbol]
        else:
            raise DataException(f"No fallback data available for {symbol}")
```

**安全数据访问**：
```python
def safe_get(data: dict, key: str, default=None):
    """安全地从字典获取值"""
    try:
        value = data.get(key, default)
        if value is None and default is not None:
            log.warning(f"Key '{key}' not found, using default: {default}")
        return value
    except Exception as e:
        log.error(f"Error accessing key '{key}': {e}")
        return default
```

#### 测试用例
1. **test_missing_field_fallback** - 缺少字段时使用上一个有效值
2. **test_invalid_price_rejected** - 无效价格被拒绝
3. **test_price_jump_detected** - 检测到价格异常跳变

---

### 3.3 数据库异常处理（2小时）

#### 核心功能
1. **连接断开自动重连**
2. **查询超时处理**
3. **事务失败回滚**

#### 实现方案

**数据库连接包装器**：
```python
class DatabaseConnection:
    """数据库连接包装器，支持自动重连"""
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.db = None
        self._connect()
    
    def _connect(self):
        """建立连接"""
        self.db = peewee.PostgresqlDatabase(**self.db_config)
    
    @retry(max_attempts=3, backoff=2.0, exceptions=(peewee.OperationalError,))
    def execute(self, query):
        """执行查询，失败自动重连"""
        try:
            return query.execute()
        except peewee.OperationalError as e:
            log.warning(f"Database error: {e}, reconnecting...")
            self._reconnect()
            raise
    
    def _reconnect(self):
        """重新连接"""
        try:
            if self.db and not self.db.is_closed():
                self.db.close()
        except:
            pass
        
        self._connect()
        log.info("Database reconnected")
    
    @contextmanager
    def transaction(self):
        """事务上下文，失败自动回滚"""
        try:
            with self.db.atomic():
                yield
        except Exception as e:
            log.error(f"Transaction failed: {e}, rolling back")
            raise
```

**查询超时处理**：
```python
def query_with_timeout(query, timeout=10):
    """带超时的查询"""
    try:
        # 设置查询超时
        with db.execution_context(timeout=timeout):
            return query.execute()
    except peewee.OperationalError as e:
        if 'timeout' in str(e).lower():
            log.warning(f"Query timeout after {timeout}s")
            raise TimeoutError("Database query timeout") from e
        raise
```

**数据库操作包装**：
```python
class SafeRepository:
    """安全的数据库操作封装"""
    
    @exception_handler(default_return=[])
    def get_all(self, model, filters=None):
        """安全的查询所有记录"""
        try:
            query = model.select()
            if filters:
                query = query.where(*filters)
            return list(query)
        except peewee.DoesNotExist:
            return []
        except peewee.OperationalError as e:
            log.error(f"Database query failed: {e}")
            raise DatabaseConnectionError("Failed to query database") from e
    
    @exception_handler(default_return=None)
    def save(self, instance):
        """安全的保存操作"""
        try:
            with db.atomic():
                instance.save()
            return instance
        except peewee.IntegrityError as e:
            log.warning(f"Integrity error: {e}")
            return None
        except Exception as e:
            log.error(f"Save failed: {e}")
            raise
```

#### 测试用例
1. **test_db_connection_lost_reconnect** - 数据库断开后自动重连
2. **test_query_timeout_handled** - 查询超时被捕获
3. **test_transaction_rollback** - 事务失败自动回滚

---

## 🧪 四、测试策略

### 4.1 单元测试

**测试目标**：覆盖率 > 85%

**关键测试场景**：

| 测试类 | 测试用例数 | 覆盖内容 |
|--------|-----------|----------|
| TestRetryDecorator | 5 | 重试逻辑、指数退避、最大次数 |
| TestConnectionMonitor | 4 | 连接检测、自动重连、订阅恢复 |
| TestDataValidator | 6 | 字段检查、类型检查、合理性检查 |
| TestDatabaseConnection | 5 | 自动重连、超时处理、事务回滚 |

**Mock策略**：
- Mock IBKR连接：模拟连接断开、超时
- Mock 数据源：返回异常数据
- Mock 数据库：模拟连接失败、查询超时

### 4.2 集成测试

**测试场景**：

1. **网络中断恢复测试**
   - 断开IBKR连接
   - 验证自动重连
   - 验证数据订阅恢复

2. **数据异常处理测试**
   - 发送缺失字段的数据
   - 发送异常价格的数据
   - 验证使用降级数据

3. **数据库故障测试**
   - 停止数据库服务
   - 验证重连机制
   - 验证查询降级

### 4.3 压力测试

**测试场景**：
- 频繁断开重连（每分钟1次，持续1小时）
- 高频异常数据（每秒100条，持续10分钟）
- 数据库间歇性故障（随机断开，持续1小时）

---

## 📦 五、实现步骤

### 步骤1：基础异常类定义（30分钟）
1. 创建 `src/common/exceptions.py`
2. 定义异常类层次结构
3. 添加异常信息模板

### 步骤2：重试装饰器实现（1小时）
1. 创建 `src/common/retry.py`
2. 实现 `@retry` 装饰器
3. 支持指数退避
4. 编写单元测试

### 步骤3：网络异常处理（2小时）
1. 创建 `src/trading/connection/monitor.py`
2. 实现连接监控
3. 实现自动重连
4. 编写单元测试和集成测试

### 步骤4：数据异常处理（2小时）
1. 创建 `src/data/validator.py`
2. 实现数据验证器
3. 实现降级策略
4. 编写单元测试

### 步骤5：数据库异常处理（2小时）
1. 创建 `src/database/safe_connection.py`
2. 实现连接包装器
3. 实现安全Repository
4. 编写单元测试和集成测试

### 步骤6：集成和调试（30分钟）
1. 集成所有模块
2. 运行所有测试
3. 修复发现的问题

---

## 🚨 六、潜在问题与解决方案

### 问题1：重试导致延迟累积
**现象**：多次重试导致响应时间过长
**解决**：
- 设置合理的最大重试次数（3次）
- 设置总超时时间限制
- 关键路径使用更短的超时

### 问题2：降级数据不准确
**现象**：使用旧数据可能导致交易决策错误
**解决**：
- 降级数据增加时间戳标记
- 超过阈值时停止交易决策
- 记录详细日志便于追溯

### 问题3：异常日志过多
**现象**：频繁的网络抖动导致日志爆炸
**解决**：
- 使用日志采样（每分钟最多N条相同日志）
- 异常去重（相同异常5分钟内只记录一次）
- 分级记录（ERROR/WARNING/INFO）

### 问题4：重连风暴
**现象**：多个连接同时重连导致资源耗尽
**解决**：
- 添加随机延迟（jitter）
- 限制并发重连数
- 使用连接池

---

## ✅ 七、验收标准

### 功能完整性
- ✅ 所有网络操作有超时和重试
- ✅ 所有数据访问有异常捕获
- ✅ 所有数据库操作有自动重连
- ✅ 异常分类清晰

### 健壮性
- ✅ 网络中断后能自动恢复
- ✅ 数据异常不导致崩溃
- ✅ 数据库故障能降级处理
- ✅ 日志记录完整

### 测试覆盖
- ✅ 单元测试覆盖率 > 85%
- ✅ 所有异常分支有测试
- ✅ 集成测试通过
- ✅ 压力测试通过

### 代码质量
- ✅ 符合PEP8规范
- ✅ 有完整的文档字符串
- ✅ 异常信息清晰
- ✅ 代码可维护性高

---

## 📊 八、时间分配

| 阶段 | 任务 | 预估时间 | 实际时间 |
|------|------|----------|----------|
| 1 | 基础异常类定义 | 0.5h | |
| 2 | 重试装饰器实现 | 1.0h | |
| 3 | 网络异常处理 | 2.0h | |
| 4 | 数据异常处理 | 2.0h | |
| 5 | 数据库异常处理 | 2.0h | |
| 6 | 集成和调试 | 0.5h | |
| **总计** | | **8.0h** | |

*注：预留2小时缓冲时间*

---

## 📝 九、总结

任务1的核心目标是**让系统具备自愈能力**：

1. **网络异常** → 自动重连、重试
2. **数据异常** → 验证、降级
3. **数据库异常** → 重连、超时处理

完成后，系统将能够：
- ✅ 网络抖动不影响运行
- ✅ 异常数据不导致崩溃
- ✅ 数据库故障能自动恢复
- ✅ 所有异常都有日志追溯

这是实现**7×24稳定运行**的基础。
