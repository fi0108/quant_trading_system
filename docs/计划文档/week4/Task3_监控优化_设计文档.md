# 任务3：监控优化 - 设计文档

**时间**: 2026-08-25  
**预估**: 6小时

---

## 📋 一、需求分析

### 1.1 核心需求
完善系统监控和告警机制，及时发现和处理问题，避免告警风暴和资源耗尽。

### 1.2 使用场景

```python
# 场景1：告警去重
alert_manager = AlertManager()
alert_manager.send_alert("IBKR连接断开")  # 第1次发送
alert_manager.send_alert("IBKR连接断开")  # 5分钟内，合并不发送
alert_manager.send_alert("IBKR连接断开")  # 5分钟后，再次发送

# 场景2：系统资源监控
system_monitor = SystemMonitor()
metrics = system_monitor.get_metrics()
# {'cpu_percent': 45.2, 'memory_percent': 68.5, 'disk_usage': 75.0}

if metrics['cpu_percent'] > 80:
    alert_manager.send_alert("CPU使用率过高: 85%")

# 场景3：策略状态监控
strategy_monitor = StrategyMonitor()
strategy_monitor.update_heartbeat()  # 收到数据时更新

if strategy_monitor.check_timeout():
    alert_manager.send_alert("策略心跳超时")
```

### 1.3 关键问题清单

#### Q1: 告警如何去重？
- **时间窗口**：相同告警5分钟内只发送一次
- **告警指纹**：根据类型+内容生成唯一标识
- **恢复通知**：问题解决后发送恢复消息

#### Q2: 监控哪些系统资源？
- **CPU**：使用率（阈值80%）
- **内存**：使用率（阈值80%）
- **磁盘**：使用率（阈值90%）
- **数据库连接数**：活跃连接（阈值100）
- **日志文件大小**：单文件大小（阈值100MB）

#### Q3: 如何检测策略状态？
- **心跳超时**：60秒无数据推送
- **指标计算延迟**：指标更新时间间隔
- **订单执行延迟**：下单到成交的时间

#### Q4: 告警如何发送？
- **日志**：所有告警记录到日志
- **控制台**：严重告警打印到控制台
- **扩展接口**：预留邮件/企业微信接口

---

## 🏗️ 二、架构设计

### 2.1 监控体系架构

```
┌─────────────────────────────────────────┐
│         Application Layer                │
│  (Strategies, Services)                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Monitor Layer                    │
│  ┌────────────────────────────────┐     │
│  │  AlertManager (告警管理器)      │     │
│  │  - send_alert()                │     │
│  │  - deduplication               │     │
│  │  - rate limiting               │     │
│  └────────────────────────────────┘     │
│                                          │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ SystemMonitor │  │ StrategyMonitor│  │
│  │ - CPU        │  │ - Heartbeat  │    │
│  │ - Memory     │  │ - Latency    │    │
│  │ - Disk       │  │ - Metrics    │    │
│  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Alert Output                     │
│  - Logging                               │
│  - Console                               │
│  - Email (扩展)                          │
│  - WeChat (扩展)                         │
└─────────────────────────────────────────┘
```

### 2.2 告警流程

```
告警触发
    ↓
生成告警指纹 (type + content)
    ↓
检查去重缓存
    ↓
    ├─ 命中（5分钟内） → 丢弃，计数+1
    │
    └─ 未命中 → 发送告警
                    ↓
               记录到缓存
                    ↓
               写入日志
                    ↓
           （可选）发送到外部渠道
```

### 2.3 关键类设计

#### Alert (告警数据类)
```python
@dataclass
class Alert:
    """告警数据类"""
    alert_type: str           # 告警类型: system/strategy/risk
    severity: str             # 严重程度: info/warning/error/critical
    message: str              # 告警消息
    context: Dict[str, Any]   # 上下文信息
    timestamp: float          # 时间戳
    
    def get_fingerprint(self) -> str:
        """生成告警指纹"""
        return f"{self.alert_type}:{self.message}"
```

