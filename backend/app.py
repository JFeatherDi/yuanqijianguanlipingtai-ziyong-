"""应用工厂：装配配置、蓝图、跨域、SPA 静态资源与错误处理。

用法：
    python -m backend.app          # 直接启动（waitress）
    flask --app backend.app run    # 开发调试
"""
from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.utils import safe_join

from . import api
from .config import Config
from .db import close_db, init_db

CORS_METHODS = "GET, POST, PUT, DELETE, OPTIONS"
CORS_HEADERS = "Content-Type"


def create_app(config_object=Config):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        hours=config_object.SESSION_LIFETIME_HOURS
    )
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    init_db()
    api.register(app)
    app.teardown_appcontext(close_db)

    _install_cors(app)
    _install_health(app)
    _install_frontend(app)
    _install_error_handlers(app)
    return app


def _install_cors(app):
    """允许前端开发服务器（默认 5173）携带 Cookie 调用接口；
    同时确保接口响应不被缓存，避免读到过期的库存数据。"""

    @app.after_request
    def add_response_headers(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"

        origin = request.headers.get("Origin")
        if origin and origin in app.config["CORS_ORIGINS"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = CORS_HEADERS
            response.headers["Access-Control-Allow-Methods"] = CORS_METHODS
            response.headers.add("Vary", "Origin")
        return response


def _install_health(app):
    @app.route("/api/health")
    def health():
        return jsonify({"ok": True, "service": "components-api"})


def _install_frontend(app):
    """托管前端构建产物；未构建时给出明确提示而不是白屏。

    缓存策略（很重要）：
    - index.html 必须每次都回源校验，否则发版后浏览器会继续用旧的入口文件，
      而旧文件引用的哈希资源已经被 emptyOutDir 删除，页面会直接白屏。
    - /assets/ 下的文件名带内容哈希，可以长期强缓存。
    """
    dist = app.config["STATIC_DIST"]

    def dist_index():
        return os.path.join(dist, "index.html")

    def has_build():
        return os.path.isfile(dist_index())

    def send_index():
        response = send_from_directory(dist, "index.html")
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    def send_asset(path):
        response = send_from_directory(dist, path)
        if path.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.route("/")
    def index():
        if not has_build():
            return _build_missing_page(dist)
        return send_index()

    @app.route("/<path:asset>")
    def frontend_asset(asset):
        if asset.startswith("api/"):
            return jsonify({"ok": False, "msg": "接口不存在"}), 404

        target = safe_join(dist, asset)
        if target and os.path.isfile(target):
            return send_asset(asset)

        # 带扩展名却没命中文件：按真正的 404 处理，避免把 JS 当 HTML 返回
        if os.path.splitext(asset)[1]:
            return jsonify({"ok": False, "msg": "资源不存在"}), 404

        if not has_build():
            return _build_missing_page(dist)
        return send_index()


def _build_missing_page(dist):
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<title>前端尚未构建</title>"
        "<style>body{font-family:system-ui,sans-serif;padding:48px;color:#1f2a37;"
        "background:#eef2f7}code{background:#e8f2fd;padding:2px 6px;border-radius:4px}</style>"
        "<h1>前端尚未构建</h1>"
        "<p>请先在 <code>frontend/</code> 目录执行 <code>npm install &amp;&amp; npm run build</code>，"
        "或运行项目根目录的一键启动脚本。</p>"
        f"<p>当前期望的产物目录：<code>{dist}</code></p>",
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


def _install_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "msg": error.description}), error.code
        return error

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        app.logger.exception("未捕获的异常: %s", error)
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "msg": "服务器内部错误"}), 500
        return (
            "<!doctype html><meta charset='utf-8'><title>服务器错误</title>"
            "<p style='font-family:system-ui;padding:48px'>服务器内部错误，请查看后端日志。</p>",
            500,
            {"Content-Type": "text/html; charset=utf-8"},
        )


def main():
    app = create_app()
    try:
        from waitress import serve
    except ImportError:
        print("[WARN] 未安装 waitress，回退到 Flask 开发服务器（不推荐生产使用）")
        app.run(host=Config.HOST, port=Config.PORT, threaded=True)
        return

    print(f"服务已启动： http://{Config.HOST}:{Config.PORT}  (线程 {Config.WORKER_THREADS})")
    serve(
        app,
        host=Config.HOST,
        port=Config.PORT,
        threads=Config.WORKER_THREADS,
        connection_limit=Config.CONNECTION_LIMIT,
        channel_timeout=Config.CHANNEL_TIMEOUT,
        recv_bytes=Config.MAX_CONTENT_LENGTH,
    )


if __name__ == "__main__":
    main()