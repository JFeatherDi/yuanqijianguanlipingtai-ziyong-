#!/usr/bin/env bash
# IOTAT 实验室元器件管理平台 - 一键启动脚本 (Linux / macOS)
# 用法: ./start.sh
set -e

cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}
DIST="frontend/dist"

echo "===================================="
echo "  IOTAT 元器件管理平台 启动中..."
echo "===================================="

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "[ERROR] 未找到 $PYTHON，请先安装 Python 3.8+"
    exit 1
fi

# ---- 1/4 前端构建产物 ----
if [ -f "$DIST/index.html" ]; then
    echo "[1/4] 检测到前端构建产物，跳过构建"
elif command -v npm >/dev/null 2>&1; then
    echo "[1/4] 未找到 $DIST，使用 npm 构建前端..."
    (cd frontend && npm install --silent && npm run build)
else
    echo "[ERROR] 缺少 $DIST，且本机没有 npm。"
    echo "        请在开发机执行： cd frontend && npm install && npm run build"
    echo "        然后把 frontend/dist 一并部署到服务器。"
    exit 1
fi

# ---- 2/4 虚拟环境 ----
if [ ! -d "venv" ]; then
    echo "[2/4] 创建虚拟环境..."
    "$PYTHON" -m venv venv
else
    echo "[2/4] 复用已存在的虚拟环境"
fi

# ---- 3/4 依赖与数据库 ----
echo "[3/4] 安装依赖并初始化数据库..."
# shellcheck disable=SC1091
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt
python -c "from backend.db import init_db; init_db()"

# ---- 4/4 启动 ----
echo "[4/4] 启动服务..."

# 检查端口占用，如果已有旧进程在运行则先提示
PORT=5000
if ss -tlnp | grep -q ":${PORT} "; then
    OLD_PID=$(ss -tlnp | grep ":${PORT} " | grep -oP 'pid=\K\d+')
    echo "[WARN] 端口 ${PORT} 已被 PID ${OLD_PID} 占用"
    echo "[WARN] 如果这是 systemd 服务，请用: systemctl restart auto-deploy"
    echo "[WARN] 即将杀掉旧进程并重新启动..."
    kill "$OLD_PID" 2>/dev/null
    sleep 1
fi

echo ""
echo "===================================="
echo "  启动成功"
echo "  本地访问:   http://localhost:${APP_PORT:-5000}"
echo "  局域网访问: http://<本机IP>:${APP_PORT:-5000}"
echo "  账号: ${APP_USERNAME:-IOTAT}"
echo "  密码: ${APP_PASSWORD:-swust350351}"
echo "  提示: 以上默认值可用同名环境变量覆盖"
echo "===================================="
echo "按 Ctrl+C 停止服务"
echo ""

exec python -m backend.app