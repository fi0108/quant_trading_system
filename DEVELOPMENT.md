# 开发规范

## 📝 编码规范

### 文件编码
**所有代码文件必须使用 UTF-8 编码（无 BOM）**

适用文件：
- ✅ `.py` - Python 源代码
- ✅ `.yaml` / `.yml` - 配置文件
- ✅ `.md` - 文档文件
- ✅ `.sql` - SQL 脚本
- ✅ `.txt` - 文本文件
- ✅ `.env` / `.env.dev` - 环境变量

### Python 文件头
```python
# -*- coding: utf-8 -*-
"""
模块说明

详细描述
"""
```

或使用 Python 3 默认（推荐）：
```python
"""
模块说明

详细描述
"""
# Python 3 默认 UTF-8，无需显式声明
```

---

## 🔧 IDE/编辑器配置

### VS Code
在 `.vscode/settings.json` 中设置：
```json
{
    "files.encoding": "utf8",
    "files.autoGuessEncoding": false,
    "python.analysis.extraPaths": ["src"],
    "python.defaultInterpreterPath": "venv/bin/python"
}
```

### PyCharm
1. `File` → `Settings` → `Editor` → `File Encodings`
2. 设置：
   - Global Encoding: `UTF-8`
   - Project Encoding: `UTF-8`
   - Default encoding for properties files: `UTF-8`

### Vim/Neovim
在 `.vimrc` 或 `init.vim` 中添加：
```vim
set encoding=utf-8
set fileencoding=utf-8
```

---

## 🐍 Python 开发规范

### 1. 代码风格
遵循 **PEP 8** 规范

```bash
# 安装代码格式化工具
pip install black flake8 isort

# 格式化代码
black src/ tests/

# 检查代码风格
flake8 src/ tests/

# 排序导入
isort src/ tests/
```

### 2. 类型提示
使用类型提示（Type Hints）

```python
def calculate_pnl(cost: float, current: float) -> float:
    """计算盈亏"""
    return current - cost
```

### 3. 文档字符串
使用 Google 风格的 docstring

```python
def create_order(symbol: str, quantity: int) -> Order:
    """创建订单
    
    Args:
        symbol: 股票代码
        quantity: 数量
        
    Returns:
        Order: 订单对象
        
    Raises:
        ValueError: 数量必须大于0
    """
    if quantity <= 0:
        raise ValueError("数量必须大于0")
    return Order(symbol, quantity)
```

### 4. 导入顺序
```python
# 1. 标准库
import os
import sys
from datetime import datetime

# 2. 第三方库
import pytest
from ib_insync import IB

# 3. 本地模块
from common.config import config
from common.logger import log
```

---

## 🧪 测试规范

### 测试文件命名
```
tests/
├── slice1/
│   ├── unit/
│   │   └── test_*.py          # 单元测试
│   ├── integration/
│   │   └── test_*.py          # 集成测试
│   └── e2e/
│       └── test_*.py          # 端到端测试
```

### 测试函数命名
```python
def test_功能_场景():
    """测试用例说明"""
    pass

# 示例
def test_create_order_success():
    """测试成功创建订单"""
    pass

def test_create_order_invalid_quantity():
    """测试无效数量时创建订单失败"""
    pass
```

### 测试标记
```python
import pytest

@pytest.mark.unit
def test_calculation():
    """单元测试"""
    pass

@pytest.mark.integration
def test_database_connection():
    """集成测试"""
    pass

@pytest.mark.e2e
@pytest.mark.slow
def test_complete_flow():
    """端到端测试"""
    pass
```

---

## 📁 目录结构规范

```
项目根目录/
├── src/                    # 源代码
│   ├── common/            # 通用模块
│   ├── data/              # 数据层
│   ├── trading/           # 交易层
│   └── strategy/          # 策略层
├── tests/                 # 测试代码
│   ├── slice1/           # Week 1 测试
│   └── slice2/           # Week 2 测试
├── config/                # 配置文件
├── database/              # 数据库相关
├── docs/                  # 文档
├── scripts/               # 工具脚本
└── logs/                  # 日志目录
```

---

## 🔐 安全规范

### 1. 不要提交敏感信息
```bash
# .gitignore
.env               # 生产环境密码
*.log              # 日志文件
__pycache__/       # Python 缓存
*.pyc
```

### 2. 密码管理
```python
# ❌ 错误：明文密码
password = "123456"

# ✅ 正确：环境变量
password = os.getenv('DB_PASSWORD')
```

---

## 📊 日志规范

### 日志级别
```python
from common.logger import log

log.debug("调试信息")      # 开发调试
log.info("正常信息")       # 一般信息
log.warning("警告信息")    # 警告
log.error("错误信息")      # 错误
log.critical("严重错误")   # 严重错误
```

### 日志格式
```python
# 包含上下文信息
log.info(f"Order created: {order_id}, symbol={symbol}, qty={quantity}")

# 异常日志
try:
    result = risky_operation()
except Exception as e:
    log.error(f"Operation failed: {e}", exc_info=True)
```

---

## 🔄 Git 提交规范

### Commit Message 格式
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型
- `feat`: 新功能
- `fix`: 修复 Bug
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具/配置

### 示例
```
feat(trading): add order status tracking

- Monitor IBKR order status events
- Auto update position after fill
- Persist order history to database

Closes #123

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

---

## ⚡ 性能规范

### 1. 避免循环中的重复计算
```python
# ❌ 错误
for order in orders:
    if order.status == OrderStatus.FILLED:
        total += order.quantity * get_price(order.symbol)  # 重复查询价格

# ✅ 正确
prices = {s: get_price(s) for s in symbols}
for order in orders:
    if order.status == OrderStatus.FILLED:
        total += order.quantity * prices[order.symbol]
```

### 2. 使用生成器
```python
# ❌ 大数据集
all_bars = [process_bar(b) for b in huge_dataset]

# ✅ 生成器
all_bars = (process_bar(b) for b in huge_dataset)
```

---

## 🚨 错误处理规范

### 1. 具体的异常
```python
# ❌ 错误：捕获所有异常
try:
    connect()
except:
    pass

# ✅ 正确：捕获具体异常
try:
    connect()
except ConnectionError as e:
    log.error(f"Connection failed: {e}")
    raise
```

### 2. 自定义异常
```python
class InsufficientFundsError(Exception):
    """资金不足异常"""
    pass

class OrderRejectedException(Exception):
    """订单被拒绝异常"""
    pass
```

---

## 📚 文档规范

### 1. README.md
每个主要模块应包含 README：
- 功能说明
- 使用示例
- 依赖说明
- 测试方法

### 2. 代码注释
```python
# 单行注释：解释为什么（而不是做什么）

"""
多行注释：
- 复杂算法的说明
- 重要的业务逻辑
- 注意事项
"""
```

---

## ✅ 代码审查清单

提交代码前检查：
- [ ] 编码格式：UTF-8
- [ ] 代码风格：符合 PEP 8
- [ ] 类型提示：关键函数添加
- [ ] 文档字符串：公开函数必须有
- [ ] 单元测试：新功能有测试覆盖
- [ ] 日志：关键操作有日志
- [ ] 异常处理：合理的异常捕获
- [ ] 敏感信息：无密码/密钥
- [ ] 导入：已移除未使用的导入
- [ ] Git：提交信息清晰

---

## 🔗 相关资源

- [PEP 8 -- Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Pytest Documentation](https://docs.pytest.org/)

---

**最后更新**: 2026-08-23  
**维护者**: 项目团队
