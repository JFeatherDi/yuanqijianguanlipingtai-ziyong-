#!/usr/bin/env bash
# ============================================================
#  器件管理系统 · Linux 一键安装/启动
#
#  用法（在项目根目录执行）：
#    ./安装为服务.sh               # 装依赖 + 注册 systemd 服务 components 并立即启动（推荐）
#    ./安装为服务.sh --foreground  # 只装依赖，然后前台运行（Ctrl+C 停止）
#    ./安装为服务.sh --no-service  # 只装依赖，不起服务（自己用 venv/bin/python -m backend.app）
#    ./安装为服务.sh --user debian # 指定 systemd 服务运行用户（默认当前用户/sudo 用户）
#    ./安装为服务.sh --port 8080   # 指定端口（默认 5000）
#    ./安装为服务.sh --password 'xxx' --username admin   # 顺手配好管理员账号密码
#    ./安装为服务.sh --uninstall   # 停止并移除 systemd 服务（不动数据与代码）
# ============================================================
set -euo pipefail

SERVICE="components"
PORT="5000"
MODE="service"
RUN_USER=""
ADMIN_PASS=""
ADMIN_USER=""
UNINSTALL=0
PIP_INDEX="${PIP_INDEX_URL:-}"

while [ $# -gt 0 ]; do
  case "$1" in
    --foreground) MODE="foreground" ;;
    --no-service) MODE="none" ;;
    --user) RUN_USER="${2:-}"; shift ;;
    --port) PORT="${2:-}"; shift ;;
    --password) ADMIN_PASS="${2:-}"; shift ;;
    --username) ADMIN_USER="${2:-}"; shift ;;
    --service) SERVICE="${2:-}"; shift ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1（用 --help 看用法）" >&2; exit 2 ;;
  esac
  shift
done

# ---- 路径解析：脚本所在目录即项目根目录 ----
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/venv"
PY="$VENV/bin/python"
REQ="$ROOT/backend/requirements.txt"
LOG_DIR="$ROOT/logs"
SELF="$(readlink -f -- "${BASH_SOURCE[0]}")"

if [ -z "$RUN_USER" ]; then
  RUN_USER="${SUDO_USER:-$(id -un)}"
fi

c_ok()   { printf '  \033[32m[OK]\033[0m %s\n' "$1"; }
c_warn() { printf '  \033[33m[!]\033[0m %s\n' "$1"; }
c_err()  { printf '  \033[31m[%s]\033[0m %s\n' "$1" "$2"; }
c_step() { printf '\n\033[36m%s\033[0m\n' "$1"; }

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    c_err ERR "该操作需要 root（systemd 服务注册）。请用 sudo 重新执行：sudo $SELF $*"
    exit 1
  fi
}

# ---------- 卸载 ----------
if [ "$UNINSTALL" -eq 1 ]; then
  need_root --uninstall
  c_step "卸载 systemd 服务 $SERVICE"
  systemctl disable --now "$SERVICE" 2>/dev/null || true
  rm -f "/etc/systemd/system/$SERVICE.service"
  systemctl daemon-reload
  c_ok "服务已移除（代码、venv、数据库与备份都保留在原处）"
  exit 0
fi

printf '\n========================================\n'
printf '   IOTAT 元器件管理平台 · 一键安装\n'
printf '========================================\n'
printf '  项目目录: %s\n' "$ROOT"
printf '  运行用户: %s\n' "$RUN_USER"

# ---------- 1/6 Python ----------
c_step '[1/6] 检查 Python…'
PYTHON=""
for cand in "${APP_PYTHON:-}" python3 python; do
  [ -n "$cand" ] || continue
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
      PYTHON="$(command -v "$cand")"
      break
    fi
  fi
done
if [ -z "$PYTHON" ]; then
  c_err ERR '找不到 Python 3.8+。Debian/Ubuntu: sudo apt install python3 python3-venv；CentOS: sudo yum install python3'
  exit 1
fi
c_ok "Python $("$PYTHON" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')  ($PYTHON)"

# ---------- 2/6 venv ----------
c_step '[2/6] 准备 venv…'
mkdir -p "$LOG_DIR"
if [ -x "$PY" ] && "$PY" -m pip --version >/dev/null 2>&1; then
  c_ok '复用已有 venv'
else
  rm -rf "$VENV"
  if ! "$PYTHON" -m venv "$VENV"; then
    c_err ERR '创建 venv 失败。多数系统需要先装 python3-venv：sudo apt install python3-venv'
    exit 1
  fi
  c_ok 'venv 已创建'
fi

