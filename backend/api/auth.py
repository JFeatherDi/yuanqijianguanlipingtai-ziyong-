"""鉴权接口：验证码、登录、登出、当前用户。"""
from __future__ import annotations

import time

from flask import Blueprint, jsonify, make_response, request, session

from .. import captcha
from ..config import Config
from ..security import (
    check_login_limit,
    clear_login_failures,
    login_required,
    record_login_failure,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# 验证码错误和密码错误都算一次失败：否则脚本可以拿「验证码错误」当免死金牌，
# 无限次试探密码，把 security.py 的 IP 限流整个绕过去。
CAPTCHA_FAILED_MSG = "验证码错误或已过期"


@bp.route("/captcha", methods=["GET"])
def captcha_image():
    """签发一张验证码图片。

    答案只留在服务端内存里，会话里只放随机 id（见 captcha.py 的说明）。
    """
    _, png = captcha.issue()
    response = make_response(png)
    response.headers["Content-Type"] = "image/png"
    # 验证码必须每次都是新的，任何一层缓存都会让第二次登录必然失败
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@bp.route("/login", methods=["POST"])
def login():
    allowed, remain = check_login_limit()
    if not allowed:
        # 这一层不消费验证码：锁定结束后用户手上的那张还能用
        return jsonify({"ok": False, "msg": f"登录失败次数过多，请 {remain} 秒后再试"}), 429

    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()

    # 先验验证码再比密码：无论对错都把这张验证码作废，客户端需要换一张
    if not captcha.verify(payload.get("captcha") or ""):
        record_login_failure()
        return jsonify({"ok": False, "msg": CAPTCHA_FAILED_MSG, "captcha": True}), 400

    if username == Config.USERNAME and password == Config.PASSWORD:
        clear_login_failures()
        session.permanent = True
        session["user"] = username
        session["login_at"] = time.time()
        return jsonify({"ok": True, "user": username})

    record_login_failure()
    return jsonify({"ok": False, "msg": "账号或密码错误"}), 401


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.route("/me")
@login_required
def me():
    return jsonify({"ok": True, "user": session.get("user")})
