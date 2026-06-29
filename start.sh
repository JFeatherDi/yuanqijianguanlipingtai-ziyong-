#!/usr/bin/env bash
# 实验室元器件管理平台 - 一键启动脚本 (Linux / macOS)
# 用法: ./start.sh
set -e

cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}

echo "===================================="
echo "  IOTAT 元器件管理平台 启动中..."
echo "===================================="

# 检查 python3
if ! command -v $PYTHON >/dev/null 2>&1; then
    echo "[ERROR] 未找到 $PYTHON，请先安装 Python 3.8+"
    exit 1
fi

# 创建虚拟环境（不存在则创建）
if [ ! -d "venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    $PYTHON -m venv venv
fi

echo "[2/4] 激活虚拟环境并安装依赖..."
# shellcheck disable=SC1091
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "[3/4] 初始化数据库..."
python -c "from app import init_db; init_db()"

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
echo "  ✅ 启动成功"
echo "  本地访问: http://localhost:5000"
echo "  局域网访问: http://<本机IP>:5000"
echo "  内网穿透域名直接访问即可"
echo "  账号: IOTAT"
echo "  密码: swust350351"
echo "===================================="
echo "按 Ctrl+C 停止服务"
echo ""

exec python app.py