#### AlertDeduplicator (告警去重器)
```python
class AlertDeduplicator:
    """告警去重器"""
    
    def __init__(self, window: int = 300):  # 5分钟
        self.window = window
        self.cache: Dict[str, AlertRecord] = {}
    
    def should_send(self, alert: Alert) -> bool:
        """判断是否应该发送告警"""
        fingerprint = alert.get_fingerprint()
        
        if fingerprint in self.cache:
            record = self.cache[fingerprint]
            
            # 在时间窗口内
            if time.time() - record.first_seen < self.window:
                record.count += 1
                record.last_seen = time.time()
                return False
            else:
                # 超过窗口，重新发送
                self._reset_record(fingerprint, alert)
                return True
        else:
            # 首次出现
            self._create_record(fingerprint, alert)
            return True
```

#### SystemMonitor (系统资源监控器)
```python
class SystemMonitor:
    """系统资源监控器"""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.thresholds = {
            'cpu_percent': 80,
            'memory_percent': 80,
            'disk_usage': 90
        }
    
    def get_metrics(self) -> Dict[str, float]:
        """获取系统指标"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent
        }
    
    def check_and_alert(self):
        """检查并告警"""
        metrics = self.get_metrics()
        
        for key, value in metrics.items():
            threshold = self.thresholds.get(key)
            if threshold and value > threshold:
                self.alert_manager.send_alert(
                    alert_type='system',
                    severity='warning',
                    message=f"{key} exceeds threshold: {value:.1f}% > {threshold}%"
                )
```

#### StrategyMonitor (策略状态监控器)
```python
class StrategyMonitor:
    """策略状态监控器"""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.last_heartbeat = time.time()
        self.heartbeat_timeout = 60  # 60秒
        self.order_latencies: List[float] = []
    
    def update_heartbeat(self):
        """更新心跳"""
        self.last_heartbeat = time.time()
    
    def check_heartbeat(self) -> bool:
        """检查心跳超时"""
        elapsed = time.time() - self.last_heartbeat
        
        if elapsed > self.heartbeat_timeout:
            self.alert_manager.send_alert(
                alert_type='strategy',
                severity='error',
                message=f"Strategy heartbeat timeout: {elapsed:.0f}s"
            )
            return True
        
        return False
    
    def record_order_latency(self, latency: float):
        """记录订单延迟"""
        self.order_latencies.append(latency)
        
        # 只保留最近100个
        if len(self.order_latencies) > 100:
            self.order_latencies.pop(0)
```

---

## 🔧 三、子任务设计

### 3.1 告警去重（2小时）

#### 核心功能
1. **告警去重**（5分钟窗口）
2. **告警频率限制**
3. **告警恢复通知**

#### 实现方案

**AlertDeduplicator（告警去重器）**：
```python
@dataclass
class AlertRecord:
    """告警记录"""
    fingerprint: str
    first_seen: float
    last_seen: float
    count: int
    alert: Alert

class AlertDeduplicator:
    """告警去重器"""
    
    def __init__(self, window: int = 300, max_count: int = 10):
        self.window = window  # 时间窗口（秒）
        self.max_count = max_count  # 窗口内最大告警次数
        self.cache: Dict[str, AlertRecord] = {}
    
    def should_send(self, alert: Alert) -> Tuple[bool, Optional[str]]:
        """
        判断是否应该发送告警
        
        Returns:
            (should_send, reason)
        """
        fingerprint = alert.get_fingerprint()
        now = time.time()
        
        if fingerprint in self.cache:
            record = self.cache[fingerprint]
            elapsed = now - record.first_seen
            
            # 在时间窗口内
            if elapsed < self.window:
                record.count += 1
                record.last_seen = now
                
                # 检查频率限制
                if record.count > self.max_count:
                    return False, f"Rate limit exceeded: {record.count} alerts in {elapsed:.0f}s"
                else:
                    return False, f"Deduplicated: {record.count} times in {elapsed:.0f}s"
            else:
                # 超过窗口，发送摘要
                summary = self._create_summary(record)
                self._reset_record(fingerprint, alert, now)
                return True, summary
        else:
            # 首次出现
            self._create_record(fingerprint, alert, now)
            return True, None
    
    def _create_summary(self, record: AlertRecord) -> str:
        """创建告警摘要"""
        elapsed = record.last_seen - record.first_seen
        return f"(repeated {record.count} times in {elapsed:.0f}s)"
    
    def _create_record(self, fingerprint: str, alert: Alert, now: float):
        """创建新记录"""
        self.cache[fingerprint] = AlertRecord(
            fingerprint=fingerprint,
            first_seen=now,
            last_seen=now,
            count=1,
            alert=alert
        )
    
    def _reset_record(self, fingerprint: str, alert: Alert, now: float):
        """重置记录"""
        self.cache[fingerprint] = AlertRecord(
            fingerprint=fingerprint,
            first_seen=now,
            last_seen=now,
            count=1,
            alert=alert
        )
    
    def cleanup_expired(self):
        """清理过期记录"""
        now = time.time()
        expired = [
            fp for fp, record in self.cache.items()
            if now - record.last_seen > self.window * 2
        ]
        
        for fp in expired:
            del self.cache[fp]
```

