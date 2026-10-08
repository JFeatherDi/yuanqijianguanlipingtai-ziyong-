"""元器件 CRUD。"""
from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request

from ..db import get_db, to_dicts
from ..security import admin_required, current_user, login_required
from ..services import catalog, custody
from ..services.inventory import TX_INIT, TX_IMPORT, apply_change
from ..services.quantity import nonnegative_quantity, round6

bp = Blueprint("components", __name__, url_prefix="/api/components")

LIST_SQL = """
SELECT * FROM components
{where}
ORDER BY category, name
"""


def _filters():
    """把查询参数翻译成 WHERE 片段，保持路由函数只做编排。"""
    clauses, args = [], []
    keyword = (request.args.get("q") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        clauses.append("(name LIKE ? OR category LIKE ? OR spec LIKE ? OR location LIKE ?)")
        args.extend([like] * 4)

    category = (request.args.get("category") or "").strip()
    if category:
        clauses.append("category = ?")
        args.append(category)

    if request.args.get("low") in ("1", "true", "yes"):
        clauses.append("threshold > 0 AND stock <= threshold")

    return ("WHERE " + " AND ".join(clauses) if clauses else ""), args


@bp.route("")
@login_required
def list_components():
    db = get_db()
    where, args = _filters()
    rows = db.execute(LIST_SQL.format(where=where), args).fetchall()
    return jsonify({"ok": True, "data": to_dicts(rows)})


@bp.route("", methods=["POST"])
@admin_required
def create_component():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    fields = catalog.normalize(payload)

    error = catalog.validate(fields)
    if error:
        return jsonify({"ok": False, "msg": error}), 400

    try:
        # 初始库存与出入库同一套精度规则：非负、最多六位小数
        opening = nonnegative_quantity(payload.get("stock"), "初始库存")
    except ValueError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400

    try:
        cursor = db.execute(
            "INSERT INTO components (name, category, spec, unit, location, stock, threshold, remark) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (
                fields["name"],
                fields["category"],
                fields["spec"],
                fields["unit"],
                fields["location"],
                fields["threshold"],
                fields["remark"],
            ),
        )
        component_id = cursor.lastrowid

        if opening:
            apply_change(db, component_id, opening, TX_INIT, current_user(), "新建初始库存")

        db.commit()
        return jsonify({"ok": True, "id": component_id})
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({"ok": False, "msg": "该器件名称与规格已存在"}), 400


@bp.route("/<int:component_id>", methods=["PUT"])
@admin_required
def update_component(component_id):
    db = get_db()
    changes = catalog.pick_changes(request.get_json(silent=True))

    if "threshold" in changes:
        changes["threshold"] = round6(catalog.to_number(changes["threshold"]))
    if "name" in changes:
        changes["name"] = catalog.to_text(changes["name"])
        if not changes["name"]:
            return jsonify({"ok": False, "msg": "器件名称不能为空"}), 400
    for key in ("category", "spec", "unit", "location", "remark"):
        if key in changes:
            changes[key] = catalog.to_text(changes[key])

    if not changes:
        return jsonify({"ok": True})

    assignments = ", ".join(f"{key} = ?" for key in changes)
    try:
        db.execute(
            f"UPDATE components SET {assignments} WHERE id = ?",
            [*changes.values(), component_id],
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({"ok": False, "msg": "该器件名称与规格已存在"}), 400

    return jsonify({"ok": True})


@bp.route("/<int:component_id>", methods=["DELETE"])
@admin_required
def delete_component(component_id):
    db = get_db()

    # 有流转历史的器件禁止删除：领用链、转交与归还记录是追踪凭证
    if custody.has_history(db, component_id):
        return jsonify({"ok": False, "msg": "该器件存在流转记录，禁止删除"}), 400

    db.execute("DELETE FROM transactions WHERE component_id = ?", (component_id,))
    db.execute("DELETE FROM components WHERE id = ?", (component_id,))
    db.commit()
    return jsonify({"ok": True})