"""集中式运行配置。

所有可变参数从环境变量读取，默认值面向低配服务器（>=350M 内存 / >=4G 存储）。
"""
from __future__ import annotations

import os


def _env(name, default, cast=str):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return default


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)

DEFAULT_DB_PATH = os.path.join(BACKEND_DIR, "data.db")
DEFAULT_DIST_DIR = os.path.join(PROJECT_DIR, "frontend", "dist")
DEFAULT_DEPLOY_SCRIPT = os.path.join(PROJECT_DIR, "deploy.sh")
DEFAULT_DEPLOY_LOG = os.path.join(PROJECT_DIR, "deploy.log")


class Config:
    """应用配置。类属性即配置项，Flask 以 from_object 方式加载。"""

    # ---- 鉴权 ----
    SECRET_KEY = _env("APP_SECRET_KEY", "swust-lab-components-2026")
    USERNAME = _env("APP_USERNAME", "IOTAT")
    PASSWORD = _env("APP_PASSWORD", "swust350351")
    SESSION_LIFETIME_HOURS = _env("APP_SESSION_HOURS", 12, int)

    # ---- 登录限流 ----
    LOGIN_MAX_FAIL = _env("APP_LOGIN_MAX_FAIL", 5, int)
    LOGIN_LOCK_SECONDS = _env("APP_LOGIN_LOCK_SECONDS", 300, int)

    # ---- 数据库 ----
    DB_PATH = _env("APP_DB_PATH", DEFAULT_DB_PATH)
    DB_BUSY_TIMEOUT_MS = _env("APP_DB_BUSY_TIMEOUT_MS", 10000, int)

    # ---- 上传 ----
    MAX_UPLOAD_MB = _env("APP_MAX_UPLOAD_MB", 8, int)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

    # ---- 前端构建产物 ----
    STATIC_DIST = _env("APP_STATIC_DIST", DEFAULT_DIST_DIR)

    # ---- 服务 ----
    HOST = _env("APP_HOST", "0.0.0.0")
    PORT = _env("APP_PORT", 5000, int)
    WORKER_THREADS = _env("APP_THREADS", 8, int)
    CONNECTION_LIMIT = _env("APP_CONNECTION_LIMIT", 20, int)
    CHANNEL_TIMEOUT = _env("APP_CHANNEL_TIMEOUT", 30, int)

    # ---- 自动部署 Webhook（GitHub push 触发）----
    # 密钥为空时接口直接拒绝服务，避免用弱默认值把部署入口开在公网
    WEBHOOK_SECRET = _env("WEBHOOK_SECRET", "")
    DEPLOY_SCRIPT = _env("APP_DEPLOY_SCRIPT", DEFAULT_DEPLOY_SCRIPT)
    DEPLOY_LOG = _env("APP_DEPLOY_LOG", DEFAULT_DEPLOY_LOG)

    # ---- 跨域（前端开发服务器）----
    CORS_ORIGINS = tuple(
        origin.strip()
        for origin in _env(
            "APP_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    )