**AlertManager（告警管理器）**：
```python
class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.deduplicator = AlertDeduplicator(window=300, max_count=10)
        self.handlers: List[AlertHandler] = []
        self.stats = AlertStats()
        
        # 默认处理器
        self._add_default_handlers()
    
    def send_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        context: Dict[str, Any] = None
    ):
        """发送告警"""
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            context=context or {},
            timestamp=time.time()
        )
        
        # 去重检查
        should_send, reason = self.deduplicator.should_send(alert)
        
        if should_send:
            # 发送到所有处理器
            for handler in self.handlers:
                try:
                    handler.handle(alert, reason)
                except Exception as e:
                    logger.error(f"Alert handler error: {e}")
            
            self.stats.record_sent(alert)
        else:
            self.stats.record_deduplicated(alert)
    
    def add_handler(self, handler: 'AlertHandler'):
        """添加告警处理器"""
        self.handlers.append(handler)
    
    def _add_default_handlers(self):
        """添加默认处理器"""
        self.handlers.append(LoggingAlertHandler())
        self.handlers.append(ConsoleAlertHandler())
```

**AlertHandler（告警处理器）**：
```python
class AlertHandler(ABC):
    """告警处理器抽象基类"""
    
    @abstractmethod
    def handle(self, alert: Alert, reason: Optional[str] = None):
        """处理告警"""
        pass

class LoggingAlertHandler(AlertHandler):
    """日志告警处理器"""
    
    def handle(self, alert: Alert, reason: Optional[str] = None):
        """写入日志"""
        suffix = f" {reason}" if reason else ""
        
        log_func = {
            'info': logger.info,
            'warning': logger.warning,
            'error': logger.error,
            'critical': logger.critical
        }.get(alert.severity, logger.warning)
        
        log_func(f"[ALERT] [{alert.alert_type}] {alert.message}{suffix}")

class ConsoleAlertHandler(AlertHandler):
    """控制台告警处理器"""
    
    def handle(self, alert: Alert, reason: Optional[str] = None):
        """打印到控制台（仅严重告警）"""
        if alert.severity in ['error', 'critical']:
            suffix = f" {reason}" if reason else ""
            print(f"🚨 [ALERT] {alert.message}{suffix}")
```

#### 测试用例
1. **test_alert_deduplication** - 5分钟内相同告警去重
2. **test_alert_rate_limit** - 频率限制
3. **test_alert_window_expiry** - 时间窗口过期后重新发送
4. **test_alert_summary** - 告警摘要生成
5. **test_cleanup_expired** - 清理过期记录

---

### 3.2 系统资源监控（2小时）

#### 核心功能
1. **CPU/内存/磁盘监控**
2. **数据库连接数监控**
3. **日志文件大小监控**

#### 实现方案

