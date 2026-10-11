"""鉴权接口：验证码、登录、登出、当前用户。"""
from __future__ import annotations

import time
import hmac

from flask import Blueprint, jsonify, make_response, request, session
from werkzeug.security import check_password_hash, generate_password_hash

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
SUPERADMIN_PASSWORD_KEY = "superadmin_password_hash"
PASSWORD_VERIFY_TTL_SECONDS = 300


def _superadmin_password_valid(db, password) -> bool:
    """优先校验站内修改后的哈希；尚未修改时兼容环境变量初始密码。"""
    row = db.execute(
        "SELECT value FROM system_meta WHERE key = ?", (SUPERADMIN_PASSWORD_KEY,)
    ).fetchone()
    candidate = str(password or "")
    if row is not None:
        return check_password_hash(row["value"], candidate)
    return hmac.compare_digest(candidate, str(Config.PASSWORD))


def _current_password_valid(db, password) -> bool:
    if session.get("role") == "superadmin":
        return _superadmin_password_valid(db, password)

    from ..services import users as user_service

    row = user_service.get_by_name(db, session.get("user") or "")
    return bool(
        row is not None
        and check_password_hash(row["password_hash"], str(password or ""))
    )


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
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = str(payload.get("password") or "")

    # 双维度限流：同一 IP 或同一账号任一超限即拒绝（账号维度防换 IP 定向爆破）
    allowed, remain = check_login_limit(username)
    if not allowed:
        # 这一层不消费验证码：锁定结束后用户手上的那张还能用
        return jsonify({"ok": False, "msg": f"登录失败次数过多，请 {remain} 秒后再试"}), 429

    # 先验验证码再比密码：无论对错都把这张验证码作废，客户端需要换一张
    if not captcha.verify(payload.get("captcha") or ""):
        record_login_failure(username)
        return jsonify({"ok": False, "msg": CAPTCHA_FAILED_MSG, "captcha": True}), 400

    session.permanent = True
    session["login_at"] = time.time()

    from ..db import get_db
    from ..services import users as user_service

    db = get_db()

    # 总管理员以环境变量密码初始化，站内修改后改用数据库中的安全哈希。
    if username == Config.USERNAME and _superadmin_password_valid(db, password):
        from ..services import admin_profile

        profile = admin_profile.get_profile(db)
        session["user"] = username
        session["role"] = "superadmin"
        session["full_name"] = profile["full_name"]
        session["phone"] = profile["phone"]
        clear_login_failures(username)
        return jsonify({
            "ok": True,
            "user": username,
            "role": "superadmin",
            "full_name": profile["full_name"],
            "phone": profile["phone"],
        })

    row = user_service.verify_user(db, username, password)
    if row is not None:
        session["user"] = row["username"]
        session["role"] = row["role"]
        session["uid"] = row["id"]
        session["ver"] = row["pw_version"]
        session["full_name"] = row["full_name"]
        session["phone"] = row["phone"]
        clear_login_failures(username)
        return jsonify({
            "ok": True,
            "user": row["username"],
            "role": row["role"],
            "full_name": row["full_name"],
            "phone": row["phone"],
        })

    # 登录失败要清掉刚写入的会话字段，避免残留半个会话
    session.clear()
    record_login_failure(username)
    return jsonify({"ok": False, "msg": "账号或密码错误"}), 401


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.route("/me")
@login_required
def me():
    full_name = session.get("full_name") or session.get("user") or ""
    phone = session.get("phone") or ""
    if session.get("role") == "superadmin":
        from ..db import get_db
        from ..services import admin_profile

        profile = admin_profile.get_profile(get_db())
        session["user"] = profile["username"]
        session["full_name"] = profile["full_name"]
        session["phone"] = profile["phone"]
        full_name = profile["full_name"]
        phone = profile["phone"]
    elif session.get("uid") is not None:
        from ..db import get_db
        from ..services import users as user_service

        row = user_service.get_user(get_db(), session["uid"])
        if row is not None:
            full_name = row["full_name"] or row["username"]
            phone = row["phone"] or ""
            session["full_name"] = full_name
            session["phone"] = phone
    return jsonify(
        {
            "ok": True,
            "user": Config.USERNAME if session.get("role") == "superadmin" else session.get("user"),
            "role": session.get("role", "member"),
            "full_name": full_name,
            "phone": phone,
        }
    )


@bp.route("/password/verify", methods=["POST"])
@login_required
def verify_password():
    """校验当前账号原密码，并给当前会话签发短时修改许可。"""
    payload = request.get_json(silent=True) or {}
    current_password = str(payload.get("current_password") or "")
    if not current_password:
        return jsonify({"ok": False, "msg": "请输入原密码"}), 400

    from ..db import get_db

    if not _current_password_valid(get_db(), current_password):
        session.pop("password_verified_at", None)
        return jsonify({"ok": False, "msg": "原密码错误"}), 400

    session["password_verified_at"] = time.time()
    return jsonify({"ok": True})


@bp.route("/password", methods=["PUT"])
@login_required
def change_password():
    """在原密码校验通过后的五分钟内修改当前登录账号密码。"""
    verified_at = session.get("password_verified_at")
    if not isinstance(verified_at, (int, float)) or time.time() - verified_at > PASSWORD_VERIFY_TTL_SECONDS:
        session.pop("password_verified_at", None)
        return jsonify({"ok": False, "msg": "请先验证原密码"}), 400

    payload = request.get_json(silent=True) or {}
    new_password = str(payload.get("new_password") or "")
    confirm_password = str(payload.get("confirm_password") or "")
    if len(new_password) < 6:
        return jsonify({"ok": False, "msg": "新密码至少 6 位"}), 400
    if len(new_password) > 128:
        return jsonify({"ok": False, "msg": "新密码不能超过 128 位"}), 400
    if new_password != confirm_password:
        return jsonify({"ok": False, "msg": "两次输入的新密码不一致"}), 400

    from ..db import get_db
    from ..services import users as user_service

    db = get_db()
    if _current_password_valid(db, new_password):
        return jsonify({"ok": False, "msg": "新密码不能与原密码相同"}), 400

    if session.get("role") == "superadmin":
        db.execute(
            "INSERT INTO system_meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (SUPERADMIN_PASSWORD_KEY, generate_password_hash(new_password)),
        )
    else:
        try:
            _username, new_version = user_service.set_password(
                db, session.get("uid"), new_password
            )
        except user_service.UserError as exc:
            return jsonify({"ok": False, "msg": str(exc)}), 400
        session["ver"] = new_version

    db.commit()
    session.pop("password_verified_at", None)
    return jsonify({"ok": True, "msg": "密码修改成功"})
