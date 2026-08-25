#!/bin/bash
# 代码审查自动化脚本
# 基于《代码审查标准》v1.0

echo "======================================"
echo "代码审查报告 - 阶段一"
echo "审查时间: $(date)"
echo "======================================"
echo ""

# ==========================================
# 一、架构一致性审查
# ==========================================
echo "【一、架构一致性审查】"
echo ""

echo "1.1 目录结构审查"
echo "--------------------------------"
echo "实际目录结构："
find src/ -type d | sort
echo ""

echo "检查孤立文件："
find src/ -maxdepth 1 -type f -name "*.py"
echo ""

echo "检查临时文件："
find . -name "*.tmp" -o -name "*.bak" -o -name "*~" 2>/dev/null | head -10
echo ""

echo "1.2 模块职责审查"
echo "--------------------------------"
echo "Manager类统计："
grep -rn "class.*Manager" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "Client类统计："
grep -rn "class.*Client" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "检查跨模块私有调用："
grep -rn "from .* import _" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "1.3 依赖关系审查"
echo "--------------------------------"
echo "检查common模块是否依赖业务模块："
grep -rn "from data\|from trading\|from strategy" src/common/ --include="*.py" 2>/dev/null | wc -l
echo "(应该为0)"
echo ""

# ==========================================
# 二、代码规范审查
# ==========================================
echo "【二、代码规范审查】"
echo ""

echo "2.1 导入规范审查（重要！）"
echo "--------------------------------"
echo "检查src.前缀（必须为0）："
grep -rn "from src\." . --include="*.py" --exclude-dir=venv --exclude-dir=.git 2>/dev/null | wc -l
echo ""

echo "详细列出src.前缀位置："
grep -rn "from src\." . --include="*.py" --exclude-dir=venv --exclude-dir=.git 2>/dev/null | head -10
echo ""

echo "2.2 命名规范审查"
echo "--------------------------------"
echo "检查文件名大写（应该为0）："
find src/ -name "*.py" | grep -E "[A-Z]" 2>/dev/null | wc -l
echo ""

echo "检查类名小写（应该为0）："
grep -rn "^class [a-z]" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "2.3 文档字符串审查"
echo "--------------------------------"
echo "公开类总数："
grep -rn "^class [A-Z]" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "带文档字符串的类数量："
grep -rn "^class.*:" -A 1 src/ --include="*.py" 2>/dev/null | grep '"""' | wc -l
echo ""

# ==========================================
# 三、功能完整性审查
# ==========================================
echo "【三、功能完整性审查】"
echo ""

echo "3.1 交付物清单"
echo "--------------------------------"
echo "源代码文件数："
find src/ -name "*.py" | wc -l
echo ""

echo "测试文件数："
find tests/ -name "*.py" 2>/dev/null | wc -l
echo ""

echo "Demo脚本："
ls -1 scripts/demo/*.py 2>/dev/null
echo ""

echo "配置文件："
ls -1 config/*.yaml 2>/dev/null
echo ""

echo "3.2 配置硬编码检查"
echo "--------------------------------"
echo "硬编码IP检查："
grep -rn "127\.0\.0\.1\|localhost" src/ --include="*.py" 2>/dev/null | grep -v "default" | wc -l
echo ""

echo "硬编码端口检查："
grep -rn "7497\|4002" src/ --include="*.py" 2>/dev/null | grep -v "default" | wc -l
echo ""

echo "config.get使用次数："
grep -rn "config\.get" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "3.3 异常处理检查"
echo "--------------------------------"
echo "try语句数："
grep -rn "try:" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "except语句数："
grep -rn "except.*:" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "logger调用数："
grep -rn "logger\." src/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "TODO/FIXME："
grep -rn "TODO\|FIXME" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

# ==========================================
# 四、测试质量审查
# ==========================================
echo "【四、测试质量审查】"
echo ""

echo "4.1 测试文件结构"
echo "--------------------------------"
echo "测试目录结构："
find tests/ -type d 2>/dev/null | sort
echo ""

echo "4.2 测试用例统计"
echo "--------------------------------"
echo "测试文件数："
find tests/ -name "test_*.py" 2>/dev/null | wc -l
echo ""

echo "测试函数数："
grep -rn "def test_" tests/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "Mock使用次数："
grep -rn "Mock\|patch" tests/ --include="*.py" 2>/dev/null | wc -l
echo ""

echo "4.3 端到端测试"
echo "--------------------------------"
echo "integration测试："
find tests/ -name "*integration*" -o -name "*e2e*" 2>/dev/null
echo ""

# ==========================================
# 五、文档同步审查
# ==========================================
echo "【五、文档同步审查】"
echo ""

echo "5.1 文档文件清单"
echo "--------------------------------"
echo "Markdown文档："
find docs/ -name "*.md" 2>/dev/null | wc -l
echo ""

echo "根目录文档："
ls -1 *.md 2>/dev/null
echo ""

echo "5.2 关键文档检查"
echo "--------------------------------"
echo "模块索引存在："
test -f docs/模块索引.md && echo "✅ 存在" || echo "❌ 缺失"
echo ""

echo "架构演进日志存在："
test -f docs/架构演进日志.md && echo "✅ 存在" || echo "❌ 缺失"
echo ""

echo "完整开发工作流存在："
test -f docs/完整开发工作流.md && echo "✅ 存在" || echo "❌ 缺失"
echo ""

# ==========================================
# 六、安全审查
# ==========================================
echo "【六、安全审查】"
echo ""

echo "6.1 敏感信息检查"
echo "--------------------------------"
echo "硬编码密码检查："
grep -rn "password.*=.*['\"]" src/ --include="*.py" 2>/dev/null | grep -v "config" | wc -l
echo ""

echo "SQL注入风险："
grep -rn "execute.*%\|execute.*format" src/ --include="*.py" 2>/dev/null | wc -l
echo ""

# ==========================================
# 总结
# ==========================================
echo ""
echo "======================================"
echo "审查完成"
echo "详细问题请查看上述输出"
echo "======================================"