**SystemMonitor（系统资源监控器）**：
```python
import psutil
import os
from typing import Dict, Any, List

class SystemMonitor:
    """系统资源监控器"""
    
    def __init__(self, alert_manager: AlertManager = None):
        self.alert_manager = alert_manager
        self.monitoring = False
        self.monitor_thread = None
        
        # 阈值配置
        self.thresholds = {
            'cpu_percent': 80,
            'memory_percent': 80,
            'disk_usage': 90,
            'db_connections': 100
        }
        
        # 历史数据
        self.history: Dict[str, List[float]] = {
            'cpu_percent': [],
            'memory_percent': [],
            'disk_usage': []
        }
        self.history_max_size = 60  # 保留60个数据点
    
    def get_cpu_metrics(self) -> Dict[str, float]:
        """获取CPU指标"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'cpu_count': psutil.cpu_count(),
            'load_average': os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0
        }
    
    def get_memory_metrics(self) -> Dict[str, float]:
        """获取内存指标"""
        mem = psutil.virtual_memory()
        return {
            'memory_percent': mem.percent,
            'memory_total': mem.total / (1024**3),  # GB
            'memory_available': mem.available / (1024**3),  # GB
            'memory_used': mem.used / (1024**3)  # GB
        }
    
    def get_disk_metrics(self, path: str = '/') -> Dict[str, float]:
        """获取磁盘指标"""
        disk = psutil.disk_usage(path)
        return {
            'disk_usage': disk.percent,
            'disk_total': disk.total / (1024**3),  # GB
            'disk_used': disk.used / (1024**3),  # GB
            'disk_free': disk.free / (1024**3)  # GB
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有系统指标"""
        metrics = {}
        metrics.update(self.get_cpu_metrics())
        metrics.update(self.get_memory_metrics())
        metrics.update(self.get_disk_metrics())
        return metrics
    
    def check_thresholds(self, metrics: Dict[str, float]):
        """检查阈值并告警"""
        if not self.alert_manager:
            return
        
        for key, value in metrics.items():
            threshold = self.thresholds.get(key)
            
            if threshold and value > threshold:
                self.alert_manager.send_alert(
                    alert_type='system',
                    severity='warning',
                    message=f"{key} exceeds threshold: {value:.1f} > {threshold}",
                    context={'metric': key, 'value': value, 'threshold': threshold}
                )
    
    def record_history(self, metrics: Dict[str, float]):
        """记录历史数据"""
        for key in ['cpu_percent', 'memory_percent', 'disk_usage']:
            if key in metrics:
                self.history[key].append(metrics[key])
                
                # 限制历史大小
                if len(self.history[key]) > self.history_max_size:
                    self.history[key].pop(0)
    
    def get_history_stats(self, key: str) -> Dict[str, float]:
        """获取历史统计"""
        if key not in self.history or not self.history[key]:
            return {}
        
        data = self.history[key]
        return {
            'current': data[-1],
            'min': min(data),
            'max': max(data),
            'avg': sum(data) / len(data)
        }
    
    def start_monitoring(self, interval: int = 60):
        """启动监控（后台线程）"""
        if self.monitoring:
            logger.warning("SystemMonitor is already running")
            return
        
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                try:
                    metrics = self.get_all_metrics()
                    self.record_history(metrics)
                    self.check_thresholds(metrics)
                except Exception as e:
                    logger.error(f"Error in system monitor loop: {e}")
                
                time.sleep(interval)
        
        self.monitor_thread = threading.Thread(
            target=monitor_loop,
            name="SystemMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"SystemMonitor started, interval: {interval}s")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logger.info("SystemMonitor stopped")
```

**LogFileMonitor（日志文件监控器）**：
```python
class LogFileMonitor:
    """日志文件大小监控器"""
    
    def __init__(self, alert_manager: AlertManager = None):
        self.alert_manager = alert_manager
        self.max_size = 100 * 1024 * 1024  # 100MB
        self.log_paths: List[str] = []
    
    def add_log_file(self, path: str):
        """添加监控的日志文件"""
        if path not in self.log_paths:
            self.log_paths.append(path)
    
    def check_log_sizes(self):
        """检查日志文件大小"""
        for path in self.log_paths:
            if not os.path.exists(path):
                continue
            
            size = os.path.getsize(path)
            
            if size > self.max_size:
                if self.alert_manager:
                    self.alert_manager.send_alert(
                        alert_type='system',
                        severity='warning',
                        message=f"Log file too large: {path} ({size/(1024**2):.1f}MB)",
                        context={'path': path, 'size': size}
                    )
```

#### 测试用例
1. **test_get_cpu_metrics** - 获取CPU指标
2. **test_get_memory_metrics** - 获取内存指标
3. **test_get_disk_metrics** - 获取磁盘指标
4. **test_threshold_alert** - 超过阈值告警
5. **test_history_recording** - 历史数据记录

---

### 3.3 策略状态监控（2小时）

#### 核心功能
1. **心跳检测**（60秒无数据告警）
2. **指标计算延迟监控**
3. **订单执行延迟监控**

#### 实现方案

