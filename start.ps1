# 项目启动脚本
# 用法: .\start.ps1

Write-Host "正在激活虚拟环境..." -ForegroundColor Green
.\venv\Scripts\Activate.ps1

Write-Host "虚拟环境已激活！" -ForegroundColor Green
Write-Host "项目路径: $PWD" -ForegroundColor Cyan
Write-Host ""
Write-Host "可用命令:" -ForegroundColor Yellow
Write-Host "  pytest tests/          - 运行测试" -ForegroundColor Gray
Write-Host "  python scripts/xxx.py  - 运行脚本" -ForegroundColor Gray
Write-Host ""
