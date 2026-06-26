@echo off
chcp 65001 >nul
REM 实验室元器件管理平台 - 一键启动脚本 (Windows)
cd /d "%~dp0"

echo ====================================
echo   IOTAT 元器件管理平台 启动中...
echo ====================================

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 python，请先安装 Python 3.8+
    pause
    exit /b 1
)

if not exist venv (
    echo [1/4] 创建虚拟环境...
    python -m venv venv
)

echo [2/4] 激活虚拟环境并安装依赖...
call venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo [3/4] 初始化数据库...
python -c "from app import init_db; init_db()"

echo [4/4] 启动服务...
echo.
echo ====================================
echo   ✅ 启动成功
echo   本地访问: http://localhost:5000
echo   局域网访问: http://本机IP:5000
echo   内网穿透域名直接访问即可
echo   账号: IOTAT
echo   密码: swust350351
echo ====================================
echo 按 Ctrl+C 停止服务
echo.

python app.py
pause