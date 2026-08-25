@echo off
REM 项目启动脚本
REM 用法: 双击 start.bat 或在命令行运行 start.bat

echo.
echo ========================================
echo   量化交易系统 - 开发环境
echo ========================================
echo.

echo [1/2] 激活虚拟环境...
call venv\Scripts\activate.bat

echo [2/2] 虚拟环境已激活！
echo.
echo 当前目录: %CD%
echo Python路径:
where python
echo.
echo ----------------------------------------
echo 可用命令:
echo   pytest tests/          - 运行测试
echo   python scripts/xxx.py  - 运行脚本
echo ----------------------------------------
echo.

cmd /k
