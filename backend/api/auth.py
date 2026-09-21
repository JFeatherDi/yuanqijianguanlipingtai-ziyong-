"""鉴权接口：登录、登出、当前用户。"""
from __future__ import annotations

import time

from flask import Blueprint, jsonify, request, session

from ..config import Config
from ..security import (
    check_login_limit,
    clear_login_failures,
    login_required,
    record_login_failure,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/login", methods=["POST"])
def login():
    allowed, remain = check_login_limit()
    if not allowed:
        return jsonify({"ok": False, "msg": f"登录失败次数过多，请 {remain} 秒后再试"}), 429

    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()

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