# ---------- 3/6 依赖 ----------
c_step '[3/6] 安装依赖（flask / waitress / openpyxl）…'
if ! "$PY" -c 'import flask, openpyxl' >/dev/null 2>&1; then
  PIP_ARGS=(install --disable-pip-version-check --quiet --upgrade pip)
  [ -n "$PIP_INDEX" ] && PIP_ARGS+=(--index-url "$PIP_INDEX")
  "$PY" "${PIP_ARGS[@]}" || c_warn 'pip 升级失败，继续尝试安装依赖'
  PIP_ARGS=(install --disable-pip-version-check --quiet -r "$REQ")
  [ -n "$PIP_INDEX" ] && PIP_ARGS+=(--index-url "$PIP_INDEX")
  if ! "$PY" "${PIP_ARGS[@]}"; then
    c_err ERR "依赖安装失败。离线环境可先在有网机器执行：pip download -r $REQ -d wheels，再拷过来 pip install --no-index --find-links wheels -r $REQ"
    exit 1
  fi
  c_ok '依赖安装完成'
else
  c_ok '依赖已就绪'
fi

# ---------- 4/6 数据库与密钥 ----------
c_step '[4/6] 初始化数据库与密钥…'
"$PY" -c 'import sys; sys.path.insert(0, "'"$ROOT"'"); from backend.db import init_db; init_db()'
c_ok "数据库就绪: ${APP_DB_PATH:-$ROOT/backend/data.db}"

if [ -f "$ROOT/backend/secret_key" ] && [ ! -f "$ROOT/.secret_key.shipped" ]; then
  # 随包分发的密钥是开发机的，等于会话可被伪造，必须丢弃
  rm -f "$ROOT/backend/secret_key"
  : > "$ROOT/.secret_key.shipped"
  c_warn '已删除随包携带的 backend/secret_key，服务首次启动会重新生成'
fi

# ---------- 5/6 环境文件 ----------
c_step '[5/6] 写入环境配置…'
ENV_FILE="$ROOT/.env.service"
umask 077
{
  echo "# 由 安装为服务.sh 生成，可手工修改后 systemctl restart $SERVICE"
  echo "APP_HOST=0.0.0.0"
  echo "APP_PORT=$PORT"
  [ -n "$ADMIN_USER" ] && echo "APP_USERNAME=$ADMIN_USER"
  [ -n "$ADMIN_PASS" ] && echo "APP_PASSWORD=$ADMIN_PASS"
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"
c_ok "已写入 $ENV_FILE"
if [ -z "$ADMIN_PASS" ]; then
  c_warn '管理员密码仍是内置默认值 swust350351 —— 强烈建议在 .env.service 里设置 APP_PASSWORD'
fi

# ---------- 6/6 启动 ----------
if [ "$MODE" = "none" ]; then
  c_step '完成（未启动服务）'
  printf '  手动启动: cd %s && %s -m backend.app\n' "$ROOT" "$PY"
  exit 0
fi

if [ "$MODE" = "foreground" ]; then
  c_step "[6/6] 前台启动，端口 $PORT（Ctrl+C 停止）"
  cd "$ROOT"
  export APP_HOST=0.0.0.0 APP_PORT="$PORT"
  [ -n "$ADMIN_USER" ] && export APP_USERNAME="$ADMIN_USER"
  [ -n "$ADMIN_PASS" ] && export APP_PASSWORD="$ADMIN_PASS"
  exec "$PY" -m backend.app
fi

c_step "[6/6] 注册并启动 systemd 服务 $SERVICE"
need_root --port "$PORT"
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=IOTAT 器件管理系统（Flask + waitress）
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$ROOT
EnvironmentFile=$ENV_FILE
ExecStart=$PY -m backend.app
Restart=always
RestartSec=3

# 沙箱加固：只允许写项目目录与日志（venv 在项目目录内，故一并可写）
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$ROOT $LOG_DIR

StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE"
sleep 2

if systemctl is-active --quiet "$SERVICE"; then
  c_ok "服务已启动：http://<本机IP>:$PORT"
  printf '  状态: systemctl status %s\n' "$SERVICE"
  printf '  日志: journalctl -u %s -f\n' "$SERVICE"
  printf '  重启: systemctl restart %s\n' "$SERVICE"
else
  c_err ERR "服务启动失败，最近日志："
  journalctl -u "$SERVICE" -n 30 --no-pager || true
  exit 1
fi

# 顺带提示备份定时器（需手工改路径后启用，见 使用与缺陷清单）
if [ -f "$ROOT/scripts/components-backup.timer" ]; then
  printf '\n  提示：数据库备份定时器位于 scripts/components-backup.{service,timer}\n'
  printf '        启用前需把里面的 /opt/components 改成 %s\n' "$ROOT"
fi
