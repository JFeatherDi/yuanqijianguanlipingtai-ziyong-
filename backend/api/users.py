"""普通用户账号管理接口（仅管理员）。"""
from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request

from ..config import Config
from ..db import get_db, to_dicts
from ..security import admin_required
from ..services import users as user_service
from ..services.users import UserError

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.errorhandler(UserError)
def on_user_error(exc):
    return jsonify({"ok": False, "msg": str(exc)}), 400


@bp.route("", methods=["GET"])
@admin_required
def list_users():
    db = get_db()
    rows = user_service.list_users(db)
    return jsonify({"ok": True, "data": to_dicts(rows)})


@bp.route("", methods=["POST"])
@admin_required
def create_user():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    if username == Config.USERNAME:
        return jsonify({"ok": False, "msg": "该用户名是内置管理员账号，不能重复使用"}), 400

    db = get_db()
    try:
        user_service.create_user(db, username, payload.get("password"))
        db.commit()
    except UserError as exc:
        db.rollback()
        return jsonify({"ok": False, "msg": str(exc)}), 400
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({"ok": False, "msg": "用户名已存在"}), 400

    return jsonify({"ok": True, "msg": f"已创建用户 {username}"}), 201


@bp.route("/<int:user_id>/password", methods=["PUT"])
@admin_required
def reset_password(user_id):
    payload = request.get_json(silent=True) or {}
    db = get_db()
    try:
        username, _version = user_service.set_password(db, user_id, payload.get("password"))
        db.commit()
    except UserError as exc:
        db.rollback()
        return jsonify({"ok": False, "msg": str(exc)}), 400
    return jsonify({"ok": True, "msg": f"已重置 {username} 的密码，该账号旧会话已失效"})


@bp.route("/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    db = get_db()
    try:
        username = user_service.delete_user(db, user_id)
        db.commit()
    except UserError as exc:
        db.rollback()
        return jsonify({"ok": False, "msg": str(exc)}), 400
    return jsonify({"ok": True, "msg": f"已删除用户 {username}，其旧会话已失效"})