**StrategyMonitor（策略状态监控器）**：
```python
class StrategyMonitor:
    """策略状态监控器"""
    
    def __init__(self, alert_manager: AlertManager = None):
        self.alert_manager = alert_manager
        
        # 心跳
        self.last_heartbeat = time.time()
        self.heartbeat_timeout = 60  # 60秒
        self.heartbeat_alerted = False
        
        # 指标延迟
        self.indicator_updates: Dict[str, float] = {}  # {indicator_name: timestamp}
        self.indicator_timeout = 120  # 2分钟
        
        # 订单延迟
        self.order_latencies: List[float] = []
        self.max_latency_samples = 100
        self.high_latency_threshold = 5.0  # 5秒
        
        # 监控状态
        self.monitoring = False
        self.monitor_thread = None
    
    def update_heartbeat(self):
        """更新心跳（收到数据时调用）"""
        self.last_heartbeat = time.time()
        
        # 如果之前告警过，现在恢复了
        if self.heartbeat_alerted:
            if self.alert_manager:
                self.alert_manager.send_alert(
                    alert_type='strategy',
                    severity='info',
                    message="Strategy heartbeat recovered"
                )
            self.heartbeat_alerted = False
    
    def check_heartbeat(self) -> bool:
        """
        检查心跳超时
        
        Returns:
            True: 超时
            False: 正常
        """
        elapsed = time.time() - self.last_heartbeat
        
        if elapsed > self.heartbeat_timeout:
            if not self.heartbeat_alerted and self.alert_manager:
                self.alert_manager.send_alert(
                    alert_type='strategy',
                    severity='error',
                    message=f"Strategy heartbeat timeout: {elapsed:.0f}s",
                    context={'elapsed': elapsed, 'timeout': self.heartbeat_timeout}
                )
                self.heartbeat_alerted = True
            
            return True
        
        return False
    
    def record_indicator_update(self, indicator_name: str):
        """记录指标更新"""
        self.indicator_updates[indicator_name] = time.time()
    
    def check_indicator_delays(self):
        """检查指标计算延迟"""
        now = time.time()
        
        for name, last_update in self.indicator_updates.items():
            delay = now - last_update
            
            if delay > self.indicator_timeout:
                if self.alert_manager:
                    self.alert_manager.send_alert(
                        alert_type='strategy',
                        severity='warning',
                        message=f"Indicator update timeout: {name} ({delay:.0f}s)",
                        context={'indicator': name, 'delay': delay}
                    )
    
    def record_order_latency(self, latency: float):
        """
        记录订单延迟
        
        Args:
            latency: 延迟时间（秒）
        """
        self.order_latencies.append(latency)
        
        # 限制样本数量
        if len(self.order_latencies) > self.max_latency_samples:
            self.order_latencies.pop(0)
        
        # 检查高延迟
        if latency > self.high_latency_threshold:
            if self.alert_manager:
                self.alert_manager.send_alert(
                    alert_type='strategy',
                    severity='warning',
                    message=f"High order latency: {latency:.2f}s",
                    context={'latency': latency, 'threshold': self.high_latency_threshold}
                )
    
    def get_latency_stats(self) -> Dict[str, float]:
        """获取延迟统计"""
        if not self.order_latencies:
            return {}
        
        return {
            'count': len(self.order_latencies),
            'min': min(self.order_latencies),
            'max': max(self.order_latencies),
            'avg': sum(self.order_latencies) / len(self.order_latencies),
            'p95': self._percentile(self.order_latencies, 0.95),
            'p99': self._percentile(self.order_latencies, 0.99)
        }
    
    def _percentile(self, data: List[float], p: float) -> float:
        """计算百分位数"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * p)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def start_monitoring(self, check_interval: int = 30):
        """启动监控"""
        if self.monitoring:
            logger.warning("StrategyMonitor is already running")
            return
        
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                try:
                    self.check_heartbeat()
                    self.check_indicator_delays()
                except Exception as e:
                    logger.error(f"Error in strategy monitor loop: {e}")
                
                time.sleep(check_interval)
        
        self.monitor_thread = threading.Thread(
            target=monitor_loop,
            name="StrategyMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"StrategyMonitor started, interval: {check_interval}s")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logger.info("StrategyMonitor stopped")
```

#### 测试用例
1. **test_heartbeat_normal** - 正常心跳
2. **test_heartbeat_timeout** - 心跳超时告警
3. **test_heartbeat_recovery** - 心跳恢复通知
4. **test_indicator_delay** - 指标延迟检测
5. **test_order_latency** - 订单延迟统计

---

## 🧪 四、测试策略

### 4.1 单元测试

**测试目标**：覆盖率 > 85%

**关键测试场景**：

