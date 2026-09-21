@echo off
chcp 65001 >nul
REM IOTAT 实验室元器件管理平台 - 一键启动脚本 (Windows)
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

REM ---- 1/4 前端构建产物 ----
if exist "frontend\dist\index.html" (
    echo [1/4] 检测到前端构建产物，跳过构建
) else (
    where npm >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] 缺少 frontend\dist，且本机没有 npm。
        echo         请在开发机执行: cd frontend ^&^& npm install ^&^& npm run build
        echo         然后把 frontend\dist 一并部署到服务器。
        pause
        exit /b 1
    )
    echo [1/4] 未找到 frontend\dist，使用 npm 构建前端...
    pushd frontend
    call npm install --silent
    call npm run build
    popd
)

REM ---- 2/4 虚拟环境 ----
if not exist venv (
    echo [2/4] 创建虚拟环境...
    python -m venv venv
) else (
    echo [2/4] 复用已存在的虚拟环境
)

REM ---- 3/4 依赖与数据库 ----
echo [3/4] 安装依赖并初始化数据库...
call venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r backend\requirements.txt
python -c "from backend.db import init_db; init_db()"

REM ---- 4/4 启动 ----
echo [4/4] 启动服务...
echo.
echo ====================================
echo   启动成功
echo   本地访问:   http://localhost:5000
echo   局域网访问: http://本机IP:5000
echo   账号: IOTAT
echo   密码: swust350351
echo   提示: 可通过 APP_PORT / APP_USERNAME / APP_PASSWORD 环境变量覆盖
echo ====================================
echo 按 Ctrl+C 停止服务
echo.

python -m backend.app
pause