# 开发规范快速参考

## 🎯 核心规则

### 1. **编码格式：UTF-8（强制）**
```
所有 .py, .yaml, .md, .sql, .txt 文件必须使用 UTF-8 编码（无 BOM）
```

### 2. **代码风格：PEP 8**
```bash
# 格式化代码
black src/ tests/

# 检查风格
flake8 src/ tests/
```

### 3. **导入顺序**
```python
# 1. 标准库
import os

# 2. 第三方库  
import pytest

# 3. 本地模块
from common.config import config
```

---

## 📁 IDE 配置已就绪

- ✅ `.vscode/settings.json` - VS Code 配置
- ✅ `setup.cfg` - Flake8/isort 配置  
- ✅ `DEVELOPMENT.md` - 完整开发规范

---

## 🚀 快速开始

```bash
# 1. 克隆项目
git clone xxx

# 2. 自动加载配置（IDE 会读取）
# - VS Code 自动加载 .vscode/settings.json
# - 所有文件自动使用 UTF-8

# 3. 开发
# - 保存时自动格式化
# - 自动检查编码
```

---

## ✅ 提交前检查

```bash
# 运行测试
pytest tests/

# 检查代码风格  
flake8 src/ tests/

# 格式化代码
black src/ tests/
```

---

**详细规范**: 查看 `DEVELOPMENT.md`
