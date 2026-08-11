@echo off
REM Module 1 Quick Start Script for Windows
REM This script sets up the environment and checks dependencies

echo ========================================
echo Module 1 Quick Start
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12+ and add to PATH
    pause
    exit /b 1
)

echo [1/3] Checking Python version...
python --version

echo.
echo [2/3] Checking Module 1 dependencies...
python scripts\check_module1_dependencies.py

if errorlevel 1 (
    echo.
    echo Some dependencies are missing.
    set /p INSTALL="Do you want to install missing dependencies? (Y/N): "
    if /i "%INSTALL%"=="Y" (
        echo.
        echo Installing dependencies...
        python scripts\check_module1_dependencies.py --install
    ) else (
        echo.
        echo Please install dependencies manually:
        echo   pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo.
echo [3/3] Environment check complete!
echo.
echo ========================================
echo You can now run Module 1 scripts:
echo ========================================
echo.
echo Historical data sync:
echo   python scripts\sync_historical_data.py --symbols AAPL
echo.
echo Real-time data service:
echo   python src\connection\market_data_service.py --symbols AAPL
echo.
echo Run tests:
echo   pytest tests\integration\test_market_data_core.py -v
echo.
echo ========================================
echo.

pause