| 测试类 | 测试用例数 | 覆盖内容 |
|--------|-----------|----------|
| TestAlertDeduplicator | 5 | 去重、频率限制、窗口过期 |
| TestAlertManager | 4 | 发送、处理器、统计 |
| TestSystemMonitor | 5 | CPU/内存/磁盘、阈值 |
| TestStrategyMonitor | 5 | 心跳、延迟、统计 |

**Mock策略**：
- Mock psutil：返回模拟系统指标
- Mock time.time：控制时间流逝
- Mock AlertHandler：验证告警发送

### 4.2 集成测试

**测试场景**：

1. **完整监控流程测试**
   - 启动监控
   - 触发告警
   - 验证去重
   - 验证发送

2. **多监控器协同测试**
   - 系统监控+策略监控
   - 告警管理器统一处理

---

## 📦 五、实现步骤

### 步骤1：告警基础类（30分钟）
1. 创建 `src/monitor/models.py`
2. 定义 `Alert` 数据类
3. 定义 `AlertHandler` 基类
4. 定义 `AlertStats` 统计类

### 步骤2：告警去重器（1小时）
1. 创建 `src/monitor/alert_deduplicator.py`
2. 实现 `AlertDeduplicator`
3. 实现去重逻辑
4. 编写单元测试

### 步骤3：告警管理器（1小时）
1. 创建 `src/monitor/alert_manager.py`
2. 实现 `AlertManager`
3. 实现告警处理器（Logging、Console）
4. 编写单元测试

### 步骤4：系统资源监控（2小时）
1. 创建 `src/monitor/system_monitor.py`
2. 实现 `SystemMonitor`
3. 实现各类指标获取
4. 编写单元测试

### 步骤5：策略状态监控（2小时）
1. 创建 `src/monitor/strategy_monitor.py`
2. 实现 `StrategyMonitor`
3. 实现心跳、延迟监控
4. 编写单元测试

### 步骤6：集成和调试（30分钟）
1. 集成所有模块
2. 运行所有测试
3. 修复发现的问题

---

## 🚨 六、潜在问题与解决方案

### 问题1：告警风暴
**现象**：大量重复告警淹没重要信息
**解决**：
- 去重窗口（5分钟）
- 频率限制（窗口内最多10次）
- 告警摘要（合并显示）

### 问题2：监控线程异常
**现象**：监控线程崩溃，无法告警
**解决**：
- 异常捕获和日志记录
- 定期健康检查
- 主线程定期检查监控状态

### 问题3：系统指标获取失败
**现象**：psutil调用失败
**解决**：
- 异常捕获，返回默认值
- 记录错误日志
- 降级处理（跳过该指标）

### 问题4：内存泄漏
**现象**：历史数据无限增长
**解决**：
- 限制历史大小（最多60个数据点）
- 定期清理过期记录
- 使用deque数据结构

---

## ✅ 七、验收标准

### 功能完整性
- ✅ 告警去重正常工作
- ✅ 系统资源监控准确
- ✅ 策略状态监控有效
- ✅ 告警处理器正常工作

### 性能
- ✅ 监控线程资源占用<1% CPU
- ✅ 告警延迟<1秒
- ✅ 历史数据内存占用<10MB

### 测试覆盖
- ✅ 单元测试覆盖率 > 85%
- ✅ 所有关键路径有测试
- ✅ 集成测试通过

### 可维护性
- ✅ 易于添加新的监控指标
- ✅ 易于扩展告警渠道
- ✅ 配置灵活
- ✅ 日志完整

---

## 📊 八、时间分配

| 阶段 | 任务 | 预估时间 | 实际时间 |
|------|------|----------|----------|
| 1 | 告警基础类 | 0.5h | |
| 2 | 告警去重器 | 1.0h | |
| 3 | 告警管理器 | 1.0h | |
| 4 | 系统资源监控 | 2.0h | |
| 5 | 策略状态监控 | 2.0h | |
| 6 | 集成和调试 | 0.5h | |
| **总计** | | **7.0h** | |

*注：预留1小时缓冲时间*

---

## 📝 九、总结

任务3的核心目标是**可观测性**，通过：

1. **告警去重** - 避免告警风暴
2. **系统监控** - 及时发现资源问题
3. **策略监控** - 确保策略正常运行
4. **统一管理** - 集中处理所有告警

完成后，系统将具备：
- ✅ 智能告警去重
- ✅ 全面系统监控
- ✅ 策略健康检查
- ✅ 灵活告警渠道

这是保障**系统稳定运行**的关键能力。
