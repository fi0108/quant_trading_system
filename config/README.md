# 配置文件说明

## 📂 文件结构

```
config/
├── config.yaml              # 开发/测试环境主配置
└── config.production.yaml   # 生产环境覆盖配置

.env.dev                     # 开发/测试环境密码（可提交git）
.env                         # 生产环境密码（不提交git）
.env.example                 # 环境变量模板
```

---

## 🎯 配置方案

### **开发/测试环境**
```
config.yaml + .env.dev
```

### **生产环境**
```
config.yaml + config.production.yaml + .env
```

---

## 🔄 配置加载流程

### **开发/测试环境**（默认）
```
1. .env.dev              # 加载密码（DB_PASSWORD=000000）
   ↓
2. config.yaml          # 加载主配置
   ↓
3. password: ""         # 被环境变量覆盖为 "000000"
```

### **生产环境**
```
1. .env                      # 加载生产密码（DB_PASSWORD=xxx）
   ↓
2. config.yaml              # 加载主配置
   ↓
3. config.production.yaml   # 覆盖生产配置
   ↓
4. password: ""             # 被环境变量覆盖为生产密码
```

---

## 📝 使用方式

### 开发/测试环境

```bash
# 方式1：直接运行（自动加载 .env.dev）
python src/main.py

# 方式2：明确指定（可选）
export ENV=development
python src/main.py
```

### 生产环境

```bash
# 1. 创建 .env 文件
cp .env.example .env

# 2. 编辑 .env，填入真实密码
nano .env

# 3. 运行程序（自动识别ENV=production）
python src/main.py
```

---

## 🔐 密码管理

### **原则**
- ❌ **不要在 config.yaml 写明文密码**
- ✅ **密码统一放在 .env 或 .env.dev**

### **文件对比**

| 文件 | 密码 | 提交git | 用途 |
|------|------|--------|------|
| `config.yaml` | `password: ""` | ✅ 提交 | 配置框架 |
| `.env.dev` | `DB_PASSWORD=000000` | ✅ 可提交 | 开发环境密码 |
| `.env` | `DB_PASSWORD=prod_xxx` | ❌ 不提交 | 生产环境密码 |

---

## 🔧 配置优先级

```
环境变量（.env / .env.dev）     ← 最高优先级
    ↓
config.production.yaml          ← 仅生产环境
    ↓
config.yaml                     ← 基础配置
```

---

## 📋 环境变量说明

| 变量名 | 说明 | 开发环境 | 生产环境 |
|--------|------|---------|---------|
| `ENV` | 环境标识 | development | production |
| `DB_PASSWORD` | 数据库密码 | 000000 | **必填** |
| `REDIS_PASSWORD` | Redis密码 | 000000 | **必填** |
| `EMAIL_PASSWORD` | 邮件密码 | 可选 | **必填** |

---

## ⚠️ 注意事项

1. **开发环境**：使用 `.env.dev`，密码可以是简单的 `000000`
2. **生产环境**：必须创建 `.env` 并填入真实密码
3. `.env` 已在 `.gitignore` 中，不会被提交
4. `.env.dev` 可以提交，方便团队统一开发环境

---

## 🧪 验证配置

```bash
# 测试配置加载
python -c "
from common.config import config
print('DB Password:', config.get('database.postgres.password'))
print('Redis Password:', config.get('database.redis.password'))
"

# 预期输出（开发环境）：
# DB Password: 000000
# Redis Password: 000000
```

---

## 📚 示例

### 开发环境完整流程

```bash
# 1. 克隆项目
git clone xxx

# 2. 直接运行（自动使用 .env.dev）
python src/main.py

# .env.dev 已包含开发环境密码，无需额外配置
```

### 生产环境完整流程

```bash
# 1. 部署到服务器
scp -r project/ server:/opt/

# 2. 创建生产环境配置
cd /opt/project
cp .env.example .env

# 3. 编辑 .env
vim .env
# ENV=production
# DB_PASSWORD=SecurePassword123!@#
# REDIS_PASSWORD=RedisPass456!@#
# EMAIL_PASSWORD=EmailAppPass789!@#

# 4. 运行
python src/main.py  # 自动识别 ENV=production
```

---

**简单总结**：
- 开发用 `.env.dev`（已提供）
- 生产用 `.env`（自己创建）
- 密码永远不写在 `config.yaml` 中
